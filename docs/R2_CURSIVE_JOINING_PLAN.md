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

R2 runs once per adjacent glyph pair `(A, B)` that the Typesetter has
already placed. It never modifies A or B — it only *adds* a connector
stroke between them when the pair passes a threshold.

### 4.1 Inputs

From glyph A (the variant that was just placed):

| Field | Meaning |
|-------|---------|
| `exit.x`, `exit.y` | Exit point in A's local glyph coordinates. |
| `exit.tangent_theta` | Angle (radians, 0 = → +x, counter-clockwise) of the pen's direction of motion leaving A. |
| `exit.pressure` | Pen pressure at the moment the pen left A. `[0, 1]`. |
| `metadata.no_connect_right` | Optional boolean. `True` ⇒ short-circuit, no connector after this variant. |

From glyph B (the variant about to be placed):

| Field | Meaning |
|-------|---------|
| `entry.x`, `entry.y` | Entry point in B's local coordinates. |
| `entry.tangent_theta` | Angle of pen's motion entering B. |
| `entry.pressure` | Pressure at entry. |
| `metadata.no_connect_left` | Optional boolean. `True` ⇒ no connector before this variant. |

From the current placement state:

- The absolute placement offsets that map A's and B's local coords to
  the Typesetter's glyph-unit plane (same transforms already used by
  `_process_glyph`).
- A's and B's zone metadata (`baseline_y`, `x_height`) — already loaded
  for zone-aware kerning.

From the caller / config:

- `connect_aggressiveness` in `[0.0, 1.0]` (default `0.5`).
- A global `--no-connect-letters` veto (takes precedence over all).

### 4.2 Compatibility scoring

After mapping `exit` and `entry` to absolute (x, y) in the typesetting
plane, compute four sub-scores, each in `[0, 1]`, then combine.

Let `Δx = entry.x − exit.x`, `Δy = entry.y − exit.y`, and
`h = current_line_height` (glyph units).

**Gap score** — penalises pairs whose natural endpoints are far apart.

```
gap      = √(Δx² + Δy²)                         # euclidean gap
gap_norm = gap / (0.4 × h)                      # h-relative
score_gap = max(0, 1 - gap_norm)                # linear falloff
```

The `0.4 × h` denominator calibrates "one normal letter width" against
the font's own line height. Pairs whose endpoints are further apart
than ~0.4 line-heights score 0 on gap.

**Zone score** — penalises pairs that want to cross zones (e.g. an
exit sitting above the x-height trying to connect into an entry that
sits below the baseline).

```
zone_A   = zone_of(exit.y, baseline_y_A, x_height_A)
zone_B   = zone_of(entry.y, baseline_y_B, x_height_B)
score_zone = {
    (same zone)          : 1.0
    (adjacent zones)     : 0.5
    (upper ↔ lower)      : 0.0
}
```

**Direction score** — penalises abrupt tangent changes. `Δθ` is the
signed shortest angular difference between `exit.tangent_theta` and
`entry.tangent_theta`, normalised so a perfectly-aligned pair (`Δθ = 0`)
scores 1 and a reversed one (`Δθ = ±π`) scores 0.

```
Δθ              = wrap_to_pi(entry.tangent_theta - exit.tangent_theta)
score_direction = max(0, 1 - |Δθ| / π)
```

**Pressure score** — mild penalty for pressure discontinuities, which
signal pen-lifts in the original capture:

```
score_pressure = 1 - min(1, |exit.pressure - entry.pressure| / 0.5)
```

**Combined score** — weighted average. Weights are the tunable part;
§12 tracks them as open questions.

```
score = 0.45 × score_gap        # dominant signal
      + 0.25 × score_direction
      + 0.20 × score_zone
      + 0.10 × score_pressure
```

**Threshold.** `connect_aggressiveness` maps linearly to a minimum
score:

```
threshold = 0.8 - 0.6 × connect_aggressiveness
# aggressiveness 0.0 → threshold 0.80 (strict)
# aggressiveness 0.5 → threshold 0.50 (balanced, default)
# aggressiveness 1.0 → threshold 0.20 (permissive)
```

A pair connects iff `score ≥ threshold` *and* no veto fires (§4.4).

### 4.3 Connector geometry

When a pair qualifies, build a single cubic bezier from exit to entry.

Let `P0 = exit`, `P3 = entry`, and let `d` be the straight-line gap.
Control points ride along each tangent by a length proportional to the
gap:

```
control_length = 0.35 × d

P1 = P0 + control_length × (cos(exit.tangent_theta),  sin(exit.tangent_theta))
P2 = P3 - control_length × (cos(entry.tangent_theta), sin(entry.tangent_theta))
```

The `0.35` factor is a typographic-feeling default — short enough that
connectors don't loop, long enough that they arc rather than forming a
visible corner. (Tracked under §12.)

