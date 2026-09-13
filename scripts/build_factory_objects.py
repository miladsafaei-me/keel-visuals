"""Render the object factory: procedural 3D objects on the stage's one camera, at 1024 and 512 px.

    python3 scripts/build_factory_objects.py build
    python3 scripts/build_factory_objects.py render --out /tmp/factory-render [--only gold-bar]
    python3 scripts/build_factory_objects.py publish --from /tmp/factory-render
    python3 scripts/build_factory_objects.py coin --face-svg mark.svg --out coin.png --size 1024
    python3 scripts/build_factory_objects.py coin --face-png mark.png --out coin.png --size 1024
    python3 scripts/build_factory_objects.py vendor

Fluent's objects stop at 256 px and no free set with transparent objects at 512 px or
more could be pinned, so the objects a hero stage needs are modelled here instead: a
gold bar, a silver bar, a stack of gold bars, an oil drum, a blank coin and a podium.
Each is a procedural three.js scene (`scripts/factory/factory.js`) rendered in headless
Chromium through Playwright, so the whole set is rebuilt from code plus a pinned
three.js, and the files are Keel originals.

Every object is rendered on the stage demo's canonical camera (focal 1400 px, the eye
340 px above the ground, image plane vertical) and lit by one key light high and to the
right, the stage's LIGHT. No ground shadow is baked in: the stage casts its own. The
manifest records the camera, the light and where the object's contact point sits in
the PNG, so a scene can stand the object on its ground without guessing.

Rendering needs Playwright with Chromium. WebGL2 there runs on SwiftShader, which Chrome
only uses when asked (`--enable-unsafe-swiftshader`, since Chrome 137). Where the host
has no Playwright, copy `scripts/` into a container that has it, run `render` there,
copy the output directory back and run `publish` here: publishing needs only Pillow.

The `coin` command is the one place a brand enters: it strikes a given SVG mark into
the coin's face, in the mark's own colours, or sets a raster mark into the face as a
clear-coated decal when the brand publishes no vector, and writes one PNG wherever it
is told. It never writes into this package; a brand's coin belongs to the package that
owns the brand (keel-finlogo).
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import math
import re
import shutil
import sys
import tarfile
from pathlib import Path

from _common import CACHE, LICENSES, STATIC, fetch_bytes, remove_stale_files, replace_set, sha256_file, variant_record

SET = "factory"
SOURCE = "https://github.com/miladsafaei-me/keel-visuals"
# Bump when a scene in factory.js changes, so every rendered file's source_version moves with it.
FACTORY_VERSION = "2"

FACTORY_DIR = Path(__file__).resolve().parent / "factory"
THREE_VERSION = "0.186.0"
VENDOR = FACTORY_DIR / "vendor" / f"three-{THREE_VERSION}"
THREE_TARBALL = f"https://registry.npmjs.org/three/-/three-{THREE_VERSION}.tgz"
THREE_TARBALL_SHA256 = "61eeff9d7616005c9a481c796f52287d81fbbbc0d55eaca5565322924252c1aa"
# Vendored file -> (its path inside the npm package, its sha256). The page imports these
# and nothing else, and a render refuses to start if any of them has changed on disk.
THREE_FILES = {
    "three.module.js": ("package/build/three.module.js", "9052042d676cb0fdc1ddfefe193053f34b7ac0513a616fdac4535d49987812ea"),
    "three.core.js": ("package/build/three.core.js", "9edde002b066a9a05676a6127f67735b62baf399bdea529f2f7e31657da769e6"),
    "RoomEnvironment.js": ("package/examples/jsm/environments/RoomEnvironment.js", "55f466192cc84298755a424c5e040345006b2ee1455589b3b54126c2ea4123f4"),
    "SVGLoader.js": ("package/examples/jsm/loaders/SVGLoader.js", "a58536582ec55d41d9ed8bedaf0633398cf9004110cb4a9741d572bded4a3129"),
}

# Chrome 137 stopped falling back to SwiftShader on its own; a headless box has no GPU,
# so WebGL2 exists only when these flags ask for it.
CHROMIUM_ARGS = ["--enable-unsafe-swiftshader", "--use-angle=swiftshader", "--use-gl=angle", "--ignore-gpu-blocklist"]
ORIGIN = "http://keel-visuals-factory.local"

SIZES = (1024, 512)
# Rendered at twice the largest size and downsampled, so edges are antialiased by real coverage.
SUPERSAMPLE = 2

# A raster face's pixel counts as part of the mark from this alpha up.
FACE_ALPHA = 128
# A raster mark is a disc when its box is square within 2 %, its opaque pixels fill 97 %
# of the circle through that box, and no more than 1 % of them fall outside it.
DISC_SQUARENESS = 0.02
DISC_FILL = 0.97
DISC_SPILL = 0.01
# A disc is cut this far inside its own radius, so the anti-aliased edge never reaches the coin.
DISC_CROP = 0.985

# The stage demo's camera, repeated here only to write the elevation into the manifest.
FOCAL = 1400
EYE_HEIGHT = 900 - 560

OBJECTS = {
    "gold-bar": {
        "title": "gold bar",
        "tags": ["bar", "bullion", "commodity", "fine gold", "gold", "ingot", "metal", "precious metal", "xau"],
        "tones": {"": {}},
    },
    "silver-bar": {
        "title": "silver bar",
        "tags": ["bar", "bullion", "commodity", "fine silver", "ingot", "metal", "precious metal", "silver", "xag"],
        "tones": {"": {}},
    },
    "gold-bar-stack": {
        "title": "stack of gold bars",
        "tags": ["bars", "bullion", "commodity", "gold", "ingot", "pyramid", "reserve", "stack", "wealth", "xau"],
        "tones": {"": {}},
    },
    "oil-barrel": {
        "title": "oil barrel",
        "tags": ["barrel", "brent", "commodity", "crude", "drum", "energy", "oil", "petroleum", "wti"],
        "tones": {"": {"paint": "#15181d"}, "blue": {"paint": "#1f4f8c"}},
    },
    "coin-blank": {
        "title": "blank coin",
        "tags": ["blank", "coin", "crypto", "metal", "mint", "money", "token"],
        "tones": {"": {"metal": "gold"}, "silver": {"metal": "silver"}, "gunmetal": {"metal": "gunmetal"}},
    },
    "podium": {
        "title": "podium with a lit rim",
        "tags": ["base", "display", "pedestal", "platform", "podium", "showcase", "stage"],
        "tones": {"": {"glow": "#eaf4ff"}, "green": {"glow": "#3dffa0"}, "blue": {"glow": "#4db8ff"}, "amber": {"glow": "#ffb547"}},
    },
}


def verify_vendor() -> None:
    """Refuse to render with a three.js that is not the pinned one."""
    for name, (_member, expected) in THREE_FILES.items():
        path = VENDOR / name
        if not path.is_file() or sha256_file(path) != expected:
            raise SystemExit(f"{path} is not three.js {THREE_VERSION} as pinned; run `build_factory_objects.py vendor`")


class Factory:
    """One headless Chromium holding the factory page, rendering one job at a time."""

    def __enter__(self) -> "Factory":
        verify_vendor()
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise SystemExit(
                "rendering needs Playwright with Chromium; run this command where it is installed "
                "(see the module docstring for the container route)"
            ) from None
        self.errors: list[str] = []
        self._playwright = sync_playwright().start()
        self.browser = self._playwright.chromium.launch(args=CHROMIUM_ARGS)
        self.page = self.browser.new_page(viewport={"width": 64, "height": 64})
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.on("console", lambda message: self.errors.append(message.text) if message.type == "error" else None)
        self.page.route(f"{ORIGIN}/**", self._serve)
        self.page.goto(f"{ORIGIN}/index.html")
        try:
            self.page.wait_for_function("window.factory && window.factory.ready === true", timeout=60_000)
        except Exception:
            raise SystemExit(f"the factory page did not load: {self.errors or 'no error reported'}") from None
        return self

    def __exit__(self, *_exc) -> None:
        self.browser.close()
        self._playwright.stop()

    def _serve(self, route) -> None:
        relative = route.request.url.removeprefix(f"{ORIGIN}/").split("?", 1)[0]
        path = (FACTORY_DIR / relative).resolve()
        if FACTORY_DIR not in path.parents or not path.is_file():
            route.fulfill(status=404, body="")
            return
        content_type = {".js": "text/javascript", ".html": "text/html"}.get(path.suffix, "application/octet-stream")
        route.fulfill(status=200, body=path.read_bytes(), headers={"content-type": content_type})

    def renderer_info(self) -> dict:
        info = self.page.evaluate("() => window.factory.info()")
        return {"three": THREE_VERSION, "three_revision": info["three"], "chromium": self.browser.version, "gl": info["gl"]}

    def render(self, job: dict):
        """Render one job and return it as a PIL image plus the page's framing record."""
        from PIL import Image

        self.errors.clear()
        try:
            result = self.page.evaluate("job => window.factory.render(job)", job)
        except Exception as error:
            raise SystemExit(f"rendering {job.get('object')} failed: {error}") from None
        if self.errors:
            raise SystemExit(f"rendering {job.get('object')} reported errors: {self.errors}")
        data = base64.b64decode(result["png"].split(",", 1)[1])
        image = Image.open(io.BytesIO(data))
        image.load()
        return image.convert("RGBA"), result["meta"]


