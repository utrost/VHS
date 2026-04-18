import os
import sys
import unittest
import xml.etree.ElementTree as ET
import shutil
import json

# Add script dir to path
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(script_dir)

from assembler import GlyphLibrary, Typesetter, Renderer

class TestAssembler(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create a mock glyphs directory for testing
        cls.test_glyphs_dir = os.path.join(script_dir, "test_glyphs_mock")
        os.makedirs(cls.test_glyphs_dir, exist_ok=True)

        # Create a mock 'a.json'
        cls.a_json_path = os.path.join(cls.test_glyphs_dir, "a.json")
        with open(cls.a_json_path, 'w') as f:
            f.write('''{
                "char": "a",
                "variants": [
                    { "strokes": [[{"x": 0, "y": 0}, {"x": 10, "y": 10}]] },
                    { "strokes": [[{"x": 0, "y": 0}, {"x": 20, "y": 20}]] }
                ]
            }''')

        # Create a mock 'period.json' (for dot)
        cls.dot_path = os.path.join(cls.test_glyphs_dir, "period.json")
        with open(cls.dot_path, 'w') as f:
            f.write('''{
                "char": ".",
                "variants": [ { "strokes": [[{"x": 5, "y": 5}, {"x": 6, "y": 6}]] } ]
            }''')

        # Create a mock 'tt.json' (ligature)
        cls.tt_path = os.path.join(cls.test_glyphs_dir, "tt.json")
        with open(cls.tt_path, 'w') as f:
            f.write('''{
                "char": "tt",
                "variants": [ { "strokes": [[{"x": 0, "y": 0}, {"x": 30, "y": 0}]] } ]
            }''')

        # Create a mock glyph with bezier_curves and normalized_strokes — 'b.json'
        cls.b_json_path = os.path.join(cls.test_glyphs_dir, "b.json")
        with open(cls.b_json_path, 'w') as f:
            json.dump({
                "char": "b",
                "metadata": {"baseline_y": 100, "x_height": 60, "canvas_size": [100, 140]},
                "variants": [{
                    "strokes": [
                        [{"x": 10, "y": 20, "p": 0.4}, {"x": 30, "y": 40, "p": 0.6},
                         {"x": 50, "y": 60, "p": 0.8}, {"x": 70, "y": 80, "p": 0.5}]
                    ],
                    "bezier_curves": [
                        [
                            {"p0": {"x": 10, "y": 20}, "p1": {"x": 15, "y": 25},
                             "p2": {"x": 25, "y": 35}, "p3": {"x": 30, "y": 40}},
                            {"p0": {"x": 30, "y": 40}, "p1": {"x": 40, "y": 50},
                             "p2": {"x": 55, "y": 65}, "p3": {"x": 70, "y": 80}}
                        ]
                    ],
                    "normalized_strokes": [
                        [{"x": 5, "y": 15, "p": 0.5}, {"x": 25, "y": 35, "p": 0.6},
                         {"x": 45, "y": 55, "p": 0.7}, {"x": 65, "y": 75, "p": 0.5}]
                    ]
                }]
            }, f)

        # Create a mock glyph with only normalized_strokes (no bezier) — 'c.json'
        cls.c_json_path = os.path.join(cls.test_glyphs_dir, "c.json")
        with open(cls.c_json_path, 'w') as f:
            json.dump({
                "char": "c",
                "metadata": {"baseline_y": 100, "x_height": 60, "canvas_size": [100, 140]},
                "variants": [{
                    "strokes": [
                        [{"x": 10, "y": 30, "p": 0.5}, {"x": 40, "y": 70, "p": 0.5}]
                    ],
                    "normalized_strokes": [
                        [{"x": 8, "y": 28, "p": 0.5}, {"x": 38, "y": 68, "p": 0.5}]
                    ]
                }]
            }, f)

        # Create a mock local kerning file
        cls.kerning_path = os.path.join(cls.test_glyphs_dir, "kerning.json")
        with open(cls.kerning_path, 'w') as f:
            f.write('''{
                "space_width": 25.0,
                "tracking_buffer": 2.0,
                "exceptions": { ".": { "min_width": 15.0 } }
            }''')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_glyphs_dir)

    def setUp(self):
        self.lib = GlyphLibrary(self.test_glyphs_dir)
        self.typesetter = Typesetter(self.lib, kerning_config_path=self.kerning_path)

    def test_library_loading(self):
        self.assertIsNotNone(self.lib.get_glyph("a"))
        self.assertIsNotNone(self.lib.get_glyph("."))
        self.assertIsNotNone(self.lib.get_glyph("tt"))
        self.assertEqual(self.lib.max_key_length, 2)

    def test_typesetting_metrics(self):
        # Test basic typesetting
        shapes = self.typesetter.typeset_text("a")
        self.assertEqual(len(shapes), 1)
        # 'a' variants have points, so they should be rendered
        self.assertTrue(len(shapes[0]) > 0)

    def test_kerning_exception(self):
        # Dot has min_width 15.0, contents width 1.0 (5 to 6)
        # Tracking buffer is 2.0
        # Total advance should be 15.0 + 2.0 = 17.0

        # We can't inspect cursors directly in the current private API,
        # but we can inspect the shape positions.

        shapes = self.typesetter.typeset_text("..")
        self.assertEqual(len(shapes), 2)

        # Helper to get start x of a shape
        def get_start_x(shape):
            return shape[0][0]['x']

        x1 = get_start_x(shapes[0])
        x2 = get_start_x(shapes[1])

        distance = x2 - x1
        self.assertAlmostEqual(distance, 17.0, delta=0.5)

    def test_ligature_recognition(self):
         # "a.tt" should parse as 'a', '.', 'tt' (3 glyphs)
         # If greedy matching fails, it might try 't', 't' (making 4 glyphs, but 't' doesn't exist so it skips or spaces)

         # Note: 't' is not defined in mock, so lookup fails for single 't'.
         # This effectively forces it to find 'tt' or nothing.

         shapes = self.typesetter.typeset_text("a.tt")
         self.assertEqual(len(shapes), 3) # a, ., tt

         # Check that the 3rd shape has width ~30 (mock tt width)
         # Using metrics from mock: min_x=0, max_x=30 -> width=30

         # We can't easily check internal metrics here, but we check count.

    def test_renderer_svg_generation(self):
        output_file = os.path.join(script_dir, "test_output_unittest.svg")
        shapes = self.typesetter.typeset_text("a.")
        renderer = Renderer()
        renderer.generate_svg(shapes, output_file)

        self.assertTrue(os.path.exists(output_file))
        filesize = os.path.getsize(output_file)
        self.assertTrue(filesize > 0)

        # Clean up
        os.remove(output_file)

    def test_paper_size_dimensions(self):
        """SVG should have fixed A4 portrait dimensions when --paper-size is used."""
        output_file = os.path.join(script_dir, "test_paper_a4.svg")
        shapes = self.typesetter.typeset_text("a.")
        renderer = Renderer()
        renderer.generate_svg(shapes, output_file, page_width_mm=210.0, page_height_mm=297.0)

        tree = ET.parse(output_file)
        root = tree.getroot()
        ns = {'svg': 'http://www.w3.org/2000/svg'}
        self.assertEqual(root.get("width"), "210.0mm")
        self.assertEqual(root.get("height"), "297.0mm")
        os.remove(output_file)

    def test_paper_size_landscape(self):
        """Landscape should swap width and height."""
        output_file = os.path.join(script_dir, "test_paper_landscape.svg")
        shapes = self.typesetter.typeset_text("a")
        renderer = Renderer()
        # A4 landscape: 297 x 210
        renderer.generate_svg(shapes, output_file, page_width_mm=297.0, page_height_mm=210.0)

        tree = ET.parse(output_file)
        root = tree.getroot()
        self.assertEqual(root.get("width"), "297.0mm")
        self.assertEqual(root.get("height"), "210.0mm")
        os.remove(output_file)

    def test_line_spacing_multiplier(self):
        """line_spacing=2.0 should double the vertical gap between lines."""
        shapes_1x = self.typesetter.typeset_text("a\na", line_spacing=1.0)
        shapes_2x = self.typesetter.typeset_text("a\na", line_spacing=2.0)

        # First shape at y=0 baseline, second shape at y=line_height * spacing
        y1_1x = shapes_1x[1][0][0]['y']
        y0_1x = shapes_1x[0][0][0]['y']
        gap_1x = y1_1x - y0_1x

        y1_2x = shapes_2x[1][0][0]['y']
        y0_2x = shapes_2x[0][0][0]['y']
        gap_2x = y1_2x - y0_2x

        self.assertAlmostEqual(gap_2x, gap_1x * 2.0, delta=0.1)

    def test_margin_offset(self):
        """Fixed page mode should add translate(margin, margin) to the content group."""
        output_file = os.path.join(script_dir, "test_margin.svg")
        shapes = self.typesetter.typeset_text("a")
        renderer = Renderer()
        renderer.generate_svg(shapes, output_file, page_width_mm=210.0, page_height_mm=297.0, margin_mm=25.0)

        tree = ET.parse(output_file)
        root = tree.getroot()
        ns = "http://www.w3.org/2000/svg"
        g = root.find(f"{{{ns}}}g")
        self.assertIsNotNone(g)
        transform = g.get("transform")
        self.assertTrue(transform.startswith("translate(25.00,25.00)"),
                        f"Transform should start with margin translate, got: {transform}")
        os.remove(output_file)

    def test_zone_aware_kerning_different_zones(self):
        """Glyphs in different zones should kern tighter with higher aggressiveness."""
        typesetter = Typesetter(self.lib)
        # Shape A: upper zone only (y 20–50, well above baseline_y=100)
        shapes_upper = [[{'x': 0, 'y': 20, 'p': 0.5}, {'x': 30, 'y': 20, 'p': 0.5},
                         {'x': 15, 'y': 50, 'p': 0.5}]]
        # Shape B: ground zone only (y 70–95, between x_height=60 and baseline=100)
        shapes_ground = [[{'x': 25, 'y': 70, 'p': 0.5}, {'x': 50, 'y': 95, 'p': 0.5}]]

        # Without zone awareness
        dist_no_zone = typesetter.calculate_optical_kerning(shapes_upper, shapes_ground)
        # With zone awareness and high aggressiveness
        dist_zone = typesetter.calculate_optical_kerning(
            shapes_upper, shapes_ground,
            baseline_y=100.0, x_height_y=60.0,
            kern_aggressiveness=0.9)
        # Zone-aware should return same or tighter (smaller) distance
        self.assertLessEqual(dist_zone, dist_no_zone)

    def test_zone_aware_kerning_same_zone(self):
        """Glyphs sharing the same zone should kern the same regardless of aggressiveness."""
        typesetter = Typesetter(self.lib)
        # Both in ground zone (y 70–95)
        shapes_a = [[{'x': 0, 'y': 70, 'p': 0.5}, {'x': 20, 'y': 95, 'p': 0.5}]]
        shapes_b = [[{'x': 25, 'y': 70, 'p': 0.5}, {'x': 45, 'y': 95, 'p': 0.5}]]

        dist_low = typesetter.calculate_optical_kerning(
            shapes_a, shapes_b,
            baseline_y=100.0, x_height_y=60.0,
            kern_aggressiveness=0.0)
        dist_high = typesetter.calculate_optical_kerning(
            shapes_a, shapes_b,
            baseline_y=100.0, x_height_y=60.0,
            kern_aggressiveness=1.0)
        # Same zone means aggressiveness has no effect
        self.assertAlmostEqual(dist_low, dist_high, places=2)

    # ── Bezier curve tests ──

    def test_bezier_svg_path_generation(self):
        """When bezier_curves are present, SVG should contain C (cubic Bezier) commands."""
        output_file = os.path.join(script_dir, "test_bezier_output.svg")
        typesetter = Typesetter(self.lib, kerning_config_path=self.kerning_path,
                                use_bezier=True, use_normalized=True)
        shapes = typesetter.typeset_text("b")
        bezier_data = typesetter._compiled_beziers

        renderer = Renderer(use_bezier=True)
        renderer.generate_svg(shapes, output_file, bezier_data=bezier_data)

        tree = ET.parse(output_file)
        root = tree.getroot()
        ns = "http://www.w3.org/2000/svg"
        paths = root.findall(f".//{{{ns}}}path")
        self.assertGreater(len(paths), 0, "Should have at least one path")

        # Check that at least one path contains C commands (bezier)
        has_bezier = any("C" in p.get("d", "") for p in paths)
        self.assertTrue(has_bezier, "SVG should contain cubic Bezier C commands")

        # Verify it does NOT contain L commands for the bezier stroke
        bezier_paths = [p for p in paths if "C" in p.get("d", "")]
        for p in bezier_paths:
            d = p.get("d", "")
            self.assertNotIn(" L ", d, "Bezier path should not contain L commands")

        os.remove(output_file)

    def test_bezier_data_populated(self):
        """Typesetter should populate _compiled_beziers when bezier_curves present."""
        typesetter = Typesetter(self.lib, kerning_config_path=self.kerning_path,
                                use_bezier=True)
        shapes = typesetter.typeset_text("b")
        bezier_data = typesetter._compiled_beziers

        self.assertEqual(len(bezier_data), len(shapes))
        # 'b' has bezier_curves, so its entry should not be None
        self.assertIsNotNone(bezier_data[0])
        self.assertEqual(len(bezier_data[0]), 1)  # one stroke
        self.assertEqual(len(bezier_data[0][0]), 2)  # two bezier segments

    def test_bezier_pressure_interpolation(self):
        """Bezier segments should carry interpolated pressure from raw stroke points."""
        typesetter = Typesetter(self.lib, kerning_config_path=self.kerning_path,
                                use_bezier=True)
        shapes = typesetter.typeset_text("b")
        bezier_data = typesetter._compiled_beziers

        for seg in bezier_data[0][0]:
            self.assertIn('pressure_start', seg)
            self.assertIn('pressure_end', seg)
            # Pressure should be in reasonable range
            self.assertGreaterEqual(seg['pressure_start'], 0.0)
            self.assertLessEqual(seg['pressure_start'], 1.0)
            self.assertGreaterEqual(seg['pressure_end'], 0.0)
            self.assertLessEqual(seg['pressure_end'], 1.0)

    def test_normalized_strokes_used(self):
        """When normalized_strokes are present and enabled, they should be used for layout."""
        # With normalization enabled (default)
        ts_norm = Typesetter(self.lib, kerning_config_path=self.kerning_path,
                             use_normalized=True, use_bezier=False)
        shapes_norm = ts_norm.typeset_text("c")

        # With normalization disabled
        ts_raw = Typesetter(self.lib, kerning_config_path=self.kerning_path,
                            use_normalized=False, use_bezier=False)
        shapes_raw = ts_raw.typeset_text("c")

        # Both should produce shapes
        self.assertEqual(len(shapes_norm), 1)
        self.assertEqual(len(shapes_raw), 1)

        # The coordinates should differ because normalized_strokes have different values
        norm_x = shapes_norm[0][0][0]['x']
        raw_x = shapes_raw[0][0][0]['x']
        # 'c' raw starts at x=10, normalized starts at x=8
        # After min_x subtraction, both start at 0, but widths differ
        # so the actual positions may differ due to metrics
        # At minimum, the points themselves should be different
        norm_pts = [(p['x'], p['y']) for stroke in shapes_norm[0] for p in stroke]
        raw_pts = [(p['x'], p['y']) for stroke in shapes_raw[0] for p in stroke]
        self.assertNotEqual(norm_pts, raw_pts,
                            "Normalized and raw strokes should produce different coordinates")

    def test_fallback_chain_bezier_to_raw(self):
        """Glyph without bezier_curves should fall back to raw strokes + smoothing."""
        output_file = os.path.join(script_dir, "test_fallback.svg")
        typesetter = Typesetter(self.lib, kerning_config_path=self.kerning_path,
                                use_bezier=True, use_normalized=True)
        shapes = typesetter.typeset_text("a")
        bezier_data = typesetter._compiled_beziers

        # 'a' has no bezier_curves, so bezier entry should be None
        self.assertIsNone(bezier_data[0])

        renderer = Renderer(smoothing=True, use_bezier=True)
        renderer.generate_svg(shapes, output_file, bezier_data=bezier_data)

        tree = ET.parse(output_file)
        root = tree.getroot()
        ns = "http://www.w3.org/2000/svg"
        paths = root.findall(f".//{{{ns}}}path")
        self.assertGreater(len(paths), 0)

        # Should contain L commands (Catmull-Rom smoothed, not bezier)
        has_L = any("L" in p.get("d", "") for p in paths)
        self.assertTrue(has_L, "Fallback path should use L commands (smoothed polyline)")

        # Should NOT contain C commands
        has_C = any("C" in p.get("d", "") for p in paths)
        self.assertFalse(has_C, "Fallback path should not contain C commands")

        os.remove(output_file)

    def test_fallback_chain_normalized_to_raw(self):
        """Glyph without normalized_strokes should use raw strokes."""
        ts = Typesetter(self.lib, kerning_config_path=self.kerning_path,
                        use_normalized=True, use_bezier=False)
        shapes = ts.typeset_text("a")  # 'a' has no normalized_strokes
        # Should still produce valid shapes from raw strokes
        self.assertEqual(len(shapes), 1)
        self.assertGreater(len(shapes[0][0]), 0)

    def test_no_bezier_flag_ignores_bezier(self):
        """When use_bezier=False, bezier_curves should be ignored even if present."""
        output_file = os.path.join(script_dir, "test_no_bezier.svg")
        typesetter = Typesetter(self.lib, kerning_config_path=self.kerning_path,
                                use_bezier=False, use_normalized=True)
        shapes = typesetter.typeset_text("b")
        bezier_data = typesetter._compiled_beziers

        # bezier data should be None because use_bezier=False
        self.assertIsNone(bezier_data[0])

        renderer = Renderer(smoothing=True, use_bezier=False)
        renderer.generate_svg(shapes, output_file, bezier_data=bezier_data)

        tree = ET.parse(output_file)
        root = tree.getroot()
        ns = "http://www.w3.org/2000/svg"
        paths = root.findall(f".//{{{ns}}}path")

        # Should NOT contain C commands since bezier is disabled
        has_C = any("C" in p.get("d", "") for p in paths)
        self.assertFalse(has_C, "With --no-bezier, SVG should not contain C commands")

        os.remove(output_file)

    def test_no_normalize_flag_uses_raw(self):
        """When use_normalized=False, raw strokes should be used even if normalized exist."""
        ts_raw = Typesetter(self.lib, kerning_config_path=self.kerning_path,
                            use_normalized=False, use_bezier=False)
        shapes_raw = ts_raw.typeset_text("c")

        # 'c' raw stroke: x from 10 to 40. After normalization (min_x=10): 0 to 30
        pts = [(p['x'], p['y']) for stroke in shapes_raw[0] for p in stroke]
        # First point x should be 0 (shifted from 10 by min_x=10)
        self.assertAlmostEqual(pts[0][0], 0.0, delta=0.01)

    def test_backward_compatibility_no_new_fields(self):
        """Glyphs without bezier_curves or normalized_strokes should work exactly as before."""
        typesetter = Typesetter(self.lib, kerning_config_path=self.kerning_path,
                                use_bezier=True, use_normalized=True)
        shapes = typesetter.typeset_text("a.")
        bezier_data = typesetter._compiled_beziers

        # Both 'a' and '.' lack bezier/normalized data
        for entry in bezier_data:
            self.assertIsNone(entry)

        # Rendering should work as before
        output_file = os.path.join(script_dir, "test_compat.svg")
        renderer = Renderer(use_bezier=True)
        renderer.generate_svg(shapes, output_file, bezier_data=bezier_data)
        self.assertTrue(os.path.exists(output_file))
        os.remove(output_file)

    def test_bezier_and_non_bezier_mixed(self):
        """Mixing glyphs with and without bezier should render both correctly."""
        output_file = os.path.join(script_dir, "test_mixed.svg")
        typesetter = Typesetter(self.lib, kerning_config_path=self.kerning_path,
                                use_bezier=True, use_normalized=True)
        shapes = typesetter.typeset_text("ab")
        bezier_data = typesetter._compiled_beziers

        # 'a' has no bezier, 'b' has bezier
        self.assertIsNone(bezier_data[0])
        self.assertIsNotNone(bezier_data[1])

        renderer = Renderer(smoothing=True, use_bezier=True)
        renderer.generate_svg(shapes, output_file, bezier_data=bezier_data)

        tree = ET.parse(output_file)
        root = tree.getroot()
        ns = "http://www.w3.org/2000/svg"
        paths = root.findall(f".//{{{ns}}}path")

        # Should have both L commands (from 'a') and C commands (from 'b')
        all_d = " ".join(p.get("d", "") for p in paths)
        self.assertIn("L", all_d, "Mixed render should have L commands from non-bezier glyph")
        self.assertIn("C", all_d, "Mixed render should have C commands from bezier glyph")

        os.remove(output_file)

    def test_compiled_beziers_length_matches_shapes(self):
        """_compiled_beziers should always have the same length as compiled_shapes."""
        typesetter = Typesetter(self.lib, kerning_config_path=self.kerning_path,
                                use_bezier=True, use_normalized=True)
        shapes = typesetter.typeset_text("a.b")
        self.assertEqual(len(typesetter._compiled_beziers), len(shapes))

    def test_nearest_pressure(self):
        """_nearest_pressure should return pressure of closest raw point."""
        pts = [
            {'x': 0, 'y': 0, 'p': 0.3},
            {'x': 10, 'y': 10, 'p': 0.7},
            {'x': 20, 'y': 20, 'p': 0.9},
        ]
        # Closest to (9, 9) should be (10, 10) with p=0.7
        p = Typesetter._nearest_pressure(pts, 9, 9)
        self.assertAlmostEqual(p, 0.7)

        # Closest to (0, 0) should be (0, 0) with p=0.3
        p = Typesetter._nearest_pressure(pts, 0, 0)
        self.assertAlmostEqual(p, 0.3)

        # Empty points should return default 0.5
        p = Typesetter._nearest_pressure([], 5, 5)
        self.assertAlmostEqual(p, 0.5)

    def test_normalized_metrics_precomputed(self):
        """GlyphLibrary should precompute normalized_metrics for variants with normalized_strokes."""
        glyph_b = self.lib.get_glyph("b")
        self.assertIsNotNone(glyph_b)
        variant = glyph_b['variants'][0]
        self.assertIn('normalized_metrics', variant)
        nm = variant['normalized_metrics']
        # normalized_strokes x range: 5 to 65 → width=60
        self.assertAlmostEqual(nm['min_x'], 5.0)
        self.assertAlmostEqual(nm['width'], 60.0)

    def test_unicode_fallbacks_applied(self):
        """Em-dash and curly quotes are substituted before placement, and
        the coverage report records the substitutions."""
        from assembler import DEFAULT_UNICODE_FALLBACKS
        typesetter = Typesetter(self.lib)
        # Our mock font has a, b, c. Use covered chars + fallback-able chars.
        typesetter.typeset_text("a\u2014b\u2018c\u2019",
                                fallbacks=DEFAULT_UNICODE_FALLBACKS)
        report = typesetter._coverage_report
        self.assertIn('\u2014', report['substituted'])
        self.assertEqual(report['substituted']['\u2014']['replacement'], '--')
        self.assertIn('\u2018', report['substituted'])
        self.assertIn('\u2019', report['substituted'])
        # '-' and "'" themselves may be missing from the mock font but not
        # part of the substituted inventory.
        self.assertEqual(report['substituted']['\u2014']['count'], 1)

    def test_coverage_missing_reported(self):
        """Characters with no glyph are recorded with counts and positions."""
        typesetter = Typesetter(self.lib)
        typesetter.typeset_text("aZbZ")  # Z is not in the mock font
        report = typesetter._coverage_report
        self.assertIn('Z', report['missing'])
        self.assertEqual(report['missing']['Z']['count'], 2)
        self.assertEqual(report['missing_count'], 2)

    def test_coverage_clean_text(self):
        """All-covered text produces empty substitution/missing maps."""
        typesetter = Typesetter(self.lib)
        typesetter.typeset_text("abc")
        report = typesetter._coverage_report
        self.assertEqual(report['substituted'], {})
        self.assertEqual(report['missing'], {})
        self.assertEqual(report['missing_count'], 0)

    def test_scan_text_coverage_function(self):
        """The module-level scan_text_coverage is usable standalone."""
        from assembler import scan_text_coverage, DEFAULT_UNICODE_FALLBACKS
        normalised, report = scan_text_coverage(
            "a\u2014Zc", self.lib, fallbacks=DEFAULT_UNICODE_FALLBACKS)
        self.assertEqual(normalised, "a--Zc")
        self.assertIn('\u2014', report['substituted'])
        self.assertIn('Z', report['missing'])

    def test_glyph_slant_jitter_changes_output(self):
        """Non-zero glyph_slant_jitter must move point coordinates."""
        t1 = Typesetter(self.lib)
        shapes1 = t1.typeset_text("abc", seed=1)
        pts1 = [(p['x'], p['y']) for s in shapes1 for st in s for p in st]

        t2 = Typesetter(self.lib)
        shapes2 = t2.typeset_text("abc", seed=1, glyph_slant_jitter=2.0,
                                  glyph_y_jitter=1.0)
        pts2 = [(p['x'], p['y']) for s in shapes2 for st in s for p in st]

        self.assertEqual(len(pts1), len(pts2))
        diffs = sum(abs(a[0] - b[0]) + abs(a[1] - b[1])
                    for a, b in zip(pts1, pts2))
        self.assertGreater(diffs, 0.0,
                           "glyph_slant_jitter / glyph_y_jitter must transform points")

    def test_glyph_slant_jitter_deterministic_with_seed(self):
        """Same seed + same jitter → byte-identical coordinates."""
        t1 = Typesetter(self.lib)
        s1 = t1.typeset_text("abc", seed=42, glyph_slant_jitter=1.5,
                             glyph_y_jitter=0.5)
        t2 = Typesetter(self.lib)
        s2 = t2.typeset_text("abc", seed=42, glyph_slant_jitter=1.5,
                             glyph_y_jitter=0.5)
        p1 = [(p['x'], p['y']) for s in s1 for st in s for p in st]
        p2 = [(p['x'], p['y']) for s in s2 for st in s for p in st]
        self.assertEqual(p1, p2)

if __name__ == '__main__':
    unittest.main()
