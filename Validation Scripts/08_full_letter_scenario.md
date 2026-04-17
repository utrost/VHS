# VS-08: Full Letter Scenario (End-to-End)

**Objective:** Verify a realistic end-to-end use case — rendering a multi-paragraph letter on A4 paper.

## Prerequisites
- Font `utrost` available in `glyphs/utrost/`

## Steps

### 1. Create a realistic letter
```bash
cd assembler
cat > vs08_letter.txt << 'EOF'
Dear Friend,

I hope this letter finds you well.
The weather here has been quite lovely
and I thought of writing to you.

Best wishes,
Uwe
EOF
```

### 2. Generate on A4 Portrait
```bash
python3 assembler.py --file vs08_letter.txt vs08_letter_a4.svg --font utrost \
  --paper-size A4 --orientation portrait --margin 25 \
  --line-height-mm 10 --line-spacing 1.3 --stroke-width 0.4
```

### 3. Generate on A5 Landscape
```bash
python3 assembler.py --file vs08_letter.txt vs08_letter_a5.svg --font utrost \
  --paper-size A5 --orientation landscape --margin 15 \
  --line-height-mm 8 --line-spacing 1.2 --stroke-width 0.4
```

### 4. Visual inspection
Open both SVGs in a browser.

**Expected (A4 Portrait):**
- [ ] Page is taller than wide (210×297mm)
- [ ] Text starts ~25mm from the top-left corner
- [ ] All 8 lines rendered (including the empty line between paragraphs)
- [ ] Empty line creates visible paragraph gap
- [ ] Baselines are 13 mm apart (10 mm line height × 1.3 line spacing)
- [ ] Text looks like natural handwriting

**Expected (A5 Landscape):**
- [ ] Page is wider than tall (210×148mm)
- [ ] Text starts ~15mm from the top-left corner
- [ ] Same content, different layout
- [ ] Smaller text area — letters may be more compact

### 5. Verify SVG dimensions
```bash
grep -o 'width="[^"]*" height="[^"]*"' vs08_letter_a4.svg
grep -o 'width="[^"]*" height="[^"]*"' vs08_letter_a5.svg
```
**Expected:**
- A4: `width="210.0mm" height="297.0mm"`
- A5 landscape: `width="210.0mm" height="148.0mm"`

## Cleanup
```bash
rm vs08_letter.txt vs08_letter_a4.svg vs08_letter_a5.svg
```
