"""List the registry the way a brief author needs it: by key, with what each asset can do.

    python -m keel_visuals.catalog --summary
    python -m keel_visuals.catalog --kind object --search money
    python -m keel_visuals.catalog --kind icon --search "chart candle" --limit 10

A brief names assets by key and nothing else, so this is where an author looks
them up, never the file tree. `largest CSS px` is the widest an asset may be drawn
on a 2x capture before it is upscaled; `vector` means there is no such limit.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter

from .manifest import KINDS, Asset, iter_assets, load_manifest, search


def describe(asset: Asset) -> dict:
    variant = asset.variant()
    return {
        "key": asset.key,
        "title": asset.title,
        "variants": sorted(asset.variants),
        "format": variant.format,
        "max_render_px": variant.max_render_px(),
        "license": asset.license,
        "trademark": asset.trademark,
    }


def summary() -> str:
    counts = Counter((entry["kind"], entry["set"]) for entry in load_manifest()["assets"].values())
    lines = ["| kind | set | assets |", "|---|---|---|"]
    lines += [f"| {kind} | {set_name} | {count} |" for (kind, set_name), count in sorted(counts.items())]
    return "\n".join(lines)


def table(rows: list[dict]) -> str:
    lines = [
        "| key | title | variants | largest CSS px | license | trademark |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        size = "vector" if row["max_render_px"] is None else str(row["max_render_px"])
        lines.append(
            f"| `{row['key']}` | {row['title']} | {', '.join(row['variants'])} | {size} | "
            f"{row['license']} | {'yes' if row['trademark'] else 'no'} |"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="List keel-visuals assets by key.")
    parser.add_argument("--kind", choices=KINDS)
    parser.add_argument("--set", dest="set_name")
    parser.add_argument("--search", default="")
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--no-trademarks", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)

    if args.summary:
        print(summary())
        return 0
    if args.search:
        assets = search(args.search, kind=args.kind, include_trademarks=not args.no_trademarks)
        if args.set_name:
            assets = [asset for asset in assets if asset.set == args.set_name]
    else:
        assets = [
            asset for asset in iter_assets(args.kind, args.set_name)
            if not (args.no_trademarks and asset.trademark)
        ]
    rows = [describe(asset) for asset in assets[: args.limit]]
    print(json.dumps(rows, indent=2) if args.json else table(rows))
    return 0 if rows else 1


if __name__ == "__main__":
    sys.exit(main())