**Pressure along the connector.** Sample the bezier at (say) 8
parameter values `t ∈ [0, 1]` and linearly interpolate
`exit.pressure → entry.pressure`. The resulting per-point list matches
the point/pressure/time format the Renderer already expects.

**Stroke flag.** Each connector carries `is_connector: true` so
downstream passes (jitter, drift) can choose to skip or attenuate
effects. Drift is applied, jitter is applied, smoothing is a no-op
(already a smooth bezier).

### 4.4 Veto paths

Checked in this order before scoring:

1. **Global.** `--no-connect-letters` on the CLI or
   `connect_letters: false` in the active config / preset → skip every
   pair.
2. **Boundary.** If A's trailing character is a space, newline,
   missing glyph, or paragraph break, or if B's leading character is a
   hard boundary → skip.
3. **Per-variant.** `metadata.no_connect_right` on A or
   `metadata.no_connect_left` on B → skip this pair only.
4. **Per-pair kerning exception.** `kerning.json` exceptions may carry
   `no_connect: true` for specific digrams (e.g. the pair `oa` in a
   font where the o's tail always looks wrong leading into a).
5. **Missing metadata.** If either A lacks `exit` or B lacks `entry` →
   skip. Backward compat for fonts captured before R2 landed.

### 4.5 Pseudocode

```python
def maybe_add_connector(prev_shape, next_shape,
                        prev_variant, next_variant,
                        prev_cursor, next_cursor,
                        line_height, cfg):
    # Global veto and missing-metadata short-circuits
    if not cfg.connect_letters:
        return None
    if not (has_exit(prev_variant) and has_entry(next_variant)):
        return None
    if prev_variant.metadata.get('no_connect_right'):
        return None
    if next_variant.metadata.get('no_connect_left'):
        return None

    # Map to absolute typeset coordinates
    exit_pt  = place(prev_variant.exit,  prev_cursor, prev_variant.baseline_y)
    entry_pt = place(next_variant.entry, next_cursor, next_variant.baseline_y)

    score = compatibility(
        exit_pt, entry_pt,
        prev_variant.baseline_y, prev_variant.x_height,
        next_variant.baseline_y, next_variant.x_height,
        line_height,
    )
    threshold = 0.8 - 0.6 * cfg.connect_aggressiveness
    if score < threshold:
        return None

    return build_connector(exit_pt, entry_pt)


def compatibility(e, i, blA, xhA, blB, xhB, h):
    gap = hypot(i.x - e.x, i.y - e.y)
    gap_norm = gap / (0.4 * h)
    s_gap = max(0.0, 1.0 - gap_norm)

    zA = zone_of(e.y, blA, xhA)
    zB = zone_of(i.y, blB, xhB)
    s_zone = {('u','u'):1.0, ('m','m'):1.0, ('l','l'):1.0,
              ('u','m'):0.5, ('m','u'):0.5,
              ('m','l'):0.5, ('l','m'):0.5,
              ('u','l'):0.0, ('l','u'):0.0}[(zA, zB)]

    dθ = wrap_pi(i.tangent_theta - e.tangent_theta)
    s_dir = max(0.0, 1.0 - abs(dθ) / math.pi)

    s_pressure = 1.0 - min(1.0, abs(e.pressure - i.pressure) / 0.5)

    return 0.45*s_gap + 0.25*s_dir + 0.20*s_zone + 0.10*s_pressure


def build_connector(p0, p3):
    d = hypot(p3.x - p0.x, p3.y - p0.y)
    L = 0.35 * d
    p1 = (p0.x + L*cos(p0.tangent_theta), p0.y + L*sin(p0.tangent_theta))
    p2 = (p3.x - L*cos(p3.tangent_theta), p3.y - L*sin(p3.tangent_theta))
    return BezierSegment(p0, p1, p2, p3, is_connector=True)
```

### 4.6 Worked example

Suppose `font1` has clean exit / entry metadata for `t` and `h`. The
pair `th` at cursor positions `(50.0, 100.0)` for `t`, `(55.5, 100.0)`
for `h`, with `line_height = 100`:

| Quantity | Value |
|----------|-------|
| `exit` (t) | `x=3.1, y=-12.0, θ=0.45, p=0.55` (local) → abs `(53.1, 88.0)` |
| `entry` (h) | `x=-2.4, y=-12.5, θ=0.48, p=0.50` (local) → abs `(53.1, 87.5)` |
| gap | `√(0² + 0.5²) = 0.5` gu |
| `gap_norm` | `0.5 / 40 = 0.0125` |
| `score_gap` | `1 - 0.0125 = 0.988` |
| zones | both upper → `score_zone = 1.0` |
| `Δθ` | `0.48 - 0.45 = 0.03` rad → `score_direction = 1 - 0.03/π = 0.990` |
| pressure Δ | `0.05` → `score_pressure = 1 - 0.1 = 0.90` |
| **combined** | `0.45·0.988 + 0.25·0.990 + 0.20·1.0 + 0.10·0.90 = 0.984` |

At default `connect_aggressiveness = 0.5`, threshold `= 0.5`. Score
`0.984 ≥ 0.5` ⇒ connect. The connector is a single bezier with
control-point length `0.35 × 0.5 = 0.175` gu along each tangent —
barely visible, which is correct for two letters whose exit and entry
almost touch.

Contrast with `ti` (dotted i, entry sits high above the dot):

| Quantity | Value |
|----------|-------|
| `exit` (t) — same as above | abs `(53.1, 88.0)` |
| `entry` (i) | abs `(55.0, 70.0)` (high on ascender dot) |
| gap | `√(1.9² + 18²) ≈ 18.1` gu |
| `gap_norm` | `18.1 / 40 = 0.45` |
| `score_gap` | `max(0, 1 - 0.45) = 0.55` |
| zones | upper → upper → `1.0` |
| `Δθ`, pressure | modest |
| **combined** | ≈ `0.78` |

At default threshold `0.5`, still connects but with a longer, more
arched connector. At `connect_aggressiveness = 0.0` (threshold `0.8`),
does not connect.

---

## 5. Data model changes

R2 adds two optional keys to the existing glyph JSON schema. Nothing
is *renamed* and nothing is *required* — a font with no R2 metadata
at all renders identically to today, just never emits a connector.

### 5.1 Per-variant `exit` and `entry`

Each variant object gains two optional sub-objects. All four numeric
fields are in the variant's own coordinate system (same system as
`strokes[*]`). Angles are in radians.

