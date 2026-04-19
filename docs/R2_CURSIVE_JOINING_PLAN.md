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

The Collector is where `exit` and `entry` metadata is *created*. R2's
output quality depends directly on the care taken here, so the tool
needs first-class affordances for marking those points and for
checking how well they compose across the font.

### 7.1 Capturing exit and entry (click-to-pin)

A new **Pins** mode in the Collector header, toggled by a keyboard
shortcut (`P`) or a header button. While Pins mode is on, normal
drawing is disabled and the canvas accepts two click gestures per
slot:

- **Click + drag** near where the pen would *leave* the glyph → sets
  `exit.x`, `exit.y`, and (from the drag direction)
  `exit.tangent_theta`. `exit.pressure` is sampled from the nearest
  existing stroke point, defaulting to `0.5`.
- **Shift + click + drag** near where the pen would *enter* → sets
  `entry.*`.

Visual feedback:

- The exit pin renders as a green arrow at the pin position, pointing
  along the tangent.
- The entry pin renders as a blue arrow, same idea.
- A faint phantom connector line draws from the exit pin to the *next
  slot's* entry pin (if any) so the author can see what would connect
  to what.

A small **Auto-guess** button in Pins mode runs the migration helper
logic (§7.5) on the current slot: it picks the last stroke point as
the exit and the first stroke point of the *next* variant's first
stroke as a candidate entry. Starting point only; the author is
expected to refine.

### 7.2 Validation

On save, the Collector checks each active variant for consistency:

| Check | Severity |
|-------|----------|
| Variant has `exit` but no `entry` (or vice-versa) | Warning, save continues. |
| `exit.x` or `exit.y` is outside the variant canvas | Warning. |
| `exit.tangent_theta` falls outside `(-π, π]` (sanity) | Auto-corrected silently. |
| `connect.enabled = true` at font level but zero variants carry pins | Warning, shown once per session. |

Warnings surface via the same confirm dialog R2 added for zone checks
(§GC9), with a "Save anyway" escape hatch.

### 7.3 Per-glyph veto flags

Two checkboxes in the Collector **Settings** panel:

- **Never connect on the left** → writes `connect.no_connect_left` to
  the top-level glyph object.
- **Never connect on the right** → writes `connect.no_connect_right`.

The checkboxes are per-character (not per-variant): the flag is a
property of the letter, not of a single drawing of it.

### 7.4 Visualiser mode

A new **Pair Visualiser** panel, opened from a fourth header button
(🔗 or similar). The panel does two things:

1. **Pair grid.** Renders a small SVG per candidate digram in the
   target set (e.g. every `ab`, `bc`, `cd`, … for Basic Latin). Each
   cell shows the two glyphs with the connector drawn if R2 would
   produce one at the current aggressiveness, and greyed out if it
   wouldn't. The compatibility score is shown as a tooltip and as a
   small badge beneath the pair.
2. **Heatmap.** A 26×26 (or N×N) colour heatmap of scores across the
   Latin alphabet. Cells in the 0.8+ range are green, 0.5–0.8 yellow,
   below 0.5 red. Lets authors see at a glance which letters have
   good exit metadata and which are dragging everything down.

Both views call the Assembler's `/api/generate` endpoint with
`connect_letters=true` and a short sample text for each pair. The
server is the one already running the GUI — no new backend.

### 7.5 Migration helper

A standalone CLI tool `assembler/tools/guess_connect_metadata.py`:

```bash
python3 -m assembler.tools.guess_connect_metadata glyphs/MyFont/ \
    --dry-run            # print what would change, don't write
```

For each `*.json` in the font directory, for each variant:

- `exit`  ← last point of the last stroke, with `tangent_theta`
  computed from the last two points, and `pressure` equal to that
  point's pressure.
- `entry` ← first point of the first stroke, similarly.

Writes the updated JSON in place (or shows a diff with `--dry-run`).
The author runs this once to bootstrap a font's metadata, then
refines pin-by-pin in the Collector. Explicit `--overwrite` is needed
to replace existing `exit` / `entry` blocks; by default the tool
leaves already-annotated variants alone.

**Safety net.** Because every step is additive JSON, `--dry-run` → git
diff → manual cherry-pick is the recommended workflow for a first
migration.

---

## 8. User-facing contract

This section is written to be pasted (with light edits) into
`docs/USER_GUIDE.md` when R2 ships.

### 8.1 How to enable

