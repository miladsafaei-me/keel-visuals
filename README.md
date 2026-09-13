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
| `object` | `factory` | 6 objects modelled here on the stage camera: gold bar, silver bar, stack of gold bars, oil barrel, blank coin, podium with a lit rim | 24 PNG, 1024 and 512 px | three.js 0.186.0 scenes in `scripts/factory/` | Keel original |
| `map` | `natural-earth` | world land polygons, and dotted world maps at 1°, 2° and 3° | GeoJSON, SVG, JSON | Natural Earth 1:110m, v5.1.2 | Public domain |
| `frame` | `keel` | phone, tablet, browser window, desktop monitor, dark and light | 8 SVG | drawn here | Keel original |

About 37 MB of files in all, 3.4 MB of it the factory's PNGs. The upstream licence texts are in [`LICENSES/`](LICENSES/).

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
  `Variant.max_render_px()`. A factory object also says where its contact point sits
  in the file, so it can be stood on a stage's ground (see below).
- **map** — `world-land` is the polygons; `world-dots` ships each grid as an SVG
  (one user unit per cell, dots in `currentColor`) and as JSON cell coordinates,
  equirectangular, cropped at 84°N and 58°S.
- **frame** — the screen is a real hole in the SVG, and `extra.screen` gives its
  rectangle and corner radius in the SVG's own units; `extra.covers_screen` lists
  anything drawn over the screen, such as a phone's camera island.

## The object factory

Fluent's objects stop at 256 px, which caps a hero object at 128 CSS px on a 2x
capture, and no free set with transparent objects at 512 px or more could be pinned.
So the objects a hero stage needs are modelled in code: procedural three.js scenes
rendered in headless Chromium, with physically based materials, a dark studio
environment for the reflections, and one key light.

| key | variants | what it is |
|---|---|---|
| `object/factory/gold-bar` | `1024`, `512` | a cast fine-gold bar: tapered, every edge rounded, struck "FINE GOLD 999.9" |
| `object/factory/silver-bar` | `1024`, `512` | the same bar in satin-polished silver, struck "FINE SILVER 999.0", exposed so its outline holds on a near-white ground |
| `object/factory/gold-bar-stack` | `1024`, `512` | six gold bars in a pyramid of three, two and one |
| `object/factory/oil-barrel` | `1024`, `512`, `blue-1024`, `blue-512` | a 55-gallon steel drum in black enamel (or blue), with rolling hoops, chimes and bungs |
| `object/factory/coin-blank` | `1024`, `512`, `silver-1024`, `silver-512`, `gunmetal-1024`, `gunmetal-512` | a minted coin on its edge: polished rim, plain field ready for a mark, reeded edge |
| `object/factory/podium` | `1024`, `512`, and `green-`, `blue-`, `amber-` of each | a short dark cylinder with a lit rim, white by default |

**One camera.** Every object is rendered on the camera of the landing-cover stage:
focal length 1400 px, the eye 340 px above the ground of a 1600 x 900 canvas (so it
looks down at 13.65°), image plane vertical. It is lit by the stage's one light, high
and to the right. **No ground shadow is baked in**, because the stage casts its own.
Each entry's `extra` says how to stand the sprite on a stage without guessing:

- `camera` — `elevation_deg`, `focal_px`, `eye_height_px`, `distance_px`, `image_plane`;
- `light` — the stage's screen-space light vector `[-0.42, 1.0]`; `light_direction` is
  the same key light in world space;
- `ground_x_px`, `ground_y_px` — where the object's contact point (the centre of its
  footprint on the ground) sits in the 1024 px file; halve them for 512;
- `stage_width_px` — how many stage pixels the whole file spans at the camera's
  reference depth, so a scene draws it at the scale it was rendered for;
- `tones` — the colour variants beyond the default; `renderer` — the three.js,
  Chromium and GL that drew it.

**A coin with a brand's face** is a command, not an asset. This package ships no
brand, so the mark comes in at the call and the PNG goes wherever the caller says:

```bash
python3 scripts/build_factory_objects.py coin --face-svg mark.svg --out coin3d-1024.png --size 1024 [--metal auto|gold|silver|gunmetal] [--counter auto|none|#rrggbb]
python3 scripts/build_factory_objects.py coin --face-png mark.png --out coin3d-1024.png --size 1024 [--metal auto|gold|silver|gunmetal]
```