```json
{
  "id": 3,
  "strokes": [ ... ],
  "bezier_curves": [ ... ],
  "normalized_strokes": [ ... ],
  "exit": {
    "x": 47.2,
    "y": 62.1,
    "tangent_theta": 0.52,
    "pressure": 0.6
  },
  "entry": {
    "x": 12.8,
    "y": 60.4,
    "tangent_theta": -0.31,
    "pressure": 0.5
  }
}
```

Validation rules (enforced by the GlyphLibrary loader, warn-only):

- If `exit` is present, all four fields are required.
- `x` and `y` must fall inside the variant's canvas (0 ≤ x ≤ width,
  0 ≤ y ≤ height). Out-of-bounds ⇒ log a warning, treat the variant
  as having no exit.
- `tangent_theta` is wrapped into `(-π, π]` on load.
- `pressure` is clamped to `[0, 1]`.

### 5.2 Per-glyph (top-level) vetoes

The top-level glyph object may carry a `connect` block:

```json
{
  "char": "o",
  "metadata": { ... },
  "connect": {
    "no_connect_left":  false,
    "no_connect_right": true
  },
  "variants": [ ... ]
}
```

Both flags default to `false`. If either is `true`, R2 skips every
pair involving this character on that side, regardless of score. Use
for letters whose natural terminals simply don't want to be
connected (e.g. `o` often ends at a closed loop).

Kerning exceptions in `kerning.json` can also set `no_connect: true`
for specific digrams — see §4.4.

### 5.3 Backward compatibility

| Font state | R2 behaviour |
|------------|--------------|
| No `exit` / `entry` anywhere | Never connects. Output identical to today. |
| `exit` on A but no `entry` on B | Skip that specific pair. |
| Everything present, `--connect-letters` off | Never connects. |
| Everything present, `--connect-letters` on | Scorer runs (§4.2). |

Upshot: no font file ever needs to change for an R2 ship to be safe.
The feature is strictly additive.

### 5.4 Font-level defaults

`glyphs/<font>/preset.yaml` (the per-font auto-preset introduced in
U3) may set a `connect` block:

```yaml
# glyphs/myscript/preset.yaml
line_height_mm: 10
stroke_width: 0.4
connect:
  enabled: true               # same as --connect-letters
  aggressiveness: 0.6         # same as --connect-aggressiveness
```

Precedence is unchanged from U3:

```
per-font preset  <  --preset  <  --config  <  CLI flags
```

A font author who has curated their `exit` / `entry` metadata can
ship the preset with `connect.enabled: true`; users who pull the font
get the cursive look by default when they select that font, and can
still switch it off via `--no-connect-letters` or the GUI toggle.

---

## 6. Assembler changes

The bulk of the work lives in `assembler/assembler.py`. Changes are
scoped so that turning R2 off at any layer reverts to today's
behaviour exactly.

### 6.1 Typesetter

A small, well-bounded addition to `typeset_text`:

