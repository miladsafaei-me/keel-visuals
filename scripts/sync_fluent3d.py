"""Vendor Microsoft's Fluent Emoji in their 3D style: the objects a finance picture uses.

    python3 scripts/sync_fluent3d.py --ref 1ffb34c752ecf5d402f04cfb4b392c77f57c54bc

Most of the 1,595 emoji have no place on a trading page and the 3D files are the
heavy part, so the set is curated by rule rather than by hand: every emoji in the
groups that hold objects and symbols, plus a short named list from the other
groups that carries trading meaning (the bull and the bear, the robot, the whale).
Skin-toned emoji ship in their default tone only. Every file is 256 px, so it may
be drawn at most 128 CSS px wide on a 2x capture.
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.parse

from _common import CACHE, LICENSES, STATIC, fetch_bytes, fetch_many, remove_stale_files, replace_set, slugify, variant_record

SET = "fluent"
REPO = "microsoft/fluentui-emoji"
SOURCE = f"https://github.com/{REPO}"
GROUPS = {"Objects", "Symbols", "Travel & Places", "Activities"}
# Outside those groups, only emoji that carry meaning on a trading page.
NAMED = {
    "Robot", "Brain", "Ox", "Water buffalo", "Bear", "Spouting whale", "Whale", "Shark", "Owl",
    "Handshake", "Thumbs up", "Thumbs down", "Flexed biceps", "Clapping hands", "Money-mouth face",
    "Nerd face", "Thinking face", "Exploding head", "Face with monocle", "Smiling face with sunglasses",
    "Star-struck", "Eyes", "Rocket", "Chart increasing", "Chart decreasing",
}
THREE_D = re.compile(r"^assets/(?P<folder>[^/]+)/(?:Default/)?3D/(?P<file>[^/]+\.png)$")


def raw_url(ref: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{REPO}/{ref}/{urllib.parse.quote(path)}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Vendor Fluent Emoji 3D objects.")
    parser.add_argument("--ref", required=True, help="an exact commit SHA of microsoft/fluentui-emoji")
    args = parser.parse_args()

    tree = json.loads(fetch_bytes(f"https://api.github.com/repos/{REPO}/git/trees/{args.ref}?recursive=1"))
    if tree.get("truncated"):
        raise SystemExit("GitHub truncated the tree listing; the set would be incomplete")
    pngs: dict[str, str] = {}
    for item in tree["tree"]:
        match = THREE_D.match(item["path"])
        if match:
            pngs.setdefault(match["folder"], item["path"])

    metadata_cache = CACHE / "fluent-metadata"
    fetch_many([
        (raw_url(args.ref, f"assets/{folder}/metadata.json"), metadata_cache / f"{slugify(folder)}.json")
        for folder in pngs
    ])
    chosen = []
    for folder, path in sorted(pngs.items()):
        meta = json.loads((metadata_cache / f"{slugify(folder)}.json").read_text(encoding="utf-8"))
        if meta.get("group") in GROUPS or folder in NAMED:
            chosen.append((folder, path, meta))
    missing_named = NAMED - {folder for folder, _, _ in chosen}

    root = STATIC / "objects" / SET
    names: dict[str, str] = {}
    jobs, plans = [], []
    for folder, path, meta in chosen:
        name = slugify(meta.get("cldr") or folder)
        if not name or name in names:
            name = f"{name}-{meta.get('unicode', '').replace(' ', '-')}".strip("-")
        names[name] = folder
        destination = root / name / "3d.png"
        jobs.append((raw_url(args.ref, path), destination))
        plans.append((name, folder, meta, destination))
    fetch_many(jobs)

    LICENSES.mkdir(exist_ok=True)
    (LICENSES / "fluentui-emoji.txt").write_bytes(fetch_bytes(raw_url(args.ref, "LICENSE")))

    entries: dict[str, dict] = {}
    for name, folder, meta, destination in plans:
        entries[f"object/{SET}/{name}"] = {
            "kind": "object",
            "set": SET,
            "name": name,
            "title": meta.get("cldr") or folder,
            "tags": sorted({str(word) for word in meta.get("keywords", [])}),
            "license": "MIT",
            "source": SOURCE,
            "source_version": args.ref,
            "trademark": False,
            "default_variant": "3d",
            "variants": {"3d": variant_record(destination, "png")},
            "extra": {"group": meta.get("group", ""), "glyph": meta.get("glyph", ""), "unicode": meta.get("unicode", "")},
        }

    removed = remove_stale_files(root, {destination for *_, destination in plans})
    replace_set(SET, entries)
    print(f"fluent 3d @ {args.ref[:10]}: {len(entries)} objects, {removed} stale files removed")
    if missing_named:
        print(f"named emoji not found upstream: {sorted(missing_named)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
