# VS-10: Error Handling

**Objective:** Verify that the assembler handles invalid input gracefully.

## Steps

### 1. No input provided
```bash
cd assembler
python3 assembler.py output.svg 2>&1
```
**Expected:** Error message about missing input. Non-zero exit code.

### 2. Non-existent font
```bash
python3 assembler.py "Hello" vs10_err.svg --font NonExistentFont 2>&1
```
**Expected:** Error message about missing glyphs directory. Non-zero exit code.

### 3. Non-existent input file
```bash
python3 assembler.py --file does_not_exist.txt vs10_err.svg --font utrost 2>&1
```
**Expected:** Error message about failing to read the input file. Non-zero exit code.

### 4. Invalid paper size
```bash
python3 assembler.py "Hello" vs10_err.svg --font utrost --paper-size B5 2>&1
```
**Expected:** argparse error listing valid choices (A3, A4, A5, A6, Letter, Legal).

### 5. Invalid orientation
```bash
python3 assembler.py "Hello" vs10_err.svg --font utrost --orientation diagonal 2>&1
```
**Expected:** argparse error listing valid choices (portrait, landscape).

**Expected:**
- [ ] All five error cases produce clear, helpful error messages
- [ ] No stack traces or uncaught exceptions
- [ ] No output SVG files are created for error cases

## Cleanup
```bash
rm -f vs10_err.svg
```
