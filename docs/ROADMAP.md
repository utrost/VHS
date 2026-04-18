# VHS Assembler — Enhancement Roadmap

Candidate improvements toward life-like handwriting and excellent UX. Items
are grouped by theme. **Status** values: `Proposed` (not scheduled),
`Planned` (will implement), `In progress`, `Done`, `Won't do`.

---

## Realism

### R1. Pressure-aware stroke width — **Won't do (for now)**

The capture pipeline stores a pressure value per stroke point. Rendering
variable-width paths (or filled ribbons) would change the visual character
from "uniform plotter line" to "fountain pen with downstroke weight".

**Why parked:** the primary output target is the pen plotter. Most plotters
draw a constant-width stroke — the pen physically can't modulate width
during a move. Emitting variable-width geometry would either be ignored by
the plotter or require a per-stroke pen-up/down dance that defeats the
point. We will keep the pressure data in the glyph JSON (it costs nothing)
and revisit if a non-plotter target (screen, PDF for print, laser/vinyl
cutter) becomes a first-class output.

**Revisit trigger:** a user explicitly requests screen- or print-quality
output, or a plotter/device with dynamic line weight is supported.

---

### R2. Cursive joining — **Proposed**

Glyph JSON carries `exit_x/y` and `entry_x/y` metadata. When the previous
glyph's exit is geometrically compatible with the next glyph's entry
(close x-gap, similar y-zone), emit a short cubic bezier that bridges
the two. Converts block printing into semi-connected cursive.

**What changes**

- Typesetter reads `exit` / `entry` metadata and records per-glyph
  pair-compatibility.
- A new stroke kind — "connector" — is synthesised between compatible
  pairs. Rendered as a regular bezier path; participates in smoothing /
  drift / scaling like any other stroke.
- Opt-in: `--connect-letters` CLI flag and matching GUI toggle.
- Heuristics + tuning: a compatibility score (gap threshold, zone match,
  direction continuity) with a `--connect-aggressiveness 0.0–1.0` knob.

**Effort:** medium. Biggest risk is the heuristic — compatibility that
produces tangled or misaligned connectors looks worse than no connector
at all. Ship behind an opt-in flag initially.

**Depends on:** glyphs having the metadata populated. Fonts captured
before this feature may need a re-capture pass or a metadata migration.

---

### R3. Per-character slant + intra-line bob — **Proposed**

Line drift already exists per-line. Real writing also wobbles per glyph:
small ±1° slant jitter and ±0.2 mm y-bob per letter.

**What changes**

