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
import json

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

    def _write_minimal_glyph(self, root, font="font1", char="x"):
        font_dir = os.path.join(root, font)
        os.makedirs(font_dir, exist_ok=True)
        filename = "".join(f"{ord(c):04X}" for c in char) + ".json"
        with open(os.path.join(font_dir, filename), "w", encoding="utf-8") as f:
            json.dump({
                "char": char,
                "metadata": {"baseline_y": 100, "x_height": 60, "canvas_size": [100, 140]},
                "variants": [{"strokes": [[{"x": 0, "y": 80}, {"x": 10, "y": 80}]]}],
            }, f)

    def test_valid_save_writes_file(self):
        r = self._post({"font": "myfont", "filename": "0061.json",
                        "glyph": {"char": "a", "variants": [{"strokes": []}]}})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["ok"])
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "myfont", "0061.json")))

    def test_generate_rejects_invalid_numeric_field_as_json_400(self):
        r = self.client.post("/api/generate", json={
            "text": "Hi", "font": "font1", "jitter": "abc"
        })
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.content_type, "application/json")
        self.assertIn("jitter", r.get_json()["error"])

    def test_generate_rejects_malformed_json_as_json_400(self):
        r = self.client.post("/api/generate", data="not json",
                             content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.content_type, "application/json")
        self.assertIn("json", r.get_json()["error"].lower())

    def test_png_rejects_invalid_dpi_as_json_400_before_optional_renderer(self):
        r = self.client.post("/api/png", json={"svg": "<svg></svg>", "dpi": "abc"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.content_type, "application/json")
        self.assertIn("dpi", r.get_json()["error"])

    def test_generate_rejects_non_finite_numeric_field_as_json_400(self):
        os.makedirs(os.path.join(self.tmp, "font1"), exist_ok=True)
        r = self.client.post("/api/generate", json={
            "text": "Hi", "font": "font1", "jitter": "nan"
        })
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.content_type, "application/json")
        self.assertIn("jitter", r.get_json()["error"])

    def test_generate_rejects_invalid_frame_numeric_field_as_json_400(self):
        os.makedirs(os.path.join(self.tmp, "font1"), exist_ok=True)
        r = self.client.post("/api/generate", json={
            "font": "font1",
            "paper_size": "A4",
            "line_height_mm": 10,
            "frames": [{"text": "Hi", "start_x": "abc", "start_y": 20, "max_width": 50}],
        })
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.content_type, "application/json")
        self.assertIn("frames[0].start_x", r.get_json()["error"])

    def test_generate_rejects_font_traversal_before_loading_external_glyphs(self):
        external = tempfile.mkdtemp(prefix="vhs_external_font_")
        try:
            self._write_minimal_glyph(external, font="", char="x")
            traversal = os.path.relpath(external, self.tmp)
            self.assertIn("..", traversal)
            r = self.client.post("/api/generate", json={"text": "x", "font": traversal})
            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.content_type, "application/json")
            self.assertIn("font", r.get_json()["error"])
        finally:
            shutil.rmtree(external, ignore_errors=True)

    def test_generate_rejects_non_string_font_as_json_400(self):
        for font in (["font1"], {"name": "font1"}, 123):
            with self.subTest(font=font):
                r = self.client.post("/api/generate", json={"text": "x", "font": font})
                self.assertEqual(r.status_code, 400)
                self.assertEqual(r.content_type, "application/json")
                self.assertIn("font", r.get_json()["error"])

    def test_coverage_rejects_font_traversal_before_loading_external_glyphs(self):
        external = tempfile.mkdtemp(prefix="vhs_external_font_")
        try:
            self._write_minimal_glyph(external, font="", char="x")
            traversal = os.path.relpath(external, self.tmp)
            self.assertIn("..", traversal)
            r = self.client.post("/api/coverage", json={"text": "x", "font": traversal})
            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.content_type, "application/json")
            self.assertIn("font", r.get_json()["error"])
        finally:
            shutil.rmtree(external, ignore_errors=True)

    def test_coverage_rejects_non_string_font_as_json_400(self):
        for font in (["font1"], {"name": "font1"}, 123):
            with self.subTest(font=font):
                r = self.client.post("/api/coverage", json={"text": "x", "font": font})
                self.assertEqual(r.status_code, 400)
                self.assertEqual(r.content_type, "application/json")
                self.assertIn("font", r.get_json()["error"])

    def test_generate_rejects_zero_line_spacing_with_lines_per_page_as_json_400(self):
        self._write_minimal_glyph(self.tmp, font="font1", char="a")
        r = self.client.post("/api/generate", json={
            "text": "a",
            "font": "font1",
            "paper_size": "A4",
            "lines_per_page": 10,
            "line_spacing": 0,
        })
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.content_type, "application/json")
        self.assertIn("line_spacing", r.get_json()["error"])

    def test_generate_rejects_non_positive_lines_per_page_even_with_explicit_line_height(self):
        self._write_minimal_glyph(self.tmp, font="font1", char="a")
        for lines_per_page in (0, -5):
            with self.subTest(lines_per_page=lines_per_page):
                r = self.client.post("/api/generate", json={
                    "text": "a",
                    "font": "font1",
                    "paper_size": "A4",
                    "line_height_mm": 10,
                    "lines_per_page": lines_per_page,
                })
                self.assertEqual(r.status_code, 400)
                self.assertEqual(r.content_type, "application/json")
                self.assertIn("lines_per_page", r.get_json()["error"])

    def test_png_rejects_non_positive_dpi_as_json_400(self):
        for dpi in (0, -1):
            with self.subTest(dpi=dpi):
                r = self.client.post("/api/png", json={"svg": "<svg></svg>", "dpi": dpi})
                self.assertEqual(r.status_code, 400)
                self.assertEqual(r.content_type, "application/json")
                self.assertIn("dpi", r.get_json()["error"])

    def test_mutating_endpoints_do_not_advertise_wildcard_cors(self):
        presets = os.path.join(self.tmp, "presets")
        orig_presets = server.PRESETS_DIR
        server.PRESETS_DIR = presets
        try:
            for path, body in [
                ("/api/save-preset", {"name": "cross-origin-write", "yaml": "margin: 12\n"}),
                ("/api/save-glyph", {"font": "corsfont", "filename": "0061.json",
                                      "glyph": {"char": "a", "variants": [{"strokes": []}]}}),
            ]:
                with self.subTest(path=path):
                    preflight = self.client.open(
                        path,
                        method="OPTIONS",
                        headers={
                            "Origin": "https://example.invalid",
                            "Access-Control-Request-Method": "POST",
                            "Access-Control-Request-Headers": "Content-Type",
                        },
                    )
                    self.assertNotEqual(preflight.headers.get("Access-Control-Allow-Origin"), "*")

                    r = self.client.post(
                        path,
                        json=body,
                        headers={"Origin": "https://example.invalid"},
                    )
                    self.assertNotEqual(r.headers.get("Access-Control-Allow-Origin"), "*")
        finally:
            server.PRESETS_DIR = orig_presets

    def test_generate_rejects_non_finite_integer_field_as_json_400(self):
        os.makedirs(os.path.join(self.tmp, "font1"), exist_ok=True)
        r = self.client.post("/api/generate",
                             data='{"text":"Hi","font":"font1","seed":Infinity}',
                             content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.content_type, "application/json")
        self.assertIn("seed", r.get_json()["error"])

    def test_png_rejects_non_finite_dpi_as_json_400(self):
        r = self.client.post("/api/png",
                             data='{"svg":"<svg></svg>","dpi":Infinity}',
                             content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.content_type, "application/json")
        self.assertIn("dpi", r.get_json()["error"])


    def test_png_returns_json_400_for_malformed_svg_conversion(self):
        class FakeCairoSvg:
            @staticmethod
            def svg2png(**_kwargs):
                raise ValueError("malformed SVG")

        original = sys.modules.get("cairosvg")
        sys.modules["cairosvg"] = FakeCairoSvg
        try:
            r = self.client.post("/api/png", json={"svg": "<svg><path", "dpi": 300})
        finally:
            if original is None:
                sys.modules.pop("cairosvg", None)
            else:
                sys.modules["cairosvg"] = original
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.content_type, "application/json")
        self.assertIn("SVG conversion failed", r.get_json()["error"])

    def test_pdf_returns_json_400_for_malformed_svg_conversion(self):
        class FakeCairoSvg:
            @staticmethod
            def svg2pdf(**_kwargs):
                raise ValueError("malformed SVG")

        original = sys.modules.get("cairosvg")
        sys.modules["cairosvg"] = FakeCairoSvg
        try:
            r = self.client.post("/api/pdf", json={"svg": "<svg><path"})
        finally:
            if original is None:
                sys.modules.pop("cairosvg", None)
            else:
                sys.modules["cairosvg"] = original
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.content_type, "application/json")
        self.assertIn("SVG conversion failed", r.get_json()["error"])

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

    def test_allows_punctuation_glyph_chars(self):
        for ch, filename in [("&", "0026.json"), ("<", "003C.json"), (">", "003E.json")]:
            with self.subTest(ch=ch):
                r = self._post({"font": "ok", "filename": filename,
                                "glyph": {"char": ch, "variants": []}})
                self.assertEqual(r.status_code, 200)

    def test_rejects_html_like_glyph_char(self):
        r = self._post({"font": "ok", "filename": "0061.json",
                        "glyph": {"char": "<img src=x onerror=alert(1)>",
                                  "variants": []}})
        self.assertEqual(r.status_code, 400)
        self.assertIn("char", r.get_json()["error"])

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

    # ── preset save ──

    def test_save_preset_writes_yaml(self):
        presets = os.path.join(self.tmp, "presets")
        orig = server.PRESETS_DIR
        server.PRESETS_DIR = presets
        try:
            r = self.client.post("/api/save-preset",
                                 json={"name": "my-preset", "yaml": "margin: 12\n"})
            self.assertEqual(r.status_code, 200)
            self.assertTrue(os.path.exists(os.path.join(presets, "my-preset.yaml")))
        finally:
            server.PRESETS_DIR = orig

    def test_save_preset_rejects_bad_name(self):
        r = self.client.post("/api/save-preset",
                             json={"name": "../evil", "yaml": "x: 1\n"})
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