**A vector face is struck up out of the coin.** Every filled path and every stroke of
the SVG is a layer, in the order the SVG paints them (a path's fill, then its stroke),
each a little higher than the last, in its own colour as a clear-coated enamel (linear
and radial gradients included), and the whole mark is scaled so its farthest point
sits just inside the rim. Holes follow each path's `fill-rule`, `nonzero` or `evenodd`,
so a hole shows whatever the SVG paints beneath it. A stroke is extruded at its own
width, with its joins and caps.

Where nothing is painted beneath a hole, the SVG shows its page, and on a coin the page
is the field. That is right for a glyph drawn on the field, such as Sui's drop, and
wrong for a mark that is a disc of its own, such as Bitcoin's orange disc with the B
knocked out: the knockout would turn the coin's metal into the glyph. So a holed shape
that is round (its area at least 0.9 of the circle through its farthest point) and
spans the mark is the mark's **plate**, and its knockouts are floored with counter
enamel: white with `--counter auto`, or dark ink (`#141414`) when the plate is lighter
than relative luminance 0.6; the colour given; or the field again with `--counter none`.

**A raster face is set into the coin as a decal**, for a brand that publishes no
vector. The mark is trimmed to its opaque pixels and centred. A mark that is a disc (a
square box, at least 97 % of the circle filled, under 1 % of it outside) is cut just
inside its own edge and laid at the bottom of a shallow well in the field, clear-coated,
so the coin's own field and rim frame it; any other outline lies on the field with its
transparency, its farthest pixel just inside the rim. The raster is magnified to fill
the face, so pass the largest official master there is.

With `--metal auto` the rim metal follows the mark: its largest layer, or a raster's
mean colour. Warm and saturated takes gold, near black takes gunmetal, anything else
silver. The command prints the metal it chose, what it found in the face (layers,
strokes, plates and counters, or whether a raster is a disc), the camera, the light
and `ground_y_px` as JSON.

**Rebuilding it.** three.js is vendored at exactly 0.186.0 in
`scripts/factory/vendor/three-0.186.0/` (`three.module.js`, `three.core.js`,
`RoomEnvironment.js`, `SVGLoader.js`), taken from
`https://registry.npmjs.org/three/-/three-0.186.0.tgz`. The tarball's SHA-256 and every
file's are pinned in the script: `vendor` re-fetches and checks them, and a render
refuses to start if a vendored file has changed. The MIT licence is
[`LICENSES/three.txt`](LICENSES/three.txt).

Rendering needs Playwright with Chromium. WebGL2 there runs on SwiftShader, which
Chrome uses only when asked; the script passes `--enable-unsafe-swiftshader` and
`--use-angle=swiftshader`. Where the host has no Playwright, render inside a container
that has it and publish on the host, which needs only Pillow:

```bash
podman cp scripts <container>:/tmp/factory/scripts
podman exec -w /tmp/factory <container> python scripts/build_factory_objects.py render --out /tmp/factory/out
podman cp <container>:/tmp/factory/out ./factory-render
python3 scripts/build_factory_objects.py publish --from ./factory-render
```

A render is byte-for-byte repeatable on the same Chromium, SwiftShader and fonts (the
bars' hallmark is canvas text). When a scene in `factory.js` changes, bump
`FACTORY_VERSION` in the script so every file's `source_version` moves with it.

## Trademarks

`trademark: true` marks a third party's brand: Tabler's `brand-*` icons, and its
cryptocurrency marks (`currency-bitcoin`, `currency-ethereum`, `currency-solana` and
every other coin, by a named rule in `sync_tabler.py`). Fiat currency signs are not
trademarks. The file's licence covers the file and never the right to use the brand;
a consumer decides whether a trademark may appear, and should refuse it by default.

## What is not here, and why

**3dicons.** Its site serves only 500 px previews baked onto a white background, and
its public repository holds the website rather than the icons. A preview with its
background cut out is not what careful hand work would produce, so the set waits for
a transparent source that can be pinned.

**Device mockup libraries.** None was found under a licence clean for commercial
images, so the frames are drawn here.

**Branded coins.** The factory can strike any mark into a coin, but a brand's coin
belongs to the package that owns the brand, so keel-finlogo writes its own.

## Updating a set

Each script owns one set, replaces it wholesale, and is pinned on the command line:

```bash
pip install -e '.[sync]'
python3 scripts/sync_tabler.py --version 3.46.0
python3 scripts/sync_fluent3d.py --ref 1ffb34c752ecf5d402f04cfb4b392c77f57c54bc
python3 scripts/build_worldmap.py --tag v5.1.2
python3 scripts/build_frames.py
python3 scripts/build_factory_objects.py build     # where Playwright runs; otherwise render + publish, above
PYTHONPATH=src python3 -m unittest discover -s tests
```

The tests hash every file against the manifest and fail on any file the manifest
does not list, so a sync that did not finish cannot be released.
