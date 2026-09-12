"""Vendor Natural Earth's land polygons and precompute world dot grids from them.

    python3 scripts/build_worldmap.py --tag v5.1.2

A dotted world map is the quietest element in a finance cover, and one drawn from
hand-typed boxes puts continents in the wrong place. These grids are computed
from the public-domain 1:110m land polygons instead: one dot per grid cell whose
centre falls on land, in equirectangular projection, cropped at 84°N and 58°S so
Antarctica does not smear across the bottom of a banner.

Each grid ships twice: as an SVG whose dots paint in `currentColor` (one user
unit per cell, so it scales to any box), and as JSON cell coordinates for a
renderer that draws its own dots.
"""

from __future__ import annotations

import argparse
import json

from _common import LICENSES, STATIC, fetch_bytes, remove_stale_files, replace_set, variant_record

SET = "natural-earth"
SOURCE = "https://www.naturalearthdata.com/"
LAT_MAX, LAT_MIN = 84.0, -58.0
STEPS = (1, 2, 3)


def rings_of(geometry: dict) -> list[list[list[list[float]]]]:
    """Every polygon as [outer ring, hole, hole, ...]."""
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"]]
    if geometry["type"] == "MultiPolygon":
        return list(geometry["coordinates"])
    return []


def inside_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    inside = False
    for index in range(len(ring)):
        x1, y1 = ring[index - 1][:2]
        x2, y2 = ring[index][:2]
        if (y2 > lat) != (y1 > lat):
            crossing = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
            if lon < crossing:
                inside = not inside
    return inside


def build_polygons(features: list[dict]) -> list[tuple[tuple[float, float, float, float], list]]:
    polygons = []
    for feature in features:
        for rings in rings_of(feature["geometry"]):
            outer = rings[0]
            lons = [point[0] for point in outer]
            lats = [point[1] for point in outer]
            polygons.append(((min(lons), max(lons), min(lats), max(lats)), rings))
    return polygons


def on_land(lon: float, lat: float, polygons) -> bool:
    for (west, east, south, north), rings in polygons:
        if not (west <= lon <= east and south <= lat <= north):
            continue
        if inside_ring(lon, lat, rings[0]) and not any(inside_ring(lon, lat, hole) for hole in rings[1:]):
            return True
    return False


def grid(step: int, polygons) -> dict:
    columns = int(360 / step)
    rows = int((LAT_MAX - LAT_MIN) / step)
    dots = [
        [column, row]
        for row in range(rows)
        for column in range(columns)
        if on_land(-180 + (column + 0.5) * step, LAT_MAX - (row + 0.5) * step, polygons)
    ]
    return {
        "projection": "equirectangular",
        "step_degrees": step,
        "lon_min": -180,
        "lat_max": LAT_MAX,
        "columns": columns,
        "rows": rows,
        "dots": dots,
    }


def svg(data: dict) -> str:
    circles = "".join(f'<circle cx="{column + 0.5}" cy="{row + 0.5}" r="0.34"/>' for column, row in data["dots"])
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {data["columns"]} {data["rows"]}" '
        f'fill="currentColor">{circles}</svg>\n'
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Vendor Natural Earth land and world dot grids.")
    parser.add_argument("--tag", required=True, help="an exact natural-earth-vector release tag, e.g. v5.1.2")
    args = parser.parse_args()

    base = f"https://raw.githubusercontent.com/nvkelso/natural-earth-vector/{args.tag}"
    raw = fetch_bytes(f"{base}/geojson/ne_110m_land.geojson")
    root = STATIC / "maps" / SET
    root.mkdir(parents=True, exist_ok=True)
    land_path = root / "ne_110m_land.geojson"
    land_path.write_bytes(raw)
    LICENSES.mkdir(exist_ok=True)
    (LICENSES / "natural-earth.md").write_bytes(fetch_bytes(f"{base}/LICENSE.md"))

    polygons = build_polygons(json.loads(raw)["features"])
    written = {land_path}
    dot_variants = {}
    counts = {}
    for step in STEPS:
        data = grid(step, polygons)
        counts[step] = len(data["dots"])
        svg_path = root / f"world-dots-{step}deg.svg"
        json_path = root / f"world-dots-{step}deg.json"
        svg_path.write_text(svg(data), encoding="utf-8")
        json_path.write_text(json.dumps(data, separators=(",", ":")) + "\n", encoding="utf-8")
        written |= {svg_path, json_path}
        dot_variants[f"svg-{step}deg"] = variant_record(svg_path, "svg")
        dot_variants[f"json-{step}deg"] = variant_record(json_path, "json")

    common = {"set": SET, "license": "Public domain", "source": SOURCE, "source_version": args.tag, "trademark": False}
    entries = {
        f"map/{SET}/world-land": {
            **common,
            "kind": "map",
            "name": "world-land",
            "title": "world land polygons, 1:110m",
            "tags": ["world", "map", "land", "continents", "geography", "global"],
            "default_variant": "geojson",
            "variants": {"geojson": variant_record(land_path, "geojson")},
            "extra": {"scale": "1:110m"},
        },
        f"map/{SET}/world-dots": {
            **common,
            "kind": "map",
            "name": "world-dots",
            "title": "dotted world map",
            "tags": ["world", "map", "dots", "dotted", "global", "coverage", "markets", "background"],
            "default_variant": "svg-2deg",
            "variants": dot_variants,
            "extra": {
                "projection": "equirectangular",
                "lat_range": [LAT_MIN, LAT_MAX],
                "paint": "currentColor",
                "dots": {f"{step}deg": count for step, count in counts.items()},
            },
        },
    }
    removed = remove_stale_files(root, written)
    replace_set(SET, entries)
    print(f"natural earth {args.tag}: dots per grid {counts}, {removed} stale files removed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
