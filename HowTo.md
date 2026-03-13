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

### 5.1 Using Multiline Files
For longer texts, save them as a `.txt` file and run:

**macOS/Linux:**
```bash
./vhs-cli.sh --file letter.txt output.svg --font MyHandwriting --line-height 120
```

**Windows:**
```cmd
vhs-cli.bat --file letter.txt output.svg --font MyHandwriting --line-height 120
```

*   `--file`: Reads the input from a text file.
*   `--line-height`: Controls the vertical gap between lines.

### 5.2 Paper Size and Line Spacing
To produce an SVG at a specific page size (useful for printing or pen plotters):

**macOS/Linux:**
```bash
./vhs-cli.sh --file letter.txt output.svg --font MyHandwriting \
  --paper-size A4 --orientation landscape --line-spacing 1.2 --margin 25
```

**Windows:**
```cmd
vhs-cli.bat --file letter.txt output.svg --font MyHandwriting \
  --paper-size A4 --orientation landscape --line-spacing 1.2 --margin 25
```

*   `--paper-size`: Sets a fixed page size (`A3`, `A4`, `A5`, `A6`, `Letter`, `Legal`). Content is automatically scaled to fit within the page area.
*   `--orientation`: `portrait` (default) or `landscape`.
*   `--line-spacing`: Multiplier for `--line-height` (e.g. `1.5` = 150% spacing).
*   `--margin`: Page margin in mm on all four sides (default: 20).

> **How auto-scaling works:** Glyph coordinates are captured in device units (e.g. tablet pixels), not millimetres. When a paper size is set, the renderer computes a uniform scale factor so the content bounding box fits within the available area (page minus margins). This means `--line-height` controls the *relative* spacing between lines — the absolute on-page size is determined automatically.

## 6. Troubleshooting

*   **"My letters are floating!"**: You likely ignored the Red Line during capture. Open the JSON file and check `baseline_y`. The assembler tries to fix this, but garbage in = garbage out.
*   **"It looks too perfect"**: Add `--jitter 1.0` to shake things up.
*   **"My text runs off the page"**: Make sure you are using `--paper-size`. The renderer automatically scales content to fit the page. Without a paper size, the SVG auto-fits to the content bounding box (no fixed dimensions).
