#!/usr/bin/env python3
"""Keel version-discipline guard — canonical copy (vendored into each package's .github/).

It makes two release drifts impossible in CI, so the discipline never depends on a
human remembering it:

  1. A release tag whose version does not match ``pyproject.toml``. This is the exact
     drift that let keel-web / keel-cms / keel-content sit at pyproject ``0.1.0`` under a
     ``v0.1.1`` git tag — the installed wheel then misreports its own version.
  2. A change to package source under ``src/`` that ships without a version bump.

The mode is chosen from ``GITHUB_REF``:

  * tag push   (``refs/tags/vX.Y.Z``) -> assert ``pyproject`` version == ``X.Y.Z``.
  * branch push                       -> if any tracked file under ``src/`` differs from
                                          the highest existing tag, assert version > that
                                          tag (a bump is mandatory before the next release).

Exit non-zero on any violation so the workflow fails the run. Pure stdlib (``tomllib`` is
3.11+, which every GitHub ``ubuntu-latest`` runner ships); no third-party deps.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

# The guard lives at <repo>/.github/keel_version_guard.py, so the repo root is two up.
ROOT = Path(__file__).resolve().parents[1]


def pyproject_version() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    return data["project"]["version"]


def parse(v: str) -> tuple[int, ...]:
    """A drift-proof numeric key (``0.1.10`` sorts above ``0.1.2``)."""
    return tuple(int(x) for x in re.findall(r"\d+", v))


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()


def latest_tag() -> str | None:
    tags = [t for t in git("tag", "--list", "v*").splitlines() if re.fullmatch(r"v\d+(?:\.\d+)*", t)]
    return max(tags, key=parse) if tags else None


def fail(msg: str) -> None:
    print(f"::error::version-guard: {msg}")
    sys.exit(1)


def main() -> None:
    ref = os.environ.get("GITHUB_REF", "")
    version = pyproject_version()

    m = re.fullmatch(r"refs/tags/(v\d+(?:\.\d+)*)", ref)
    if m:
        tag = m.group(1)
        if parse(version) != parse(tag):
            fail(
                f"tag {tag} but pyproject version is {version} — a release tag must match "
                f"pyproject [project].version. Fix the version or retag."
            )
        print(f"OK: tag {tag} matches pyproject version {version}")
        return

    tag = latest_tag()
    if not tag:
        print("OK: no prior tag to compare against")
        return
    changed = git("diff", "--name-only", f"{tag}..HEAD", "--", "src")
    if changed and parse(version) <= parse(tag):
        fail(
            f"src/ changed since {tag} but pyproject version is still {version} "
            f"(<= {tag[1:]}). Bump [project].version before the next release.\n"
            f"Changed files:\n{changed}"
        )
    print(f"OK: pyproject {version} vs latest tag {tag}")


if __name__ == "__main__":
    main()
