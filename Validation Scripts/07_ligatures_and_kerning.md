# VS-07: Ligatures and Auto-Kerning

**Objective:** Verify that ligature substitution and optical kerning work correctly.

## Prerequisites
- Font `utrost` available in `glyphs/utrost/` (includes ligature files like `00740074.json` for "tt")

## Steps

### 1. Test ligature substitution
```bash
cd assembler
python3 assembler.py "butter" vs07_ligature.svg --font utrost --smooth
```

Open `vs07_ligature.svg` in a browser.

**Expected:**
- [ ] The word "butter" renders correctly
- [ ] The "tt" pair appears as a single connected glyph (not two separate t's)

### 2. Test auto-kerning
```bash
python3 assembler.py "WAVE" vs07_no_kern.svg --font utrost --smooth
python3 assembler.py "WAVE" vs07_auto_kern.svg --font utrost --smooth --auto-kern
```

Open both SVGs in a browser.

**Expected:**
- [ ] Auto-kerned version has tighter, more optically even spacing
- [ ] Non-kerned version may have wider or uneven gaps between letters

### 3. Test German characters
```bash
python3 assembler.py "Größe Übung Ärger straße" vs07_german.svg --font utrost --smooth
```

**Expected:**
- [ ] Umlauts (ö, Ü, Ä) render correctly with dots above
- [ ] ß (Eszett) renders as a single glyph
- [ ] All ligatures within words are applied (e.g., "st" in "straße")

## Cleanup
```bash
rm vs07_ligature.svg vs07_no_kern.svg vs07_auto_kern.svg vs07_german.svg
```
