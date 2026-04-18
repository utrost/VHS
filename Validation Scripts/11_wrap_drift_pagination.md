# VS-11: Balanced Wrap, Line Drift, and Pagination

**Objective:** Verify the three organic-typography features introduced for
the mm layout: `--wrap-mode balanced`, `--line-drift-angle` / `--line-drift-y`,
and `--paginate`.

## Prerequisites
- Font `font1` (or any other) available in `glyphs/`
- A long input text (≥ 500 characters) saved to `/tmp/moby.txt`

## Steps

### 1. Balanced vs. greedy wrap

```bash
python3 assembler/assembler.py -f /tmp/moby.txt output/vs11_greedy.svg \
  --font font1 --paper-size A5 --margin 10 \
  --line-height-mm 12 --start-x 10 --start-y 10 --stroke-width 0.4 \
  --wrap-mode greedy --seed 42

python3 assembler/assembler.py -f /tmp/moby.txt output/vs11_balanced.svg \
  --font font1 --paper-size A5 --margin 10 \
  --line-height-mm 12 --start-x 10 --start-y 10 --stroke-width 0.4 \
  --wrap-mode balanced --seed 42
```

**Expected:**
- [ ] Both SVGs render the same text content.
- [ ] `vs11_balanced.svg` shows visibly more uniform line lengths than `vs11_greedy.svg` (less "stair-step" right edge).
- [ ] Neither file overflows 128 mm of wrap width.

### 2. Space width and jitter

```bash
python3 assembler/assembler.py -f /tmp/moby.txt output/vs11_spaces.svg \
  --font font1 --paper-size A5 --margin 10 \
  --line-height-mm 12 --start-x 10 --start-y 10 --stroke-width 0.4 \
  --space-width-mm 2.5 --space-jitter-mm 0.5 --seed 42
```

**Expected:**
- [ ] Gaps between words are noticeably tighter than the font's default.
- [ ] Spaces vary in width within the same line (subtle, not grid-aligned).

### 3. Per-line drift

```bash
python3 assembler/assembler.py -f /tmp/moby.txt output/vs11_drift.svg \
  --font font1 --paper-size A5 --margin 10 \
  --line-height-mm 12 --start-x 10 --start-y 10 --stroke-width 0.4 \
  --line-drift-angle 0.4 --line-drift-y 0.5 --seed 42
```

**Expected:**
- [ ] Each line tilts by a fraction of a degree (both directions, not all the same).
- [ ] Lines wobble slightly above/below their nominal baseline.
- [ ] Running the same command again with `--seed 42` produces byte-identical output.
- [ ] `grep -c 'rotate(' output/vs11_drift.svg` equals the number of rendered lines.

### 4. Pagination

```bash
python3 assembler/assembler.py -f /tmp/moby.txt output/vs11_pages.svg \
  --font font1 --paper-size A5 --margin 10 \
  --line-height-mm 12 --start-x 10 --start-y 10 --stroke-width 0.4 \
  --paginate --seed 42
```

**Expected:**
- [ ] CLI logs `Pagination: N page(s)` for some N ≥ 2.
- [ ] `output/vs11_pages-01.svg`, `output/vs11_pages-02.svg`, … are produced.
- [ ] Each file has `width="148.0mm" height="210.0mm"` (A5 portrait).
- [ ] Page 1's first line is at `start-y` = 10 mm; page 2 starts with the continuation of the text.

## Cleanup

```bash
rm output/vs11_*.svg
```
