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
from flask import Flask, render_template, request, jsonify, Response

# Ensure the assembler module is importable
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from assembler import GlyphLibrary, Typesetter, Renderer, PAPER_SIZES

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

BASE_GLYPHS_DIR = os.path.normpath(os.path.join(script_dir, "..", "glyphs"))


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
    line_height = data.get("line_height")
    line_spacing = float(data.get("line_spacing", 1.0))
    paper_size = data.get("paper_size")
    orientation = data.get("orientation", "portrait")
    margin = float(data.get("margin", 20.0))
    stroke_width = float(data.get("stroke_width", 2.0))
    seed_val = data.get("seed")
    seed = int(seed_val) if seed_val is not None else None

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

    # Build pipeline
    lib = GlyphLibrary(glyphs_path)
    typesetter = Typesetter(lib, kerning_config_path=kerning_path)

    override_lh = float(line_height) if line_height is not None else None
    shapes = typesetter.typeset_text(text, override_line_height=override_lh,
                                     auto_kern=auto_kern, line_spacing=line_spacing,
                                     kern_aggressiveness=kern_aggressiveness)

    renderer = Renderer(jitter_amount=jitter, smoothing=smooth, color=color,
                        stroke_width=stroke_width, seed=seed)

    svg_str = renderer.generate_svg_string(shapes, page_width_mm=page_w,
                                           page_height_mm=page_h, margin_mm=margin)

    return Response(svg_str, mimetype="image/svg+xml")


if __name__ == "__main__":
    print("\n  VHS Assembler Web UI")
    print("  ====================")
    print(f"  Glyphs dir : {BASE_GLYPHS_DIR}")
    print(f"  Fonts found: {', '.join(list_fonts()) or '(none)'}")
    print(f"  Open       : http://localhost:5001\n")
    app.run(host="0.0.0.0", port=5001, debug=True)
