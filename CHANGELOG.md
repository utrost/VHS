# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- **Unicode fallbacks + coverage feedback**: on-by-default substitution for em-dash, curly quotes, ellipsis, NBSP, and other typographic characters that hand-drawn fonts rarely cover. `--no-fallbacks` disables the pass. Every substitution and every still-missing codepoint is surfaced: CLI prints a `Glyph coverage:` banner on stderr with short context snippets; the web GUI shows a dedicated Coverage panel under the preview; and the response returns an `X-Glyph-Coverage` header / `/api/coverage` endpoint for tooling.
- **Strict glyph mode**: `--strict-glyphs` exits with status `2` when any codepoint is uncovered after fallbacks — CI-friendly.
- **Layout report / dry-run**: `--report` skips SVG emission and prints a structured layout + coverage summary. `--report-format {text,json}` chooses the format.
- **Millimetre-first page layout**: New flags `--line-height-mm`, `--lines-per-page`, `--start-x`, `--start-y`, `--max-width-mm` give direct, millimetre-based control over line height, text-block origin, and word-wrap width. The renderer applies a single scale factor (`line_height_mm / native_line_height`) so a 12 mm line on paper stays 12 mm regardless of how much text is present — no more auto-shrink-to-fit. Exposed in both the CLI and the web GUI.
- **Balanced line wrap** (`--wrap-mode balanced`, default): the typesetter lays every word out on a single line, records per-word widths, then runs a minimum-raggedness DP per paragraph to choose line breaks that minimise total squared slack. `--wrap-mode greedy` keeps the legacy first-fit algorithm.
- **Natural whitespace controls**: `--space-width-mm` overrides the font default; `--space-jitter-mm` adds a seeded per-space ± variation so spaces don't look mechanically uniform.
- **Per-line drift**: `--line-drift-angle` (deg) and `--line-drift-y` (mm) wrap each rendered line in its own `rotate(θ 0 baseline) translate(0 dy)` sub-group for an organic drifting-hand look. Seeded reproducibly via `--seed`.
- **Pagination**: `--paginate` splits overflowing content into numbered files (`output-01.svg`, `output-02.svg`, …). Lines-per-page is derived from the writable height and effective line height.
- **Typesetter metadata**: `typeset_text` now populates `_line_info` (per-line `{start_idx, end_idx, baseline_y}`) and `_word_info`, consumed by the Renderer for drift and by the CLI for pagination.
- **GUI fields** for wrap mode, space width / jitter (mm), and line drift (angle + y, mm).
- **User Guide**: `docs/USER_GUIDE.md` — full walkthrough of the mm layout model, every flag, recipes, and a sizing cheat-sheet.
- CONTRIBUTING.md
- This CHANGELOG
- **Template Overlay in Glyph Collector**: Semi-transparent handwriting font guides behind canvas slots. 17 Google Fonts in two option groups (Formal and Casual) help maintain consistent glyph proportions during capture.
- **Bezier Curve Fitting**: Schneider algorithm with adaptive corner detection and Newton-Raphson refinement. Captured polylines are converted to cubic Bezier curves for smoother SVG output. Stored as `bezier_curves` in glyph JSON.
- **Stroke Normalization**: Automatic slant correction, pressure smoothing, height normalization, and configurable strength blending. Stored as `normalized_strokes` in glyph JSON.
- **Assembler Bezier SVG paths**: The assembler reads `bezier_curves` from glyph JSON and generates SVG `<path>` elements with cubic Bezier `C` commands instead of polylines.
- **Assembler normalized stroke support**: The assembler reads `normalized_strokes` from glyph JSON and uses them for layout and rendering when available.
- **Assembler priority chain**: `bezier_curves` > `normalized_strokes` > raw `strokes`. Each level falls back gracefully.
- **`--no-bezier` flag**: CLI flag to skip Bezier curve rendering and fall back to normalized/raw strokes.
- **`--no-normalize` flag**: CLI flag to skip normalized strokes and use raw capture points.
- **Word wrapping**: The typesetter accepts an optional `max_width` parameter for automatic word-level line wrapping (exposed as `--max-width-mm` in the CLI).
- **Zone-aware auto-kerning**: Optical kerning now classifies glyph strokes into vertical zones (upper/ground/lower) using `baseline_y` and `x_height` metadata. Letter pairs in different zones (e.g., "Te") kern tighter because their strokes don't collide. Configurable via `--kern-aggressiveness` (CLI, 0.0–1.0, default 0.5) and a slider in the Web UI.
- **Deterministic jitter**: Jitter output is now reproducible — the RNG is seeded from the content hash, so the same input always produces the same output. Use `--seed` to override with an explicit seed.
- **Undo/Redo in Glyph Collector**: Per-stroke undo (Ctrl+Z) and redo (Ctrl+Shift+Z) in the capture UI. Buttons also added to the header.
- **Auto-save in Glyph Collector**: Drawing sessions are automatically saved to localStorage and restored on page reload. No more lost work from accidental browser closes.

### Changed
- **Adaptive smoothing**: Catmull-Rom spline interpolation now uses adaptive step counts based on segment length (2–12 steps) instead of a fixed 5. Short segments get fewer steps to avoid over-smoothing; long curves get more for smoother results.
- **`--stroke-width` is now in millimetres on paper** (default: 2.0; typical handwriting: 0.3–0.6). The renderer divides it by the page scale so the on-paper thickness is exactly what you set, regardless of glyph scale.
- **Smoothing is now on by default.** The `--smooth` flag has been replaced with `--no-smooth` to disable it. Catmull-Rom spline smoothing produces natural curves from low-resolution glyph captures.

### Removed
- **`--line-height` (glyph units)** and **`--max-width` (glyph units)**: superseded by `--line-height-mm` and `--max-width-mm`. With `--paper-size`, one of `--line-height-mm` / `--lines-per-page` is now required.
- **Scale-to-fit paper mode**: the fixed-page renderer no longer auto-shrinks content to fit. Callers specify an explicit scale (via the mm flags), keeping the output the size they asked for.

## [1.0] — 2025

### Added
- Deterministic handwriting pipeline for pen plotters
- Browser-based GlyphCollectorUI for capturing stroke variants
- Python assembler with kerning support
- Stochastic shaping engine (no neural networks)
- JSON glyph format with multi-variant support
- TestFont sample data
- AGPL-3.0 license, GitHub Actions CI