Three equivalent paths. Pick whichever fits your workflow:

- **CLI**: `--connect-letters` (with an optional
  `--connect-aggressiveness 0.0–1.0`).
- **GUI**: the **Connect Letters** toggle in the Styling section, with
  the accompanying slider.
- **Preset / config**: a `connect:` block in any YAML config file or
  bundled preset (§5.4).

Explicit CLI flags still override presets and configs — the precedence
chain from U3 is unchanged.

### 8.2 Experimental status — what that means

- **On first use per process**, the CLI prints a one-line stderr
  notice pointing at this document.
- **In the GUI**, the toggle wears an `experimental` badge.
- **Behaviour may change** between minor releases: scoring weights,
  connector geometry, and the default threshold are all in flux until
  the feature graduates. Pin a Assembler version if you need
  byte-stable output across a release.
- **R2 will never become default-on** — even after graduating to
  `Done`, users (or fonts, via a preset) must opt in explicitly.

### 8.3 Expected failure modes

- **Everything looks disconnected.** The threshold is too strict for
  your font. Raise `--connect-aggressiveness` toward `1.0` (or slide
  the GUI knob right).
- **Connectors cross through letterforms.** Two glyphs whose exit and
  entry sit in incompatible zones are connecting anyway. Either
  lower aggressiveness, set a per-glyph `no_connect_*` on the
  offending letter, or refine its exit / entry metadata in the
  Collector.
- **A connector loops or overshoots.** The `0.35` control-point
  length (§4.3) is too long for a very short gap. This is a scorer
  tuning issue tracked in §12; for now, either add a per-pair
  `no_connect` kerning exception or tighten the exit / entry
  tangents in the Collector.
- **The first letter of every word is on its own.** Correct — R2 only
  connects *within* a word. Spaces are hard boundaries.
- **Connectors disappear at a page break.** Correct — a connector
  between the last word of one page and the first of the next would
  be cut in half, so §9.2 drops them.

### 8.4 Per-font sensitivity

R2 is only as good as the font's exit / entry metadata. Rules of
thumb:

| Font style | R2 verdict |
|------------|------------|
| Connected cursive hand, captured with care | Excellent — this is the design target. |
| Print-style hand with exits near the baseline | Good, tune aggressiveness to taste. |
| Block print with square letter ends | Poor — no amount of scoring will make unfriendly terminals look connected. |
| Scribbled / high-jitter hand | Unpredictable — exits and entries wander across captures. |

Before enabling R2 on a font in production, run the Pair Visualiser
(§7.4) and glance at the heatmap. A font that's mostly green across
the main diagonal will look great; a font that's mostly red won't.

### 8.5 Graduation path (Experimental → Done)

R2 stays `Experimental` until *all* of these are true:

1. **Reference font fixture exists**: `glyphs/reference/` ships with
   curated exit / entry metadata and passes every pair in the
   visualiser heatmap at score ≥ 0.6.
2. **Visual regression suite is green**: `docs/img/r2-visual-
   regression/` contains before/after PNGs for the reference font
   across five sample sentences; all byte-identical across two
   consecutive minor releases.
3. **User-reported issues** (GitHub label `R2`) close at the same
   rate as any other Assembler feature over a 2-release window. No
   open high-severity bugs.
4. **Scorer weights are frozen.** No parameter in §4.2 has moved
   since the start of the 2-release stability window.

When all four are met, the status flips to `Done` in
`docs/ROADMAP.md`, the stderr notice stops firing, the GUI badge is
removed, and this planning document is linked from the User Guide
as historical context.

---

## 9. Architectural implications

Shipping R2 is not *just* a local feature add — it introduces new
coupling between the Typesetter and the font data, and new
interactions with every other feature that touches stroke geometry.

### 9.1 Typesetter ⇄ font metadata quality

Before R2, the Typesetter was robust to low-quality fonts: missing
glyphs got a debug log and a space-width advance, nothing else. With
R2 on, output quality depends on `exit` and `entry` accuracy. The
risk is silent degradation — a font that used to render fine now
looks wrong because someone moved a pin by a few pixels in the
Collector.

**Mitigations**:

- Validation warnings at load time (§7.2 rules, enforced
  server-side too).
- The Pair Visualiser (§7.4) as the standard "does this font still
  look ok?" sanity check before committing font changes.
- The opt-in gate (§1) means fonts default to the pre-R2 rendering
  pipeline unless the user or preset asks for R2.

