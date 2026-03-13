# VS-03: Paper Size Presets

**Objective:** Verify that `--paper-size` and `--orientation` produce SVGs with correct fixed dimensions.

## Prerequisites
- Font `utrost` available in `glyphs/utrost/`

## Steps

### 1. Create a test text file
```bash
cd assembler
cat > vs03_input.txt << 'EOF'
Paper size test.
Second line of text.
Third line here.
EOF
```

### 2. Generate A4 Portrait
```bash
python3 assembler.py --file vs03_input.txt vs03_a4_portrait.svg --font utrost \
  --paper-size A4 --orientation portrait
```

**Verify dimensions:**
```bash
grep -o 'width="[^"]*" height="[^"]*"' vs03_a4_portrait.svg
```
**Expected:** `width="210.0mm" height="297.0mm"`

### 3. Generate A4 Landscape
```bash
python3 assembler.py --file vs03_input.txt vs03_a4_landscape.svg --font utrost \
  --paper-size A4 --orientation landscape
```

**Verify dimensions:**
```bash
grep -o 'width="[^"]*" height="[^"]*"' vs03_a4_landscape.svg
```
**Expected:** `width="297.0mm" height="210.0mm"`

### 4. Generate A5 Portrait
```bash
python3 assembler.py --file vs03_input.txt vs03_a5_portrait.svg --font utrost \
  --paper-size A5 --orientation portrait
```

**Verify dimensions:**
```bash
grep -o 'width="[^"]*" height="[^"]*"' vs03_a5_portrait.svg
```
**Expected:** `width="148.0mm" height="210.0mm"`

### 5. Generate A3 Landscape
```bash
python3 assembler.py --file vs03_input.txt vs03_a3_landscape.svg --font utrost \
  --paper-size A3 --orientation landscape
```

**Verify dimensions:**
```bash
grep -o 'width="[^"]*" height="[^"]*"' vs03_a3_landscape.svg
```
**Expected:** `width="420.0mm" height="297.0mm"`

### 6. Visual check
Open all four SVGs side by side in a browser.

**Expected:**
- [ ] Each SVG has a different canvas size
- [ ] A4 Portrait is taller than wide
- [ ] A4 Landscape is wider than tall
- [ ] A5 is noticeably smaller than A4
- [ ] Text appears in the top-left area inside the default margin
- [ ] Content is automatically scaled to fit within the page (no overflow beyond margins)

## Cleanup
```bash
rm vs03_input.txt vs03_a4_portrait.svg vs03_a4_landscape.svg vs03_a5_portrait.svg vs03_a3_landscape.svg
```
