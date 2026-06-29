# VHS Assembler — Web GUI Guide

A walkthrough of the browser UI at `http://localhost:5001`. Every
knob in the sidebar has a matching CLI flag; start here when you want
to see changes as you make them.

> Start the server with `./vhs-gui.sh` (or `python3 assembler/server.py`)
> and open [http://localhost:5001](http://localhost:5001).

---

## 1. The layout

![GUI overview](img/gui-overview.png)

The sidebar is divided into sections that mirror the flag groups in the
CLI guide:

- **Text / Font** — text input, font family, file upload.
- **Preset** — bundled recipes (see `docs/USER_GUIDE.md` §4) with a
  **Save…** button that exports the current sidebar state as YAML.
- **Page Setup** — paper size, orientation, margin, explicit start-x /
  start-y, max-width (all mm).
- **Typography** — line height mm (or lines/page), spacing, wrap mode,
  space width and jitter.
- **Styling** — smoothing, auto-kern, fallbacks, jitter, stroke width,
  ink colour, line drift, per-glyph jitter.
- **Sidebar actions** — live-preview toggle, Generate, and SVG / PNG /
  PDF download buttons.

The right-hand **preview** area shows the currently rendered SVG and
updates live as you change controls.

The top bar has two tabs: **✦ Assemble** (this view) and **✍ Capture
glyphs**, which embeds the GlyphCollector in the same window. Capture a
glyph there and switch back — the font list refreshes automatically and
your new glyph is ready to typeset (a capture → assemble round trip; see
the GlyphCollector guide for details).

---

## 2. Live preview

![Sidebar controls](img/gui-sidebar.png)

With the **Live Preview** toggle on (default), any change to a control
triggers a fresh render 350 ms after the last input. Superseded
requests are cancelled so stale renders never overwrite fresh ones.
The server caches loaded glyph libraries across requests, so steady-
state updates are ~20× faster than a cold render.

Disable the toggle to fall back to click-to-generate when you want to
batch changes.

### Actual size vs fit-to-window

The preview defaults to **fit-to-window** (the page is scaled to fit the
panel). The **⊞ Actual size** button in the toolbar switches to a **1:1**
view, where the page renders at its real physical dimensions — an A5 page
is shown A5-sized, A4 A4-sized, and so on — and the panel scrolls if the
page is larger than the window. Click **⊟ Fit to window** to switch back.

This relies on CSS millimetre units, so it's true-to-life at **100 %
browser zoom** on a calibrated display; if your monitor's DPI is
non-standard it will be close but not exact. Paper size and orientation
(portrait / landscape) both feed the displayed dimensions, shown in the
top-right of the toolbar (e.g. `148.0mm × 210.0mm`).

---

## 3. Presets

The **Preset** dropdown loads a bundled recipe from
`configs/presets/`:

| Preset | What it is |
|---|---|
| `letter-a4` | Formal A4 letter, 10 mm lines, subtle organic jitter. |
| `letter-a5` | Note-sized A5, 8 mm lines. |
| `notebook-page` | Compact ruled-paper feel, 6 mm lines. |
| `casual-a4` | Looser handwriting, bigger drift + per-glyph jitter. |
| `architects-a3` | Landscape A3 drafting-style capitals, 15 mm lines. |

The **Save…** button prompts for a filename and downloads the current
sidebar state as a YAML file you can drop into `configs/presets/` (or
pass to `--config`). CLI and GUI share the same preset format.

---

## 4. The Coverage panel

![Coverage panel with substituted and missing characters](img/gui-coverage.png)

When the rendered text contains characters the font doesn't cover, a
**Glyph coverage** panel appears beneath the preview:

- **Substituted** — codepoints replaced by the Unicode fallback map
  (em-dash → `--`, curly quotes → straight, ellipsis → `...`, …). Each
  entry shows the original → replacement and the count.
- **Missing** — codepoints neither the font nor the fallback map
  covered. Each entry shows a short snippet from the source text so you
  can find the offending character.

The panel stays hidden while the text is fully covered. Disable the
fallback pass with the **Unicode Fallbacks** toggle in the Styling
section — handy when you want to see exactly which characters your
font is missing.

---

## 5. Exporting

- **SVG** — always available. The vector original, ready for pen
  plotters or lossless printing.
- **PNG** — requires `cairosvg`. Uses the **PNG DPI** field (default
  300) and the **transparent** checkbox.
- **PDF** — requires `cairosvg` + `pypdf`. Exports the current preview
  as a one-page PDF. Multi-page PDFs come from the CLI's `--paginate
  --format pdf` combination.

---

## 6. Edit on page (WYSIWYG)

Click **✎ Edit on page** in the preview toolbar to turn the rendered
page into the editing surface. The button needs a **paper size** selected
(positions are in millimetres); in auto-fit mode it shows a hint instead.

What you get on the page:

- **Type on the page.** A transparent text layer sits exactly over the
  rendered handwriting — type into it and the handwriting re-renders live
  underneath. It mirrors the sidebar **Text** box (they stay in sync).
- **Drag to position.** A square **move** handle at the text block's
  top-left sets **start-x / start-y**; a round **width** handle on the
  right edge sets **max-width**; a purple handle at the top-centre of the
  page sets the **margin**. A small label shows the live mm values. Every
  gesture writes the matching sidebar field — there's one source of truth.
- **Click-to-caret.** Click anywhere on the handwriting to place the text
  caret at that letter (it snaps to the nearest glyph), so editing lands
  where you point rather than where a hidden textarea would guess.
- **Ruled line guides** show the writing lines at the current pitch.
- **Fit chip** (top-left of the preview) has **line-height** and
  **spacing** `−/+` steppers and a live **"≈ N lines fit"** readout. If the
  text runs past the writable area the chip warns **"overflows by ~K
  lines"** and the text block turns amber.

### Multiple text frames

Click **➕ Frame** to add another independently-positioned block — a
heading box plus a body column, a margin note, two columns, etc. Each
extra frame is drawn in green with its own:

- draggable **box** (move + width handles) writing that frame's
  start-x / start-y / max-width,
- transparent **textarea** (type on it; click-to-caret works per frame),
- **label** (`Frame 2: x, y mm`) and a red **✕** to delete it.

Frame 0 stays the sidebar-driven block. Overlap is allowed (later frames
draw on top) but intersecting frames are flagged with an amber dashed
outline. Deleting the last extra frame reverts to the single-text render.

Under the hood the editor sends the same `frames` payload the CLI's
`--frames` flag uses (see the CLI guide §11), so a multi-frame layout you
build here is reproducible from the command line.

---

## 7. CLI / GUI parity

Every non-paginate flag has a matching GUI field. The documented
CLI-only features are:

- `--paginate` (the GUI shows a single preview).
- `--report` and `--report-format` (output is a text / JSON dump,
  not a rendered file).
- `--strict-glyphs` (CI gate — same reason).

Conversely, **Edit on page** (drag-to-position, click-to-caret, on-page
typing) is a GUI-only *interaction* — it introduces no capability the CLI
lacks: every gesture resolves to an existing flag, and multi-frame layouts
map to `--frames`. See `docs/ROADMAP.md` → *Ground rules* and the
`U7` entries.

When a new flag lands on the CLI, a matching GUI input lands in the
same pull request.

---

## 8. How to refresh the screenshots in this guide

Screenshots in this guide are captured by
`docs/tools/capture_screenshots.py`. Start the server in one terminal,
then run the script in another:

```bash
./vhs-gui.sh
# in a second terminal
python3 docs/tools/capture_screenshots.py
```

Images land in `docs/img/`. The script uses seeded sample text so
repeated runs produce visually identical shots unless the UI itself
changed.
