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

> **See [`docs/R2_CURSIVE_JOINING_PLAN.md`](R2_CURSIVE_JOINING_PLAN.md)** for
> the full implementation plan: algorithm, data model, Assembler and
> GlyphCollector changes, user contract, architectural implications,
> testing strategy, and phased rollout.

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

### U6. Multi-page PDF export + widow/orphan control — **Done**

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

### U7. Lightweight WYSIWYG page editor — **In progress** (Phase 1 landed)

> **Phase 1 status:** shipped in the web GUI as an additive "✎ Edit on page"
> mode — page-as-canvas with a margin frame, a draggable text block
> (writes `start-x`/`start-y`), a column-width handle (`max-width-mm`), a
> margin handle (`margin`), and a transparent on-page text layer that types
> back into the sidebar and re-renders live. Also: ruled writing-line guides
> across the column, a "fit chip" with line-height / line-spacing steppers,
> a live "≈ N lines fit" capacity readout, and an overflow warning that
> flags the text block amber when the rendered ink runs past the writable
> area (measured from the real glyph geometry, so it's exact). It owns no
> state of its own and reuses the existing render pipeline. Overlay↔ink
> alignment uses the SVG's `getScreenCTM()` (exact, letterbox-safe).
> Phase 2 (click-to-caret, multiple text frames) remains proposed.

The web GUI today is a *control panel beside a preview*: you type in a
sidebar textarea, tune ~20 numeric knobs, and watch a rendered image
update. Everything the casual user asked for already exists as fields —
text, paper size, margin, `start-x`/`start-y` (positioning), lines-per-
page, line spacing, and a "Download SVG" button. What's missing is the
*interaction model*: editing **on the page** with direct manipulation,
so a non-technical user never has to reason about millimetre offsets.

This item does not add rendering capability — it is a new front-end over
the **existing** `/api/generate` + `/api/png` + `/api/coverage`
endpoints and the existing parameters. The goal is to make the page the
editing surface.

**The core constraint.** The rendered output is hand-drawn glyph *paths*,
not selectable web text — you cannot drop a browser caret inside an SVG
`<path>`. So "WYSIWYG" here means an **aligned editing overlay**, not
contenteditable glyph paths. That choice keeps the feature lightweight
and is what makes Phase 1 small.

**What changes**

*Phase 1 — overlay editing + direct-manipulation layout (lightweight):*

- **Page-as-canvas.** Render the current page (SVG via U2's live preview)
  as the centrepiece, at a true-to-paper aspect ratio with a visible
  sheet, margins, and baseline guides drawn as overlays.
- **Type on the page.** A transparent, exactly-aligned `textarea`
  (or contenteditable) sits over the text region. The caret and
  selection are the browser's; keystrokes debounce-trigger a re-render
  underneath (reusing U2's pipeline). The user types "into" the page and
  watches their handwriting appear. This replaces the sidebar textarea
  for casual users; the sidebar stays available as "advanced".
- **Drag to position.** Dragging the text block writes back to
  `start-x` / `start-y`; dragging the margin guide writes `margin`;
  dragging the right edge of the text column writes `max-width-mm`.
  Every gesture maps 1:1 to an existing parameter — no new render
  semantics.
- **Pick paper & fit visually.** Paper-size dropdown (already present)
  plus a live "N lines fit / page" readout driven by U1's report data;
  `lines-per-page` and `line-spacing` get small +/- steppers shown on
  the page margin rather than buried in the sidebar.
- **Save as SVG / PNG.** Reuse the existing download endpoints; add a
  one-click "Save SVG" in the editor toolbar (PNG/PDF behind a menu).
- **Presets as starting points.** "New from preset" (U3) seeds paper,
  margins, and realism settings so a first-time user starts from
  `notebook-page` rather than a blank slate.

*Phase 2 — richer editing (optional follow-up):*

- **Click-to-caret on the rendered glyphs.** Have `/api/generate` emit a
  per-glyph `data-char-index` on each glyph `<g>` so a click on rendered
  ink maps back to a text offset and positions the overlay caret there.
  This is the only piece that needs a backend change (a small metadata
  emission, already feasible from `_word_info`).
- **Multiple text frames.** More than one independently-positioned block
  per page (e.g. a heading box + a body box), each with its own
  `start-x/y` and width. Requires the Assembler to accept a list of
  placed blocks rather than a single text + origin — a real but
  contained typesetter extension.
- **Live coverage inline.** Surface U4's missing-glyph markers directly
  under the offending character on the page instead of in a side panel.

**Effort:** Phase 1 **medium** — almost entirely front-end, because the
backend (render, PNG, coverage, presets, live preview) already exists;
the work is the overlay alignment maths (mm↔px), drag handles, and
keeping the editable layer pixel-locked to the render across zoom and
paper-size changes. Phase 2 **medium–large** — click-to-caret needs a
small backend metadata change; multiple text frames is a genuine
typesetter/data-model extension and should be scoped separately if
pursued.

**CLI / GUI parity note.** Under the Ground-rules parity rule, direct
manipulation is a justified **GUI-only** interaction, exactly like U2's
live preview — it introduces *no* capability the CLI lacks. Every editor
gesture resolves to an existing flag (`--start-x`, `--start-y`,
`--margin`, `--max-width-mm`, `--paper-size`, `--lines-per-page`,
`--line-spacing`). Phase 2's multiple-text-frames is the exception that
*would* add a new capability; if built, it must land with a matching CLI
surface (e.g. a multi-block config schema) to preserve parity, and is
flagged here so that requirement isn't forgotten.

**Depends on:** U2 (live preview pipeline + server caching — the editor
re-renders on every keystroke), U3 (presets as starting points), U1
(line-fit readout), U5 (SVG/PNG export). All **Done**, so Phase 1 has no
blocking prerequisites. Phase 2's click-to-caret depends on a new
per-glyph character-index emission from the renderer.

**Watch out for:**

- **Overlay drift.** The editable text layer must stay pixel-aligned to
  the rendered glyphs across window resize, zoom, and paper-size change.
  This is the main technical risk — get the single mm↔px transform right
  and reuse it everywhere; don't let the overlay and the render compute
  geometry independently.
- **Render latency on every keystroke.** Long documents with heavy
  realism effects can make per-keystroke re-render feel laggy. Reuse
  U2's debounce + in-flight cancellation, and consider a "fast draft"
  render mode (skip jitter/smoothing) while actively typing, swapping in
  the full render on pause.
- **Don't fork the parameter model.** The editor and the sidebar must
  read/write the *same* state object, so a value changed by dragging is
  reflected in the sidebar field and vice-versa. Two sources of truth
  here would be a maintenance trap.

---

## GlyphCollector UI

The browser-based capture tool already covers variant capture, Bezier
fitting, normalisation, template overlay, undo/redo, and auto-save.
The items below turn it from a single-glyph tool into a proper
font-building workflow.

### GC1. Font-completeness dashboard — **Done**

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

### GC2. Character-set presets — **Done**

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

### GC3. Frequency-aware capture suggestions — **Done**

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

### GC4. Batch / queue capture mode — **Done**

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

### GC5. Jump-to-character / edit existing — **Done**

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

### GC6. Per-variant reject & re-capture — **Done**

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

### GC7. Direct save to `glyphs/<font>/` — **Done**

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

### GC8. Assembler live-preview panel — **Done**

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

### GC9. Zone-coverage warnings — **Done**

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

### GC10. Post-hoc baseline / x-height adjust per variant — **Done**

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

### GC11. Mobile / tablet layout — **Done**

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

### D1. Illustrated user guides with screenshots — **Done**

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
| U7 | Lightweight WYSIWYG page editor (Phase 1) | High | Medium | Medium (overlay alignment) | 10 |
| R1 | Pressure-aware stroke | — | — | — | Won't do |

U7 deliberately sits after the building-block items: it is a new
front-end over machinery that R4/U1/U2/U3/U5 already provide, so it
carries little backend risk and high end-user value (it's the item that
makes the tool approachable to a non-technical writer). Phase 2
(click-to-caret, multiple text frames) is intentionally *not* in this
table — it should be re-scoped on its own once Phase 1 ships and real
usage shows which richer-editing features are actually wanted.

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
| D1 | Illustrated user guides (3 × screenshots) | High | Medium | Low | **Done** |
