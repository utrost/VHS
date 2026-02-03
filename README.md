# Vector Handwriting System (VHS)

VHS is a deterministic pipeline for generating realistic handwriting for pen plotters. It replaces neural-network-based generation with a stochastic "Shaping Engine" utilizing a custom-captured library of single-stroke vector glyphs.

## Project Structure

- **`GlyphCollectorUI/`**: A browser-based tool for capturing handwriting glyph variants.
- **`assembler/`**: Python tools to assemble captured glyphs into handwritten SVG text.
- **`glyphs/`**: Storage for captured glyph data (JSON format).

## Quick Start

### 1. Capture Glyphs
1. Open `GlyphCollectorUI/GlyphCollectorUI.html` in a browser.
2. Draw multiple variants of characters.
3. Save them as JSON files (automatically saved to your downloads, move them to `glyphs/` folder).

### 2. Generate Handwriting
Use the assembler to convert text into an SVG suitable for plotting.

```bash
cd assembler
python assembler.py "Hello World" output.svg
```

## Features

- **True Single-Stroke**: Output paths are 1-pixel wide vectors.
- **Curve Smoothing**: Uses Catmull-Rom splines to turn raw input into fluid, natural curves.
- **Micro-Variations**: Randomly selects from multiple variants of each character to avoid the "font" look.
- **Ligature Support**: Handles multi-character sequences if captured (e.g., "sch", "tt").
- **Pressure Data**: Preserves pressure information from the capture phase (if supported by hardware).

## Requirements

- Python 3.x
- Modern Web Browser (for Capture UI)
