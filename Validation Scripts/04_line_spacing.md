# VS-04: Line Spacing Multiplier

**Objective:** Verify that `--line-spacing` controls the vertical gap between lines as a multiplier on top of `--line-height-mm`.

## Prerequisites
- Font `utrost` available in `glyphs/utrost/`

## Steps

### 1. Create a test text file
```bash
cd assembler
cat > vs04_input.txt << 'EOF'
Line one
Line two
Line three
Line four
EOF
```

### 2. Generate with default spacing (1.0)
```bash
python3 assembler.py --file vs04_input.txt vs04_spacing_1x.svg --font utrost \
  --paper-size A4 --line-height-mm 8 --line-spacing 1.0
```

### 3. Generate with 1.5× spacing
```bash
python3 assembler.py --file vs04_input.txt vs04_spacing_1.5x.svg --font utrost \
  --paper-size A4 --line-height-mm 8 --line-spacing 1.5
```

### 4. Generate with 2.0× spacing
```bash
python3 assembler.py --file vs04_input.txt vs04_spacing_2x.svg --font utrost \
  --paper-size A4 --line-height-mm 8 --line-spacing 2.0
```

### 5. Visual comparison
Open all three SVGs in a browser.

**Expected:**
- [ ] 1.0× — lines are at the baseline distance (compact)
- [ ] 1.5× — visibly more space between lines than 1.0×
- [ ] 2.0× — double the gap of 1.0×, lines are generously spaced
- [ ] All four text lines are present in each SVG
- [ ] Text content is identical across all three

## Cleanup
```bash
rm vs04_input.txt vs04_spacing_1x.svg vs04_spacing_1.5x.svg vs04_spacing_2x.svg
```
