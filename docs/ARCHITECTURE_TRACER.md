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

The whole program is ~870 lines: a `<style>` block, static DOM, and one
`<script>`. There is no framework and no global build of DOM — the toolbar
is hand-wired in section 12 of the script.

---

## 2. Module map

The script is organised into labelled sections (each fenced by a `// ───`
banner comment). Reading top to bottom:

```
State                    (229)  AW/AH, bgImage, view, dpr, dirHandle, dragLayerId,
                                 layers, activeId, undo/redo, cfg, LAYER_PALETTE, helpers
Canvas sizing (HiDPI)    (271)  resize()
Coordinate transforms    (284)  toArtboard(), fitView(), zoomAbout()
Stabilisation            (310)  stabilize(), catmullRom(), processStroke(), halfWidth()
Rendering                (366)  worldTransform(), ensureOff(), render(), drawStroke(), outline*()
Pointer input            (465)  pointerdown/move/up routing, addPoint(); startGesture() (515)
HUD                      (558)  updateHud(), showPressure()
Image loading            (573)  loadImageFromSrc(), readImageFile(), drag & drop
Save / load              (608)  download(), showToast(), saveFile(), buildJSON(),
                                 svgStroke(), buildSVG(), loadTraceJSON()
Toolbar + layers         (763)  bindRange(), setStab(), layer panel + drag-reorder,
                                 connect-folder, undo(), redo()
Boot                     (986)  first layer + resize + fitView + window.__tracer hooks
```

There is no central event loop or state store. The model is a plain
mutable-state + explicit-`render()` design: input handlers mutate `layers`
/ `view` and call `render()`. Every visual is recomputed from state on each
`render()` — there is no incremental/dirty-rect drawing.

---

## 3. Data model

Module-level state (`TracerUI.html:229`) holds everything:

- **`AW`, `AH`** — artboard width/height in *artboard units*. Set to the
  reference image's natural pixel size when an image loads; default
  `1000×1400`. This is the SVG `viewBox` on export.
- **`bgImage`, `bgName`** — the loaded `Image` and its filename. Images are
  always loaded via `FileReader.readAsDataURL`, so `bgImage.src` is a
  `data:` URL — which is what lets the project embed the image (§10).
- **`view = { s, ox, oy }`** — the pan/zoom transform (see §4).
- **`layers`** — the document: an ordered array of layer objects, drawn
  bottom-to-top (later in the array = higher in the stack):
  ```js
  { id, name, color, visible, opacity,
    strokes: [ { color, width, points: [ {x, y, p, t}, … ] } ] }
  ```
  A **stroke's** coordinates are in **artboard space** (zoom-independent);
  `p` is pen pressure 0–1; `t` is a capture timestamp. `newLayer()` mints
  ids and cycles default names/colours from `LAYER_PALETTE`; `activeLayer()`
  resolves `activeId`; `allStrokes()` flattens for counting/iteration.
- **`activeId`** — the layer new strokes are drawn into.
- **`cfg`** — the live settings mirror of the toolbar. `cfg.penColor`
  tracks the *active layer's* colour (a layer is one colour, §10).
- **`dirHandle`** — a `FileSystemDirectoryHandle` when a folder is connected
  for direct saves (§10); `null` otherwise (→ download fallback).
- **`dragLayerId`** — the layer currently being drag-reordered in the panel
  (§6.2); `null` when not dragging.

`undoStack`/`redoStack` hold `{layerId, stroke}` records in draw order (§6.1);
`current` is the in-progress stroke, already pushed into its layer so
appending points is live.

**Key invariant:** points are stored **raw** in artboard space. Nothing in
the pipeline writes back into `stroke.points`. Stabilisation and smoothing
are pure functions applied at render/export time (§5). Colour *is* mutated
in place when a layer is recoloured — that is a document edit, not the
smoothing pipeline.

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

**Screen → artboard** (`toArtboard`, `:287`), used to store points:
```js
artboard = (client − rect.left − view.ox) / view.s
```

