# TODO — keel-visuals

## Open

### 3dicons: find a transparent source that can be pinned
- **Priority:** low
- **Context:** 3dicons (CC0) was verified as free for commercial use, but the only
  programmatic source is the site's 500 px previews on a white background
  (`supabase.co/storage/v1/object/public/sizes/<id>/<angle>/<size>/<style>.webp`), and
  `github.com/realvjy/3dicons` holds the website, not the icon files. Cutting the white
  out of a 3D render with soft shadows does not meet the quality bar.
- **Done when:** a transparent PNG or source file per icon can be fetched at a pinned
  version, a `scripts/sync_3dicons.py` owns the `3dicons` set, and its licence text is
  in `LICENSES/`.

### Factory: the bars' hallmark depends on the rendering machine's fonts
- **Priority:** low
- **Context:** `scripts/factory/factory.js` strikes "FINE GOLD 999.9" and "FINE SILVER
  999.0" with canvas text in Montserrat, falling back to FreeSans. The signalbots-web
  container, where the set was rendered, has both; a machine without them strikes a
  different typeface, so a re-render there changes the bytes of `gold-bar`,
  `silver-bar` and `gold-bar-stack` even though nothing was meant to change. Everything
  else the factory draws depends only on the pinned three.js and Chromium.
- **Done when:** the hallmark is drawn from glyph outlines or a font file vendored
  under `scripts/factory/vendor/` with its licence in `LICENSES/`, loaded through
  `FontFace`, and `FACTORY_VERSION` is bumped with the re-render.
