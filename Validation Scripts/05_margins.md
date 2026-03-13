# VS-05: Page Margins

**Objective:** Verify that `--margin` offsets content from the page edges.

## Prerequisites
- Font `utrost` available in `glyphs/utrost/`

## Steps

### 1. Generate with small margin (5mm)
```bash
cd assembler
python3 assembler.py "Margin test" vs05_margin_5.svg --font utrost \
  --paper-size A5 --margin 5
```

### 2. Generate with large margin (40mm)
```bash
python3 assembler.py "Margin test" vs05_margin_40.svg --font utrost \
  --paper-size A5 --margin 40
```

### 3. Verify the translate transform
```bash
grep 'translate' vs05_margin_5.svg
grep 'translate' vs05_margin_40.svg
```
**Expected:**
- File 1: transform starts with `translate(5.00,5.00)` followed by a `scale(...)` and content-origin translate
- File 2: transform starts with `translate(40.00,40.00)` followed by a `scale(...)` and content-origin translate

> **Note:** In fixed-page mode, the full transform is `translate(margin, margin) scale(s) translate(-offsetX, -offsetY)`. The scale factor is computed automatically to fit content within the available area.

### 4. Visual comparison
Open both SVGs in a browser.

**Expected:**
- [ ] 5mm margin — text starts very close to the top-left corner
- [ ] 40mm margin — text is noticeably inset from the edges
- [ ] Both have the same A5 page size (148×210mm)
- [ ] Content is scaled to fit within the page in both cases

## Cleanup
```bash
rm vs05_margin_5.svg vs05_margin_40.svg
```