def downsample(image, size: int):
    """Resize in premultiplied alpha, so a transparent edge does not pick up a dark fringe."""
    from PIL import Image

    return image.convert("RGBa").resize((size, size), Image.Resampling.LANCZOS).convert("RGBA")


def variant_name(tone: str, size: int) -> str:
    return f"{tone}-{size}" if tone else str(size)


def render_set(out: Path, only: list[str] | None = None) -> None:
    unknown = sorted(set(only or []) - set(OBJECTS))
    if unknown:
        raise SystemExit(f"no factory object {unknown}; the factory makes {sorted(OBJECTS)}")
    out.mkdir(parents=True, exist_ok=True)
    record_path = out / "render.json"
    record = json.loads(record_path.read_text(encoding="utf-8")) if record_path.is_file() else {"objects": {}}
    with Factory() as factory:
        record["renderer"] = factory.renderer_info()
        for name, spec in OBJECTS.items():
            if only and name not in only:
                continue
            tones = {}
            for tone, options in spec["tones"].items():
                image, meta = factory.render({"object": name, "options": options, "size": SIZES[0] * SUPERSAMPLE})
                files = {}
                for size in SIZES:
                    variant = variant_name(tone, size)
                    path = out / f"{name}.{variant}.png"
                    downsample(image, size).save(path, format="PNG", optimize=True)
                    files[variant] = path.name
                tones[tone] = {"files": files, "meta": meta}
                print(f"rendered {name} {tone or 'default'}: ground at {meta['ground']['y'] * SIZES[0]:.1f} px")
            record["objects"][name] = {"factory_version": FACTORY_VERSION, "tones": tones}
    record_path.write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")


