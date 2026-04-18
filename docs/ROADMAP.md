# VHS Assembler — Enhancement Roadmap

Candidate improvements toward life-like handwriting and excellent UX. Items
are grouped by theme. **Status** values:

- `Proposed` — not yet scheduled.
- `Planned` — will implement.
- `In progress` — being built.
- `Experimental` — shipped and usable, but output quality depends on
  font data / parameters and may not be production-ready. Experimental
  features are always **opt-in**, carry an explicit notice in the CLI
  help, the GUI control, and the User Guide, and can change behaviour
  between releases until graduated to `Done`.
- `Done` — shipped and stable.
- `Won't do` — explicitly parked with a documented rationale.

---

## Ground rules

**CLI / GUI parity.** Every user-facing Assembler feature must be reachable
from both the CLI and the web GUI. New flags land together with
corresponding form fields — a feature that ships only on one side is
treated as incomplete, not as "phase one". The single justified exception
is functionality that's inherently unsuitable for one medium (e.g.
`--paginate` produces multiple numbered files; the GUI shows a single
live preview, so the flag stays CLI-only). Each such exception must be
documented explicitly in the item's "What changes" section and in the
User Guide.

This applies retroactively: any current asymmetry is a bug and should be
filed against the item that introduced it.

**GlyphCollector scope.** The Collector is a capture tool — it
produces glyph JSON, it does not render finished documents. Any output
/ preview features (GC8 live preview) must go through the Assembler
backend, not reimplement typesetting inside the Collector.

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

### R2. Cursive joining — **Proposed → Experimental when shipped**

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
- **Opt-in** flag `--connect-letters` (default: off) with a matching
  sidebar toggle. Default output is unchanged — users have to ask for
  joining explicitly, so the feature can't regress anyone's existing
  workflow.
- Heuristics + tuning: a compatibility score (gap threshold, zone match,
  direction continuity) with a `--connect-aggressiveness 0.0–1.0` knob.
  A per-font preset can ship sensible defaults (see U3).
- Per-glyph JSON may also carry an explicit `no_connect_left` /
  `no_connect_right` flag that the heuristic honours as a hard veto.

**Effort:** medium.

**Quality risk (when enabled):** the visual quality depends heavily on
the glyphs having sensible exit/entry metadata and on letterforms
captured in a style that supports connection. Three failure modes
drive the "Medium-high" rating:

1. Bad joins look *worse* than none — a tangled connector between
   mismatched zones is more offensive than two clean unconnected
   letters.
2. Glyphs captured before this feature may lack the `exit_x/y`
   metadata; without it every pair is a guess.
3. Block-printing glyphs don't become convincing cursive just by
   bridging — letterforms themselves aren't cursive-shaped.

**Mitigations** (all baked in): (a) the opt-in gate keeps default
output identical; (b) the compatibility score defaults conservative,
so only high-confidence pairs connect; (c) the per-glyph veto lets
font authors disable joining for specific characters without touching
the code; (d) ship with a small validation script that visualises
every pair's compatibility score so authors can tune their metadata
before enabling joining on that font; (e) the feature ships with
**Experimental** status — `--connect-letters` prints a one-line
"(experimental — output quality varies)" notice on stderr the first
time it's used in a session, and the matching GUI toggle wears an
`experimental` badge. The status graduates to `Done` once we have
a reference font with curated metadata that produces consistently
acceptable output.

**Depends on:** glyphs having `exit_x/y` and `entry_x/y` metadata
populated. Fonts captured before this feature may need a re-capture
pass or a metadata migration.

---

### R3. Per-character slant + intra-line bob — **Done**

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

### R4. Missing-glyph fallbacks — **Done**

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

### U1. Dry-run / layout report — **Done**

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

### U2. Live preview in the web GUI — **Done**

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

### U3. Config files and presets — **Done**

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

### U4. Glyph-coverage feedback — **Done**

Today, a missing glyph produces a log line per occurrence and, after
R4 lands, a one-line substitution summary. That's still too quiet —
users shouldn't have to read the console to discover their text isn't
fully renderable, and they shouldn't be surprised after a 20 MB render.

**What changes**

- Up-front coverage check: before typesetting, scan the input against
  the loaded `GlyphLibrary` and compute
  `{missing_codepoints: {codepoint: [positions], ...}, missing_count, total_count}`.
- CLI:
  - A prominent banner on stderr before rendering begins, listing every
    missing codepoint with counts and showing a short context snippet
    (`"…having litt—le or no money…"`) for the first occurrence of each.
  - `--strict-glyphs` makes missing glyphs a fatal error (CI-friendly).
  - Exit code 2 reserved for "rendered but with missing glyphs".
