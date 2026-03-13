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
- `--jitter [FLOAT]`: Apply Gaussian noise to the points to simulate organic shake/imperfection. Default is `0.0`. Suggested values: `0.5` - `1.5` depending on desired messiness. Jitter is deterministic (same input produces same output). Use `--seed` to override.
- `--seed [INT]`: Random seed for deterministic jitter. If omitted, a stable seed is derived from the content itself.
- `--no-smooth`: Disable Catmull-Rom spline smoothing (smoothing is enabled by default). Smoothing uses adaptive interpolation — short segments get fewer steps, long curves get more.
- `--line-height [FLOAT]`: Override the vertical space between lines (default: 100.0).
- `--line-spacing [FLOAT]`: Multiplier for line height (e.g. `1.5` = 150% spacing). Default: `1.0`.
- `--paper-size [SIZE]`: Fixed paper size for the output SVG. Choices: `A3`, `A4`, `A5`, `A6`, `Letter`, `Legal`.
- `--orientation [portrait|landscape]`: Page orientation when `--paper-size` is set. Default: `portrait`.
- `--margin [FLOAT]`: Page margin in mm on all sides (default: 20.0). Used with `--paper-size`.
- `--auto-kern`: Enable automatic optical kerning to reduce whitespace.
- `--kern-aggressiveness [FLOAT]`: How aggressively zone-aware kerning tightens non-overlapping zones (0.0–1.0). `0.0` = no extra tightening, `1.0` = fully ignore non-shared zones. Default: `0.5`. Only effective with `--auto-kern`.
- `--stroke-width [FLOAT]`: Stroke width in SVG units (default: 2.0). Automatically scaled in fixed-page mode to maintain consistent visual weight.

> **Note:** When `--paper-size` is set, the renderer automatically scales the content to fit within the available page area (page minus margins). Glyph coordinates (captured in device units) are mapped to millimetres via this uniform scale. Changing `--line-height` or `--line-spacing` adjusts the relative proportions between lines; the final on-page size is determined by the auto-scale.

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
   - **Auto-scaling**: When a fixed paper size is set, the renderer computes the content bounding box and applies a uniform scale transform so that all content fits within the available page area (page dimensions minus margins). Stroke width is inversely scaled to remain visually consistent.

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
