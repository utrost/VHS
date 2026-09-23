# VHS architecture note

This file describes the current shape of VHS. It is not a roadmap.

## Purpose

VHS converts typed text into handwriting-style vector paths for pen plotters. A user captures glyph variants with a pen or tablet, saves them as JSON, and uses the assembler to place those glyphs on a page.

## Main parts

### Glyph collector

Location: `GlyphCollectorUI/`

The collector is a browser UI for drawing glyph variants. It stores stroke points, pressure values where available, and optional processed data such as Bezier curves or normalized strokes.

The hosted collector is static and only captures glyph JSON. The local app embeds the collector and can save into a connected font folder when the browser supports it.

### Glyph data

Location: `glyphs/`

A font is a folder of JSON files. Each file represents one character or ligature. Filenames use Unicode hex by default, for example:

- `0061.json` for `a`
- `0041.json` for `A`
- `007300630068.json` for `sch`

This avoids case conflicts on Windows.

### Assembler

Location: `assembler/assembler.py`

The assembler loads glyph JSON, picks variants, applies layout rules, and renders SVG paths. It supports:

- text input or file input,
- multiple positioned text frames via `--frames`,
- paper sizes and margins in millimetres,
- balanced or greedy wrapping,
- pagination,
- ligatures,
- Unicode fallbacks,
- layout reports,
- SVG/PNG/PDF output,
- line drift and per-glyph variation.

### Local web app

Location: `assembler/server.py` and `assembler/templates/index.html`

The local app wraps the assembler in a Flask server. It provides the Assemble UI, live preview, export buttons, coverage feedback, on-page editing, and the embedded Capture tab.

By default it binds to `localhost`.

## Rendering model

The renderer emits stroked SVG paths. The main target is a pen plotter, so the default output is path-based and does not depend on filled font outlines.

Page layout is millimetre-first. The renderer scales glyph coordinates so line height, margins, stroke width, and page size match the requested paper settings.

## Current non-goals

- No neural handwriting model.
- No filled pressure-ribbon output by default.
- No full assembler in the hosted static collector.
- No claim that screen output is a substitute for real plotter testing.

See [`docs/ROADMAP.md`](docs/ROADMAP.md) for current future candidates.
