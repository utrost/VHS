# Vector Handwriting System (VHS)

**🌐 Live Demo:** [utrost.github.io/VHS](https://utrost.github.io/VHS/) · [simiono.com/vhs](https://simiono.com/vhs/)

VHS is a deterministic pipeline for generating realistic handwriting for pen plotters. It replaces neural-network-based generation with a stochastic "Shaping Engine" utilizing a custom-captured library of single-stroke vector glyphs.

## Project Structure

- **`GlyphCollectorUI/`**: A browser-based tool for capturing handwriting glyph variants.
- **`assembler/`**: Python tools to assemble captured glyphs into handwritten SVG text.
- **`glyphs/`**: Storage for captured glyph data (JSON format). Personal glyph data is gitignored.
- **`vhs-cli.*` / `vhs-gui.*`**: Platform-specific scripts to run the CLI and Web UI from the root.

![VHS Glyph Collector — capturing handwriting variants](docs/glyph-collector.jpg)

### Example Output

![Example: "Hello World" rendered by VHS](docs/example-hello-world.png)

*Generated SVG output — single-stroke paths ready for pen plotting.*

## Quick Start

### 1. Capture Glyphs
1. Open `GlyphCollectorUI/GlyphCollectorUI.html` in a browser.
2. Draw multiple variants of characters.
3. Save them as JSON files (automatically saved to your downloads, move them to `glyphs/YourFont/`).

### 2. Generate Handwriting (CLI)

Use the provided start scripts for your platform:

**macOS/Linux:**
```bash
./vhs-cli.sh "Hello World" output.svg --font YourFont
./vhs-cli.sh --file letter.txt output.svg --font YourFont --paper-size A4 --line-spacing 1.5 --margin 25
```

**Windows:**
```cmd
vhs-cli.bat "Hello World" output.svg --font YourFont
vhs-cli.bat --file letter.txt output.svg --font YourFont --paper-size A4 --line-spacing 1.5 --margin 25
```

### 3. Web UI

**macOS/Linux:**
```bash
./vhs-gui.sh
```

**Windows:**
```cmd
vhs-gui.bat
```

Open [http://localhost:5001](http://localhost:5001) in your browser.

The web UI provides a modern visual interface with live SVG preview, file upload, paper size presets, and real-time adjustment of all assembler parameters.

## Features

- **True Single-Stroke**: Output paths are 1-pixel wide vectors — ready for pen plotters.
- **Fixed Paper Sizes**: Support for A3, A4, A5, A6, Letter, and Legal with Portrait/Landscape orientation. Content is automatically scaled to fit within the page area.
- **Micro-Variations**: Randomly selects from multiple variants of each character to avoid the "font" look.
- **Curve Smoothing**: Catmull-Rom splines turn raw input into fluid, natural curves.
- **Zone-Aware Auto-Kerning**: Scanline-based algorithm calculates optimal letter spacing with vertical zone awareness (upper/ground/lower). Letters in non-overlapping zones kern tighter. Configurable aggressiveness (0.0–1.0).
- **Ligature Support**: Greedy matching for multi-character sequences (e.g., "sch", "tt", "th").
- **Typography Controls**: Advanced control over line height, line spacing (multiplier), and page margins. Word wrapping is supported via the `max_width` parameter.
- **Pressure Data**: Preserves pressure information from the capture phase.
- **Multi-Font**: Organize different handwriting styles in separate `glyphs/` subdirectories.
- **Windows Safe**: Unicode hex filenames (e.g., `0041.json`) prevent case-insensitivity conflicts.

## Testing

The system includes a comprehensive automated test suite:
- **Unit Tests**: 11 tests covering the core engine logic (kerning, zone-aware kerning, ligatures, metrics).
- **CLI Tests**: 30 tests verifying the command-line interface, including paper sizes, margins, kerning aggressiveness, deterministic jitter, and error handling.

Run all tests:
```bash
cd assembler
python3 -m unittest test_assembler test_cli -v
```

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
