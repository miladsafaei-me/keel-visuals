"""Draw the device and window frames: phone, tablet, browser and desktop, dark and light.

    python3 scripts/build_frames.py

No free library ships device mockups under a licence that is clean for commercial
images, so these are drawn here. Each frame is an SVG whose screen is a real hole
(an even-odd path, not a painted rectangle), so content placed behind it shows
through, and the manifest records that screen's rectangle and corner radius in the
SVG's own units. A renderer places content by those numbers and never guesses.
"""

from __future__ import annotations

from _common import STATIC, remove_stale_files, replace_set, variant_record

SET = "keel"
SOURCE = "https://github.com/miladsafaei-me/keel-visuals"
VERSION = "1"

TONES = {
    "dark": {"body": "#0f171f", "edge": "#2b3845", "detail": "#3c4a58", "ink": "#05080b", "bar": "#16212b", "pill": "#1f2b36"},
    "light": {"body": "#f4f7fa", "edge": "#d3dbe3", "detail": "#b6c2cd", "ink": "#0b1118", "bar": "#e9eef3", "pill": "#dde4ea"},
}


def rounded_rect(x: float, y: float, width: float, height: float, radius: float) -> str:
    """One closed rounded rectangle as path data, so it can cut a hole in another."""
    r = min(radius, width / 2, height / 2)
    return (
        f"M{x + r},{y}H{x + width - r}A{r},{r} 0 0 1 {x + width},{y + r}"
        f"V{y + height - r}A{r},{r} 0 0 1 {x + width - r},{y + height}"
        f"H{x + r}A{r},{r} 0 0 1 {x},{y + height - r}V{y + r}A{r},{r} 0 0 1 {x + r},{y}Z"
    )


def svg(width: int, height: int, body: str) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">{body}</svg>\n'


def phone(tone: dict) -> tuple[str, dict]:
    width, height, bezel, radius = 430, 880, 18, 66
    screen = {"x": bezel, "y": bezel, "width": width - 2 * bezel, "height": height - 2 * bezel, "radius": radius - bezel}
    shell = rounded_rect(0, 0, width, height, radius) + rounded_rect(screen["x"], screen["y"], screen["width"], screen["height"], screen["radius"])
    island = rounded_rect(width / 2 - 62, bezel + 16, 124, 36, 18)
    body = (
        f'<path fill-rule="evenodd" fill="{tone["body"]}" stroke="{tone["edge"]}" stroke-width="2" d="{shell}"/>'
        f'<path fill="{tone["ink"]}" d="{island}"/>'
        f'<rect x="-3" y="170" width="4" height="64" rx="2" fill="{tone["detail"]}"/>'
        f'<rect x="{width - 1}" y="210" width="4" height="96" rx="2" fill="{tone["detail"]}"/>'
    )
    return svg(width, height, body), {"screen": screen, "covers_screen": [{"x": width / 2 - 62, "y": bezel + 16, "width": 124, "height": 36}]}


def tablet(tone: dict) -> tuple[str, dict]:
    width, height, bezel, radius = 860, 1180, 30, 52
    screen = {"x": bezel, "y": bezel, "width": width - 2 * bezel, "height": height - 2 * bezel, "radius": 20}
    shell = rounded_rect(0, 0, width, height, radius) + rounded_rect(screen["x"], screen["y"], screen["width"], screen["height"], screen["radius"])
    body = (
        f'<path fill-rule="evenodd" fill="{tone["body"]}" stroke="{tone["edge"]}" stroke-width="2" d="{shell}"/>'
        f'<circle cx="{width / 2}" cy="{bezel / 2}" r="5" fill="{tone["detail"]}"/>'
    )
    return svg(width, height, body), {"screen": screen, "covers_screen": []}