- Typesetter applies a small random affine per placed glyph (rotation
  around the glyph's baseline-left corner, plus a tiny y offset) drawn
  from a seeded uniform distribution.
- Two new CLI flags: `--glyph-slant-jitter` (deg) and
  `--glyph-y-jitter` (mm). Zero defaults preserve current output.
- Same pattern in the GUI (two number inputs under the realism section).

**Effort:** small. One new method on the Typesetter; passes existing
tests.

**Watch out for:** compounding with `--line-drift-*` can make text look
drunk. Document sensible ranges in the User Guide.

---

### R4. Missing-glyph fallbacks — **Planned (next)**

Inputs frequently contain characters that no hand-captured font will
cover: em-dashes, curly quotes, en-dashes, ellipsis. They are currently
silently skipped, leaving visible gaps.

**What changes**

- A small Unicode-normalisation step in the typesetter runs before
  ligature matching: `— / – → --`, `' ' → '`, `" " → "`, `… → ...`,
  NBSP → space. Configurable map, sensible defaults.
- `--no-fallbacks` escape hatch to disable.
- After rendering, log a one-line summary: `3 codepoints substituted (—
  → --, ' → '), 1 codepoint dropped (¶)`.
- GUI surfaces the summary beneath the preview.

**Effort:** small. Mostly a table and a pre-pass.

---

## UX

### U1. Dry-run / layout report — **Planned**

Let users tune parameters before they commit to a full render.

**What changes**

- New `--report` flag: typesets normally but skips SVG emission and
  prints a structured summary:
  ```
  Page: A4 portrait (210×297 mm), margin 20 mm
  Layout: line-height 10 mm × line-spacing 1.3 → advance 13 mm
  Content: 312 words, 26 lines, 338 mm tall
  Fits: 1 page needed (1 × 247 mm writable)
  Missing codepoints: —, ', ' (4 occurrences, will substitute)
  ```
- JSON variant (`--report-format json`) for scripting / CI.
- CLI exit code reflects overflow / missing glyphs so CI can gate on it.

**Effort:** small. Reuses existing `_line_info` / `_word_info` and the
fallback summary from R4.

---

### U2. Live preview in the web GUI — **Proposed**

Today every knob change requires clicking "Generate". Debounced
auto-regen (200–400 ms after the last input) would turn the GUI into a
proper typography playground.

**What changes**

- Wire an `input` listener on every form field to a debounced call of
  the existing `generate()` function.
- Show a subtle "rendering…" indicator; cancel in-flight requests when a
  new one starts.
- Server-side: cache the `GlyphLibrary` and `Typesetter` across requests
  (they don't change per request) to keep round-trip times low.
- Keep the current Generate button for "force re-render" and for cases
  where the user disables auto-preview (add a toggle).

**Effort:** medium. Front-end debouncing is trivial; server caching and
cancellation add complexity. The biggest design decision is when *not*
to auto-regen (large text + heavy effects could be slow).

---

### U3. Config files and presets — **Proposed**

A good recipe today is a ~12-flag shell line. Users forget. Presets and
config files solve both reuse and sharing.

**What changes**

- `--config path/to/config.yaml` reads any subset of the CLI flags.
  Command-line flags override file values.
- `--preset <name>` loads a named preset from
  `configs/presets/<name>.yaml`. Ship a starter set:
  - `letter-a4`, `letter-a5`, `notebook-page`, `cursive-a4`,
    `architects-a3`.
- Per-font recommended defaults: fonts may include a
  `glyphs/<font>/preset.yaml` that's applied when `--font` is set and no
  explicit preset is named.
- GUI: a "Load preset" dropdown and a "Save as preset" button that
  writes the current sidebar state to a user-chosen file.

**Effort:** medium. Mostly plumbing — YAML parse + merge order
(preset → config file → CLI flags).

---

### U4. Multi-page PDF export + widow/orphan control — **Proposed**

`--paginate` currently produces numbered SVG files. For real-world
letters that's one conversion step away from usable; PDFs would be more
directly shareable/printable. And pagination can strand a single line of
a paragraph on the next page, which looks wrong.

**What changes**

- `--format pdf` combines all pages into a single multi-page PDF. Needs
  a dependency (cairosvg / reportlab / weasyprint) — pick the lightest.
  SVG remains the default.
- Widow/orphan control: during pagination, if a page would end with
  fewer than `--min-orphan-lines` lines of the paragraph that continues
  next, pull one line forward; if a page would start with a single line
  of the previous paragraph, push it back. Config defaults:
  orphan-min = 2, widow-min = 2.
- User Guide gains a "Printing and PDF" section.

**Effort:** medium. PDF export is a dependency + a thin wrapper. Widow
/ orphan control requires tracking paragraph boundaries through
pagination (easy — `_word_info` already has `line_break_after`).

---

## Ordering & rough sizing

| # | Item | Value | Effort | Risk | Order |
|---|------|-------|--------|------|-------|
| R4 | Missing-glyph fallbacks | High | Small | Low | 1 |
| U1 | Dry-run / report | High | Small | Low | 2 |
| R3 | Per-glyph slant + bob | Medium-high | Small | Low | 3 |
| U2 | Live preview in GUI | High | Medium | Medium | 4 |
| U3 | Config files + presets | Medium | Medium | Low | 5 |
| U4 | PDF + widow/orphan | Medium | Medium | Low | 6 |
| R2 | Cursive joining | High | Medium | Medium-high | 7 |
| R1 | Pressure-aware stroke | — | — | — | Won't do |

The first two are the lowest-risk biggest wins and should land together
— R4 removes an obvious output defect, U1 gives users a way to see what
the Assembler is about to produce.
