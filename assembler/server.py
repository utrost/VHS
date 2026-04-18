#!/usr/bin/env python3
"""
VHS Assembler Web Server
~~~~~~~~~~~~~~~~~~~~~~~~
A lightweight Flask server that wraps the VHS assembler engine,
providing a browser-based UI for generating handwriting SVGs.

Usage:
    pip install flask
    python3 server.py
    # Open http://localhost:5001
"""

import os
import sys
import json
import logging
from typing import Dict, Tuple
from flask import Flask, render_template, request, jsonify, Response

# Ensure the assembler module is importable
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from assembler import (GlyphLibrary, Typesetter, Renderer, PAPER_SIZES,
                       DEFAULT_UNICODE_FALLBACKS, format_coverage_banner,
                       _list_presets, _preset_path, _load_config_file)

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

BASE_GLYPHS_DIR = os.path.normpath(os.path.join(script_dir, "..", "glyphs"))

# Module-level cache of loaded GlyphLibrary instances keyed by glyphs_path.
# The library is purely data derived from on-disk JSON, so caching across
# requests is safe and keeps live-preview renders fast. Invalidates when
# any .json file under the path has a newer mtime than the cached stamp.
_library_cache: Dict[str, Tuple[float, GlyphLibrary]] = {}


def _latest_mtime(path: str) -> float:
    latest = 0.0
    try:
        for entry in os.scandir(path):
            if entry.is_file() and entry.name.endswith('.json'):
                latest = max(latest, entry.stat().st_mtime)
    except FileNotFoundError:
        return 0.0
    return latest


def _get_library(glyphs_path: str) -> GlyphLibrary:
    stamp = _latest_mtime(glyphs_path)
    cached = _library_cache.get(glyphs_path)
    if cached and cached[0] >= stamp:
        return cached[1]
    lib = GlyphLibrary(glyphs_path)
    _library_cache[glyphs_path] = (stamp, lib)
    return lib


def list_fonts():
    """List available font subdirectories in the glyphs folder."""
    fonts = []
    if os.path.isdir(BASE_GLYPHS_DIR):
        for entry in sorted(os.listdir(BASE_GLYPHS_DIR)):
            full = os.path.join(BASE_GLYPHS_DIR, entry)
            if os.path.isdir(full) and not entry.startswith('.'):
                fonts.append(entry)
    return fonts


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/fonts")
def api_fonts():
    return jsonify(list_fonts())


@app.route("/api/paper-sizes")
def api_paper_sizes():
    sizes = {k: {"width": v[0], "height": v[1]} for k, v in PAPER_SIZES.items()}
    return jsonify(sizes)


@app.route("/api/presets")
def api_presets():
    """List bundled preset names found under configs/presets/."""
    return jsonify(_list_presets())