def publish_set(source: Path) -> None:
    """Write a finished render into the package and replace the set's manifest entries."""
    record = json.loads((source / "render.json").read_text(encoding="utf-8"))
    missing = [name for name in OBJECTS if record["objects"].get(name, {}).get("factory_version") != FACTORY_VERSION]
    if missing:
        raise SystemExit(f"{source} has no render of {missing} at factory version {FACTORY_VERSION}; render them first")
    root = STATIC / "objects" / SET
    written: set[Path] = set()
    entries: dict[str, dict] = {}
    renderer = record["renderer"]
    for name, spec in OBJECTS.items():
        rendered = record["objects"][name]["tones"]
        variants = {}
        for tone in spec["tones"]:
            for variant, filename in rendered[tone]["files"].items():
                destination = root / name / f"{variant}.png"
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source / filename, destination)
                written.add(destination)
                variants[variant] = variant_record(destination, "png")
        meta = rendered[""]["meta"]
        width = variants[str(SIZES[0])]["width"]
        entries[f"object/{SET}/{name}"] = {
            "kind": "object",
            "set": SET,
            "name": name,
            "title": spec["title"],
            "tags": sorted(spec["tags"]),
            "license": "Keel original",
            "source": SOURCE,
            "source_version": f"factory-{FACTORY_VERSION}+three-{renderer['three']}",
            "trademark": False,
            "default_variant": str(SIZES[0]),
            "variants": variants,
            "extra": {
                "camera": {
                    "elevation_deg": round(math.degrees(math.atan(EYE_HEIGHT / FOCAL)), 2),
                    "focal_px": FOCAL,
                    "eye_height_px": EYE_HEIGHT,
                    "distance_px": FOCAL,
                    "image_plane": "vertical",
                },
                "light": meta["light"],
                "light_direction": meta["light_direction"],
                "ground_x_px": round(meta["ground"]["x"] * width, 1),
                "ground_y_px": round(meta["ground"]["y"] * width, 1),
                "stage_width_px": round(meta["stage_width_px"], 1),
                "shadow": "none",
                "tones": [tone for tone in spec["tones"] if tone],
                "object": meta["object"],
                "renderer": renderer,
            },
        }
    removed = remove_stale_files(root, written)
    replace_set(SET, entries)
    print(f"factory {FACTORY_VERSION}: {len(entries)} objects, {len(written)} files, {removed} stale files removed")


