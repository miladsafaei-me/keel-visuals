"""Vendor the Tabler icon set: every outline and filled SVG, with Tabler's own tags.

    python3 scripts/sync_tabler.py --version 3.46.0

Tabler's SVGs paint with `currentColor`, so an icon takes the colour of whatever it
is inlined into; drawn through a plain `<img>` it paints black. Brand icons
(`brand-*`, category Brand) and cryptocurrency marks (`currency-<coin>`) are marked
as trademarks.
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

# A cryptocurrency's symbol is that project's brand mark, even though Tabler files it
# under Currencies beside the fiat signs: the B of `currency-bitcoin` names Bitcoin the
# way a broker's logo names the broker, while `currency-euro` is a public sign no one
# owns. The rule keys on the name after `currency-`. A coin Tabler does not ship yet
# (`dash`) is listed anyway, so the release that adds it is flagged on the day it lands.
CRYPTO_CURRENCIES = frozenset({
    "bitcoin",
    "dash",
    "dogecoin",
    "ethereum",
    "husd",  # Huobi's dollar stablecoin
    "litecoin",
    "monero",
    "nano",
    "ripple",
    "solana",
    "tether",
    "xrp",
    "zcash",
})

# Tags Tabler puts only on coins. A `currency-*` icon carrying one whose name is not in
# CRYPTO_CURRENCIES stops the sync, so a coin added upstream can never ship unflagged.
CRYPTO_TAGS = frozenset({"crypto", "cryptocurrency", "blockchain"})


def is_crypto_currency(name: str, tags: set[str]) -> bool:
    """Whether a `currency-*` icon is a coin's mark; stops on a coin the rule does not name."""
    if not name.startswith("currency-"):
        return False
    coin = name.removeprefix("currency-")
    if coin in CRYPTO_CURRENCIES:
        return True
    if tags & CRYPTO_TAGS:
        raise SystemExit(
            f"{name} is tagged {sorted(tags & CRYPTO_TAGS)} but {coin!r} is not in CRYPTO_CURRENCIES; "
            "add it there if it is a coin's mark, so it ships as a trademark"
        )
    return False


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
        tags = {str(tag) for tag in meta.get("tags", [])}
        entries[f"icon/{SET}/{name}"] = {
            "kind": "icon",
            "set": SET,
            "name": name,
            "title": name.replace("-", " "),
            "tags": sorted(tags),
            "license": "MIT",
            "source": SOURCE,
            "source_version": args.version,
            "trademark": category == "Brand" or name.startswith("brand-") or is_crypto_currency(name, tags),
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
