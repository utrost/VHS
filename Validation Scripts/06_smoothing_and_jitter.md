# VS-06: Smoothing and Jitter

**Objective:** Verify that `--no-smooth` and `--jitter` affect the visual output. Smoothing is on by default.

## Prerequisites
- Font `utrost` available in `glyphs/utrost/`

## Steps

### 1. Generate without smoothing
```bash
cd assembler
python3 assembler.py "Smooth test" vs06_raw.svg --font utrost --no-smooth
```

### 2. Generate with smoothing (default)
```bash
python3 assembler.py "Smooth test" vs06_smooth.svg --font utrost
```

### 3. Generate with smoothing + jitter
```bash
python3 assembler.py "Smooth test" vs06_jitter.svg --font utrost --jitter 1.0
```

### 4. Visual comparison
Open all three SVGs in a browser.

**Expected:**
- [ ] Raw — strokes appear angular / polygonal
- [ ] Smooth — curves are fluid and natural
- [ ] Jitter — similar to smooth but with slight organic wobble / imperfection
- [ ] All three render the same text content

## Cleanup
```bash
rm vs06_raw.svg vs06_smooth.svg vs06_jitter.svg
```
