# VHS Assembler — User Guide

The Assembler turns plain text into a "handwritten" SVG using a library of
vector glyphs. Everything page-related is expressed in **millimetres** so the
output matches real paper: a 12 mm line on the page stays 12 mm regardless of
how much text you feed it.

---

## 1. Quick start

```bash
python3 assembler/assembler.py \
    --font font1 \
    --paper-size A5 --margin 10 \
    --line-height-mm 12 \
    --start-x 10 --start-y 10 \
    --stroke-width 0.4 \
    -f mytext.txt output/page.svg
```

That reads `mytext.txt`, lays it out on an A5 page, writes one 12 mm line at a
time starting 10 mm from the top-left corner, wraps at the right margin, and
draws with a 0.4 mm pen.

---

## 2. The layout model

Every coordinate you supply is a millimetre on the final page.

```
   0                 page_width
   ┌──────────────────────────┐   ← page_height = 0
   │                          │
   │     (start-x, start-y)   │
   │        ┌── text block ── ┤
   │        │                 │ ← each line is --line-height-mm tall
   │        │                 │   (line-to-line advance)
   │        │                 │
   │        │                 │
   │                          │
   └──────────────────────────┘   ← page_height
```

The Assembler picks a single scale factor that makes the glyphs' native line
height equal `--line-height-mm`. That scale then applies uniformly to every
stroke, so letter widths and heights are all consistent with the line height
you chose.

Word wrap happens at `--max-width-mm`: when a word would overflow, the whole
word is moved to the next line. `\n` in the input text forces a line break.
Text that runs off the bottom of the page is **not** auto-shrunk — you stay in
control.

---

## 3. CLI reference

### Input / output

| Flag | Purpose |
|------|---------|
| `text` (positional) | Inline text to render. Omit if using `--file`. |
| `output` (positional) | Output SVG path (required). |
| `--file`, `-f PATH` | Read input text from a file. |
| `--font NAME` | Glyph subdirectory under `glyphs/` (e.g. `font1`). |

### Page & layout (the important ones)

| Flag | Unit | Default | Purpose |
|------|------|---------|---------|
| `--paper-size` | — | (none) | One of `A3`, `A4`, `A5`, `A6`, `Letter`, `Legal`. Required for page output. |
| `--orientation` | — | `portrait` | `portrait` or `landscape`. |
| `--margin` | mm | `20` | Default page margin; also the fallback for `--start-x/--start-y`. |
| `--line-height-mm` | mm | — | **Baseline-to-baseline line height.** Required with `--paper-size` (unless `--lines-per-page` is used). |
| `--lines-per-page` | — | — | Alternative to `--line-height-mm`: derives it as `(page_h − 2·margin) / (N · line_spacing)`. |
| `--line-spacing` | ratio | `1.0` | Multiplier applied on top of the native glyph line height (e.g. `1.3` for 30 % extra leading). |
| `--start-x` | mm | `--margin` | X of the top-left of the text block. |
| `--start-y` | mm | `--margin` | Y of the top-left of the text block. |
| `--max-width-mm` | mm | `page_w − margin − start_x` | Word-wrap threshold. |

### Typesetting behaviour

| Flag | Unit | Default | Purpose |
|------|------|---------|---------|
| `--wrap-mode` | — | `balanced` | `balanced` runs a minimum-raggedness DP so line lengths stay uniform across the paragraph; `greedy` is the legacy first-fit wrap. |
| `--space-width-mm` | mm | (font default) | Width of a space. Handwriting looks more natural at **2–3 mm**; font defaults are often wider. |
| `--space-jitter-mm` | mm | `0.0` | Max ± random variation applied to every space width. `0.3`–`0.6` mm gives subtle "pen-on-paper" unevenness. Deterministic when `--seed` is set. |

### Realism / organic touch

| Flag | Unit | Default | Purpose |
|------|------|---------|---------|
| `--line-drift-angle` | degrees | `0.0` | Max ± per-line rotation. Real handwriting drifts; `0.2`–`0.5`° is plausible. |
| `--line-drift-y` | mm | `0.0` | Max ± per-line baseline wobble. Try `0.2`–`0.6` mm. |

### Multi-page

| Flag | Default | Purpose |
|------|---------|---------|
| `--paginate` | off | Split content across numbered files (`output-01.svg`, `output-02.svg`, …) when it overflows the page height. Requires `--paper-size`. |

### Ink & style

| Flag | Unit | Default | Purpose |
|------|------|---------|---------|
| `--stroke-width` | mm | `2.0` | Pen thickness on paper. Typical handwriting: `0.3`–`0.6`. |
| `--color` | — | `black` | Any SVG colour name or `#rrggbb`. |
| `--jitter` | mm-ish | `0.0` | Gaussian noise per stroke point. Try `0.5`–`1.5`. |
| `--seed` | int | derived | Fix the RNG for reproducible jitter / space-jitter / line-drift. |
| `--no-smooth` | flag | off | Disable Catmull-Rom smoothing. |

