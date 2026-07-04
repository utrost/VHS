# VHS Tracer — guide

A pen-first tracing surface, spun off from the GlyphCollector. Load a
reference image, drop its opacity, and trace over it with a pen-enabled
device (Android tablet + stylus, iPad + Apple Pencil, or a mouse). Strokes
capture **pen pressure** per point and are drawn with variable line width.

It is a single self-contained HTML file — no build step, no CDN, no server.
Open `TracerUI/TracerUI.html` straight off disk (or host the file
anywhere) and it works, including offline on a tablet.

## Quick start

1. Open `TracerUI/TracerUI.html`.
2. Click **🖼️ Image** (or drag an image onto the window) to load a
   reference. The artboard resizes to the image and fits to the view.
3. Turn the **Image** opacity down so you can see your ink over it.
4. Trace with your pen. Export with **💾 JSON** or **⬇︎ SVG**.

## Gestures

| Input | Action |
|-------|--------|
| **Pen / mouse** | Draw a stroke |
| **One finger** | Pan the view |
| **Two fingers** | Pinch-zoom |
| **Mouse wheel** | Zoom (centred on the cursor) |
| **⤢ Fit** | Reset the view to fit the image |
| <kbd>Ctrl/Cmd</kbd>+<kbd>Z</kbd> | Undo · <kbd>⇧</kbd> to redo |

Drawing and view gestures never fight: the pen always draws, touches always
move the view (a natural fit for a stylus + fingers on a tablet, and it
gives palm-rejection for free).

## Pen pressure

Every point stores its pen pressure (`p`, 0–1). Pressure is:

- **shown live** in the bottom-right meter while you draw, and
- **rendered as variable width** — light pressure draws thin, hard pressure
  draws thick. Toggle this with the **Pressure** checkbox (off = a plain
  constant-width line).

Devices without pressure (a mouse) fall back to `p = 0.5`.

## Stabilisation

Two non-destructive smoothing mechanics, both ported from the collector.
Neither touches the raw captured points — they run when the stroke is drawn
and exported, so you can re-tune them any time:

- **Stabilizer** (slider) — an exponential "pull" over the point positions
  that damps hand jitter. `0` = raw; higher = steadier (and slightly
  laggier) lines. Great for shaky freehand tracing.
- **Smooth** (checkbox) — Catmull-Rom interpolation that turns the point
  samples into a flowing curve.

## Export formats

**JSON** (`💾 JSON`) is **lossless and re-openable** — it stores the artboard
size, every raw `{x, y, p, t}` point, per-stroke colour/width, and your
stabiliser/smooth settings. Re-open it later with **📂 Open** to keep
tracing or re-tune the smoothing. Schema:

```json
{
  "type": "vhs-trace", "version": 1,
  "artboard": { "width": 1200, "height": 1600 },
  "image": { "name": "reference.jpg" },
  "settings": { "stabilizer": 35, "smooth": true, "variable_width": true },
  "strokes": [
    { "color": "#111111", "width": 4,
      "points": [ { "x": 210.4, "y": 88.1, "p": 0.62, "t": 1720000000000 } ] }
  ]
}
```

**SVG** (`⬇︎ SVG`) is the **processed** result — stabilised, smoothed, with
pressure baked into true variable-width ink outlines (`<path fill=…>`), on a
`viewBox` matching the artboard. This is the shareable/printable artwork.
With **Pressure** off you get plain constant-width `stroke` paths instead.

## Relationship to the rest of VHS

The tracer shares the collector's capture DNA — coalesced pointer events,
per-point pressure, Catmull-Rom smoothing — and the same `{x, y, p}` stroke
shape the assembler engine already understands. It is deliberately its own
tool, though: the GlyphCollector captures *characters* into a font library;
the Tracer captures *free-form artwork* over a reference image.

## Ideas / not yet built

- Variable-width in SVG uses a simple centerline-offset outline; a
  round-capped, self-intersection-clean outline is a future refinement.
- Layers (per-layer colour/visibility), per-stroke re-colour after the fact.
- Direct-save to a folder (File System Access API), like the collector.
- Optionally embed the reference image in the JSON for a fully portable file.
