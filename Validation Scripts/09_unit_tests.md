# VS-09: Automated Unit Tests

**Objective:** Verify that all automated tests pass.

## Steps

### 1. Run the test suite
```bash
cd assembler
python3 -m unittest test_assembler -v
```

### 2. Verify results
**Expected output:**
```
test_kerning_exception ... ok
test_library_loading ... ok
test_ligature_recognition ... ok
test_line_spacing_multiplier ... ok
test_margin_offset ... ok
test_paper_size_dimensions ... ok
test_paper_size_landscape ... ok
test_renderer_svg_generation ... ok
test_typesetting_metrics ... ok

----------------------------------------------------------------------
Ran 9 tests in ...s

OK
```

**Expected:**
- [ ] All 9 tests pass
- [ ] No errors or failures
- [ ] No temporary files left behind
