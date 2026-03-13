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

### 4. Verify deterministic jitter
```bash
python3 assembler.py "Smooth test" vs06_jitter_a.svg --font utrost --jitter 1.0
python3 assembler.py "Smooth test" vs06_jitter_b.svg --font utrost --jitter 1.0
diff vs06_jitter_a.svg vs06_jitter_b.svg
```
**Expected:** No differences — jitter is deterministic (content-seeded).

### 5. Verify explicit seed
```bash
python3 assembler.py "Smooth test" vs06_seed42.svg --font utrost --jitter 1.0 --seed 42
python3 assembler.py "Smooth test" vs06_seed99.svg --font utrost --jitter 1.0 --seed 99
```
**Expected:** Different seed values produce different jitter patterns.

### 6. Visual comparison
Open the SVGs in a browser.

**Expected:**
- [ ] Raw — strokes appear angular / polygonal
- [ ] Smooth — curves are fluid and natural (adaptive: short segments less smooth, long curves very smooth)
- [ ] Jitter — similar to smooth but with slight organic wobble / imperfection
- [ ] All render the same text content
- [ ] Deterministic jitter produces identical output for identical input

## Cleanup
```bash
rm vs06_raw.svg vs06_smooth.svg vs06_jitter.svg vs06_jitter_a.svg vs06_jitter_b.svg vs06_seed42.svg vs06_seed99.svg
```