- Web GUI:
  - A dedicated "Coverage" panel under the preview. Red rows per missing
    codepoint with count and a "Jump to first occurrence" button that
    highlights the character in the input textarea.
  - If the font ships a `preset.yaml` (see U3) with suggested fallbacks,
    offer a "Apply R4 fallbacks" button that substitutes and re-renders.
- Report integration: `--report` (U1) includes the full coverage
  dictionary in its JSON output.

**Effort:** small once R4's codepoint inventory is built — this reuses
the same scan. The GUI highlight/jump is the biggest UI piece.

**Depends on:** R4 for the substitution context; U1 for the machine-
readable report surface. Can ship standalone with just the CLI banner
and a simple GUI list first, then enhance.

---

### U5. PNG export — **Done**

SVG is ideal for pen plotters and lossless print, but users often want a
PNG for sharing on messaging apps, embedding in documents, generating
previews, or archiving.

**What changes**

- `--format png` writes a rasterised bitmap instead of / alongside SVG.
  SVG remains the default.
- `--dpi INT` controls raster resolution (default: 300). Image pixel
  dimensions fall out of page size × DPI, e.g. A4 @ 300 dpi →
  2480 × 3508 px.
- `--transparent` toggles a transparent background (default: white).
- Pagination: `--paginate` plus `--format png` produces
  `output-01.png`, `output-02.png`, ….
- Renderer stays SVG-first; PNG output is a thin conversion step
  (`cairosvg` is the likely dependency — small, pure-python bindings,
  ships PNG via a single call). Keep it optional: the SVG path has no
  new dependency, PNG requires the extra install.
- GUI: a "Download PNG" button alongside "Download SVG", with a DPI
  input in the export section.

**Effort:** small. One wrapper around `cairosvg.svg2png(...)`, plus the
CLI/GUI surfaces. No changes to the typesetter or renderer.

**Watch out for:** some SVG features (filters, advanced text) render
differently across SVG→PNG libraries. Our output is simple paths in
a `<g>`, so this should be safe, but include a smoke test comparing
render output to a reference checksum.

---

### U6. Multi-page PDF export + widow/orphan control — **Proposed**

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

## GlyphCollector UI

The browser-based capture tool already covers variant capture, Bezier
fitting, normalisation, template overlay, undo/redo, and auto-save.
The items below turn it from a single-glyph tool into a proper
font-building workflow.

### GC1. Font-completeness dashboard — **Proposed**

A persistent panel showing which characters of the target set have
saved JSONs, how many variants each has, and which are missing. Turns
"what next?" into a checklist and makes it obvious when a font is
ready for real use.

**What changes**

- A target character set drawn from a preset (see GC2) or a custom
  list.
- For each char: ✅ captured (with variant count) / ⚠️ few variants / ❌
  missing. Counts come from scanning `glyphs/<font>/*.json`.
- Progress bar: "47 / 128 captured (37 %)".
- Clicking a missing/partial entry loads it into the canvas (see GC5).

**Effort:** small. Requires a way to enumerate the font directory —
via the File System Access API (GC7) or a manual "rescan" button that
reads a user-selected folder.

---

### GC2. Character-set presets — **Proposed**

One-click queues of common target sets so users don't have to
hand-roll a list.

**What changes**

- Built-in presets: *Basic Latin*, *Numbers*, *Basic punctuation*,
  *German umlauts (äöüÄÖÜß)*, *French accents*, *Scandinavian*,
  *Smart quotes & dashes*, *Greek*, *Common ligatures (tt, ff, fi, sch)*.
- Multi-select: tick the presets you want; dashboard targets the
  union.
- Custom list box for one-off additions.
- Persisted to localStorage per font.

**Effort:** small. Pure UI + a static map of presets.

---

### GC3. Frequency-aware capture suggestions — **Proposed**

"Capture these next" hints based on letter frequency so an in-progress
font is usable for real text as early as possible.

**What changes**

- Static language-specific frequency tables (English, German, French
  to start).
- Dashboard surfaces the next *N* missing chars ordered by frequency.
- Optional ETA: "Capturing these 5 letters would raise coverage from
  38 % to 71 % of typical English text."

**Effort:** small. Frequency tables are fixed data.

---

### GC4. Batch / queue capture mode — **Planned**

The biggest single session speed-up: type a target string once, step
through characters in sequence, auto-advance after each save.

**What changes**

- A new "Queue" field accepts a string (e.g. `abcdefghijklmnopqrstuvwxyz`).
- After Save (or Enter), the grid clears and the next queue character
  loads into the label input automatically.
- Progress bar inside the queue (`12 / 26 · next: m`).
- ESC / explicit Stop exits queue mode.
- Queue entries can be multi-char for ligatures (`sch, tt, ff`).
- Integrates with GC1 so finished queue items tick off the dashboard
  in real time.