def browser(tone: dict) -> tuple[str, dict]:
    width, height, bar, radius = 1280, 820, 56, 18
    screen = {"x": 0, "y": bar, "width": width, "height": height - bar, "radius": 0}
    outline = rounded_rect(0, 0, width, height, radius) + rounded_rect(1, bar, width - 2, height - bar - 1, 0)
    dots = "".join(
        f'<circle cx="{28 + index * 22}" cy="{bar / 2}" r="7" fill="{colour}"/>'
        for index, colour in enumerate(("#ff5f57", "#febc2e", "#28c840"))
    )
    body = (
        f'<path fill-rule="evenodd" fill="{tone["bar"]}" stroke="{tone["edge"]}" stroke-width="2" d="{outline}"/>'
        f'{dots}'
        f'<path fill="{tone["pill"]}" d="{rounded_rect(width / 2 - 300, 13, 600, 30, 15)}"/>'
        f'<circle cx="{width / 2 - 280}" cy="{bar / 2}" r="5" fill="none" stroke="{tone["detail"]}" stroke-width="2"/>'
    )
    return svg(width, height, body), {"screen": screen, "covers_screen": []}


def desktop(tone: dict) -> tuple[str, dict]:
    width, monitor_height, bezel, chin = 1280, 820, 22, 50
    height = monitor_height + 150
    screen = {"x": bezel, "y": bezel, "width": width - 2 * bezel, "height": monitor_height - bezel - chin, "radius": 6}
    shell = rounded_rect(0, 0, width, monitor_height, 22) + rounded_rect(screen["x"], screen["y"], screen["width"], screen["height"], screen["radius"])
    neck = f"M{width / 2 - 70},{monitor_height}H{width / 2 + 70}L{width / 2 + 96},{height - 26}H{width / 2 - 96}Z"
    body = (
        f'<path fill="{tone["detail"]}" d="{neck}"/>'
        f'<path fill="{tone["body"]}" stroke="{tone["edge"]}" stroke-width="2" d="{rounded_rect(width / 2 - 230, height - 30, 460, 30, 10)}"/>'
        f'<path fill-rule="evenodd" fill="{tone["body"]}" stroke="{tone["edge"]}" stroke-width="2" d="{shell}"/>'
        f'<circle cx="{width / 2}" cy="{monitor_height - chin / 2}" r="6" fill="{tone["detail"]}"/>'
    )
    return svg(width, height, body), {"screen": screen, "covers_screen": []}


FRAMES = {
    "phone": (phone, "smartphone frame", ["phone", "mobile", "smartphone", "app", "device", "mockup", "ios", "android"]),
    "tablet": (tablet, "tablet frame", ["tablet", "ipad", "device", "mockup", "app"]),
    "browser": (browser, "browser window frame", ["browser", "window", "web", "extension", "dashboard", "chrome", "mockup"]),
    "desktop": (desktop, "desktop monitor frame", ["desktop", "monitor", "computer", "terminal", "platform", "mockup"]),
}


def main() -> int:
    root = STATIC / "frames" / SET
    written, entries = set(), {}
    for name, (draw, title, tags) in FRAMES.items():
        variants, geometry = {}, {}
        for tone_name, tone in TONES.items():
            text, geometry = draw(tone)
            path = root / name / f"{tone_name}.svg"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            written.add(path)
            variants[tone_name] = variant_record(path, "svg")
        view = text.split('viewBox="0 0 ', 1)[1].split('"', 1)[0].split()
        entries[f"frame/{SET}/{name}"] = {
            "kind": "frame",
            "set": SET,
            "name": name,
            "title": title,
            "tags": tags,
            "license": "Keel original",
            "source": SOURCE,
            "source_version": VERSION,
            "trademark": False,
            "default_variant": "dark",
            "variants": variants,
            "extra": {"viewbox": {"width": float(view[0]), "height": float(view[1])}, **geometry},
        }
    removed = remove_stale_files(root, written)
    replace_set(SET, entries)
    print(f"frames: {len(entries)} frames x {len(TONES)} tones, {removed} stale files removed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
