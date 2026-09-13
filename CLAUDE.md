# CLAUDE.md — keel-visuals

Guidance for Claude Code in **keel-visuals**, a reusable Keel **package** (not a
consumer app). Inherits the global rules in `~/.claude/CLAUDE.md` and the Keel
methodology in `~/www/keel-kit/methodology/`.

## Task tracking

Remaining and follow-up work for this project is tracked in [TODO.md](TODO.md), not in chat memory. Every pending task — priority, prerequisites/dependencies, enough context to resume cold — goes there before starting new work; remove a task from TODO.md the moment it's done.

## What this package is

A **business-blind registry of free visual assets** that an image brief names by
key: icons, rendered 3D objects, world maps and device frames. It exists so a
brief can say *which* thing to draw without ever naming a file, and so a renderer
can prove what it drew.

It is the sibling of `keel-finlogo`, not a replacement: **brand marks** (brokers,
exchanges, prop firms, coins, trading platforms) and **country flags** live in
keel-finlogo. This package holds everything that is not somebody's brand.

## The key is the only address

An asset is `<kind>/<set>/<name>` — `icon/tabler/chart-candle`,
`object/fluent/money-bag`, `map/natural-earth/world-dots`, `frame/keel/phone` —
with one or more named variants. A consumer resolves a key through
`keel_visuals.require_asset()` and never builds a path by hand. Renaming a key is
a breaking change for every plan that names it: bump the minor version and say so.

| kind | what it is | how a renderer may use it |
|---|---|---|
| `icon` | flat vector glyph painting in `currentColor` | inline the SVG so it takes the surrounding colour; through `<img>` it paints black |
| `object` | rendered 3D object with its own colour and light | raster: never wider than `Variant.max_render_px()`; a factory object is stood on the ground by `extra.ground_y_px` |
| `map` | land polygons, and precomputed dot grids (SVG + JSON) | the dot SVG paints in `currentColor` |
| `frame` | device or window frame with a real hole for its screen | place content by `extra.screen`, never by eye |

## manifest.json is the source of truth

`static/keel_visuals/manifest.json` records every asset's licence, source,
source version, pixel size and every file's SHA-256. Never write a file under
`static/keel_visuals/` without the sync script that owns its set also writing the
manifest entry; never edit the manifest by hand.

**Each script owns exactly one set and replaces it wholesale**
(`_common.replace_set`), so a re-run is idempotent and an asset removed upstream
disappears here too. Pin every source to an exact release or commit on the
command line — a sync that tracks `main` makes the registry change under a
consumer that did not re-pin.

| set | script | source pin |
|---|---|---|
| `tabler` | `scripts/sync_tabler.py --version X.Y.Z` | npm `@tabler/icons` release |
| `fluent` | `scripts/sync_fluent3d.py --ref <sha>` | `microsoft/fluentui-emoji` commit |
| `factory` | `scripts/build_factory_objects.py build`, or `render` where Playwright runs and `publish` here | three.js `THREE_VERSION` vendored in `scripts/factory/vendor/`, every file's SHA-256 pinned in the script; `FACTORY_VERSION` for the scenes |
| `natural-earth` | `scripts/build_worldmap.py --tag vX.Y.Z` | `nvkelso/natural-earth-vector` tag |
| `keel` | `scripts/build_frames.py` | drawn here |

**3dicons is deliberately absent.** Its site serves only 500 px previews baked onto a
white background, and its public repository holds the website, not the icons; the
transparent originals sit behind a Figma plugin and a browser download. A preview
with its background cut out is not what careful hand work would produce, so the
set waits until a transparent source can be pinned.

## The factory draws; it never takes a brand

`factory` objects are Keel originals rendered from `scripts/factory/factory.js` in
headless Chromium (WebGL2 on SwiftShader, which needs `--enable-unsafe-swiftshader`),
on the landing-cover stage's one camera and light, with no ground shadow. Change a
scene and you bump `FACTORY_VERSION` and re-render the whole set; a partial render
cannot be published. Read every render on a dark and a light ground, and crop at
native size, before publishing: a test cannot tell a gold bar from brass.

The `coin` command strikes a brand's SVG into a coin and writes the PNG wherever it
is told. It must never write under `static/keel_visuals/`: a branded coin belongs to
keel-finlogo, which owns the brand.

## Curation is a rule, not a hand-picked list

The heavy sets are curated so the package stays installable: Fluent ships the
object and symbol groups plus a short named list of emoji that carry trading
meaning, in the default skin tone only. Change the rule in the script's
constants and re-run; never delete files by hand.

## Trademarks

`trademark: true` marks a third party's brand (Tabler's `brand-*` icons, a social
network's 3D icon, a cryptocurrency's mark). **The file's licence covers the file,
never the right to use the brand.** This package only records the fact; whether a
trademark may appear on an image is the consumer's decision, and a consumer should
refuse it by default.

Coins are flagged by rule, never by editing the manifest: `CRYPTO_CURRENCIES` in
`sync_tabler.py` names every coin whose `currency-*` icon is a brand, and the sync
stops on a crypto-tagged currency icon the list does not name. Fiat signs are not
trademarks.

## No models, no migrations, no URL

Like keel-finlogo, this app exists only for Django's staticfiles finder. The
runtime (`manifest.py`, `catalog.py`) is stdlib only so a headless renderer can
read it with no Django in the process. Do not add a model, a view or a `urls.py`.

## Self-check before shipping

- `PYTHONPATH=src python3 -m unittest discover -s tests` — it hashes every file
  against the manifest, so it is the check that a sync finished cleanly.
- `python3 -m keel_visuals.catalog --summary` from `src/` and read the counts.
- No banner comments; English only in code, identifiers and docs.

## Release

Same as every Keel package: `~/www/keel-kit/scripts/keel-release.sh X.Y.Z` from the
repo root. `version-guard` CI enforces tag == `pyproject.toml` version and that
`src/` never changes without a bump — see
`keel-kit/methodology/versioning-and-release.md`.
