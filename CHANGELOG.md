# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- CONTRIBUTING.md
- This CHANGELOG
- **Auto-scaling in fixed-page mode**: When a paper size is set, the renderer computes a uniform scale factor so that content fits within the available page area (page minus margins). Stroke width is inversely scaled for consistent visual weight.
- **Word wrapping**: The typesetter accepts an optional `max_width` parameter for automatic word-level line wrapping.
- **Zone-aware auto-kerning**: Optical kerning now classifies glyph strokes into vertical zones (upper/ground/lower) using `baseline_y` and `x_height` metadata. Letter pairs in different zones (e.g., "Te") kern tighter because their strokes don't collide. Configurable via `--kern-aggressiveness` (CLI, 0.0–1.0, default 0.5) and a slider in the Web UI.
- **Deterministic jitter**: Jitter output is now reproducible — the RNG is seeded from the content hash, so the same input always produces the same output. Use `--seed` to override with an explicit seed.
- **Undo/Redo in Glyph Collector**: Per-stroke undo (Ctrl+Z) and redo (Ctrl+Shift+Z) in the capture UI. Buttons also added to the header.
- **Auto-save in Glyph Collector**: Drawing sessions are automatically saved to localStorage and restored on page reload. No more lost work from accidental browser closes.

### Changed
- **Adaptive smoothing**: Catmull-Rom spline interpolation now uses adaptive step counts based on segment length (2–12 steps) instead of a fixed 5. Short segments get fewer steps to avoid over-smoothing; long curves get more for smoother results.
- Default `line_height` reduced from 200 to 100. With auto-scaling, 100 gives natural handwriting proportions (~3.4mm x-height for 15 lines on A5).
- **Stroke width** is now configurable via `--stroke-width` (CLI) and the GUI. Default: 2.0. Automatically scaled in fixed-page mode.
- **Smoothing is now on by default.** The `--smooth` flag has been replaced with `--no-smooth` to disable it. Catmull-Rom spline smoothing produces natural curves from low-resolution glyph captures.

## [1.0] — 2025

### Added
- Deterministic handwriting pipeline for pen plotters
- Browser-based GlyphCollectorUI for capturing stroke variants
- Python assembler with kerning support
- Stochastic shaping engine (no neural networks)
- JSON glyph format with multi-variant support
- TestFont sample data
- AGPL-3.0 license, GitHub Actions CI
