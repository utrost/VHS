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

    # ── read endpoints (edit-existing / add-missing round trip) ──

    def test_list_glyphs(self):
        self._post({"font": "f", "filename": "0061.json",
                    "glyph": {"char": "a", "variants": [{"strokes": []}]}})
        self._post({"font": "f", "filename": "0062.json",
                    "glyph": {"char": "b", "variants": [{"strokes": []}, {"strokes": []}]}})
        r = self.client.get("/api/glyphs/f")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        chars = {g["char"]: g["variants"] for g in data["glyphs"]}
        self.assertEqual(chars, {"a": 1, "b": 2})

    def test_list_glyphs_unknown_font_is_empty(self):
        r = self.client.get("/api/glyphs/nope")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["glyphs"], [])

    def test_get_glyph_roundtrip(self):
        self._post({"font": "f", "filename": "0061.json",
                    "glyph": {"char": "a", "variants": [{"strokes": [[{"x": 1, "y": 2}]]}]}})
        r = self.client.get("/api/glyph/f/0061.json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["char"], "a")

    def test_get_glyph_missing_is_404(self):
        r = self.client.get("/api/glyph/f/0099.json")
        self.assertEqual(r.status_code, 404)

    def test_get_glyph_rejects_bad_filename(self):
        r = self.client.get("/api/glyph/f/passwd")  # not hex.json
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
