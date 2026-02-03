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

- `--font [NAME]`: Name of the subdirectory in `glyphs/` to load glyphs from (e.g., `myFont`). Defaults to root `glyphs/`.
- `--jitter [FLOAT]`: Apply Gaussian noise to the points to simulate organic shake/imperfection. Default is `0.0`. Suggested values: `0.5` - `1.5` depending on desiredMessiness.
- `--smooth`: Enable Catmull-Rom spline smoothing to create fluid curves from captured points.

## Directory Structure

The assembler supports organizing glyphs into folders.
- Default: `glyphs/*.json`
- Named Font: `glyphs/myFont/*.json` (accessed via `--font myFont`)

Each font directory can have its own `kerning.json`.

## How It Works

1. **Loading**: Loads all `.json` glyph files from the `../glyphs` directory.
2. **Typesetting**:
   - Calculates spacing based on glyph bounding boxes.
   - select variants stochastically (randomly, but avoiding immediate repetition).
   - Applies kerning rules (if defined in `kerning.json`).
3. **Rendering**:
   - Generates an SVG with a single path element per stroke.
   - Applies jitter if requested.

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