- Accept two new kwargs: `connect_letters: bool = False` and
  `connect_aggressiveness: float = 0.5`.
- Maintain `last_variant_placed` alongside the existing
  `last_shape_placed` — we need access to the variant object, not just
  its stroke list, to read `exit` metadata.
- After a glyph lands and auto-kern has shifted it, invoke
  `maybe_add_connector(prev_variant, next_variant, …)` per §4.5. When
  it returns a `BezierSegment`, append a new shape to `compiled_shapes`
  (`strokes=[[connector_points]]`) and the same geometry to
  `self._compiled_beziers` so both the polyline and the bezier-path
  emitter can render it.
- Mark the new shape: `{"is_connector": True}` sits alongside the
  existing stroke data. The Renderer keys off this to route
  connectors through the bezier path — Catmull-Rom smoothing is a
  no-op for an already-smooth curve.

**Interaction with `auto_kern`.** The kerning shift runs *before* the
connector decision, so the exit / entry points are already in their
final positions when R2 scores them. If kerning pulled two letters
tight, the gap score rises; if it pushed them apart, the gap score
falls. This is the correct coupling.

**Interaction with balanced wrap.** Wrap decisions are made at word
boundaries (a space commits the previous word). Connectors only
exist *within* a word, so balanced wrap doesn't see them — the
word's width is still the sum of its glyph widths + kerning +
connector arcs. One subtle point: the connector may extend the
word's bounding box by a fraction of a glyph unit. The word-width
measurement in `_apply_balanced_wrap` must include connectors; a
small change to the measurement pass covers this.

**Interaction with line drift.** Line drift is applied at the Renderer
level via a `<g>` around each line. Connectors belong to their line;
they rotate with it, same as any other stroke.

### 6.2 Renderer

No structural change. Connectors go through the existing path emitter:

- If a shape has `is_connector=True` AND `bezier_data` is set, emit as
  a single `<path d="M… C…">`. Already the fast path.
- Smoothing is skipped for connector shapes (they're already smooth).
- Jitter is applied per-point as today. In practice each connector
  only has 4 bezier control points, so it picks up a very mild jitter
  — which looks right.
- Per-line drift wraps connectors just like any other stroke (they
  live inside the line's `<g>`).
- In `--format png` / `--format pdf` pipelines, connectors render
  exactly like strokes. No special casing.

### 6.3 CLI

Three new flags in `argparse`:

```
--connect-letters            Enable cursive joining (Experimental).
--no-connect-letters         Disable; wins over preset / config.
--connect-aggressiveness F   Minimum-score knob, 0.0 strict → 1.0
                             permissive. Default: 0.5.
```

On first use in a run, emit a one-line **stderr** notice:

```
[R2 experimental] Cursive joining is enabled. Output quality depends
on each font's exit / entry metadata; see docs/R2_CURSIVE_JOINING_PLAN.md
```

The notice is suppressed by `--quiet` or by setting
`VHS_SUPPRESS_EXPERIMENTAL=1` in the env so CI doesn't drown in it.

### 6.4 Server + GUI

`server.py` accepts two new fields on `/api/generate`:
`connect_letters` (bool) and `connect_aggressiveness` (float). They
pass straight through to `typeset_text`.

`templates/index.html` gains, in the Styling section:

- A **Connect Letters** toggle with an `experimental` badge next to the
  label.
- A slider labelled **Connect Aggressiveness** (0.0 – 1.0, default
  0.5), visible only when the toggle is on.

Both feed through the existing payload-construction code in
`generate()`. The badge is pure CSS (no new asset).

### 6.5 Tests

New unit tests in `assembler/test_assembler.py`:

- `test_connector_scorer_pure` — feed the scorer synthetic exit /
  entry inputs and assert the 4 sub-score edge cases: perfect match →
  1.0, reversed tangent → `score_direction ≈ 0`, cross-zone upper ↔
  lower → `score_zone == 0`, very large gap → `score_gap == 0`.
- `test_connector_threshold_monotonic` — at a fixed score, sweep
  `connect_aggressiveness` from 0 to 1 and assert the connect /
  no-connect decision flips at exactly one aggressiveness.
- `test_connector_geometry` — given exit, entry, and tangents, assert
  the cubic bezier's control-point length equals `0.35 × gap`.
- `test_connector_veto_precedence` — per-variant veto wins over high
  score; `--no-connect-letters` wins over preset. Missing `exit` or
  `entry` short-circuits.
- `test_connect_no_effect_without_flag` — with the flag off, a font
  carrying full R2 metadata renders byte-identically to the same font
  rendered today.

New CLI test in `assembler/test_cli.py`:

- `test_cli_connect_letters_experimental_notice` — asserts the stderr
  notice fires on first invocation and doesn't duplicate across
  subsequent renders in the same process.

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
