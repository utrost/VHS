# VHS roadmap

This page separates what already works from what is still a candidate. The root README is for first-time users. This file is for deciding what to build next.

## Current baseline

VHS is usable today as a local plotter-oriented handwriting tool.

Shipped:

- Browser glyph capture with multiple variants per character.
- Folder-connected capture in browsers that support the File System Access API, with download fallback elsewhere.
- Local web app with Capture and Assemble tabs.
- Live SVG preview, coverage feedback, presets, PNG/PDF export, and on-page editing.
- Multiple text frames through the GUI and `--frames` on the CLI.
- CLI output for SVG, PNG, and PDF.
- Millimetre-based page controls: paper size, margin, line height, start position, wrapping width, spacing, stroke width.
- Balanced wrapping, pagination, widow/orphan handling, and layout reports.
- Unicode fallbacks and strict glyph checks.
- Per-line drift, per-glyph slant/y jitter, smoothing, Bezier paths, normalization, ligatures, and zone-aware kerning.

Current public demo:

- The hosted page is a collector only. It captures glyph JSON and downloads it.
- Full assembly needs the local app or the CLI.

## Ground rules

- Keep the default output plotter-friendly: stroked SVG paths, no filled font outlines.
- Keep page controls in millimetres.
- Keep the hosted collector small. Do not rebuild the full typesetter inside the static collector unless the project explicitly moves to a browser-only build.
- New assembler features should work in both the CLI and the local GUI unless one side makes no sense. Document exceptions.
- Prefer real plotted output over more private polishing. If a change affects handwriting quality, test a short SVG on paper.

## Good next work

### 1. Real plotter smoke tests

Status: next useful validation.

Run a small set of generated SVGs through the actual plotter workflow. Check scale, pen-up behaviour, path order, repeated letters, line rhythm, and import quirks in the plotter software.

Useful samples:

- One short phrase with repeated letters.
- One A5 note.
- One A4 page with line drift and balanced wrapping.
- One multi-frame page.

Outcome: document any plotter-specific fixes. Do not guess from screen output alone.

### 2. Better sample fonts and sample texts

Status: useful for adoption.

The shipped `glyphs/font1` lets people test the tool, but a public release benefits from known-good samples:

- a tiny starter font for a quick smoke test,
- a fuller sample font for screenshots and CLI examples,
- sample text files sized for A5 and A4.

Keep sample glyphs clearly separate from personal handwriting data.

### 3. Cursive joining

Status: future candidate, opt-in only.

Idea: use entry/exit metadata on glyphs to draw short connector strokes between compatible letters.

Why this is still future work:

- Bad joins look worse than no joins.
- Existing block-print glyphs may not have useful entry/exit points.
- Cursive quality depends on how the glyphs were captured, not only on the algorithm.

If built, ship it as experimental and off by default. The detailed design lives in [`R2_CURSIVE_JOINING_PLAN.md`](R2_CURSIVE_JOINING_PLAN.md).

### 4. Static browser build

Status: future candidate.

The hosted collector is static today, but the assembler runs locally through Python/Flask. A browser-only build could use Pyodide so a user can capture glyphs and assemble text without running a local server.

This is not required for the first public release. The detailed plan lives in [`PYODIDE_STATIC_BUILD_PLAN.md`](PYODIDE_STATIC_BUILD_PLAN.md).

### 5. Plotter import compatibility notes

Status: documentation candidate.

Different plotter tools treat SVGs differently. Add short notes once there is evidence from real software and hardware:

- Inkscape
- vpype
- AxiDraw-style workflows
- iDraw / other pen plotter workflows
- common browser or SVG viewer traps

Keep this evidence-based. No compatibility table without a tested file.

## Parked work

### Pressure-aware stroke width

Status: parked.

VHS stores pressure data from capture. Rendering variable-width strokes is not a priority because the main target is pen plotting with a physical pen of fixed width. Filled pressure ribbons may look better on screen, but they are a different output mode and can make plotting worse.

Revisit only if screen/print output becomes a main goal or a target plotter can use pressure-like width changes in a practical way.

## Done, but worth remembering

These used to be roadmap items and are now part of the baseline:

- Live preview.
- Presets and config files.
- Layout reports.
- Coverage feedback.
- Unicode fallbacks.
- PNG/PDF export.
- Pagination with widow/orphan control.
- On-page editing.
- Multiple text frames.
- Glyph collector queue, coverage, connected-folder save, and edit-existing-glyph flow.
