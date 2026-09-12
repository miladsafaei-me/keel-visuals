"""keel-visuals: a shared registry of free visual assets that an image brief names by key.

Public surface::

    from keel_visuals import get_asset, require_asset, iter_assets, search

An asset is addressed as ``<kind>/<set>/<name>`` (``icon/tabler/chart-candle``,
``object/fluent/money-bag``, ``map/natural-earth/world-dots``,
``frame/keel/phone``) and ships one or more variants: a style, weight, angle or
tone. Every file lives under ``static/keel_visuals/``, and ``manifest.json``
records each one's licence, source, pixel size and SHA-256, so a renderer can
prove what it drew and a brief can never name something that is not here.
"""

from .manifest import (
    KINDS,
    Asset,
    Variant,
    get_asset,
    iter_assets,
    manifest_sha256,
    require_asset,
    search,
    verify_asset,
)

__all__ = [
    "KINDS",
    "Asset",
    "Variant",
    "get_asset",
    "iter_assets",
    "manifest_sha256",
    "require_asset",
    "search",
    "verify_asset",
]