@app.route("/api/preset/<name>")
def api_preset(name):
    """Return the contents of a named preset as JSON so the GUI can
    apply the values to its form fields."""
    path = _preset_path(name)
    if path is None:
        return jsonify({"error": f"Preset {name!r} not found"}), 404
    try:
        return jsonify(_load_config_file(path))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json(force=True)

    text = data.get("text", "")
    if not text.strip():
        return jsonify({"error": "No text provided"}), 400

    font_name = data.get("font", "")
    smooth = data.get("smooth", True)
    jitter = float(data.get("jitter", 0.0))
    auto_kern = data.get("auto_kern", False)
    kern_aggressiveness = float(data.get("kern_aggressiveness", 0.5))
    color = data.get("color", "black")
    line_spacing = float(data.get("line_spacing", 1.0))
    paper_size = data.get("paper_size")
    orientation = data.get("orientation", "portrait")
    margin = float(data.get("margin", 20.0))
    stroke_width = float(data.get("stroke_width", 0.4))
    seed_val = data.get("seed")
    seed = int(seed_val) if seed_val is not None else None

    # mm layout controls (used when a paper size is selected)
    def _opt_float(key):
        v = data.get(key)
        if v is None or v == "":
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    line_height_mm = _opt_float("line_height_mm")
    lines_per_page = data.get("lines_per_page")
    lines_per_page = int(lines_per_page) if lines_per_page not in (None, "") else None
    start_x_in = _opt_float("start_x")
    start_y_in = _opt_float("start_y")
    max_width_mm_in = _opt_float("max_width_mm")
    wrap_mode = data.get("wrap_mode", "balanced")
    if wrap_mode not in ("greedy", "balanced"):
        wrap_mode = "balanced"
    space_width_mm_in = _opt_float("space_width_mm")
    space_jitter_mm = _opt_float("space_jitter_mm") or 0.0
    line_drift_angle = _opt_float("line_drift_angle") or 0.0
    line_drift_y_mm = _opt_float("line_drift_y") or 0.0
    glyph_slant_jitter = _opt_float("glyph_slant_jitter") or 0.0
    glyph_y_jitter_mm = _opt_float("glyph_y_jitter") or 0.0
    fallbacks_enabled = bool(data.get("fallbacks", True))

    # Resolve glyphs path
    if font_name:
        glyphs_path = os.path.join(BASE_GLYPHS_DIR, font_name)
    else:
        glyphs_path = BASE_GLYPHS_DIR

    if not os.path.isdir(glyphs_path):
        return jsonify({"error": f"Font directory not found: {font_name}"}), 404

    # Kerning config
    kerning_path = os.path.join(glyphs_path, "kerning.json")
    if not os.path.exists(kerning_path):
        kerning_path = os.path.join(script_dir, "kerning.json")

    # Resolve page dims
    page_w, page_h = None, None
    if paper_size and paper_size in PAPER_SIZES:
        pw, ph = PAPER_SIZES[paper_size]
        if orientation == "landscape":
            pw, ph = ph, pw
        page_w, page_h = float(pw), float(ph)

    # Build pipeline — library cached across requests for live preview speed
    lib = _get_library(glyphs_path)
    typesetter = Typesetter(lib, kerning_config_path=kerning_path)

    explicit_scale = None
    start_x_mm = None
    start_y_mm = None
    max_width = None

    if page_w is not None:
        if lines_per_page is not None and lines_per_page > 0:
            avail_h = page_h - 2 * margin
            line_height_mm = avail_h / (lines_per_page * line_spacing)

        if not line_height_mm or line_height_mm <= 0:
            return jsonify({"error": "line_height_mm or lines_per_page is required "
                                     "when a paper size is selected"}), 400

        mm_per_glyph = line_height_mm / typesetter.line_height
        explicit_scale = mm_per_glyph

        start_x_mm = start_x_in if start_x_in is not None else margin
        start_y_mm = start_y_in if start_y_in is not None else margin

        max_width_mm = (max_width_mm_in
                        if max_width_mm_in is not None
                        else page_w - margin - start_x_mm)
        max_width = (max_width_mm / mm_per_glyph) if max_width_mm and max_width_mm > 0 else None

    space_width_override = None
    space_jitter = 0.0
    line_drift_y_glyph = 0.0
    glyph_y_jitter_glyph = 0.0
    if explicit_scale is not None:
        if space_width_mm_in is not None:
            space_width_override = space_width_mm_in / explicit_scale
        if space_jitter_mm > 0:
            space_jitter = space_jitter_mm / explicit_scale
        if line_drift_y_mm > 0:
            line_drift_y_glyph = line_drift_y_mm / explicit_scale
        if glyph_y_jitter_mm > 0:
            glyph_y_jitter_glyph = glyph_y_jitter_mm / explicit_scale

    fallbacks = DEFAULT_UNICODE_FALLBACKS if fallbacks_enabled else None

    shapes = typesetter.typeset_text(text,
                                     auto_kern=auto_kern, line_spacing=line_spacing,
                                     max_width=max_width,
                                     kern_aggressiveness=kern_aggressiveness,
                                     wrap_mode=wrap_mode,
                                     space_width_override=space_width_override,
                                     space_jitter=space_jitter,
                                     seed=seed,
                                     fallbacks=fallbacks,
                                     glyph_slant_jitter=glyph_slant_jitter,
                                     glyph_y_jitter=glyph_y_jitter_glyph)

    renderer = Renderer(jitter_amount=jitter, smoothing=smooth, color=color,
                        stroke_width=stroke_width, seed=seed)

    svg_str = renderer.generate_svg_string(shapes, page_width_mm=page_w,
                                           page_height_mm=page_h, margin_mm=margin,
                                           explicit_scale=explicit_scale,
                                           start_x_mm=start_x_mm, start_y_mm=start_y_mm,
                                           line_info=typesetter._line_info,
                                           line_drift_angle_deg=line_drift_angle,
                                           line_drift_y=line_drift_y_glyph,
                                           drift_seed=seed)

    response = Response(svg_str, mimetype="image/svg+xml")
    # Coverage report surfaces to the GUI via a custom header so the
    # SVG body stays pure.
    response.headers['X-Glyph-Coverage'] = json.dumps(
        typesetter._coverage_report, default=str)
    return response