### Kerning

| Flag | Default | Purpose |
|------|---------|---------|
| `--auto-kern` | off | Enable zone-aware optical kerning. |
| `--kern-aggressiveness` | `0.5` | 0.0 = conservative, 1.0 = fully tighten non-shared zones. |

### Bezier / normalization (advanced)

| Flag | Purpose |
|------|---------|
| `--no-bezier` | Ignore Bezier paths stored in the glyph JSON. |
| `--no-normalize` | Ignore normalized strokes stored in the glyph JSON. |

---

## 4. Recipes

**10 lines of text on A5, big and loose:**

```bash
python3 assembler/assembler.py \
    --font font1 \
    --paper-size A5 --margin 10 \
    --lines-per-page 10 --line-spacing 1.2 \
    --stroke-width 0.5 --jitter 0.4 \
    -f note.txt output/a5-10-lines.svg
```

**A4 letter with a specific text block:**

```bash
python3 assembler/assembler.py \
    --font font1 \
    --paper-size A4 --margin 20 \
    --line-height-mm 8 --line-spacing 1.3 \
    --start-x 25 --start-y 40 \
    --max-width-mm 160 \
    --stroke-width 0.4 --auto-kern \
    -f letter.txt output/letter.svg
```

**Landscape A4, dense:**

```bash
python3 assembler/assembler.py \
    --font font1 \
    --paper-size A4 --orientation landscape \
    --lines-per-page 18 --line-spacing 1.1 \
    --stroke-width 0.35 \
    -f transcript.txt output/transcript.svg
```

**Natural, multi-page manuscript:**

```bash
python3 assembler/assembler.py \
    --font font1 \
    --paper-size A4 --margin 20 \
    --line-height-mm 10 --line-spacing 1.3 \
    --space-width-mm 2.5 --space-jitter-mm 0.4 \
    --line-drift-angle 0.3 --line-drift-y 0.4 \
    --stroke-width 0.4 --jitter 0.4 --auto-kern \
    --paginate --seed 42 \
    -f novel.txt output/novel.svg
# writes output/novel-01.svg, output/novel-02.svg, ...
```

---

## 5. Sizing cheat-sheet

For human-readable handwriting, `--line-height-mm` is typically **6–12 mm** and
`--stroke-width` is **0.3–0.6 mm**. Keep `--line-spacing` at `1.0`–`1.4`.

Rough characters-per-line for font1 at 170 mm wrap width:

| line-height-mm | approx. chars/line |
|----------------|--------------------|
| 6 | ~55 |
| 8 | ~40 |
| 10 | ~32 |
| 12 | ~27 |

(Numbers depend on the font, kerning, and text.)

If a run of text overflows the bottom of the page, either lower
`--line-height-mm`, raise `--max-width-mm`, or split the input across pages
yourself — the Assembler will not auto-shrink to fit.

---

## 6. How it works under the hood

1. **Typesetter** walks the input text and places glyphs in an internal
   coordinate system (glyph units). Ligatures match greedily; word-wrap
   triggers when the cursor exceeds `max_width` (computed internally from
   `--max-width-mm`).
2. **Renderer** emits one SVG path per stroke, wrapped in a `<g>` with
   `transform="translate(start-x, start-y) scale(mm_per_glyph) translate(...)"`.
   That single transform converts every glyph-unit coordinate into millimetres
   on the page.
3. **Stroke width** is divided by the scale inside the SVG so the final
   on-paper thickness equals `--stroke-width` mm regardless of glyph scale.
4. **Jitter** and **smoothing** are applied in glyph units before scaling, so
   the visible wobble is proportional to the letter size.

The glyph's "native" line height (`100` by default, configurable per-font in
each font's `kerning.json`) is what `--line-height-mm` is scaled against.

---

## 7. Web GUI

An optional browser UI wraps the same Assembler:

```bash
pip install flask
./vhs-gui.sh        # or: python3 assembler/server.py
# open http://localhost:5001
```

All mm-based controls from the CLI are exposed in the sidebar: paper size,
orientation, margin, start-x / start-y, max width (mm), line height (mm) or
lines/page, line spacing, stroke width (mm), colour, jitter, auto-kern, and
the kerning aggressiveness slider. Selecting a paper size requires either
"Line Height (mm)" or "Lines / Page"; leaving paper size on "Auto-fit" falls
back to bounding-box output for quick previews.

---

## 8. Custom fonts

Drop glyph JSON files into `glyphs/<yourfont>/` and select with
`--font yourfont`. Optionally include a `glyphs/<yourfont>/kerning.json` with
`space_width`, `tracking_buffer`, `line_height`, and per-character
`exceptions`.

See `assembler/README.md` for the glyph format and kerning schema details.
