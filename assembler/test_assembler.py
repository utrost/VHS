import os
import sys
import unittest
import xml.etree.ElementTree as ET
import shutil

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

if __name__ == '__main__':
    unittest.main()
