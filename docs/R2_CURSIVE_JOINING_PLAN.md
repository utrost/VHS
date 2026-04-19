# R2 — Cursive Joining: Implementation Plan

> Status: **draft** (Proposed → ships as Experimental). Scope expanded
> from `docs/ROADMAP.md#R2`. This document is the source of truth for
> the feature; the roadmap entry will stay short and link here.

---

## 1. Summary & scope

R2 adds **automatic cursive-style joining** to the Assembler: between
two consecutive glyph variants that the Typesetter has already placed,
synthesise a short stroke ("connector") that bridges the previous
glyph's natural exit to the next glyph's natural entry. The synthesised
stroke participates in smoothing, drift, jitter, pagination, and
rendering like any other stroke — it is *not* a post-process SVG
filter.

R2 is **opt-in and Experimental** when shipped. Default output is
byte-identical to today: users must pass `--connect-letters` (or flip
the matching GUI toggle, or name the preset that carries it). The
first use in a session prints a one-line stderr notice; the GUI
control wears an `experimental` badge. Behaviour — scoring weights,
default threshold, connector geometry — may change between minor
releases until the feature graduates to stable.

**Out of scope.** R2 does *not* reshape glyphs, does not invent a
cursive style where one isn't captured, does not retrofit connected
writing onto a block-print hand by warping letterforms, and does not
generate exit / entry metadata from nothing. It is a joining step on
top of the existing data model.

---

## 2. Goals and non-goals

### Goals

- **Convincing connected script** for fonts that carry exit / entry
  metadata for their variants.
- **Deterministic** — given a seed and unchanged glyphs, output is
  byte-identical across runs.
- **Tunable** — a single `--connect-aggressiveness` knob covers the
  range from "only very clean matches connect" to "anything vaguely
  compatible connects".
- **Opt-in without surprise** — default off, clear notice on first
  use, per-glyph and per-font veto paths, preset-friendly.
- **Compatible with everything we shipped** — balanced wrap,
  pagination, widow / orphan shift, line drift, per-glyph slant
  jitter, PNG / PDF export.
- **Offline safe** — no new runtime dependencies beyond what's
  already in the Assembler.

### Non-goals

- **Auto-generating** exit / entry points from scratch. A migration
  helper (§7.5) can *guess* initial values from the last / first
  stroke point of each variant, but the font author owns correctness.
- **Cursive shape transformation.** If your "b" doesn't end at a
  place that wants to flow into the next letter, the only fix is to
  re-capture it. R2 will not bend the b.
- **Right-to-left / vertical scripts.** The scoring geometry assumes
  left-to-right progression.
- **Replacing ligatures.** Greedy ligature matching (`sch`, `tt`, …)
  still wins; a matched ligature is a single glyph from the
  Typesetter's perspective and connectors attach on its boundaries
  just like any other glyph.
- **Every font looking good with this on.** Block-print hands with
  consistent letter caps / valleys will produce ugly connectors no
  matter how well the algorithm works. The visualiser (§7.4) exists
  so authors can see the mess before shipping.

---

## 3. Terminology

| Term | Meaning |
|------|---------|
| **Exit point** | The (x, y) in glyph coordinates where the writer's pen would naturally leave glyph A to continue writing. Carries a tangent angle θ and pressure. |
| **Entry point** | The (x, y) where glyph B naturally wants the pen to arrive. Carries its own tangent angle and pressure. |
| **Connector stroke** | The synthesised cubic bezier from A's exit to B's entry. Emitted as a regular stroke so downstream passes (smoothing, drift, jitter, pagination) treat it uniformly. |
| **Compatibility score** | Dimensionless number in `[0, 1]`. Inputs: normalised gap distance, zone match (upper / mid / lower), direction continuity (tangent angle difference), pressure continuity. Formula in §4.2. |
| **Connect aggressiveness** | CLI / GUI knob in `[0.0, 1.0]`. Maps to the minimum score a pair needs to get a connector. `0.0` ≈ only very clean matches (≥ 0.8 score). `1.0` ≈ anything plausible (≥ 0.2). Default `0.5`. |
| **Veto** | A hard "never connect this pair" decision that short-circuits the scorer. Sources: per-variant `no_connect_left` / `no_connect_right`, whitespace, forced ligature boundaries, `--no-connect-letters` on the CLI. |
| **Reference font** | A curated, hand-authored font with vetted exit / entry metadata, shipped under `glyphs/reference/`. Used as the graduation-gate fixture for visual regressions. |
| **Zone** | Vertical band in glyph coords: `upper` (above x-height), `mid` (x-height to baseline), `lower` (below baseline). Same definition as the existing zone-aware kerning code. |

