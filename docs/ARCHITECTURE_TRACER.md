# VHS Tracer — architecture

Technical companion to the [Tracer user guide](GUIDE_TRACER.md). This
document describes how `TracerUI/TracerUI.html` is built: its design
constraints, data model, coordinate math, input pipeline, stabilisation,
rendering, and export. Line references point into that single file.

---

## 1. Design constraints

These constraints shape every decision below; they are inherited from the
GlyphCollector and are deliberate, not incidental.

| Constraint | Consequence |
|-----------|-------------|
| **Single self-contained file** | All HTML/CSS/JS inline. No modules, no bundler. |
| **No build step** | Ships as source; "open the file" is the install. |
| **No CDN / no network** | Inline CSS (no Tailwind), no web fonts, no remote assets → works offline on a tablet. |
| **No server** | All state in memory; persistence is file download / upload. |
| **Pen-first** | The pen is the primary instrument; touch drives the *view*, not the ink. |
| **Non-destructive** | Raw captured points are never mutated; smoothing is applied downstream and stays re-tunable. |

The whole program is ~625 lines: a `<style>` block, static DOM, and one
`<script>`. There is no framework and no global build of DOM — the toolbar
is hand-wired in section 12 of the script.

---

## 2. Module map

The script is organised into labelled sections (each fenced by a `// ───`
banner comment). Reading top to bottom:

```
State                    (169)  AW/AH, bgImage, view, dpr, strokes, cfg, touches, gesture
Canvas sizing (HiDPI)    (189)  resize()
Coordinate transforms    (202)  toArtboard(), fitView(), zoomAbout()
Stabilisation            (230)  stabilize(), catmullRom(), processStroke(), halfWidth()
Rendering                (284)  render(), drawStroke(), outlinePoints(), outlinePath()
Pointer input            (351)  pointerdown/move/up routing, addPoint()
Touch gestures           (396)  startGesture(), updateGesture(), wheel zoom
HUD                      (442)  updateHud(), showPressure()
Image loading            (456)  loadImageFromSrc(), readImageFile(), drag & drop
Save / load              (491)  download(), buildJSON(), buildSVG(), loadTraceJSON()
Toolbar wiring           (566)  bindRange(), setStab(), event bindings
Boot                     (618)  resize + fitView + window.__tracer test hooks
```

There is no central event loop or state store. The model is a plain
mutable-state + explicit-`render()` design: input handlers mutate `strokes`
/ `view` and call `render()`. Every visual is recomputed from state on each
`render()` — there is no incremental/dirty-rect drawing.

---

## 3. Data model

Five pieces of module-level state (`TracerUI.html:169`) hold everything:

- **`AW`, `AH`** — artboard width/height in *artboard units*. Set to the
  reference image's natural pixel size when an image loads; default
  `1000×1400`. This is the SVG `viewBox` on export.
- **`bgImage`, `bgName`** — the loaded `Image` and its filename.
- **`view = { s, ox, oy }`** — the pan/zoom transform (see §4).
- **`strokes`** — the document. An array of stroke objects:
  ```js
  { color: "#111111", width: 4, points: [ {x, y, p, t}, … ] }
  ```
  Coordinates are in **artboard space** (zoom-independent). `p` is pen
  pressure 0–1; `t` is a capture timestamp (`Date.now()`).
- **`cfg`** — the live settings mirror of the toolbar (`imgOpacity`,
  `penColor`, `penWidth`, `stab`, `smooth`, `varw`).

`redoStack` holds popped strokes for redo; `current` is the in-progress
stroke (a reference also pushed into `strokes`, so appending points is live).

**Key invariant:** points are stored **raw** in artboard space. Nothing in
the pipeline writes back into `stroke.points`. Stabilisation and smoothing
are pure functions applied at render/export time (§5).

---

## 4. Coordinate systems

Three spaces, two transforms. Getting this right is the crux of the tool.

