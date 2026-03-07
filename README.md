# Vector Handwriting System (VHS)

VHS is a deterministic pipeline for generating realistic handwriting for pen plotters. It replaces neural-network-based generation with a stochastic "Shaping Engine" utilizing a custom-captured library of single-stroke vector glyphs.

## Project Structure

- **`GlyphCollectorUI/`**: A browser-based tool for capturing handwriting glyph variants.
- **`assembler/`**: Python tools to assemble captured glyphs into handwritten SVG text.
- **`glyphs/`**: Storage for captured glyph data (JSON format). Personal glyph data is gitignored — capture your own.

## Quick Start

### 1. Capture Glyphs
1. Open `GlyphCollectorUI/GlyphCollectorUI.html` in a browser.
2. Draw multiple variants of characters.
3. Save them as JSON files (automatically saved to your downloads, move them to `glyphs/YourFont/`).

### 2. Generate Handwriting

```bash
cd assembler

# Direct text
python assembler.py "Hello World" output.svg --font YourFont --smooth

# From file (multiline)
python assembler.py --file letter.txt output.svg --font YourFont --smooth --line-height 250
```

## Features

- **True Single-Stroke**: Output paths are 1-pixel wide vectors — ready for pen plotters.
- **Curve Smoothing**: Catmull-Rom splines turn raw input into fluid, natural curves.
- **Micro-Variations**: Randomly selects from multiple variants of each character to avoid the "font" look.
- **Ligature Support**: Greedy matching for multi-character sequences (e.g., "sch", "tt", "th").
- **Optical Auto-Kerning**: Scanline-based algorithm calculates optimal letter spacing.
- **Multiline Support**: Render text files with configurable line height.
- **Pressure Data**: Preserves pressure information from the capture phase.
- **Multi-Font**: Organize different handwriting styles in separate `glyphs/` subdirectories.
- **Windows Safe**: Unicode hex filenames (e.g., `0041.json`) prevent case-insensitivity conflicts.

## Documentation

- [How to Create Realistic Handwriting](HowTo.md) — Step-by-step capture guide
- [Assembler Reference](assembler/README.md) — CLI options, kerning, ligatures
- [Glyph Collector UI](GlyphCollectorUI/README.md) — Capture tool documentation
- [Technical Design Document](Handwriting%20Simulation%20System%20TDD.md) — Architecture and data specification

## Requirements

- Python 3.10+
- Modern web browser (for Capture UI)
- A pen plotter (for the fun part)

## License

Copyright © 2025–2026 Uwe Trostheide

Licensed under the [GNU Affero General Public License v3.0](LICENSE).

Note: The VHS engine is open source. Your captured glyph data (your handwriting) is yours — keep it private or share it, your choice.
