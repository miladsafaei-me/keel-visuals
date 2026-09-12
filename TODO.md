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

### Larger 3D objects than 256 px
- **Priority:** medium
- **Context:** Fluent's 3D files are 256 px, so an object may be drawn at most 128 CSS px
  on a 2x capture. A hero object on a cover wants 200–300 CSS px. No verified free set
  with transparent files at 512 px or more was found in the first pass.
- **Done when:** a set with objects at ≥ 512 px is vendored with its licence verified,
  or the decision not to is recorded here.