### 9.2 Pagination (`--paginate`)

A connector lives between two adjacent glyphs. When pagination slices
`_line_info` into pages, a word may straddle a page break (rare —
wrap prevents it), but two words cannot. Connectors therefore never
cross a page boundary; no special case needed.

**Edge case**: if a font is configured with connectors between
*words* (hypothetical future work), `_word_info` would need a
per-word-boundary connector flag so pagination can decide whether to
suppress or render the boundary connector. Not in scope for R2 v1.

### 9.3 Widow / orphan shift

Widow / orphan logic in `_adjust_page_breaks` operates on whole
lines; it moves entire lines between pages. A line's connectors move
with it. No interaction.

### 9.4 R3 per-glyph slant jitter

R3 applies a small rotation to each glyph around a pivot (baseline
midpoint). That rotation happens *before* connector placement, so
the exit / entry points fed into §4.2 are already in their
post-jitter positions. Connectors inherit the jitter naturally: they
attach to the rotated exit and rotated entry, so the connector bends
to match.

**Subtlety**: if the author sets a very large `--glyph-slant-jitter`
(e.g. > 3°), a pair that scored 0.6 at rest may score 0.1 post-jitter
because the tangent angles diverged. That's fine — the scorer runs
per render, so it always sees the actual geometry. It does mean R2
output is *less reproducible* under large jitter than without,
which the Experimental notice already warns about.

### 9.5 Catmull-Rom smoothing

The Renderer currently runs Catmull-Rom splines over each stroke's
polyline. For stroke lists from the original capture, this adds
fluidity. For R2 connectors, the "stroke" is a synthesised 4-point
bezier control polygon — running Catmull-Rom over those four points
would smooth a curve that's already smooth, introducing overshoot.
Connectors therefore bypass the smoother and render directly via
the existing bezier path (`<path d="M… C…">`). The `is_connector`
flag on the shape drives that branch.

### 9.6 Pen-plotter implications

A pen plotter interprets each SVG `<path>` as "pen down, trace this,
pen up". R2 connectors are regular `<path>` elements, so the plotter
stays in contact through the connector — which is what a real
cursive hand does. This is the right default.

Two wrinkles for plotter users:

- **Ink flow**. The connector carries interpolated pressure per
  §4.3, but most pen plotters ignore pressure and draw at constant
  ink. The on-paper result is a constant-width curve where a real
  writer might have varied pressure. Acceptable; matches current
  Assembler behaviour for all strokes.
- **Pen lifts inside a glyph**. If a variant's strokes required the
  writer to lift the pen mid-glyph (e.g. the cross-bar on a `t`),
  R2 does not collapse those lifts. It only adds a connector *after*
  the variant's last stroke. The plotter still lifts the pen between
  the variant's internal strokes.

### 9.7 Live preview in the Collector (GC8)

The Collector's live preview goes through `/api/generate` with the
current font's saved glyphs. When the author enables R2 in the
preview panel, they see the current font's connector behaviour
live. This is explicit synergy with the visualiser (§7.4), which
does the same thing but structured as a pair-wise grid rather than a
prose sample.

---

## 10. Testing & validation

Testing R2 is unusually subjective because the output is visual. The
plan is to pin down the mechanical parts with unit tests and the
subjective parts with a reference fixture + committed PNGs.

### 10.1 Unit tests (assembler/test_assembler.py)

Pure-function tests that don't need a font:

| Test | Asserts |
|------|---------|
| `test_connector_scorer_perfect` | Identical exit/entry → score = 1.0 exactly. |
| `test_connector_scorer_subscore_edges` | Each of the four sub-scores hits 0 at its worst case (huge gap / reversed tangent / cross-zone / pressure Δ=1). |
| `test_connector_threshold_monotonic` | At a fixed score, the connect / no-connect decision flips exactly once as aggressiveness sweeps 0 → 1. |
| `test_connector_geometry` | Control-point distance = `0.35 × gap`, tangent-aligned. |
| `test_connector_veto_wins` | Per-variant `no_connect_*` short-circuits even at score 1.0. |
| `test_connect_no_effect_without_flag` | R2 metadata present + `connect_letters=False` → output byte-identical to today. |

### 10.2 CLI tests (assembler/test_cli.py)

