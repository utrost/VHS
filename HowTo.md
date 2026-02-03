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

### The "Negative Tracking" Trick
To make letters touch (for a cursive look):
1.  Create a `kerning.json` file in your font folder.
2.  Set a **negative** `tracking_buffer`.

```json
{
    "space_width": 30.0,
    "tracking_buffer": -5.0,
    "exceptions": {
        ".": { "min_width": 15.0 }
    }
}
```
This forces the next character to start *before* the previous one ends, creating overlaps.

## 5. Generating Text

Open your terminal in `VHS/assembler/` and run:

```bash
python assembler.py "Your text here" output.svg --font MyHandwriting --smooth
```

*   `--font MyHandwriting`: Tells it to look in `glyphs/MyHandwriting/`.
*   `--smooth`: Turns your jagged input points into fluid, curvy strokes (highly recommended for realism).

## 6. Troubleshooting

*   **"My letters are floating!"**: You likely ignored the Red Line during capture. Open the JSON file and check `baseline_y`. The assembler tries to fix this, but garbage in = garbage out.
*   **"It looks too perfect"**: Add `--jitter 1.0` to shake things up.
