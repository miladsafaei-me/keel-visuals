"""Shared plumbing for the sync scripts: paths, downloads, hashes and manifest merges.

The scripts are maintenance tooling for this repository and never run in a
consumer. Each one owns exactly one `set` in the manifest and replaces that set
wholesale, so re-running a sync is idempotent and an asset removed upstream
disappears here too instead of lingering.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "keel_visuals" / "static" / "keel_visuals"
MANIFEST = STATIC / "manifest.json"
LICENSES = ROOT / "LICENSES"
CACHE = ROOT / ".cache"
SCHEMA_VERSION = 1
USER_AGENT = "keel-visuals-sync/1.0 (+https://github.com/miladsafaei-me/keel-visuals)"


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch_bytes(url: str, *, retries: int = 4, timeout: int = 90) -> bytes:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except Exception as error:  # a flaky network is retried, then reported
            last_error = error
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"could not fetch {url}: {last_error}")


def fetch_many(jobs: list[tuple[str, Path]], *, workers: int = 16) -> None:
    """Download (url, destination) pairs in parallel, skipping files already on disk."""

    def one(job: tuple[str, Path]) -> None:
        url, destination = job
        if destination.is_file() and destination.stat().st_size:
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(fetch_bytes(url))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, jobs))


def raster_size(path: Path) -> tuple[int, int]:
    from PIL import Image

    with Image.open(path) as image:
        return image.size


def variant_record(path: Path, fmt: str) -> dict:
    """What the manifest records about one file: where, what, how big, which bytes."""
    record = {"file": path.relative_to(STATIC).as_posix(), "format": fmt, "sha256": sha256_file(path)}
    if fmt in {"png", "webp", "jpg"}:
        record["width"], record["height"] = raster_size(path)
    return record


def load_manifest() -> dict:
    if MANIFEST.is_file():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {"schema": SCHEMA_VERSION, "assets": {}}


def replace_set(set_name: str, entries: dict[str, dict]) -> None:
    """Swap one set's entries for a fresh list, keep every other set, write sorted."""
    manifest = load_manifest()
    kept = {key: entry for key, entry in manifest["assets"].items() if entry["set"] != set_name}
    for key, entry in entries.items():
        if key in kept:
            raise ValueError(f"{key} already belongs to set {kept[key]['set']}")
        if entry["set"] != set_name:
            raise ValueError(f"{key} claims set {entry['set']}, not {set_name}")
    kept.update(entries)
    output = {"schema": SCHEMA_VERSION, "assets": dict(sorted(kept.items()))}
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(output, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def remove_stale_files(directory: Path, keep: set[Path]) -> int:
    """Delete files under one set's directory that the new manifest no longer lists."""
    if not directory.exists():
        return 0
    removed = 0
    for path in sorted(directory.rglob("*"), reverse=True):
        if path.is_file() and path not in keep:
            path.unlink()
            removed += 1
        elif path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    return removed