| Test | Asserts |
|------|---------|
| `test_cli_connect_letters_flag` | `--connect-letters` produces SVG that contains at least one connector path (has `is_connector` data attribute or bezier with known pattern). |
| `test_cli_connect_aggressiveness_range` | `--connect-aggressiveness 2.0` rejected with clear error. |
| `test_cli_no_connect_letters_wins` | `--preset <with-connect-on> --no-connect-letters` → no connectors. |
| `test_cli_experimental_notice_fires_once` | Running two renders in the same process prints the stderr notice only once. |

### 10.3 Reference-font fixture

Shipped as `glyphs/reference/` (small, maybe 30 glyphs: lowercase + a
handful of caps and punctuation), with hand-authored exit / entry
metadata. Committed to the repo and carved out of `.gitignore` the
same way `font1` is.

The reference font is both a CI dependency (visual regression uses
it) and an example for font authors — "here's what the metadata
should look like for a font that joins well".

### 10.4 Visual regression suite

Directory: `docs/img/r2-visual-regression/`.

A new capture script, `docs/tools/capture_r2_regressions.py`, renders
five sample sentences with the reference font both on and off:

- `quick-brown-fox.png` / `.off.png`
- `call-me-ishmael.png` / `.off.png`
- `alphabet.png` / `.off.png` (full alphabet twice)
- `digits-punct.png` / `.off.png` (`0123 4567 89.,;:!?`)
- `drift-stack.png` / `.off.png` (R3 drift on top of R2, to catch
  coupling bugs)

The committed PNGs are the reference. CI runs the same script and
asserts the PNGs byte-match (or match within a tolerance, via
`pixelmatch`). Any pixel-level change requires a deliberate re-commit
of the reference PNGs — that's the graduation gate (§8.5, item 2).

### 10.5 Manual checklist (release readiness)

Before cutting a minor release with R2 changes:

- [ ] All unit tests green, both runs and CI matrix.
- [ ] Visual regression suite green.
- [ ] Pair Visualiser heatmap for the reference font has no
  regression cells (new red where there was green).
- [ ] Experimental notice fires as expected on a fresh CLI run.
- [ ] GUI badge renders.
- [ ] `--no-connect-letters` still overrides presets.

---

## 11. Rollout

R2 lands in three phases spread across at least three minor releases.

### 11.1 Phase 1 — Engine + opt-in CLI / GUI

- `assembler/assembler.py` gains the scorer, geometry, flags, tests.
- `server.py` + `index.html` gain the toggle + slider.
- Data model accepts `exit` / `entry` but *no one captures it yet*.
- Users who want to experiment can hand-author metadata or run the
  migration helper (§7.5) for an approximate starting point.
- Status: **Experimental**.
- Visible regressions this phase: zero (the feature is strictly
  additive and default-off).

### 11.2 Phase 2 — Collector + reference font

- Pins mode in the Collector (§7.1) so authoring metadata is
  first-class.
- Pair Visualiser (§7.4) and migration helper (§7.5) shipped.
- `glyphs/reference/` baked and carved out of `.gitignore`.
- Visual regression suite wired into CI.
- Status: still **Experimental**.

### 11.3 Phase 3 — Graduation

- Two minor releases of stable visual regressions with no scorer
  changes.
- All four §8.5 criteria met.
- Status flips to **Done** in `docs/ROADMAP.md`.
- Stderr notice + GUI badge removed.
- This planning document becomes historical reference, still linked
  from the User Guide.

### 11.4 Kill-switch

Because R2 is strictly additive and gated behind `--connect-letters`,
disabling it is always a flag flip away. Three kill-switch levels:

1. **Per render**: `--no-connect-letters` (CLI) / toggle off (GUI).
2. **Per font**: set `connect.enabled: false` in the font's preset,
   or delete the per-font preset.
3. **Global**: remove the feature flag's default from the shipping
   Assembler — no code paths unique to R2 run when the flag is off.

If a serious regression surfaces post-ship, step 3 can be delivered
as a patch release (`connect_letters` default forced to `False` in
`argparse`; preset / config values ignored with a one-line log
warning). No data migration needed — the `exit` / `entry` metadata
stays dormant in the JSON until the feature is re-enabled.

---

## 12. Open questions

Things that are *deliberately* unresolved in this plan. Each will be
answered as we build and measure. Tracked here so decisions are
visible, not buried.

### Scorer shape

- **Q1. Weight tuning.** Are `(0.45, 0.25, 0.20, 0.10)` the right
  weights for (gap, direction, zone, pressure)? We'll know after the
  reference font is curated and the heatmap looks reasonable.
  Expected to land before Phase 2.
