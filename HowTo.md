# How to Create Realistic Handwriting with VHS

This guide will walk you through the process of capturing your handwriting and generating vector text suitable for pen plotters.

## 1. Setup

1.  **Open the Collector**: Navigate to `VHS/GlyphCollectorUI/GlyphCollectorUI.html` and open it in a modern web browser (Chrome/Edge recommended).
2.  **Input Device**: For best results, use a **Graphics Tablet** (Wacom, Huion) or an iPad with Pencil (via Sidecar/EasyCanvas). You *can* use a mouse, but it will look like mouse-writing.

## 2. Capturing Glyphs (The Art)

The quality of your output depends entirely on the quality of your input.

### Alignment is Key
*   **The Red Line**: This is your **Baseline**.
    *   Letters like `a`, `b`, `c`, `A`, `H` should sit **on** this line.
    *   Letters like `g`, `j`, `y`, `q`, `p` should have their distinct tails hanging **below** this line.
*   **The Blue Line**: This is the **x-Height**.
    *   Ideally, the top of your `a`, `c`, `e`, `o` should touch this line.

### Template Overlay
The Collector UI can display a **semi-transparent handwriting font** behind each canvas slot as a guide. Select a template font from the dropdown — 17 Google Fonts are available in two groups:
*   **Formal**: Clean, structured styles for precise letterforms.
*   **Casual**: Loose, natural styles for relaxed handwriting.

The overlay helps you maintain consistent sizing, baseline alignment, and proportions across all your glyph variants. Adjust the opacity or disable the overlay entirely from the settings panel.

### Smooth Preview
The Collector UI applies **live Catmull-Rom smoothing** to the canvas so you can see how your strokes will look after the assembler processes them. Click the **Smooth** button in the header to toggle between the smoothed preview and the raw polygonal capture. Note: this is visual-only — the exported JSON always contains the raw capture data.

### Consistency vs. Variation
*   **Draw Naturally**: Use your normal writing speed. Slowing down creates "shaky" lines (jitter).
*   **Create Variants**: Draw 5-10 versions of each letter.
    *   Make them slightly different! If they are identical, the result looks fake.
    *   Slightly vary the angle, the loop size, or the starting point.

## 3. Organizing Your Font

1.  Create a folder `VHS/glyphs/MyHandwriting/`.
2.  In the Collector UI, enter a character (e.g., `a`) and draw your variants.
3.  Press **Enter** or "Save JSON".
4.  A file named `0061.json` (hex for 'a') will download. Move this to your font folder.
5.  Repeat for `a`-`z`, `A`-`Z`, `0`-`9`, and punctuation.

## 4. Advanced Techniques: Mimicking Cursive

The system builds text one block at a time, which is naturally better for "Print" style. However, you can cheat to achieve a Cursive or Hybrid look.

### The "Ligature" Trick
Ligatures are special glyphs that represent multiple characters (e.g., "tt" or "sch"). You can use them to fix awkward connections.

1.  In the Collector input box, type the sequence (e.g., `tt`).
2.  Draw the two 't's connected exactly how you want them to look.
3.  Save. It will be named `00740074.json`.

**When the assembler sees "butter", it will prioritize your `tt` glyph over two separate `t` glyphs.**
*   **Common Candidates**: `th`, `he`, `in`, `er`, `an`, `re`, `on`, `at`, `en`, `nd`, `sch`, `ch`.

### Zone-Aware Auto-Kerning
The assembler's `--auto-kern` flag uses a scanline-based algorithm that understands vertical zones. Each glyph's strokes are classified as **upper** (above x-height), **ground** (between x-height and baseline), or **lower** (below baseline) based on the `baseline_y` and `x_height` stored in glyph metadata.

When two letters occupy different zones (e.g., "Te" — T has upper strokes, e sits in the ground zone), the kerning algorithm allows them to move closer because their strokes won't collide. Use `--kern-aggressiveness` (0.0–1.0) to control how much tighter non-overlapping zones are kerned:
*   `0.0` = no extra tightening (same as non-zone-aware kerning)
*   `0.5` = moderate (default)
*   `1.0` = fully ignore non-shared zones (maximum tightening)

```bash
./vhs-cli.sh "The quick brown fox" output.svg --font MyHandwriting --auto-kern --kern-aggressiveness 0.7
```

### The "Negative Tracking" Trick
To make letters touch (for a cursive look):
1.  Create a `kerning.json` file in your font folder.
2.  Set a **negative** `tracking_buffer`.

```json
{
    "space_width": 30.0,
    "tracking_buffer": -5.0,
    "line_height": 100.0,
    "exceptions": {
        ".": { "min_width": 15.0 }
    }
}
```
This forces the next character to start *before* the previous one ends, creating overlaps.

## 4b. Bezier Curve Fitting

When you save glyphs, the Collector automatically fits **cubic Bezier curves** to your raw strokes using the Schneider algorithm. This produces smoother, more compact path data:

*   **Adaptive corner detection**: Sharp direction changes are preserved as segment boundaries.
*   **Newton-Raphson refinement**: Control points are iteratively optimized for the best fit.
*   The fitted curves are stored as `bezier_curves` in the glyph JSON alongside the raw `strokes`.

The assembler uses Bezier curves by default when available. Use `--no-bezier` to fall back to Catmull-Rom smoothed polylines.

## 4c. Stroke Normalization

The Collector also computes **normalized strokes** that correct for common capture inconsistencies:

