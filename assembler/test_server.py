"""Tests for the Flask server's /api/save-glyph endpoint (the GlyphCollector
→ Assembler round trip). Focuses on the write-path validation, since this is
the one endpoint that writes files. Uses Flask's test client against a
temporary glyphs directory.
"""

import os
import sys
import shutil
import tempfile
import unittest

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

import server  # noqa: E402


class SaveGlyphTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._orig = server.BASE_GLYPHS_DIR
        server.BASE_GLYPHS_DIR = self.tmp
        self.client = server.app.test_client()

    def tearDown(self):
        server.BASE_GLYPHS_DIR = self._orig
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _post(self, body):
        return self.client.post("/api/save-glyph", json=body)

    def test_valid_save_writes_file(self):
        r = self._post({"font": "myfont", "filename": "0061.json",
                        "glyph": {"char": "a", "variants": [{"strokes": []}]}})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["ok"])
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "myfont", "0061.json")))

    def test_rejects_font_traversal(self):
        r = self._post({"font": "../evil", "filename": "0061.json",
                        "glyph": {"variants": []}})
        self.assertEqual(r.status_code, 400)
        # Nothing escaped the glyphs root.
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "..", "evil")))

    def test_rejects_filename_traversal(self):
        r = self._post({"font": "ok", "filename": "../../etc/passwd",
                        "glyph": {"variants": []}})
        self.assertEqual(r.status_code, 400)

    def test_rejects_non_hex_filename(self):
        r = self._post({"font": "ok", "filename": "glyph.json",
                        "glyph": {"variants": []}})
        self.assertEqual(r.status_code, 400)

    def test_rejects_glyph_without_variants(self):
        r = self._post({"font": "ok", "filename": "0061.json",
                        "glyph": {"nope": 1}})
        self.assertEqual(r.status_code, 400)

    def test_new_font_appears_in_fonts_list(self):
        self._post({"font": "freshfont", "filename": "0062.json",
                    "glyph": {"variants": [{"strokes": []}]}})
        r = self.client.get("/api/fonts")
        self.assertIn("freshfont", r.get_json())


if __name__ == "__main__":
    unittest.main()