- **Q2. Is pressure continuity pulling its weight?** A `0.10`
  contribution may be noise. If the pressure sub-score correlates
  strongly with the others in practice, drop it and redistribute.
- **Q3. Should the threshold be linear in aggressiveness?** Current
  formula is `0.8 - 0.6 × a`. A sigmoid-ish mapping might feel more
  natural at the extremes. Needs user testing with the slider.

### Geometry

- **Q4. Control-point length factor.** The `0.35` factor works on
  paper; short gaps at high tangent divergence may produce
  unsightly loops. An adaptive factor (e.g. scale by
  `cos(Δθ / 2)`) may be better.
- **Q5. Pressure sampling density.** 8 samples along the connector is
  a guess. If pen-plotter users report visible quantisation, raise
  to 16.

### Interaction

- **Q6. Should connectors participate in per-glyph slant jitter at a
  fraction of the glyph's angle?** Currently they inherit it in full.
  Half might look more natural.
- **Q7. Between-word connectors?** Some styles ligate across word
  boundaries (e.g. French handwriting with "e le" connecting). Out of
  scope for v1; revisit after graduation.
- **Q8. Visualiser shipping unit.** The Pair Visualiser (§7.4) is
  proposed inside the Collector. Should it also ship as a standalone
  tool (e.g. `docs/tools/pair_visualiser.html`) for authors who don't
  want to open the full Collector?

### Cross-feature

- **Q9. Migration helper defaults.** Should `guess_connect_metadata`
  default to `--dry-run` or to in-place write? Trading safety against
  ergonomics. Leaning dry-run.
- **Q10. Kerning-exception sharing.** Per-pair `no_connect` lives in
  `kerning.json`. Should it be per-font (shared with kerning
  overrides) or in a separate file so it can travel independently?
  Current plan: co-located with kerning; revisit if `kerning.json`
  grows too large.

---

## Appendix A — Reference citations

Not a literature review — just the prior art the scorer and geometry
draw from.

- **Schneider, P. J. (1990)** — *An Algorithm for Automatically
  Fitting Digitized Curves.* The bezier-fit pipeline already
  shipped in the Collector's Bezier mode uses this; R2's `is_connector`
  path re-uses the same cubic output format.
- **Catmull-Rom splines** — the existing renderer smoothing. Section
  §9.5 explains why R2 bypasses it.
- **Knuth, D. E. & Plass, M. F. (1981)** — *Breaking Paragraphs into
  Lines.* The minimum-raggedness DP from the balanced wrap work
  (item U1) is not directly used by R2, but its "decide across the
  whole paragraph before committing" pattern informed §4's "score
  every placed pair before committing connectors" approach.
- **Prior art in typography tools**: Glyphs, FontForge, and Adobe's
  "contextual alternates" (OpenType's `calt`) all solve a related
  problem for TTF/OTF fonts. R2 targets a different output (single-
  stroke plotter-ready SVG) so the implementations aren't directly
  portable, but the UX affordances around opt-in + per-pair
  exceptions borrow from that tradition.

---

## Appendix B — How to re-run the visual regressions

Analogous to the "how to refresh the screenshots" appendix in each
illustrated user guide.

### Prerequisites

```bash
pip install pyyaml cairosvg pypdf playwright pixelmatch
```

### Regenerate all regression images

Run from the repo root:

```bash
python3 docs/tools/capture_r2_regressions.py
```

The script boots the Assembler server (or assumes one running at
`http://localhost:5001`), renders every sample listed in §10.4 twice
(with `--connect-letters` and `--no-connect-letters`), and writes
PNGs into `docs/img/r2-visual-regression/`.

### Accept a deliberate change

If a real change to the pipeline (scorer weights, geometry, etc.) is
supposed to alter the reference images, the flow is:

1. Run the script.
2. Inspect the diff against the committed PNGs.
3. If the diff looks right, `git add docs/img/r2-visual-regression/`
   and commit with a message explaining *why* the images changed.
4. Note the change in `docs/ROADMAP.md` under R2's "Phase" bullet so
   the graduation-stability clock resets if scorer weights moved
   (§8.5, item 4).

### Why seeded and reproducible

All R2 renders use the `--seed 42` convention from the rest of the
capture tooling. Together with the deterministic-seed guarantee from
U2, identical inputs produce identical outputs across runs and
machines. If the regression suite is flaky, the bug is in the
pipeline, not the test.
