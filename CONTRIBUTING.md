# Contributing to VHS

## Development Setup

1. Clone the repository
2. **Glyph Capture:** Open `GlyphCollectorUI/GlyphCollectorUI.html` in a browser
3. **Assembly:** `cd assembler && python assembler.py` (requires Python 3.8+)

## Architecture

- `GlyphCollectorUI/` — Browser-based stroke capture tool (HTML/JS)
- `assembler/` — Python pipeline: glyph selection → shaping → kerning → SVG
- `glyphs/` — JSON glyph libraries (per-font directories)

Personal glyph data is gitignored. Capture your own handwriting to create fonts.

## Commit Messages

Use conventional prefixes: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
