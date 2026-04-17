# VS-02: Multiline File Input

**Objective:** Verify that `--file` reads a text file and preserves line breaks verbatim.

## Prerequisites
- Font `utrost` available in `glyphs/utrost/`

## Steps

### 1. Create a test text file
```bash
cd assembler
cat > vs02_input.txt << 'EOF'
The quick brown fox
jumps over the lazy dog.
1234567890
EOF
```

### 2. Run the assembler with file input
```bash
python3 assembler.py --file vs02_input.txt vs02_multiline.svg --font utrost \
  --paper-size A4 --line-height-mm 10
```

### 3. Open in browser
Open `vs02_multiline.svg` in a browser or SVG viewer.

**Expected:**
- [ ] Three distinct lines of text, vertically separated
- [ ] Line 1: "The quick brown fox"
- [ ] Line 2: "jumps over the lazy dog."
- [ ] Line 3: "1234567890"
- [ ] Lines do not overlap
- [ ] Punctuation (period) renders correctly

## Cleanup
```bash
rm vs02_input.txt vs02_multiline.svg
```