---

## 4. The algorithm

*The heart of the doc. Subsections:*

- 4.1 **Inputs** — what data the algorithm needs from each glyph pair.
- 4.2 **Compatibility scoring** — gap, zone, direction continuity,
  pressure continuity. Formula, defaults, how `--connect-aggressiveness`
  moves the threshold.
- 4.3 **Connector geometry** — cubic bezier from exit to entry, tangent
  derivation, pressure interpolation.
- 4.4 **Veto paths** — per-glyph metadata flags, kerning-exception
  blacklist, punctuation rules.
- 4.5 **Pseudocode** — ~30-line reference implementation.
- 4.6 **Worked example** — one paragraph run through the scorer for a
  handful of letter pairs.

---

## 5. Data model changes

*Exactly which fields appear in glyph JSON, what types they carry, and
the migration story for fonts captured before R2.*

- 5.1 Per-variant `exit` and `entry` metadata.
- 5.2 Per-glyph `no_connect_left` / `no_connect_right` vetoes.
- 5.3 Backward compatibility: what happens when `exit` / `entry` are
  missing (answer: that pair never connects).
- 5.4 Font-level defaults in `glyphs/<font>/preset.yaml`.

---

## 6. Assembler changes

*Everything that touches `assembler/`. Split by layer.*

- 6.1 Typesetter — new connector stroke kind, placement inside the
  existing glyph-pair loop, interaction with `auto_kern` and balanced
  wrap.
- 6.2 Renderer — connectors as regular bezier paths, participation in
  smoothing / drift / scaling / jitter.
- 6.3 CLI — `--connect-letters`, `--connect-aggressiveness`,
  experimental-status notice on first use.
- 6.4 Server + GUI — matching toggle and slider, experimental badge.
- 6.5 Tests — unit coverage for scorer, geometry, and the
  veto-wins-over-score precedence.

---

## 7. GlyphCollector changes

*What the capture tool needs to produce fonts that connect well.*

- 7.1 Capturing **exit** and **entry** per variant (click-to-pin UI).
- 7.2 Validation — flag variants that have connectors enabled but no
  exit/entry metadata.
- 7.3 Per-glyph veto flags surfaced as toggles.
- 7.4 Visualiser mode — render "what would connect to what" so font
  authors can tune their metadata before enabling the feature.
- 7.5 Migration helper — a small tool that reads an existing font and
  guesses exit/entry from the last / first stroke point of each
  variant (as a starting point).

---

## 8. User-facing contract

*What users need to know before turning R2 on.*

- 8.1 How to enable (CLI flag, GUI toggle, preset key).
- 8.2 Experimental status — what that means in practice (notice on
  first use, may change between releases).
- 8.3 Expected failure modes and how to recognise them.
- 8.4 Per-font sensitivity — not every font will look good with it on.
- 8.5 Graduation path — what has to be true before R2 → `Done`.

---

## 9. Architectural implications

*Bigger-picture consequences of adding R2.*

- 9.1 New dependency graph: Typesetter → font metadata quality.
- 9.2 Interaction with pagination (connectors crossing page boundaries).
- 9.3 Interaction with `--paginate`'s widow/orphan shift.
- 9.4 Interaction with R3 per-glyph slant jitter (connectors must ride
  the jitter rotation of the glyph they exit).
- 9.5 Interaction with the Catmull-Rom smoother.
- 9.6 Plotter pen-up/pen-down implications — a connector *is* a stroke,
  so a pen plotter stays in contact through it.

---

## 10. Testing & validation

- 10.1 Unit tests — scorer, geometry, veto precedence.
- 10.2 CLI smoke tests.
- 10.3 Reference-font fixture — a small curated font with hand-tuned
  exit/entry metadata used as the graduation gate.
- 10.4 Visual regression — before/after PNGs committed to `docs/img/`.

---

## 11. Rollout

- 11.1 Phase 1 — ship behind `--connect-letters`, default off.
- 11.2 Phase 2 — bake a reference font and ship it under `glyphs/`.
- 11.3 Phase 3 — graduate status to `Done`, keep flag on for opt-in
  (not default).
- 11.4 Kill-switch plan if the feature causes regressions in later
  refactors.

---

## 12. Open questions

*Things we haven't decided yet. Will shrink as sections above firm up.*

---

## Appendix A — Reference citations

*Papers / prior art on automatic handwriting joining, if useful.*

---

## Appendix B — How to re-run the visual regressions

*Analogous to the "how to refresh the screenshots" appendix in the
illustrated user guides.*