**Effort:** small–medium. New state machine for queue progress and
input handling.

---

### GC5. Jump-to-character / edit existing — **Planned**

Typing a label that has an existing JSON should load it for editing
rather than starting blank.

**What changes**

- On label input change, look up `glyphs/<font>/<label>.json` (via
  File System Access API or a pre-scanned manifest).
- If found, populate the grid with existing variants and flag each
  box "loaded" so the user knows it isn't fresh.
- "Keep" / "Replace" / "Append" choice when saving back.
- Disabled when no font directory is connected.

**Effort:** medium. Needs the reverse of the save path: read + parse
existing JSON, rebuild the stroke buffer + Bezier data, redraw to
canvas.

**Depends on:** GC7 (direct folder access) for a smooth flow, or a
manual file-picker fallback.

---

### GC6. Per-variant reject & re-capture — **Proposed**

A single wobbly variant shouldn't force clearing the whole grid. Let
users wipe and redraw one box at a time.

**What changes**

- X (or "redo") button on each variant slot; clears only that slot.
- Single-slot focus mode: click a slot to isolate; grid dims the
  others until you exit.
- The rest of the capture state (label, font settings, other variants)
  is preserved.

**Effort:** small. Mostly per-slot state cleanup.

---

### GC7. Direct save to `glyphs/<font>/` — **Planned**

Eliminate the download + manual move shuffle on Chromium-family
browsers via the File System Access API.

**What changes**

- "Connect font folder" button at the top of the Settings panel.
- Once connected, Save writes directly to
  `<folder>/<label>.json`, creating or overwriting.
- Connection is persisted (with explicit re-prompt on reload, per the
  permission model).
- Firefox/Safari: graceful fallback to the existing download flow,
  with an explicit notice that direct-save isn't available.
- Opens the door to GC1's dashboard scan and GC5's existing-glyph
  load.

**Effort:** medium. File System Access API is well documented;
permission lifecycle and fallback path are the main work.

**Watch out for:** permission expiry between sessions (browser
dependent); users should never be surprised by "save did nothing" if
the handle was revoked.

---

### GC8. Assembler live-preview panel — **Proposed**