def vendor() -> None:
    """Fetch the pinned three.js tarball and write the files the page imports, checking every hash."""
    archive_bytes = fetch_bytes(THREE_TARBALL)
    if hashlib.sha256(archive_bytes).hexdigest() != THREE_TARBALL_SHA256:
        raise SystemExit(f"{THREE_TARBALL} does not hash to the pinned sha256")
    archive = tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz")
    VENDOR.mkdir(parents=True, exist_ok=True)
    for name, (member, expected) in THREE_FILES.items():
        data = archive.extractfile(member).read()
        if hashlib.sha256(data).hexdigest() != expected:
            raise SystemExit(f"{member} in three {THREE_VERSION} does not hash to the pinned sha256")
        (VENDOR / name).write_bytes(data)
    LICENSES.mkdir(exist_ok=True)
    (LICENSES / "three.txt").write_bytes(archive.extractfile("package/LICENSE").read())
    print(f"three {THREE_VERSION}: {len(THREE_FILES)} files vendored into {VENDOR}")


def raster_face(path: Path) -> tuple[str, dict]:
    """Trim a raster mark, centre it on a square texture, and say whether it is a disc.

    A mark whose opaque pixels fill the circle through its bounding box, and almost
    nothing outside it, is a disc: the texture is that circle's square, cut a little
    inside the disc's own edge so its anti-aliased rim never shows, and flattened onto
    the mark's mean colour so a stray transparent pixel cannot paint black. Any other
    outline keeps its transparency, on a square whose half-width is the distance from
    the mark's centre to its farthest opaque pixel, so the page can put that pixel just
    inside the rim the way it scales an SVG mark. The mean colour of the opaque pixels
    is the colour the rim metal is chosen from.
    """
    from PIL import Image, ImageDraw

    image = Image.open(path).convert("RGBA")
    alpha = image.getchannel("A")
    solid = alpha.point(lambda value: 255 if value >= FACE_ALPHA else 0)
    box = solid.getbbox()
    if box is None:
        raise SystemExit(f"{path} has no opaque pixel to put on a coin")
    left, top, right, bottom = box
    cx, cy = (left + right) / 2, (top + bottom) / 2
    radius = max(right - left, bottom - top) / 2

    circle = Image.new("L", image.size, 0)
    ImageDraw.Draw(circle).ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=255)
    solid_pixels = solid.histogram()[255]
    circle_pixels = circle.histogram()[255]
    inside = sum(1 for opaque, within in zip(solid.tobytes(), circle.tobytes()) if opaque and within)
    square = abs((right - left) - (bottom - top)) <= DISC_SQUARENESS * 2 * radius
    disc = square and inside >= DISC_FILL * circle_pixels and solid_pixels - inside <= DISC_SPILL * solid_pixels

    rgb = [0.0, 0.0, 0.0]
    weight = 0
    reach = 0.0
    pixels = image.tobytes()
    for index in range(image.width * image.height):
        red, green, blue, opacity = pixels[4 * index : 4 * index + 4]
        if opacity < FACE_ALPHA:
            continue
        rgb[0] += red
        rgb[1] += green
        rgb[2] += blue
        weight += 1
        x, y = index % image.width + 0.5, index // image.width + 0.5
        reach = max(reach, math.hypot(x - cx, y - cy))
    dominant = "#" + "".join(f"{round(channel / weight):02x}" for channel in rgb)

    half = radius * DISC_CROP if disc else reach
    crop = image.crop((round(cx - half), round(cy - half), round(cx + half), round(cy + half)))
    if disc:
        ground = Image.new("RGBA", crop.size, dominant)
        ground.alpha_composite(crop)
        crop = ground
    buffer = io.BytesIO()
    crop.save(buffer, format="PNG")
    face = {"disc": disc, "dominant": dominant, "source_px": list(image.size), "texture_px": list(crop.size)}
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii"), face