**Artboard → device** (in `render`, `:385`), one combined matrix:
```js
ctx.setTransform(dpr*view.s, 0, 0, dpr*view.s, dpr*view.ox, dpr*view.oy);
```
Because it composes translate-then-scale into a single matrix, the whole
scene (sheet, image, every stroke) is drawn in raw artboard coordinates and
the GPU handles pan/zoom/DPR. Ink is part of the artwork, so it scales with
zoom (a stroke's `width` is in artboard units, not screen pixels).

**`fitView`** (`:292`) centres the artboard with padding.
**`zoomAbout(cx, cy, factor)`** (`:300`) zooms while keeping the artboard
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
`processStroke` (`:357`):

```
raw points ──▶ stabilize(strength) ──▶ [smooth?] catmullRom() ──▶ display / export
   (stored)      EMA position pull        Catmull-Rom resample
```

### 5a. Stabilizer — `stabilize(points, strength)` (`:315`)

An exponential moving average that "pulls" each point toward the running
average, damping hand jitter:
```js
a = 1 − strength                     // fraction of the new raw point kept
sx += (raw.x − sx) · a               // (same for y and pressure p)
```
`strength = 0` returns the input unchanged. The toolbar slider (0–100) maps
to `strength ∈ [0, 0.85]` (`setStab`, `:772`) — capped below 1 so the line
can never fully freeze. Pressure is smoothed alongside position, so width
transitions stay clean.

This is the piece added on top of the collector (the collector smooths for
rendering but has no jitter-damping stabiliser); it is what makes shaky
freehand tracing usable.

### 5b. Smooth — `catmullRom(stroke)` (`:331`)

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
(`pointerdown`, `:470`):

```
pointerdown ─┬─ type 'touch'          ─▶ touches.set(id); startGesture()   (view)
             └─ type 'pen' | 'mouse'  ─▶ new stroke in active layer; addPoint()  (ink)
```

Drawing and view gestures live in separate channels and never conflict —
which is exactly the tablet ergonomic you want (pen inks, fingers pan/zoom)
and gives **palm rejection for free** (a resting palm registers as `touch`
and only ever moves the view, never draws).

A new stroke is pushed into `activeLayer().strokes` (taking the layer's
colour) and recorded on `undoStack` as `{layerId, stroke}`.

**`addPoint(e)`** (`:505`):
1. `toArtboard(e.clientX, e.clientY)` → artboard coordinates.
2. Pen pressure from `e.pressure`; mouse (no pressure) falls back to `0.5`.
3. Push `{x, y, p, t}` onto `current.points`; update the pressure meter.

**Coalesced events:** on `pointermove` (`:484`), `e.getCoalescedEvents()`
replays the sub-frame samples the OS batched, so fast strokes keep their
fidelity instead of being decimated to the animation-frame rate. Same trick
as the collector.

`setPointerCapture` keeps the stroke attached to the canvas even if the pen
strays outside it mid-stroke.

### 6.1 Undo / redo

`undo`/`redo` (`:966`) are layer-aware and preserve true **draw order** across
layers. Each completed stroke pushes `{layerId, stroke}` onto `undoStack`
(and clears `redoStack`). `undo` pops the record, splices the stroke out of
its layer, and pushes to `redoStack`; `redo` re-appends it. Because a new
stroke clears `redoStack`, redo only runs with no intervening draws, so
z-order is never scrambled. Deleting or clearing a layer prunes both stacks
of that layer's records.

### 6.2 Layer drag-reorder

Each panel row has a grip (`.lgrip`) whose `pointerdown` calls
`startLayerDrag(id)` (`:948`), recording `dragLayerId` and attaching
`pointermove`/`pointerup` on **`document`** — not the row, because
`renderLayerPanel` rebuilds the rows on every move, which would detach a
row-bound listener. On move, `onLayerDragMove` finds the insertion slot by
comparing the pointer's Y to each row's mid-line, then `reorderTo(dragId,
insertVisual)` (`:919`) restacks. Since rows are drawn **top-first** (the
array reversed), `reorderTo` reorders a reversed copy and maps it back,
adjusting the index for the removed element; it returns `false` on a no-op
so the panel only re-renders when the order actually changed. Works with
pen, mouse, and touch (the grip sets `touch-action: none`).

---

## 7. Gesture system

Touch pointers accumulate in the `touches` map; `startGesture`/
`updateGesture` (`:515`) interpret them:

- **1 touch → pan.** Record `view.ox/oy` and the start position; on move,
  translate by the finger delta.
- **2 touches → pinch-zoom.** Record start distance, midpoint, and
  transform; on move, `factor = dist/startDist`, then re-solve `ox/oy` so
  the gesture's start artboard-midpoint follows the *current* midpoint —
  combined pan **and** zoom in one gesture (the §4 zoom-about math with a
  moving anchor).
- Adding/removing a finger re-seeds the gesture (`startGesture` is called on
  every touch down/up), so 1↔2 finger transitions don't jump.

**Wheel** (`:551`) calls `zoomAbout` at the cursor with a 1.1× step.
`preventDefault` + `touch-action: none` on the canvas stop the browser from
hijacking scroll/zoom.

---

## 8. Rendering

`render()` (`:385`) is the single draw entry point, called after any state
change. It:
1. Resets and clears the device-pixel canvas.
2. Installs the combined artboard→device matrix via `worldTransform` (§4).
3. Paints the white artboard sheet, then the reference image at
   `cfg.imgOpacity`.
4. Iterates `layers` bottom-to-top, skipping hidden/empty ones, and draws
   each layer's strokes via `drawStroke`.

### Layer group opacity — offscreen compositing

A layer at `opacity < 1` must be **flattened first**, or overlapping strokes
within it would double-darken at the seams. So `render` special-cases it:
draw the layer's strokes into a reusable offscreen canvas (`ensureOff`,
`:378`, same size + world transform as the main canvas), then blit that
buffer once onto the main context with `globalAlpha = layer.opacity`.
Opaque layers (`opacity ≈ 1`) skip the buffer and draw direct — the fast,
common path. The offscreen canvas is allocated once and only resized when
the viewport changes.

