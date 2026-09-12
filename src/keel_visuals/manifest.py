"""Load and query manifest.json, the index of every visual asset this package ships.

Stdlib only on purpose. A headless renderer reads these files straight from disk
with no Django in the process, and a brief author lists them from a shell; both
need the index without an app registry.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
STATIC_ROOT = PACKAGE_ROOT / "static" / "keel_visuals"
MANIFEST_PATH = STATIC_ROOT / "manifest.json"
SCHEMA_VERSION = 1

# What an asset is decides how a renderer may use it:
#   icon   - a flat vector glyph that takes the colour it is painted in;
#   object - a rendered 3D object with its own colour and light (raster);
#   map    - geography, as land polygons or a precomputed dot grid;
#   frame  - a device or window frame that declares its screen rectangle.
KINDS = ("icon", "object", "map", "frame")

KEY_PATTERN = re.compile(r"^(icon|object|map|frame)/[a-z0-9-]+/[a-z0-9][a-z0-9.-]*$")


@dataclass(frozen=True)
class Variant:
    """One file of an asset: a style, weight, angle or tone of the same thing."""

    name: str
    file: str
    format: str
    sha256: str
    width: int | None = None
    height: int | None = None

    @property
    def path(self) -> Path:
        return STATIC_ROOT / self.file

    @property
    def static_path(self) -> str:
        """The path Django's staticfiles serves this file under."""
        return f"keel_visuals/{self.file}"

    @property
    def is_raster(self) -> bool:
        return self.format in {"png", "webp", "jpg"}

    def max_render_px(self, device_scale: int = 2) -> int | None:
        """The widest CSS size this file may be drawn at without being upscaled.

        A raster drawn wider than its own pixels divided by the capture's device
        scale is stretched and goes soft. Vectors and data files have no limit.
        """
        if not self.is_raster or not self.width:
            return None
        return self.width // device_scale


@dataclass(frozen=True)
class Asset:
    """One thing a brief can name, with every variant it ships in."""

    key: str
    kind: str
    set: str
    name: str
    title: str
    tags: tuple[str, ...]
    license: str
    source: str
    source_version: str
    # A mark that belongs to a third party. The file's licence covers the file,
    # never the right to use the brand, so a consumer decides whether it may appear.
    trademark: bool
    default_variant: str
    variants: dict[str, Variant]
    extra: dict = field(default_factory=dict)

    def variant(self, name: str | None = None) -> Variant:
        chosen = name or self.default_variant
        try:
            return self.variants[chosen]
        except KeyError:
            raise KeyError(f"{self.key} has no variant {chosen!r}; it ships {sorted(self.variants)}") from None


@lru_cache(maxsize=1)
def load_manifest() -> dict:
    """The whole manifest. Cached: it only changes when the package is re-pinned."""
    if not MANIFEST_PATH.is_file():
        return {"schema": SCHEMA_VERSION, "assets": {}}
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _build(key: str, entry: dict) -> Asset:
    variants = {
        name: Variant(
            name=name,
            file=data["file"],
            format=data["format"],
            sha256=data["sha256"],
            width=data.get("width"),
            height=data.get("height"),
        )
        for name, data in entry["variants"].items()
    }
    return Asset(
        key=key,
        kind=entry["kind"],
        set=entry["set"],
        name=entry["name"],
        title=entry.get("title", entry["name"]),
        tags=tuple(str(tag) for tag in entry.get("tags", ())),
        license=entry["license"],
        source=entry["source"],
        source_version=entry["source_version"],
        trademark=bool(entry.get("trademark", False)),
        default_variant=entry["default_variant"],
        variants=variants,
        extra=dict(entry.get("extra", {})),
    )


def get_asset(key: str) -> Asset | None:
    entry = load_manifest()["assets"].get(key)
    return _build(key, entry) if entry else None


def require_asset(key: str) -> Asset:
    """The asset, or a KeyError that names the closest keys that do exist."""
    asset = get_asset(key)
    if asset is not None:
        return asset
    if not KEY_PATTERN.match(key):
        raise KeyError(f"{key!r} is not a visuals key; keys look like icon/tabler/chart-candle")
    kind = key.split("/", 1)[0]
    same_kind = [candidate for candidate, entry in load_manifest()["assets"].items() if entry["kind"] == kind]
    near = difflib.get_close_matches(key, same_kind, n=5, cutoff=0.8)
    hint = f"; nearest: {', '.join(near)}" if near else ""
    raise KeyError(f"no visual asset {key!r}{hint}")


def iter_assets(kind: str | None = None, set_name: str | None = None):
    for key, entry in load_manifest()["assets"].items():
        if kind and entry["kind"] != kind:
            continue
        if set_name and entry["set"] != set_name:
            continue
        yield _build(key, entry)


def search(
    query: str,
    *,
    kind: str | None = None,
    include_trademarks: bool = True,
    limit: int | None = None,
) -> list[Asset]:
    """Assets whose name, title or tags match every word of the query, best first.

    A word scores 3 when it is a whole part of the asset's name, 2 when it is one
    of its tags and 1 when it only appears inside the title or name; an asset
    that misses any word is dropped.
    """
    words = [word for word in re.split(r"[\s/_-]+", query.lower()) if word]
    if not words:
        return []
    scored = []
    for asset in iter_assets(kind):
        if asset.trademark and not include_trademarks:
            continue
        name = asset.name.lower()
        parts = set(name.split("-"))
        tags = {tag.lower() for tag in asset.tags}
        title = asset.title.lower()
        score = 0
        for word in words:
            if word in parts:
                score += 3
            elif word in tags:
                score += 2
            elif word in title or word in name:
                score += 1
            else:
                score = 0
                break
        if score:
            scored.append((-score, len(name), asset.key, asset))
    scored.sort(key=lambda row: row[:3])
    found = [row[3] for row in scored]
    return found[:limit] if limit else found


def verify_asset(asset: Asset) -> list[str]:
    """Every way this asset's files disagree with the manifest. Empty means intact."""
    problems = []
    for variant in asset.variants.values():
        if not variant.path.is_file():
            problems.append(f"{asset.key}#{variant.name}: {variant.file} is missing")
            continue
        digest = hashlib.sha256(variant.path.read_bytes()).hexdigest()
        if digest != variant.sha256:
            problems.append(f"{asset.key}#{variant.name}: {variant.file} does not match its recorded hash")
    return problems


def manifest_sha256() -> str:
    """One hash for the whole registry. The manifest records every file's own hash,
    so a change to any file changes this."""
    if not MANIFEST_PATH.is_file():
        return ""
    return hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
