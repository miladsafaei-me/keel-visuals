# keel-visuals

A shared, business-blind registry of **free visual assets that an image brief names
by key**: icons, rendered 3D objects, world maps and device frames. Every file ships
as a Django static asset and is indexed by `manifest.json`, which records its
licence, source, pinned source version, pixel size and SHA-256.

Brand marks (brokers, exchanges, prop firms, coins, trading platforms) and country
flags are **not** here; they live in the sibling package `keel-finlogo`.

## What it ships

| kind | set | assets | files | source | licence |
|---|---|---|---|---|---|
| `icon` | `tabler` | 5,130 icons (outline, and filled where it exists) | 6,184 SVG | Tabler Icons 3.46.0 | MIT |
| `object` | `fluent` | 809 rendered 3D objects, 256 px | 809 PNG | Microsoft Fluent Emoji, pinned commit | MIT |
| `map` | `natural-earth` | world land polygons, and dotted world maps at 1°, 2° and 3° | GeoJSON, SVG, JSON | Natural Earth 1:110m, v5.1.2 | Public domain |
| `frame` | `keel` | phone, tablet, browser window, desktop monitor, dark and light | 8 SVG | drawn here | Keel original |

About 57 MB in all. The upstream licence texts are in [`LICENSES/`](LICENSES/).

Fluent is curated by rule, not by hand: every emoji in the Objects, Symbols,
Travel & Places and Activities groups, plus a short list from the other groups that
carries trading meaning (the ox and the bear, the robot, the whale, the handshake),
in the default skin tone only.

## Addressing an asset

A key is `<kind>/<set>/<name>`, and an asset has one or more named variants.

```python
from keel_visuals import require_asset, search

coin = require_asset("object/fluent/coin").variant()     # the default variant
coin.path            # the file on disk, for a headless renderer
coin.static_path     # "keel_visuals/objects/fluent/coin/3d.png", for {% static %}
coin.max_render_px() # 128: widest CSS size on a 2x capture before it is upscaled

search("chart candle", kind="icon")                     # best matches first
require_asset("icon/tabler/chart-candles")              # KeyError: ... nearest: icon/tabler/chart-candle
```

From a shell, the way a brief author looks keys up:

```bash
cd src
python3 -m keel_visuals.catalog --summary
python3 -m keel_visuals.catalog --kind object --search money
python3 -m keel_visuals.catalog --kind icon --search "shield check" --no-trademarks
```

In Django, add `"keel_visuals"` to `INSTALLED_APPS`; `collectstatic` does the rest,
and `keel_visuals.resolve.static_url(key, variant)` returns the static URL. The
runtime is stdlib only, so the manifest and catalog work with no Django at all.

## What each kind promises

- **icon** — an SVG painting in `currentColor`. Inline it so it takes the surrounding
  colour; drawn through `<img>` it paints black.
- **object** — a raster with its own colour and light. Never draw it wider than
  `Variant.max_render_px()`.
- **map** — `world-land` is the polygons; `world-dots` ships each grid as an SVG
  (one user unit per cell, dots in `currentColor`) and as JSON cell coordinates,
  equirectangular, cropped at 84°N and 58°S.
- **frame** — the screen is a real hole in the SVG, and `extra.screen` gives its
  rectangle and corner radius in the SVG's own units; `extra.covers_screen` lists
  anything drawn over the screen, such as a phone's camera island.

## Trademarks

`trademark: true` marks a third party's brand, such as Tabler's `brand-*` icons. The
file's licence covers the file and never the right to use the brand; a consumer
decides whether a trademark may appear, and should refuse it by default.

## What is not here, and why

**3dicons.** Its site serves only 500 px previews baked onto a white background, and
its public repository holds the website rather than the icons. A preview with its
background cut out is not what careful hand work would produce, so the set waits for
a transparent source that can be pinned.

**Device mockup libraries.** None was found under a licence clean for commercial
images, so the frames are drawn here.

## Updating a set

Each script owns one set, replaces it wholesale, and is pinned on the command line:

```bash
pip install -e '.[sync]'
python3 scripts/sync_tabler.py --version 3.46.0
python3 scripts/sync_fluent3d.py --ref 1ffb34c752ecf5d402f04cfb4b392c77f57c54bc
python3 scripts/build_worldmap.py --tag v5.1.2
python3 scripts/build_frames.py
PYTHONPATH=src python3 -m unittest discover -s tests
```

The tests hash every file against the manifest and fail on any file the manifest
does not list, so a sync that did not finish cannot be released.
