"""The manifest is the contract: every entry is complete, and every file holds the bytes it claims.

Run from the repository root:

    PYTHONPATH=src python3 -m unittest discover -s tests
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import struct
import sys
import unittest
from pathlib import Path

from keel_visuals import manifest

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {"kind", "set", "name", "title", "tags", "license", "source", "source_version", "trademark", "default_variant", "variants"}
LICENCE_FILES = {"tabler": "tabler-icons.txt", "fluent": "fluentui-emoji.txt", "natural-earth": "natural-earth.md", "factory": "three.txt"}
FACTORY_OBJECTS = {"gold-bar", "silver-bar", "gold-bar-stack", "oil-barrel", "coin-blank", "podium"}


def load_factory_script():
    """The factory build script, imported by path: scripts/ is tooling, not a package."""
    scripts = ROOT / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        spec = importlib.util.spec_from_file_location("build_factory_objects", scripts / "build_factory_objects.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(scripts))


def png_header(path: Path) -> tuple[int, int, int]:
    """Width, height and colour type straight from the IHDR chunk, so the test needs no imaging library."""
    with path.open("rb") as handle:
        head = handle.read(26)
    width, height = struct.unpack(">II", head[16:24])
    return width, height, head[25]


class ManifestContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = manifest.load_manifest()
        cls.assets = list(manifest.iter_assets())

    def test_the_registry_is_not_empty(self):
        self.assertEqual(self.data["schema"], manifest.SCHEMA_VERSION)
        self.assertGreater(len(self.assets), 1000)

    def test_every_entry_is_complete_and_keyed_by_its_own_fields(self):
        for key, entry in self.data["assets"].items():
            with self.subTest(key=key):
                self.assertFalse(REQUIRED - set(entry), f"missing {sorted(REQUIRED - set(entry))}")
                self.assertRegex(key, manifest.KEY_PATTERN)
                self.assertEqual(key, f"{entry['kind']}/{entry['set']}/{entry['name']}")
                self.assertIn(entry["kind"], manifest.KINDS)
                self.assertIn(entry["default_variant"], entry["variants"])

    def test_every_file_exists_and_matches_its_hash(self):
        problems = [problem for asset in self.assets for problem in manifest.verify_asset(asset)]
        self.assertEqual(problems[:10], [], f"{len(problems)} files disagree with the manifest")

    def test_no_file_on_disk_is_missing_from_the_manifest(self):
        listed = {variant.path for asset in self.assets for variant in asset.variants.values()}
        on_disk = {path for path in manifest.STATIC_ROOT.rglob("*") if path.is_file() and path != manifest.MANIFEST_PATH}
        self.assertEqual(sorted(str(path) for path in on_disk - listed)[:10], [])

    def test_every_vendored_set_ships_its_licence(self):
        sets = {asset.set for asset in self.assets}
        for set_name, filename in LICENCE_FILES.items():
            if set_name in sets:
                with self.subTest(set=set_name):
                    self.assertTrue((ROOT / "LICENSES" / filename).is_file())

    def test_brand_icons_are_marked_as_trademarks(self):
        brands = [asset for asset in manifest.iter_assets("icon", "tabler") if asset.name.startswith("brand-")]
        self.assertTrue(brands)
        self.assertTrue(all(asset.trademark for asset in brands))
        self.assertFalse(manifest.require_asset("icon/tabler/chart-candle").trademark)

    def test_cryptocurrency_marks_are_trademarks_and_fiat_signs_are_not(self):
        for coin in ("bitcoin", "ethereum", "solana", "xrp", "ripple", "dogecoin", "litecoin", "monero", "zcash", "tether"):
            with self.subTest(coin=coin):
                self.assertTrue(manifest.require_asset(f"icon/tabler/currency-{coin}").trademark)
        for fiat in ("dollar", "euro", "pound", "yen", "rupee", "lira", "bahraini"):
            with self.subTest(fiat=fiat):
                self.assertFalse(manifest.require_asset(f"icon/tabler/currency-{fiat}").trademark)

    def test_every_crypto_tagged_currency_icon_is_a_trademark(self):
        """The sync refuses an unflagged coin; this proves the shipped manifest agrees with that rule."""
        for asset in manifest.iter_assets("icon", "tabler"):
            if asset.name.startswith("currency-") and {"crypto", "cryptocurrency", "blockchain"} & set(asset.tags):
                with self.subTest(key=asset.key):
                    self.assertTrue(asset.trademark)

    def test_the_factory_ships_every_object_at_1024_and_512_as_transparent_png(self):
        objects = {asset.name: asset for asset in manifest.iter_assets("object", "factory")}
        self.assertEqual(set(objects), FACTORY_OBJECTS)
        for asset in objects.values():
            with self.subTest(key=asset.key):
                self.assertFalse(asset.trademark)
                self.assertEqual(asset.default_variant, "1024")
                tones = [""] + asset.extra["tones"]
                expected = {f"{tone}-{size}" if tone else str(size) for tone in tones for size in (1024, 512)}
                self.assertEqual(set(asset.variants), expected)
                for name, variant in asset.variants.items():
                    size = int(name.rsplit("-", 1)[-1])
                    self.assertEqual((variant.width, variant.height), (size, size))
                    self.assertEqual(png_header(variant.path), (size, size, 6), f"{name} is not RGBA")

    def test_factory_objects_record_the_stage_camera_light_and_contact_point(self):
        elevation = math.degrees(math.atan((900 - 560) / 1400))
        for asset in manifest.iter_assets("object", "factory"):
            with self.subTest(key=asset.key):
                camera = asset.extra["camera"]
                self.assertAlmostEqual(camera["elevation_deg"], elevation, places=1)
                self.assertEqual(camera["focal_px"], 1400)
                self.assertEqual(asset.extra["light"], [-0.42, 1.0])
                self.assertEqual(asset.extra["shadow"], "none")
                self.assertTrue(0 < asset.extra["ground_y_px"] <= 1024)
                self.assertTrue(0 < asset.extra["ground_x_px"] < 1024)
                self.assertGreater(asset.extra["stage_width_px"], 0)

    def test_the_factory_renders_with_the_pinned_three_js(self):
        script = load_factory_script()
        for name, (_member, expected) in script.THREE_FILES.items():
            with self.subTest(file=name):
                self.assertEqual(hashlib.sha256((script.VENDOR / name).read_bytes()).hexdigest(), expected)
        for asset in manifest.iter_assets("object", "factory"):
            self.assertEqual(asset.extra["renderer"]["three"], script.THREE_VERSION)
            self.assertEqual(asset.source_version, f"factory-{script.FACTORY_VERSION}+three-{script.THREE_VERSION}")

    def test_a_raster_may_be_drawn_at_half_its_pixels_and_a_vector_at_any_size(self):
        coin = manifest.require_asset("object/fluent/coin").variant()
        self.assertEqual(coin.max_render_px(), coin.width // 2)
        self.assertIsNone(manifest.require_asset("icon/tabler/chart-candle").variant().max_render_px())

    def test_search_ranks_a_name_above_a_tag(self):
        found = manifest.search("candle", kind="icon")
        self.assertTrue(found)
        self.assertIn("candle", found[0].name)

    def test_an_unknown_key_names_its_nearest_neighbours(self):
        with self.assertRaisesRegex(KeyError, "nearest: .*chart-candle"):
            manifest.require_asset("icon/tabler/chart-candles")
        with self.assertRaisesRegex(KeyError, "is not a visuals key"):
            manifest.require_asset("chart-candle")

    def test_frames_declare_a_screen_inside_their_viewbox(self):
        for asset in manifest.iter_assets("frame"):
            with self.subTest(key=asset.key):
                screen, view = asset.extra["screen"], asset.extra["viewbox"]
                self.assertGreater(screen["width"], 0)
                self.assertLessEqual(screen["x"] + screen["width"], view["width"])
                self.assertLessEqual(screen["y"] + screen["height"], view["height"])

    def test_dot_grids_stay_inside_their_own_grid_and_cover_real_land(self):
        world = manifest.require_asset("map/natural-earth/world-dots")
        for name, variant in world.variants.items():
            if variant.format != "json":
                continue
            with self.subTest(variant=name):
                grid = json.loads(variant.path.read_text(encoding="utf-8"))
                self.assertTrue(all(0 <= c < grid["columns"] and 0 <= r < grid["rows"] for c, r in grid["dots"]))
                share = len(grid["dots"]) / (grid["columns"] * grid["rows"])
                self.assertTrue(0.2 < share < 0.45, f"land share {share:.2f} is not Earth's")


if __name__ == "__main__":
    unittest.main()
