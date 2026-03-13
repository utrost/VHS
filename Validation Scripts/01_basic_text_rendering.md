# VS-01: Basic Text Rendering

**Objective:** Verify that the assembler converts inline text to a valid SVG.

## Prerequisites
- Python 3.10+ installed
- Font `utrost` available in `glyphs/utrost/`

## Steps

### 1. Run the assembler with inline text
```bash
cd assembler
python3 assembler.py "Hello World" vs01_hello.svg --font utrost
```

### 2. Verify output file exists
```bash
ls -la vs01_hello.svg
```
**Expected:** File exists and has non-zero size.

### 3. Inspect the SVG structure
```bash
head -5 vs01_hello.svg
```
**Expected:** Valid XML declaration and an `<svg>` root element with `viewBox`, `width`, and `height` attributes in mm.

### 4. Open in browser
Open `vs01_hello.svg` in a web browser or SVG viewer.

**Expected:**
- [x] "Hello World" rendered in handwriting style
- [x] All letters visible, no overlapping or missing glyphs
- [x] Space between "Hello" and "World"
- [x] Single line of text

## Cleanup
```bash
rm vs01_hello.svg
```