A small embedded preview panel that types a short sample ("The quick
brown fox …") using the current font's saved glyphs plus the currently
captured grid. Gives immediate visual feedback on whether new variants
match the existing set.

**What changes**

- Pane underneath (or beside) the capture grid, 150–200 px tall.
- Re-renders on every save and on demand via a "Preview now" button.
- Uses the Assembler server endpoint (see U2's server caching note for
  performance) with a fixed mm layout.
- Sample text configurable.

**Effort:** medium. Requires the Collector to talk to the Assembler
backend (currently it's pure static HTML). Either the Collector moves
under the Flask server, or a small new endpoint is exposed with CORS.

**Depends on:** reliable round-trip performance (≤ 500 ms) for it to
feel live. Will likely need server-side caching.

---

### GC9. Zone-coverage warnings — **Proposed**

Catch the "floating letter" class of bugs at capture time by detecting
when a glyph's strokes don't cross expected zones.

**What changes**

- Rule table keyed by character: e.g. `g, p, q, y, j` must have a
  descender (strokes below baseline); `b, d, f, h, k, l, t` must have
  an ascender (strokes above x-height); `a, c, e, n, o, s, u, v, w,
  x, z` should stay within the x-height zone.
- On Save, any variant that violates the rule for its character
  triggers a soft warning ("Variant 3 has no descender — continue
  anyway?").
- Override with a "save as-is" button; dismiss saves a per-font
  preference so experimental styles don't nag forever.

**Effort:** small. Static rule table + zone analysis already exists
for auto-kern.

---

### GC10. Post-hoc baseline / x-height adjust per variant — **Proposed**

Sometimes you realise the default baseline was wrong only after
drawing. Today the fix is to redraw; better to drag the lines.

**What changes**

- Enter a per-variant edit mode: a draggable baseline and x-height
  overlay on a single enlarged variant.
- New values are stored in the variant's `metadata` instead of the
  font-wide default.
- Assembler already reads per-variant metadata when present, so no
  Assembler changes needed.

**Effort:** small–medium. Main work is the drag interaction.

---

### GC11. Mobile / tablet layout — **Proposed**

The Collector's pressure-sensitive inputs live on tablets (iPad,
Surface, Wacom), but the current grid layout assumes a ≥ 1280 px
desktop. A responsive one-variant-at-a-time flow would make capture
on those devices first-class.

**What changes**

- Below ~900 px wide: switch to a single large canvas, with arrow
  buttons / swipe to move between variants and a compact bottom
  toolbar.
- Use touch-event hit targets of ≥ 44 px; keep stylus pressure where
  supported (Pointer Events already give us this).
- Settings panel becomes a slide-over sheet.
- Test on iPad (Apple Pencil), Surface Pen, and Android stylus devices.

**Effort:** medium. Responsive CSS + a mode toggle; no data-model
changes. Testing spread is the real cost.

---

## Documentation

### D1. Illustrated user guides with screenshots — **Proposed (once implementation settles)**

The existing docs are flag references. Once the Assembler and
GlyphCollector roadmap items land, the visible surface changes enough
that a fresh pass with real screenshots and end-to-end walkthroughs
will be worth more than incremental touch-ups.

**What changes**

Three separate illustrated guides:

- `docs/GUIDE_ASSEMBLER_CLI.md` — captioned terminal captures of the
  common recipes (A4 letter, A5 notebook, paginated manuscript), the
  new `--report` output, and missing-glyph banners.
- `docs/GUIDE_ASSEMBLER_GUI.md` — annotated sidebar screenshots, a
  before/after slider for balanced vs greedy wrap, the drift / space
  controls in action, and the coverage panel.
- `docs/GUIDE_GLYPHCOLLECTOR.md` — capture workflow walkthrough: queue
  mode, dashboard, per-variant redo, direct folder save, live preview.

Each guide pairs a short "why you'd want this" with a screenshot,
then the exact command or click path. Images live under `docs/img/`.

**Effort:** medium. The actual writing is mechanical — the
bottleneck is capturing screenshots that remain accurate. So this
item is explicitly scheduled **after** the Ordering-table items above
are done, to avoid re-shooting on every iteration.

**Watch out for:** image drift. Add a short "how to refresh these
screenshots" appendix to each guide so future maintainers can redo
the captures consistently.

---

## Ordering & rough sizing

### Assembler

| # | Item | Value | Effort | Risk | Order |
|---|------|-------|--------|------|-------|
| R4 | Missing-glyph fallbacks | High | Small | Low | 1 |
| U4 | Glyph-coverage feedback | High | Small | Low | 2 |
| U1 | Dry-run / report | High | Small | Low | 3 |
| U5 | PNG export | High | Small | Low | 4 |
| R3 | Per-glyph slant + bob | Medium-high | Small | Low | 5 |
| U2 | Live preview in GUI | High | Medium | Medium | 6 |
| U3 | Config files + presets | Medium | Medium | Low | 7 |
| U6 | PDF + widow/orphan | Medium | Medium | Low | 8 |
| R2 | Cursive joining (opt-in, Experimental) | High | Medium | Medium-high quality-risk when enabled (default output unchanged) | 9 |
| R1 | Pressure-aware stroke | — | — | — | Won't do |

R4 + U4 + U1 form a natural first bundle: together they remove the
single biggest current defect (silent drops) and give the user both a
clear signal ("this text has 4 uncovered glyphs") and a clear answer
("substituted 3, dropped 1, will fit on one page").

### GlyphCollector UI

| # | Item | Value | Effort | Risk | Order |
|---|------|-------|--------|------|-------|
| GC1 | Font-completeness dashboard | High | Small | Low | 1 |
| GC4 | Batch / queue capture | High | Small–Medium | Low | 2 |
| GC7 | Direct save to folder | High | Medium | Medium | 3 |
| GC2 | Character-set presets | Medium | Small | Low | 4 |
| GC6 | Per-variant reject & re-capture | Medium-high | Small | Low | 5 |
| GC5 | Jump-to-character / edit existing | High | Medium | Low | 6 |
| GC9 | Zone-coverage warnings | Medium | Small | Low | 7 |
| GC3 | Frequency-aware suggestions | Medium | Small | Low | 8 |
| GC10 | Per-variant baseline/x-height | Medium | Small–Medium | Low | 9 |
| GC8 | Assembler live-preview panel | High | Medium | Medium | 10 |
| GC11 | Mobile / tablet layout | Medium-high | Medium | Low | 11 |

**First bundle**: GC1 + GC4 + GC7. Together they turn the Collector
from a single-glyph tool into a proper font-capture workflow — the
dashboard tells you what to work on, the queue mode lets you rip
through a character set without click-to-save breaks, and direct
folder save removes the download-and-move friction that makes the
current workflow feel clunky. GC7 is a prerequisite for the smoothest
version of GC1 and GC5, so land it with or before them.

### Documentation

| # | Item | Value | Effort | Risk | Order |
|---|------|-------|--------|------|-------|
| D1 | Illustrated user guides (3 × screenshots) | High | Medium | Low | after the bundles |
