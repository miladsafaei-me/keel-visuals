"""Vendor the Tabler icon set: every outline and filled SVG, with Tabler's own tags.

    python3 scripts/sync_tabler.py --version 3.46.0

Tabler's SVGs paint with `currentColor`, so an icon takes the colour of whatever it
is inlined into; drawn through a plain `<img>` it paints black. Brand icons
(`brand-*`, category Brand) are marked as trademarks.
"""

from __future__ import annotations

import argparse
import io
import json
import tarfile

from _common import LICENSES, STATIC, fetch_bytes, remove_stale_files, replace_set, variant_record

SET = "tabler"
SOURCE = "https://github.com/tabler/tabler-icons"
STYLES = ("outline", "filled")


def main() -> int:
    parser = argparse.ArgumentParser(description="Vendor the Tabler icon set.")
    parser.add_argument("--version", required=True, help="an exact @tabler/icons release, e.g. 3.46.0")
    args = parser.parse_args()

    release = json.loads(fetch_bytes(f"https://registry.npmjs.org/@tabler/icons/{args.version}"))
    archive = tarfile.open(fileobj=io.BytesIO(fetch_bytes(release["dist"]["tarball"])), mode="r:gz")
    members = {member.name: member for member in archive.getmembers()}
    icons = json.load(archive.extractfile(members["package/icons.json"]))
    LICENSES.mkdir(exist_ok=True)
    (LICENSES / "tabler-icons.txt").write_bytes(archive.extractfile(members["package/LICENSE"]).read())

    root = STATIC / "icons" / SET
    written: set = set()
    entries: dict[str, dict] = {}
    for name, meta in sorted(icons.items()):
        variants = {}
        for style in STYLES:
            member = members.get(f"package/icons/{style}/{name}.svg")
            if member is None:
                continue
            destination = root / style / f"{name}.svg"
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.extractfile(member).read())
            written.add(destination)
            variants[style] = variant_record(destination, "svg")
        if not variants:
            continue
        category = meta.get("category") or ""
        entries[f"icon/{SET}/{name}"] = {
            "kind": "icon",
            "set": SET,
            "name": name,
            "title": name.replace("-", " "),
            "tags": sorted({str(tag) for tag in meta.get("tags", [])}),
            "license": "MIT",
            "source": SOURCE,
            "source_version": args.version,
            "trademark": category == "Brand" or name.startswith("brand-"),
            "default_variant": "outline" if "outline" in variants else next(iter(variants)),
            "variants": variants,
            "extra": {"category": category, "paint": "currentColor"},
        }

    removed = remove_stale_files(root, written)
    replace_set(SET, entries)
    print(f"tabler {args.version}: {len(entries)} icons, {len(written)} files, {removed} stale files removed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
