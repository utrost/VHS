# VS-05: Page Margins

**Objective:** Verify that `--margin` offsets content from the page edges.

## Prerequisites
- Font `utrost` available in `glyphs/utrost/`

## Steps

### 1. Generate with small margin (5mm)
```bash
cd assembler
python3 assembler.py "Margin test" vs05_margin_5.svg --font utrost --smooth \
  --paper-size A5 --margin 5
```

### 2. Generate with large margin (40mm)
```bash
python3 assembler.py "Margin test" vs05_margin_40.svg --font utrost --smooth \
  --paper-size A5 --margin 40
```

### 3. Verify the translate transform
```bash
grep 'translate' vs05_margin_5.svg
grep 'translate' vs05_margin_40.svg
```
**Expected:**
- File 1: `translate(5.00,5.00)`
- File 2: `translate(40.00,40.00)`

### 4. Visual comparison
Open both SVGs in a browser.

**Expected:**
- [ ] 5mm margin — text starts very close to the top-left corner
- [ ] 40mm margin — text is noticeably inset from the edges
- [ ] Both have the same A5 page size (148×210mm)

## Cleanup
```bash
rm vs05_margin_5.svg vs05_margin_40.svg
```