**`drawStroke(c, st)`** (`:421`) takes an explicit context (main *or*
offscreen), runs `processStroke`, then renders per mode:

- **1 point** → a filled dot (`arc`, radius from pressure).
- **Pressure on (`cfg.varw`)** → a filled **outline** (variable width).
- **Pressure off** → a plain centreline `stroke` at constant `st.width`.

### Variable-width outline — `outlinePoints` (`:445`)

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
filled ribbon whose thickness tracks pressure. `halfWidth` (`:364`) is the
one place the pressure→width curve lives, shared by canvas dots, canvas
outlines, and SVG export, so all three agree.

---

## 9. Pressure model

- **Capture:** `e.pressure` per point (incl. coalesced sub-samples), stored
  as `p`. Absent/again-`0.5` mouse input defaults to `0.5`.
- **Live feedback:** `showPressure` (`:568`) drives the bottom-right meter.
- **Rendering:** variable-width outline (§8), toggle `cfg.varw`.
- **Persistence:** `p` is written per point in JSON (lossless) and baked
  into outline geometry in SVG.

Pressure is stabilised together with position (§5a), so width doesn't
flicker on noisy pressure sensors.

---

## 10. Export & round-trip

### JSON — `buildJSON` (`:656`) — lossless, re-openable (v2)

