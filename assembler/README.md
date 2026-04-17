# VHS Assembler

The Assembler is the backend engine that converts input text and a library of vector glyphs into a "handwritten" SVG file.

## Usage

```bash
python assembler.py [TEXT] [OUTPUT_FILE] [OPTIONS]
```

### Arguments

- `text`: The string of text to render.
- `output`: The filename for the resulting SVG (e.g., `out.svg`).

### Options

- `--file [PATH]`, `-f [PATH]`: Read input text from a file instead of the command line.
- `--font [NAME]`: Name of the subdirectory in `glyphs/` to load glyphs from (e.g., `myFont`). Defaults to root `glyphs/`.
- `--paper-size [SIZE]`: Fixed paper size for the output SVG. Choices: `A3`, `A4`, `A5`, `A6`, `Letter`, `Legal`. When set, `--line-height-mm` or `--lines-per-page` is required.
- `--orientation [portrait|landscape]`: Page orientation. Default: `portrait`.
- `--margin [FLOAT]`: Page margin in mm on all sides (default: `20.0`). Doubles as the default for `--start-x` / `--start-y`.
- `--line-height-mm [FLOAT]`: Baseline-to-baseline line height in millimetres. Required with `--paper-size` unless `--lines-per-page` is used.
- `--lines-per-page [INT]`: Derive `--line-height-mm` so this many lines (times `--line-spacing`) fit in the writable page area.
- `--line-spacing [FLOAT]`: Multiplier on the line height (e.g. `1.3` = 30 % extra leading). Default: `1.0`.
- `--start-x [FLOAT]`, `--start-y [FLOAT]`: Top-left of the text block in mm (default: `--margin`).
- `--max-width-mm [FLOAT]`: Word-wrap width in mm (default: `page_w − margin − start-x`).
- `--stroke-width [FLOAT]`: Pen thickness in mm on paper (default: `2.0`; typical handwriting: `0.3`–`0.6`).
- `--color`: SVG colour name or `#rrggbb` (default: `black`).
- `--jitter [FLOAT]`: Gaussian noise on stroke points to simulate hand tremor. Default `0.0`. Try `0.5`–`1.5`.
- `--seed [INT]`: Random seed for deterministic jitter. If omitted, derived from the content.
- `--no-smooth`: Disable Catmull-Rom smoothing.
- `--auto-kern`: Enable zone-aware optical kerning.
- `--kern-aggressiveness [FLOAT]`: `0.0` – `1.0`. Higher = tighter on non-shared zones. Default: `0.5`.
- `--no-bezier`, `--no-normalize`: Ignore Bezier paths / normalized strokes stored in glyph JSON.

> **How page sizing works:** the renderer scales glyphs so that one glyph-unit line equals `--line-height-mm`. The scale applies uniformly to every stroke (widths, heights, tracking). Text is placed at `(start-x, start-y)` and wraps at `--max-width-mm`; it is **not** auto-shrunk to fit the page. See [`docs/USER_GUIDE.md`](../docs/USER_GUIDE.md) for the full walkthrough.

## Directory Structure

The assembler supports organizing glyphs into folders.
- Default: `glyphs/*.json`
- Named Font: `glyphs/myFont/*.json` (accessed via `--font myFont`)

Each font directory can have its own `kerning.json`.

## How It Works

1. **Loading**: Loads all `.json` glyph files from the `../glyphs` directory.
2. **Typesetting**:
   - Calculates spacing based on glyph bounding boxes.
   - Selects variants stochastically (randomly, but avoiding immediate repetition).
   - Applies kerning rules (if defined in `kerning.json`).
   - **Zone-aware optical kerning**: When `--auto-kern` is enabled, the scanline-based algorithm classifies each glyph's strokes into vertical zones (upper, ground, lower) using `baseline_y` and `x_height` from glyph metadata. Letter pairs occupying different zones (e.g., "Te") can kern tighter because their strokes don't collide. The `--kern-aggressiveness` parameter controls how much non-shared zones are relaxed.
   - Supports word wrapping via the `max_width` parameter — when a word would exceed the available width, the entire word is moved to the next line.
3. **Rendering**:
   - Generates an SVG with a single path element per stroke.
   - Applies jitter if requested.
   - **mm-based scaling**: The renderer chooses a scale factor equal to `--line-height-mm / native_glyph_line_height` and applies it uniformly to every stroke. Content is translated to `(start-x, start-y)` in millimetres. Stroke width is inversely scaled so the on-paper thickness equals `--stroke-width` mm.

## Ligatures
The assembler supports automatic ligature substitution via **Greedy Matching**.
- To add a ligature, save a glyph with the name of the sequence (e.g., `tt.json`, `sch.json`).
- If the assembler encounters "sch" in the text and `sch.json` exists, it will use that single glyph instead of `s`, `c`, and `h`.

## File Naming
The assembler supports two naming conventions for glyph files:
1.  **Direct**: `a.json`, `b.json`, `tt.json`. (Note: distinct files for `A` and `a` are not possible on Windows).
2.  **Unicode Hex**: `0061.json` (a), `0041.json` (A), `007300630068.json` (sch). This is the default output format of the Glyph Collector UI to ensure Windows compatibility.

## Kerning

The assembler looks for a `kerning.json` file in the same directory. This file can define:
- `space_width`: Width of a space character.
- `tracking_buffer`: Additional space between characters.
- `exceptions`: Specific rules for certain characters (e.g., minimum width for punctuation).

Example `kerning.json`:
```json
{
    "space_width": 30.0,
    "tracking_buffer": 5.0,
    "exceptions": {
        ".": { "min_width": 20.0 }
    }
}
```