def coin(face_svg: Path | None, face_png: Path | None, out: Path, size: int, metal: str, counter: str) -> None:
    job = {"object": "coin", "options": {"metal": metal, "counter": counter}, "size": size * SUPERSAMPLE}
    if face_svg:
        job["svg"] = face_svg.read_text(encoding="utf-8")
    else:
        job["png"], job["face"] = raster_face(face_png)
    with Factory() as factory:
        image, meta = factory.render(job)
        renderer = factory.renderer_info()
    out.parent.mkdir(parents=True, exist_ok=True)
    downsample(image, size).save(out, format="PNG", optimize=True)
    report = {
        "file": str(out),
        "size": size,
        "metal": meta["object"]["metal"],
        "face": meta["object"]["face"],
        "camera": {"elevation_deg": round(math.degrees(math.atan(EYE_HEIGHT / FOCAL)), 2), "focal_px": FOCAL},
        "light": meta["light"],
        "ground_y_px": round(meta["ground"]["y"] * size, 1),
        "stage_width_px": round(meta["stage_width_px"], 1),
        "renderer": renderer,
    }
    json.dump(report, sys.stdout, indent=1)
    print()


def counter_choice(value: str) -> str:
    """`auto`, `none` or a #rrggbb colour; anything else is refused before Chromium starts."""
    if value in {"auto", "none"} or re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        return value
    raise argparse.ArgumentTypeError(f"--counter takes auto, none or #rrggbb, not {value!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the keel-visuals object factory.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("build", help="render every object and publish the set (needs Playwright)")
    render_cmd = commands.add_parser("render", help="render objects into a directory (needs Playwright)")
    render_cmd.add_argument("--out", type=Path, required=True)
    render_cmd.add_argument("--only", nargs="*", help="render only these objects, for iterating on one")
    publish_cmd = commands.add_parser("publish", help="write a finished render into the package (needs Pillow)")
    publish_cmd.add_argument("--from", dest="source", type=Path, required=True)
    coin_cmd = commands.add_parser("coin", help="strike a brand mark into a coin and write one PNG")
    face = coin_cmd.add_mutually_exclusive_group(required=True)
    face.add_argument("--face-svg", type=Path, help="a vector mark, extruded into the face")
    face.add_argument("--face-png", type=Path, help="a raster mark, set into the face as a clear-coated decal")
    coin_cmd.add_argument("--out", type=Path, required=True)
    coin_cmd.add_argument("--size", type=int, default=1024)
    coin_cmd.add_argument("--metal", choices=["auto", "gold", "silver", "gunmetal"], default="auto")
    coin_cmd.add_argument(
        "--counter",
        type=counter_choice,
        default="auto",
        help="the enamel in a disc mark's knockouts: auto (white, or dark ink on a light disc), none (the field shows), or #rrggbb",
    )
    commands.add_parser("vendor", help=f"re-fetch three.js {THREE_VERSION} and check it against the pinned hashes")
    args = parser.parse_args()

    if args.command == "build":
        out = CACHE / "factory-render"
        render_set(out)
        publish_set(out)
    elif args.command == "render":
        render_set(args.out, args.only)
    elif args.command == "publish":
        publish_set(args.source)
    elif args.command == "coin":
        coin(args.face_svg, args.face_png, args.out, args.size, args.metal, args.counter)
    elif args.command == "vendor":
        vendor()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
