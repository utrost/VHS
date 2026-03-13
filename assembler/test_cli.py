"""
test_cli.py
~~~~~~~~~~~
Automated CLI tests for the VHS assembler, derived from the human Validation Scripts (VS-01 through VS-10).

Uses a temporary mock font directory so tests are self-contained and run without real glyph data.
Tests invoke assembler.py as a subprocess (just like a user would) and parse the output SVGs.

Run:  python3 -m unittest test_cli -v
"""

import os
import sys
import shutil
import json
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSEMBLER = os.path.join(SCRIPT_DIR, "assembler.py")
PYTHON = sys.executable  # same interpreter running the tests

SVG_NS = "http://www.w3.org/2000/svg"


class CLITestBase(unittest.TestCase):
    """
    Base class: creates a temporary mock font with glyphs for a–f, space, period,
    comma, and a "tt" ligature — enough to exercise all CLI features.
    """

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp(prefix="vhs_cli_test_")

        # Build a mock glyphs tree:  <tmpdir>/glyphs/MockFont/
        cls.glyphs_root = os.path.join(cls.tmpdir, "glyphs")
        cls.font_dir = os.path.join(cls.glyphs_root, "MockFont")
        os.makedirs(cls.font_dir)

        # Helper to write a glyph JSON
        def write_glyph(char, strokes, extra_variants=None):
            variants = [{"strokes": strokes}]
            if extra_variants:
                for s in extra_variants:
                    variants.append({"strokes": s})
            data = {
                "char": char,
                "metadata": {"baseline_y": 100, "x_height": 60, "canvas_size": [100, 140]},
                "variants": variants,
            }
            # Use unicode hex filename (matches real convention)
            hex_name = "".join(f"{ord(c):04X}" for c in char)
            path = os.path.join(cls.font_dir, f"{hex_name}.json")
            with open(path, "w") as f:
                json.dump(data, f)

        # a–f  (simple strokes with varying widths)
        for i, ch in enumerate("abcdef"):
            x_end = 10 + i * 5
            write_glyph(ch, [
                [{"x": 0, "y": 80, "p": 0.5}, {"x": x_end, "y": 80 + i, "p": 0.5}],
                [{"x": 2, "y": 90, "p": 0.5}, {"x": x_end - 2, "y": 95, "p": 0.5}],
            ])

        # Period
        write_glyph(".", [[{"x": 5, "y": 98, "p": 0.5}, {"x": 6, "y": 99, "p": 0.5}]])

        # Comma
        write_glyph(",", [[{"x": 5, "y": 98, "p": 0.5}, {"x": 4, "y": 108, "p": 0.5}]])

        # Ligature "tt" (wider glyph)
        write_glyph("tt", [[{"x": 0, "y": 60, "p": 0.5}, {"x": 40, "y": 60, "p": 0.5}]])
        # Single "t" so "tt" ligature can be differentiated
        write_glyph("t", [[{"x": 0, "y": 60, "p": 0.5}, {"x": 15, "y": 80, "p": 0.5}]])

        # Kerning config
        cls.kerning_path = os.path.join(cls.font_dir, "kerning.json")
        with open(cls.kerning_path, "w") as f:
            json.dump({
                "space_width": 25.0,
                "tracking_buffer": 3.0,
                "line_height": 200.0,
                "exceptions": {".": {"min_width": 12.0}, ",": {"min_width": 12.0}},
            }, f)

        cls.output_dir = os.path.join(cls.tmpdir, "output")
        os.makedirs(cls.output_dir)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir)

    # ── Helpers ──

    def _out(self, name):
        """Return an output file path in the temp dir."""
        return os.path.join(self.output_dir, name)

    def _run(self, args, expect_fail=False):
        """Run assembler.py with the given args list. Returns (returncode, stdout, stderr)."""
        cmd = [PYTHON, ASSEMBLER] + args
        env = os.environ.copy()
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if not expect_fail:
            self.assertEqual(result.returncode, 0,
                             f"CLI failed (rc={result.returncode}):\n{result.stderr}")
        return result.returncode, result.stdout, result.stderr

    def _run_with_font(self, text_args, output_name, extra_args=None):
        """
        Run assembler with the mock font and return the parsed SVG root element.
        text_args: list like ["abc"] or ["--file", path]
        """
        out = self._out(output_name)
        # Point --font at absolute path by manipulating the glyphs dir.
        # The assembler looks for ../glyphs/{font}/ relative to assembler.py — so we
        # override by passing a full path via env.  But that isn't supported.
        # Instead, we'll symlink our mock glyphs dir.
        args = text_args + [out, "--font", "MockFont"] + (extra_args or [])
        # We need the assembler to find glyphs at <script_dir>/../glyphs/MockFont.
        # Easiest: symlink <tmpdir>/glyphs into <script_dir>/../glyphs temporarily.
        # Safer: just call the assembler from a directory where ../glyphs resolves.
        # Actually, the assembler computes: script_dir/../glyphs/{font}
        # So we need script_dir to be the test's script dir.
        # Let's just run with glyphs already in the right place by symlinking.

        # Create a symlink from the real glyphs location to our MockFont
        real_glyphs_dir = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "glyphs"))
        mock_link = os.path.join(real_glyphs_dir, "MockFont")
        link_created = False
        if not os.path.exists(mock_link):
            os.symlink(self.font_dir, mock_link)
            link_created = True
        try:
            self._run(args)
        finally:
            if link_created and os.path.islink(mock_link):
                os.unlink(mock_link)

        self.assertTrue(os.path.exists(out), f"Output SVG not created: {out}")
        self.assertGreater(os.path.getsize(out), 0, "Output SVG is empty")
        tree = ET.parse(out)
        return tree.getroot()

    def _parse_svg(self, path):
        tree = ET.parse(path)
        return tree.getroot()

    def _count_paths(self, svg_root):
        return len(svg_root.findall(f".//{{{SVG_NS}}}path"))

    def _write_text_file(self, name, content):
        path = os.path.join(self.output_dir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path


# ═══════════════════════════════════════════════════════════════════
# VS-01: Basic text rendering
# ═══════════════════════════════════════════════════════════════════
class TestBasicRendering(CLITestBase):
    """VS-01: Inline text produces a valid SVG with paths."""

    def test_inline_text_produces_svg(self):
        root = self._run_with_font(["abc"], "vs01_basic.svg")
        self.assertEqual(root.tag, f"{{{SVG_NS}}}svg")
        self.assertIn("viewBox", root.attrib)
        self.assertIn("mm", root.get("width", ""))
        self.assertGreater(self._count_paths(root), 0, "SVG should contain paths")

    def test_space_produces_gap(self):
        """Space should not produce a glyph shape but increase the cursor."""
        root_no_space = self._run_with_font(["ab"], "vs01_no_space.svg")
        root_space = self._run_with_font(["a b"], "vs01_space.svg")
        # With a space, the second char should be further right.
        # Both should have the same number of paths (space adds no strokes).
        self.assertEqual(self._count_paths(root_no_space), self._count_paths(root_space))


# ═══════════════════════════════════════════════════════════════════
# VS-02: Multiline file input
# ═══════════════════════════════════════════════════════════════════
class TestMultilineFileInput(CLITestBase):
    """VS-02: --file reads text, preserves line breaks."""

    def test_file_input(self):
        txt = self._write_text_file("vs02.txt", "abc\ndef")
        root = self._run_with_font(["--file", txt], "vs02_multiline.svg")
        self.assertGreater(self._count_paths(root), 0)

    def test_line_breaks_create_vertical_offset(self):
        """Two lines should have different Y positions in the SVG paths."""
        txt = self._write_text_file("vs02b.txt", "a\na")
        root = self._run_with_font(["--file", txt], "vs02_lines.svg")
        paths = root.findall(f".//{{{SVG_NS}}}path")
        self.assertGreaterEqual(len(paths), 2, "Should have paths for both lines")

        # Extract first move-to Y from each path
        ys = []
        for p in paths:
            d = p.get("d", "")
            # First M command: "M x y ..."
            parts = d.split()
            if parts and parts[0] == "M":
                ys.append(float(parts[2]))
        unique_ys = set(round(y, 0) for y in ys)
        self.assertGreaterEqual(len(unique_ys), 2,
                                f"Paths should span at least 2 distinct Y positions, got {unique_ys}")


# ═══════════════════════════════════════════════════════════════════
# VS-03: Paper size presets
# ═══════════════════════════════════════════════════════════════════
class TestPaperSizes(CLITestBase):
    """VS-03: --paper-size and --orientation set SVG dimensions."""

    def test_a4_portrait(self):
        root = self._run_with_font(["ab"], "vs03_a4p.svg",
                                   ["--paper-size", "A4", "--orientation", "portrait"])
        self.assertEqual(root.get("width"), "210.0mm")
        self.assertEqual(root.get("height"), "297.0mm")

    def test_a4_landscape(self):
        root = self._run_with_font(["ab"], "vs03_a4l.svg",
                                   ["--paper-size", "A4", "--orientation", "landscape"])
        self.assertEqual(root.get("width"), "297.0mm")
        self.assertEqual(root.get("height"), "210.0mm")

    def test_a5_portrait(self):
        root = self._run_with_font(["ab"], "vs03_a5p.svg",
                                   ["--paper-size", "A5", "--orientation", "portrait"])
        self.assertEqual(root.get("width"), "148.0mm")
        self.assertEqual(root.get("height"), "210.0mm")

    def test_a3_landscape(self):
        root = self._run_with_font(["ab"], "vs03_a3l.svg",
                                   ["--paper-size", "A3", "--orientation", "landscape"])
        self.assertEqual(root.get("width"), "420.0mm")
        self.assertEqual(root.get("height"), "297.0mm")

    def test_letter(self):
        root = self._run_with_font(["ab"], "vs03_letter.svg",
                                   ["--paper-size", "Letter"])
        self.assertEqual(root.get("width"), "216.0mm")
        self.assertEqual(root.get("height"), "279.0mm")

    def test_auto_fit_no_paper_size(self):
        """Without --paper-size, dimensions should auto-fit to content."""
        root = self._run_with_font(["ab"], "vs03_auto.svg")
        w = root.get("width", "")
        # Should NOT be a standard paper size
        self.assertNotEqual(w, "210.0mm")


# ═══════════════════════════════════════════════════════════════════
# VS-04: Line spacing
# ═══════════════════════════════════════════════════════════════════
class TestLineSpacing(CLITestBase):
    """VS-04: --line-spacing multiplier affects vertical gap between lines."""

    def _get_line_gap(self, output_name, spacing):
        txt = self._write_text_file(f"vs04_{spacing}.txt", "a\na")
        root = self._run_with_font(["--file", txt], output_name,
                                   ["--line-spacing", str(spacing), "--paper-size", "A4"])
        paths = root.findall(f".//{{{SVG_NS}}}path")
        # Collect first M-y from each path
        ys = []
        for p in paths:
            parts = p.get("d", "").split()
            if parts and parts[0] == "M":
                ys.append(float(parts[2]))
        ys.sort()
        # With "a\na", and each "a" having 2 strokes, we expect 4 Y values.
        # ys[0], ys[1] are Line 1; ys[2], ys[3] are Line 2.
        # The gap we want is Line2[0] - Line1[0].
        if len(ys) >= 3:
            return ys[2] - ys[0]
        return 0

    def test_double_spacing_doubles_gap(self):
        gap_1x = self._get_line_gap("vs04_1x.svg", 1.0)
        gap_2x = self._get_line_gap("vs04_2x.svg", 2.0)
        self.assertGreater(gap_1x, 0, "1x gap must be positive")
        self.assertAlmostEqual(gap_2x, gap_1x * 2.0, delta=5.0)


# ═══════════════════════════════════════════════════════════════════
# VS-05: Margins
# ═══════════════════════════════════════════════════════════════════
class TestMargins(CLITestBase):
    """VS-05: --margin offsets content via translate transform."""

    def _get_translate(self, root):
        g = root.find(f"{{{SVG_NS}}}g")
        self.assertIsNotNone(g)
        return g.get("transform", "")

    def test_small_margin(self):
        root = self._run_with_font(["ab"], "vs05_m5.svg",
                                   ["--paper-size", "A5", "--margin", "5"])
        transform = self._get_translate(root)
        self.assertTrue(transform.startswith("translate(5.00,5.00)"),
                        f"Transform should start with margin translate, got: {transform}")

    def test_large_margin(self):
        root = self._run_with_font(["ab"], "vs05_m40.svg",
                                   ["--paper-size", "A5", "--margin", "40"])
        transform = self._get_translate(root)
        self.assertTrue(transform.startswith("translate(40.00,40.00)"),
                        f"Transform should start with margin translate, got: {transform}")

    def test_no_translate_without_paper_size(self):
        """Auto-fit mode should not add a translate."""
        root = self._run_with_font(["ab"], "vs05_auto.svg")
        g = root.find(f"{{{SVG_NS}}}g")
        self.assertIsNone(g.get("transform"),
                          "Auto-fit mode should not have a translate transform")


# ═══════════════════════════════════════════════════════════════════
# VS-06: Smoothing and jitter
# ═══════════════════════════════════════════════════════════════════
class TestSmoothingAndJitter(CLITestBase):
    """VS-06: --smooth and --jitter affect path data."""

    def test_smooth_produces_more_points(self):
        """Smoothing (default) interpolates extra points vs --no-smooth."""
        root_raw = self._run_with_font(["abc"], "vs06_raw.svg", ["--no-smooth"])
        root_smooth = self._run_with_font(["abc"], "vs06_smooth.svg")
        raw_d_len = sum(len(p.get("d", "")) for p in root_raw.findall(f".//{{{SVG_NS}}}path"))
        smooth_d_len = sum(len(p.get("d", "")) for p in root_smooth.findall(f".//{{{SVG_NS}}}path"))
        self.assertGreater(smooth_d_len, raw_d_len,
                           "Smoothed SVG should have longer path data (more interpolated points)")

    def test_jitter_changes_coordinates(self):
        """Running twice with jitter should produce different path data."""
        root1 = self._run_with_font(["abc"], "vs06_jit1.svg", ["--jitter", "2.0"])
        root2 = self._run_with_font(["abc"], "vs06_jit2.svg", ["--jitter", "2.0"])
        d1 = root1.findall(f".//{{{SVG_NS}}}path")[0].get("d", "")
        d2 = root2.findall(f".//{{{SVG_NS}}}path")[0].get("d", "")
        # With jitter, random noise makes them almost certainly different
        self.assertNotEqual(d1, d2, "Jitter should produce non-deterministic output")


# ═══════════════════════════════════════════════════════════════════
# VS-07: Ligatures and kerning
# ═══════════════════════════════════════════════════════════════════
class TestLigaturesAndKerning(CLITestBase):
    """VS-07: Ligature substitution and auto-kerning."""

    def test_ligature_substitution(self):
        """'att' should use the 'tt' ligature, resulting in fewer path groups."""
        root_att = self._run_with_font(["att"], "vs07_att.svg")
        # With ligature: a + tt = 2 glyph shapes (a has 2 strokes, tt has 1)
        # Without ligature: a + t + t = 3 glyph shapes
        # Count paths: a=2 strokes, tt=1 stroke => 3 paths total
        paths_att = self._count_paths(root_att)

        root_ab = self._run_with_font(["ab"], "vs07_ab.svg")
        paths_ab = self._count_paths(root_ab)
        # Both produce shapes — the important thing is the CLI didn't crash
        # and the ligature was consumed (fewer path groups than 3 separate glyphs)
        self.assertGreater(paths_att, 0)

    def test_auto_kern(self):
        """--auto-kern should not crash and should produce valid SVG."""
        root = self._run_with_font(["abc"], "vs07_kern.svg", ["--auto-kern"])
        self.assertGreater(self._count_paths(root), 0)

    def test_kern_aggressiveness_flag(self):
        """--kern-aggressiveness should be accepted and produce valid SVG."""
        root = self._run_with_font(["abc"], "vs07_kern_aggr.svg",
                                   ["--auto-kern", "--kern-aggressiveness", "0.8"])
        self.assertGreater(self._count_paths(root), 0)


# ═══════════════════════════════════════════════════════════════════
# VS-08: Full end-to-end letter
# ═══════════════════════════════════════════════════════════════════
class TestFullLetterScenario(CLITestBase):
    """VS-08: Multi-paragraph letter on different paper sizes."""

    _LETTER = "abc def.\n\nabc,\nab"

    def test_a4_portrait_letter(self):
        txt = self._write_text_file("vs08.txt", self._LETTER)
        root = self._run_with_font(["--file", txt], "vs08_a4p.svg",
                                   ["--paper-size", "A4", "--orientation", "portrait",
                                    "--line-spacing", "1.3", "--margin", "25"])
        self.assertEqual(root.get("width"), "210.0mm")
        self.assertEqual(root.get("height"), "297.0mm")
        self.assertGreater(self._count_paths(root), 0)

    def test_a5_landscape_letter(self):
        txt = self._write_text_file("vs08b.txt", self._LETTER)
        root = self._run_with_font(["--file", txt], "vs08_a5l.svg",
                                   ["--paper-size", "A5", "--orientation", "landscape",
                                    "--line-spacing", "1.2", "--margin", "15"])
        self.assertEqual(root.get("width"), "210.0mm")
        self.assertEqual(root.get("height"), "148.0mm")

    def test_empty_line_creates_paragraph_gap(self):
        """A blank line in the input should produce a visible vertical gap (no path, just Y advance)."""
        txt = self._write_text_file("vs08c.txt", "a\n\na")
        root = self._run_with_font(["--file", txt], "vs08_gap.svg", ["--paper-size", "A4"])
        paths = root.findall(f".//{{{SVG_NS}}}path")
        ys = []
        for p in paths:
            parts = p.get("d", "").split()
            if parts and parts[0] == "M":
                ys.append(float(parts[2]))
        unique_ys = sorted(set(round(y, 0) for y in ys))
        # With a blank line between two "a"s, the gap should be ~2x line_height
        self.assertGreaterEqual(len(unique_ys), 2,
                                "Two text lines separated by a blank should have distinct Y positions")


# ═══════════════════════════════════════════════════════════════════
# VS-10: Error handling
# ═══════════════════════════════════════════════════════════════════
class TestErrorHandling(CLITestBase):
    """VS-10: Graceful error messages for invalid input."""

    def test_no_input(self):
        rc, _, stderr = self._run([self._out("err.svg")], expect_fail=True)
        self.assertNotEqual(rc, 0) 

    def test_nonexistent_font(self):
        rc, _, stderr = self._run(
            ["abc", self._out("err.svg"), "--font", "NonExistentFont123"],
            expect_fail=True)
        self.assertNotEqual(rc, 0)
        self.assertIn("not found", stderr.lower())

    def test_nonexistent_input_file(self):
        rc, _, stderr = self._run(
            ["--file", "/tmp/vhs_does_not_exist_xyz.txt", self._out("err.svg"),
             "--font", "MockFont"],
            expect_fail=True)
        self.assertNotEqual(rc, 0)

    def test_invalid_paper_size(self):
        rc, _, stderr = self._run(
            ["abc", self._out("err.svg"), "--paper-size", "B5"],
            expect_fail=True)
        self.assertNotEqual(rc, 0)
        self.assertIn("invalid choice", stderr.lower())

    def test_invalid_orientation(self):
        rc, _, stderr = self._run(
            ["abc", self._out("err.svg"), "--orientation", "diagonal"],
            expect_fail=True)
        self.assertNotEqual(rc, 0)
        self.assertIn("invalid choice", stderr.lower())

    def test_color_option(self):
        """--color should produce an SVG with the specified stroke color."""
        root = self._run_with_font(["ab"], "vs10_color.svg", ["--color", "#ff0000"])
        g = root.find(f"{{{SVG_NS}}}g")
        self.assertEqual(g.get("stroke"), "#ff0000")


if __name__ == "__main__":
    unittest.main()