```
 artboard space          CSS pixel space           device pixel space
 (stroke storage,   ──▶  (client coords,      ──▶  (canvas backing store,
  SVG viewBox)            getBoundingClientRect)     canvas.width/height)

   css = o + s · artboard                 device = dpr · css
```

- **`view.s`** — scale (artboard units → CSS px).
- **`view.ox`, `view.oy`** — translation in CSS px.
- **`dpr`** — `devicePixelRatio`, applied only at the very end for HiDPI.

**Screen → artboard** (`toArtboard`, `:202`), used to store points:
```js
artboard = (client − rect.left − view.ox) / view.s
```

**Artboard → device** (in `render`, `:284`), one combined matrix:
```js
ctx.setTransform(dpr*view.s, 0, 0, dpr*view.s, dpr*view.ox, dpr*view.oy);
```
Because it composes translate-then-scale into a single matrix, the whole
scene (sheet, image, every stroke) is drawn in raw artboard coordinates and
the GPU handles pan/zoom/DPR. Ink is part of the artwork, so it scales with
zoom (a stroke's `width` is in artboard units, not screen pixels).

**`fitView`** (`:207`) centres the artboard with padding.
**`zoomAbout(cx, cy, factor)`** (`:215`) zooms while keeping the artboard
point under `(cx, cy)` fixed — the standard "zoom toward cursor" math:
```js
a  = (c − o) / s        // artboard point under the cursor, before
s' = clamp(s · factor)
o' = c − a · s'         // solve so a maps back to c, after
```
Wheel zoom and pinch zoom both reduce to this.

---

## 5. Stabilisation & smoothing pipeline

Two independent, non-destructive stages, both **ported from the
GlyphCollector** and both pure functions over a point array. Composed by
`processStroke` (`:272`):

```
raw points ──▶ stabilize(strength) ──▶ [smooth?] catmullRom() ──▶ display / export
   (stored)      EMA position pull        Catmull-Rom resample
```

### 5a. Stabilizer — `stabilize(points, strength)` (`:230`)

An exponential moving average that "pulls" each point toward the running
average, damping hand jitter:
```js
a = 1 − strength                     // fraction of the new raw point kept
sx += (raw.x − sx) · a               // (same for y and pressure p)
```
`strength = 0` returns the input unchanged. The toolbar slider (0–100) maps
to `strength ∈ [0, 0.85]` (`setStab`, `:572`) — capped below 1 so the line
can never fully freeze. Pressure is smoothed alongside position, so width
transitions stay clean.

This is the piece added on top of the collector (the collector smooths for
rendering but has no jitter-damping stabiliser); it is what makes shaky
freehand tracing usable.

### 5b. Smooth — `catmullRom(stroke)` (`:246`)

Catmull-Rom interpolation, copied from the collector's `catmullRomPoints`.
Turns sparse/steppy samples into a flowing curve by inserting interpolated
points between each pair (step count scales with segment length,
`floor(segLen/4)`, clamped 2–12). Pressure is linearly interpolated across
each inserted span. Toggled by `cfg.smooth`.

Because both stages are recomputed on every `render()`, moving the
Stabilizer slider or toggling Smooth re-derives the whole document live from
the untouched raw points — and the same `processStroke` feeds SVG export, so
what you see is what you get.

---

## 6. Input pipeline

Pointer Events unify pen, touch, and mouse. Routing is by `pointerType`
(`pointerdown`, `:353`):

```
pointerdown ─┬─ type 'touch'          ─▶ touches.set(id); startGesture()   (view)
             └─ type 'pen' | 'mouse'  ─▶ new stroke; setPointerCapture; addPoint()  (ink)
```

Drawing and view gestures live in separate channels and never conflict —
which is exactly the tablet ergonomic you want (pen inks, fingers pan/zoom)
and gives **palm rejection for free** (a resting palm registers as `touch`
and only ever moves the view, never draws).

**`addPoint(e)`** (`:386`):
1. `toArtboard(e.clientX, e.clientY)` → artboard coordinates.
2. Pen pressure from `e.pressure`; mouse (no pressure) falls back to `0.5`.
3. Push `{x, y, p, t}` onto `current.points`; update the pressure meter.

**Coalesced events:** on `pointermove` (`:365`), `e.getCoalescedEvents()`
replays the sub-frame samples the OS batched, so fast strokes keep their
fidelity instead of being decimated to the animation-frame rate. Same trick
as the collector.

`setPointerCapture` keeps the stroke attached to the canvas even if the pen
strays outside it mid-stroke.

---

## 7. Gesture system

Touch pointers accumulate in the `touches` map; `startGesture`/
`updateGesture` (`:396`) interpret them:

- **1 touch → pan.** Record `view.ox/oy` and the start position; on move,
  translate by the finger delta.
- **2 touches → pinch-zoom.** Record start distance, midpoint, and
  transform; on move, `factor = dist/startDist`, then re-solve `ox/oy` so
  the gesture's start artboard-midpoint follows the *current* midpoint —
  combined pan **and** zoom in one gesture (the §4 zoom-about math with a
  moving anchor).
- Adding/removing a finger re-seeds the gesture (`startGesture` is called on
  every touch down/up), so 1↔2 finger transitions don't jump.

**Wheel** (`:432`) calls `zoomAbout` at the cursor with a 1.1× step.
`preventDefault` + `touch-action: none` on the canvas stop the browser from
hijacking scroll/zoom.

---

## 8. Rendering

`render()` (`:284`) is the single draw entry point, called after any state
change. It:
1. Resets and clears the device-pixel canvas.
2. Installs the combined artboard→device matrix (§4).
3. Paints the white artboard sheet, then the reference image at
   `cfg.imgOpacity`.
4. Draws every stroke via `drawStroke`.

**`drawStroke(st)`** (`:304`) runs `processStroke` then renders per mode:

- **1 point** → a filled dot (`arc`, radius from pressure).
- **Pressure on (`cfg.varw`)** → a filled **outline** (variable width).
- **Pressure off** → a plain centreline `stroke` at constant `st.width`.

### Variable-width outline — `outlinePoints` (`:328`)

Pressure can't be expressed by SVG/canvas `stroke-width` along a path, so
width is turned into geometry. For each centreline point:
```
tangent  = normalize(next − prev)
normal   = (−tangent.y, tangent.x)
w        = halfWidth(baseW, p)         # baseW·(0.35 + 1.15·p)/2
left  = point + normal·w
right = point − normal·w
```
The polygon walks `left[]` forward then `right[]` reversed and closes — a
filled ribbon whose thickness tracks pressure. `halfWidth` (`:279`) is the
one place the pressure→width curve lives, shared by canvas dots, canvas
outlines, and SVG export, so all three agree.

---

## 9. Pressure model

- **Capture:** `e.pressure` per point (incl. coalesced sub-samples), stored
  as `p`. Absent/again-`0.5` mouse input defaults to `0.5`.
- **Live feedback:** `showPressure` (`:448`) drives the bottom-right meter.
- **Rendering:** variable-width outline (§8), toggle `cfg.varw`.
- **Persistence:** `p` is written per point in JSON (lossless) and baked
  into outline geometry in SVG.

Pressure is stabilised together with position (§5a), so width doesn't
flicker on noisy pressure sensors.

---

## 10. Export & round-trip

### JSON — `buildJSON` (`:499`) — lossless, re-openable

Serialises artboard size, image name, current `settings`, and every stroke
with **raw** points (coordinates rounded to 2 dp, pressure to 3 dp for
size). Because raw points and the smoothing settings are both stored, a
re-opened file reproduces the look *and* stays re-tunable. Schema is in the
[user guide](GUIDE_TRACER.md#export-formats).

### SVG — `buildSVG` (`:515`) — processed artwork

Emits a `viewBox="0 0 AW AH"` document. Each stroke runs through
`processStroke`, then:
- 1 point → `<circle>`;
- pressure on → `<path fill=…>` from `outlinePoints` (variable-width ribbon);
- pressure off → `<path fill="none" stroke=… stroke-width=…>` centreline.

SVG is a one-way render of the current settings — it is the shareable /
printable output, not the editable source (that's the JSON).

### Load — `loadTraceJSON` (`:540`)

Validates `type === "vhs-trace"`, restores artboard, rebuilds `strokes`
(defensively defaulting missing fields), and re-applies saved settings to
`cfg` and the toolbar controls, then `fitView()`. `readImageFile` (`:466`)
and the drag-and-drop handlers cover image loading via `FileReader` →
data-URL → `Image`.

---

## 11. Relationship to the VHS project

The tracer **shares capture DNA** with the GlyphCollector and reuses two of
its algorithms verbatim (coalesced-event capture, Catmull-Rom smoothing) and
its `{x, y, p}` stroke shape — the same shape the Python assembler engine
consumes (`assembler/assembler.py`, `_nearest_pressure` and the
`pressure_start/end` bezier metadata).

It is intentionally a **separate tool**, not a mode of the collector:

| | GlyphCollector | Tracer |
|--|----------------|--------|
| Captures | *characters* into a font library | *free-form artwork* over a reference |
| Organised by | a keyed glyph grid (char → variants) | a single artboard + stroke list |
| Reference | a font template glyph | an arbitrary raster image |
| Normalises to | glyph em/baseline (for typesetting) | the image/artboard viewBox |
| Output | glyph JSON for the assembler | trace JSON + standalone SVG |

Keeping them separate avoids overloading the collector's character-centric
UI with an unrelated image-tracing mode, while the shared philosophy (one
file, no build, pen-first, raw-preserving) keeps them maintainable together.

---

## 12. Testing

There is no build, so tests drive the file directly in a headless browser
(Playwright/Chromium). The boot block exposes `window.__tracer` (`:622`)
with `strokes`, `addStroke`, `processStroke`, `buildJSON`, `buildSVG`,
`loadTraceJSON`, `render`, `updateHud`, and the `view` — enough to:

- push synthetic pressured/jittery strokes and assert
  `processStroke` expands raw → smoothed points;
- assert `buildJSON` yields `type:"vhs-trace"` with per-point pressure;
- assert `buildSVG` yields a correct `viewBox` and `<path>` output;
- round-trip `buildJSON` → `loadTraceJSON` and compare;
- screenshot the canvas to confirm pressure renders as visible taper.

`pageerror`/`console.error` are collected and fail the run. This mirrors how
the assembler's browser features are verified (abort external CDN requests,
call internals, screenshot) — except the tracer has **no** CDN dependency,
so it renders fully in-sandbox.

---

## 13. Known limitations & extension points

Ordered roughly by value; each is a localised change:

- **Outline quality.** `outlinePoints` is a simple centreline offset —
  sharp corners can pinch and tight curves can self-intersect. A round-join
  / miter-clipped outline (or per-segment quad ribbons) would refine it.
  Localised to `outlinePoints` + `drawStroke`/`buildSVG`.
- **Layers.** `strokes` is a flat list. A layer is a labelled stroke
  group with visibility/opacity/colour — add a `layerId` to strokes and a
  layer panel; `render`/export iterate groups.
- **Portable JSON.** Store the reference image as a data-URL in the JSON
  (`buildJSON`/`loadTraceJSON`) behind an "embed image" toggle.
- **Direct-save.** Adopt the collector's File System Access API path to
  write files to a connected folder instead of downloading.
- **Per-stroke edit.** Re-colour/re-width or delete an existing stroke
  (hit-test against `outlinePoints`), beyond the current global undo/redo.
- **Smoothing on capture.** The stabiliser currently runs at render time
  over the whole stroke; a per-sample real-time predictor would reduce the
  slight lag at high strength.

None require structural change: the mutable-state + `render()` model means a
new feature is "mutate state, call `render()`," and export reads the same
state through `processStroke`.
