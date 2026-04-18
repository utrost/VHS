# R2 — Cursive Joining: Implementation Plan

> Status: **draft** (Proposed → ships as Experimental). Scope expanded
> from `docs/ROADMAP.md#R2`. This document is the source of truth for
> the feature; the roadmap entry will stay short and link here.

---

## 1. Summary & scope

*One-paragraph description of what R2 does, what it explicitly is NOT
(not a cursive font generator, not a stroke-shape transformer), and
the Experimental-status contract.*

---

## 2. Goals and non-goals

*Bullet list of outcomes we're shipping for, plus bullet list of
things explicitly out of scope so the feature doesn't sprawl.*

---

## 3. Terminology

*Short glossary: exit point, entry point, connector stroke,
compatibility score, connect aggressiveness, no-connect veto. Avoids
ambiguity in the rest of the doc.*

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
