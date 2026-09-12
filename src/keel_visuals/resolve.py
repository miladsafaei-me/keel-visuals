"""Turn a visuals key into a Django static URL."""

from __future__ import annotations

from .manifest import require_asset


def static_url(key: str, variant: str | None = None) -> str:
    """The ``{% static %}`` URL of one variant of an asset. Raises KeyError for an unknown key."""
    from django.templatetags.static import static

    return static(require_asset(key).variant(variant).static_path)