@app.route("/api/png", methods=["POST"])
def api_png():
    """Convert a client-provided SVG string to PNG.

    Body: {"svg": "<svg ...>...</svg>", "dpi": 300, "transparent": false}
    """
    try:
        import cairosvg  # type: ignore
    except ImportError:
        return jsonify({"error": "PNG output requires cairosvg. "
                                   "Install with: pip install cairosvg"}), 503

    data = request.get_json(force=True)
    svg_text = data.get("svg", "")
    if not svg_text.strip():
        return jsonify({"error": "No SVG provided"}), 400
    dpi = int(data.get("dpi", 300))
    transparent = bool(data.get("transparent", False))

    kwargs = {"bytestring": svg_text.encode("utf-8"), "dpi": dpi}
    if not transparent:
        kwargs["background_color"] = "white"
    png_bytes = cairosvg.svg2png(**kwargs)
    return Response(png_bytes, mimetype="image/png")


@app.route("/api/pdf", methods=["POST"])
def api_pdf():
    """Convert a client-provided SVG string to a single-page PDF.

    Body: {"svg": "<svg ...>...</svg>"}
    """
    try:
        import cairosvg  # type: ignore
    except ImportError:
        return jsonify({"error": "PDF output requires cairosvg. "
                                   "Install with: pip install cairosvg"}), 503

    data = request.get_json(force=True)
    svg_text = data.get("svg", "")
    if not svg_text.strip():
        return jsonify({"error": "No SVG provided"}), 400
    pdf_bytes = cairosvg.svg2pdf(bytestring=svg_text.encode("utf-8"))
    return Response(pdf_bytes, mimetype="application/pdf")


@app.route("/api/coverage", methods=["POST"])
def api_coverage():
    """Standalone coverage check — no typesetting, no SVG emission.

    Intended for GUI live hints ("this text has 3 uncovered glyphs")
    without the cost of a full render.
    """
    from assembler import scan_text_coverage

    data = request.get_json(force=True)
    text = data.get("text", "")
    font_name = data.get("font", "")
    fallbacks_enabled = bool(data.get("fallbacks", True))

    if font_name:
        glyphs_path = os.path.join(BASE_GLYPHS_DIR, font_name)
    else:
        glyphs_path = BASE_GLYPHS_DIR
    if not os.path.isdir(glyphs_path):
        return jsonify({"error": f"Font directory not found: {font_name}"}), 404

    lib = _get_library(glyphs_path)
    fallbacks = DEFAULT_UNICODE_FALLBACKS if fallbacks_enabled else None
    _, report = scan_text_coverage(text, lib, fallbacks=fallbacks)
    return jsonify(report)


if __name__ == "__main__":
    print("\n  VHS Assembler Web UI")
    print("  ====================")
    print(f"  Glyphs dir : {BASE_GLYPHS_DIR}")
    print(f"  Fonts found: {', '.join(list_fonts()) or '(none)'}")
    print(f"  Open       : http://localhost:5001\n")
    app.run(host="0.0.0.0", port=5001, debug=True)