*   **Slant correction**: Compensates for unintentional italic lean.
*   **Pressure smoothing**: Evens out erratic pressure spikes from tablet input.
*   **Height normalization**: Scales strokes to a consistent x-height.
*   **Strength blending**: Controls how aggressively corrections are applied (0.0 = no correction, 1.0 = full).

Normalized strokes are stored as `normalized_strokes` in the glyph JSON. The assembler uses them automatically when available. Use `--no-normalize` to fall back to raw strokes.

### Assembler Priority Chain

The assembler picks the best available data for each glyph:

1.  `bezier_curves` → SVG cubic Bezier `C` commands (smoothest)
2.  `normalized_strokes` → corrected points with Catmull-Rom smoothing
3.  `strokes` → raw capture points with optional smoothing

Use `--no-bezier` and/or `--no-normalize` to override this chain.

## 5. Generating Text

Use the provided start scripts in the project root to run the assembler.

**macOS/Linux:**
```bash
./vhs-cli.sh "Your text here" output.svg --font MyHandwriting
```

**Windows:**
```cmd
vhs-cli.bat "Your text here" output.svg --font MyHandwriting
```

*   `--font MyHandwriting`: Tells it to look in `glyphs/MyHandwriting/`.
*   Smoothing is enabled by default (Catmull-Rom splines turn raw input into fluid, curvy strokes). Use `--no-smooth` to disable it and get raw polygonal output.
*   `--no-bezier`: Skip Bezier curve rendering — fall back to normalized or raw strokes.
*   `--no-normalize`: Skip normalized strokes — use raw capture points (with Bezier or smoothing).

### 5.1 Using Multiline Files
For longer texts, save them as a `.txt` file and run:

**macOS/Linux:**
```bash
./vhs-cli.sh --file letter.txt output.svg --font MyHandwriting \
  --paper-size A4 --margin 20 --line-height-mm 10
```

**Windows:**
```cmd
vhs-cli.bat --file letter.txt output.svg --font MyHandwriting ^
  --paper-size A4 --margin 20 --line-height-mm 10
```

*   `--file`: Reads the input from a text file.
*   `--line-height-mm`: Baseline-to-baseline line height in millimetres. Required when `--paper-size` is set (unless `--lines-per-page` is used).

### 5.2 Paper Size and Line Layout
To produce an SVG at a specific page size (useful for printing or pen plotters):

**macOS/Linux:**
```bash
./vhs-cli.sh --file letter.txt output.svg --font MyHandwriting \
  --paper-size A4 --orientation landscape --margin 25 \
  --line-height-mm 8 --line-spacing 1.2 --stroke-width 0.4
```

**Windows:**
```cmd
vhs-cli.bat --file letter.txt output.svg --font MyHandwriting ^
  --paper-size A4 --orientation landscape --margin 25 ^
  --line-height-mm 8 --line-spacing 1.2 --stroke-width 0.4
```

*   `--paper-size`: Sets a fixed page size (`A3`, `A4`, `A5`, `A6`, `Letter`, `Legal`).
*   `--orientation`: `portrait` (default) or `landscape`.
*   `--margin`: Page margin in mm on all four sides (default: `20`). Also the fallback origin when `--start-x`/`--start-y` are omitted.
*   `--line-height-mm`: Baseline-to-baseline line height in mm.
*   `--lines-per-page`: Alternative to `--line-height-mm`: derives it as `(page_h − 2·margin) / (N · line_spacing)`.
*   `--line-spacing`: Multiplier on top of the line height (e.g. `1.3` = 30 % extra leading).
*   `--start-x`, `--start-y`: Top-left of the text block in mm (default: `--margin`).
*   `--max-width-mm`: Word-wrap width in mm (default: `page_w − margin − start-x`).
*   `--wrap-mode`: `balanced` (default, minimum-raggedness DP) or `greedy` (legacy first-fit).
*   `--space-width-mm`, `--space-jitter-mm`: Width of a space in mm, and per-space ± variation. 2.5 mm with 0.4 mm jitter reads as natural handwriting.
*   `--line-drift-angle`, `--line-drift-y`: Per-line rotation (deg) and baseline wobble (mm) for an organic drifting-hand effect. Try `0.3` and `0.4`.
*   `--paginate`: Split content that overflows the page into numbered files (`output-01.svg`, `output-02.svg`, …).
*   `--stroke-width`: Pen thickness in mm on paper (default: `2.0`; typical handwriting: `0.3`–`0.6`).

> **How mm layout works:** Glyph coordinates are captured in device units (tablet pixels). The renderer multiplies them by a single scale factor so that one glyph-unit line equals `--line-height-mm`, then places the block at `(start-x, start-y)`. Content is **not** auto-shrunk to fit the page — short texts stay their real size and long texts can overflow, so you keep precise control. Stroke width is inversely scaled so `--stroke-width 0.4` gives a 0.4 mm pen regardless of glyph scale.
>
> See [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) for the full layout model, recipes, and a sizing cheat-sheet.

## 6. Troubleshooting

*   **"My letters are floating!"**: You likely ignored the Red Line during capture. Open the JSON file and check `baseline_y`. The assembler tries to fix this, but garbage in = garbage out.
*   **"It looks too perfect"**: Add `--jitter 1.0` to shake things up. Jitter is deterministic — the same input produces the same output. Use `--seed 42` to get a different jitter pattern.
*   **"My text runs off the page"**: Make sure you are using `--paper-size`. The renderer automatically scales content to fit the page. Without a paper size, the SVG auto-fits to the content bounding box (no fixed dimensions).
