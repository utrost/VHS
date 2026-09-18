# Contributing to VHS

## Development Setup

1. Clone the repository.
2. Use **Python 3.10+**.
3. Start the full local web UI:

   ```bash
   ./vhs-gui.sh
   ```

   On Windows:

   ```cmd
   vhs-gui.bat
   ```

4. Capture glyphs either from the **Capture glyphs** tab in the local UI or by opening `GlyphCollectorUI/GlyphCollectorUI.html` directly.
5. Run a CLI smoke from the repository root when changing the assembler:

   ```bash
   cd assembler
   python3 assembler.py "Hello World" /tmp/vhs-hello.svg --font font1
   ```

## Architecture

- `GlyphCollectorUI/` — Browser-based stroke capture tool (HTML/JS)
- `assembler/` — Python pipeline: glyph selection → shaping → kerning → SVG
- `glyphs/` — JSON glyph libraries (per-font directories); `glyphs/font1` is the shipped sample font

Personal glyph data is gitignored. Capture your own handwriting to create fonts.

## Tests

Run the Python and static contract tests from the repository root:

```bash
python3 -m pytest -q
```

## Commit Messages

Use conventional prefixes: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
