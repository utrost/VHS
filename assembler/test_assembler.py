import os
import sys
import unittest
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
        self.assertIsNone(self.lib.get_glyph("z"))

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

if __name__ == '__main__':
    unittest.main()