Serialises artboard size, image meta, current `settings`, and the full
**`layers`** array — each layer's name/colour/visibility/opacity plus its
strokes with **raw** points (coordinates rounded to 2 dp, pressure to 3 dp
for size). Because raw points and the smoothing settings are both stored, a
re-opened file reproduces the look *and* stays re-tunable. Written as
`version: 2`; schema is in the [user guide](GUIDE_TRACER.md#export-formats).

**Embedded image (portable project).** `buildImageMeta` writes
`image: { name }` and, when the **Embed** toggle (`cfg.embedImage`, default
on) is set and an image is loaded, also `image.data = bgImage.src` — the
image's data-URL. That makes the JSON a self-contained project: it reopens
with its reference image, and can be shared as a single file. Toggling Embed
off keeps the JSON lean (filename only). No re-encoding is needed since the
image already lives as a data-URL on `bgImage.src`.

### SVG — `buildSVG` (`:695`) — processed artwork

Emits a `viewBox="0 0 AW AH"` document. Each **visible** layer becomes a
`<g data-layer="…">` (carrying `opacity` when < 1), preserving the layer
structure in the output. Within a group, `svgStroke(st)` (`:679`) renders one
element per stroke after `processStroke`:
- 1 point → `<circle>`;
- pressure on → `<path fill=…>` from `outlinePoints` (variable-width ribbon);
- pressure off → `<path fill="none" stroke=… stroke-width=…>` centreline.

Layer names are attribute-escaped (`escapeAttr`). SVG is a one-way render of
the current settings — the shareable/printable output, not the editable
source (that's the JSON).

### Load — `loadTraceJSON` (`:715`)

Validates `type === "vhs-trace"`, restores artboard, and rebuilds `layers`
(defensively defaulting missing fields). It accepts both schemas: a **v2**
file rebuilds each layer; a **v1** file (a flat `strokes` array) is wrapped
into a single layer, so old traces still open. If the file carries
`image.data`, the embedded reference is restored via `loadImageFromSrc`
(otherwise `bgImage` is cleared and only `bgName` kept). Saved `settings`
are re-applied to `cfg` and the toolbar; then `syncPenColor` +
`renderLayerPanel` + `fitView`. `readImageFile` (`:586`) and the
drag-and-drop handlers cover fresh image loading via `FileReader` →
data-URL → `Image`.

### Destination — `saveFile` (`:632`)

Both save buttons route through `saveFile(name, mime, data)`. If a folder is
connected (`dirHandle`), it writes straight into it —
`getFileHandle(name, {create:true})` → `createWritable` → `write` → `close`
— and confirms with a toast; on any failure it falls back to a download. If
no folder is connected, it downloads as before. The **📁 Folder** button
calls `showDirectoryPicker({ mode: 'readwrite' })` (mirroring the
collector's GC7 direct-save) and is hidden entirely when the API is absent
(Safari/Firefox), so those browsers simply always download. This is the one
place the tool touches the File System Access API; the handle is
session-scoped (reconnect per session).

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
| Organised by | a keyed glyph grid (char → variants) | a layered artboard (layers → strokes) |
| Reference | a font template glyph | an arbitrary raster image |
| Normalises to | glyph em/baseline (for typesetting) | the image/artboard viewBox |
| Output | glyph JSON for the assembler | trace JSON + standalone SVG |

Keeping them separate avoids overloading the collector's character-centric
UI with an unrelated image-tracing mode, while the shared philosophy (one
file, no build, pen-first, raw-preserving) keeps them maintainable together.

---

## 12. Testing

There is no build, so tests drive the file directly in a headless browser
(Playwright/Chromium). The boot block exposes `window.__tracer` (`:996`)
with `layers`, `activeId`, `strokes` (flattened), `addLayer`, `addStroke`
(into the active layer), `processStroke`, `buildJSON`, `buildSVG`,
`loadTraceJSON`, `reorderTo`, `saveFile`, `setDirHandle`, `loadImageFromSrc`,
`cfg`, `renderLayerPanel`, `render`, `updateHud`, and the `view` — enough to:

- push synthetic pressured/jittery strokes and assert
  `processStroke` expands raw → smoothed points;
- add layers and assert `buildJSON` yields `version:2` with per-layer,
  per-point pressure;
- assert `buildSVG` yields a correct `viewBox` and one `<g>` per *visible*
  layer (with `opacity` when dimmed);
- round-trip `buildJSON` → `loadTraceJSON` (v2) and a v1 flat-`strokes`
  file, and compare; embed an image and assert it survives the round trip;
- exercise `reorderTo` and a real grip-drag, asserting the array restacks;
- inject a mock `dirHandle` via `setDirHandle` and assert `saveFile` writes
  to it (and toasts) rather than downloading;
- screenshot the canvas to confirm pressure renders as visible taper and
  layer colours/opacity composite correctly.

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
  Localised to `outlinePoints` + `drawStroke`/`svgStroke`.
- **Per-stroke edit.** Re-colour/re-width or delete an *individual* stroke
  (hit-test against `outlinePoints`), beyond per-layer colour and undo/redo.
- **Persist the folder handle.** `dirHandle` is session-scoped; storing it in
  IndexedDB (with a permission re-prompt) would remember the folder across
  reloads, like the collector.
- **Smoothing on capture.** The stabiliser currently runs at render time
  over the whole stroke; a per-sample real-time predictor would reduce the
  slight lag at high strength.

None require structural change: the mutable-state + `render()` model means a
new feature is "mutate state, call `render()`," and export reads the same
state through `processStroke`.
