# U7 Phase 2b — Multiple text frames

Implementation plan for placing more than one independently-positioned
block of text on a single page (e.g. a heading box plus a body box, or a
two-column layout). This is the last open item of the U7 WYSIWYG editor
and the only one that changes the rendering data model, so it is scoped
here separately per the roadmap.

Status: **Slice 1 shipped** (backend foundation — §6 phase 1: `typeset_frames`
with position baking, renderer `prebaked` + `data-frame`, and the `--frames`
CLI, with tests). Slices 2–3 (multi-frame editor UI, polish) remain proposed.

---

## 1. User contract

A document becomes an ordered list of **frames**. Each frame carries its
own text, position, and column width; everything else (font, line height,
line spacing, realism, colour, stroke) stays **document-global** in this
first version. That covers the common cases (heading + body, side note,
two columns) without the complexity of per-frame fonts, which can come
later if asked for.

A single-frame document is exactly today's behaviour — a one-element
frame list — so nothing regresses and the simple path stays simple.

```jsonc
// one frame  == today's single block
{ "frames": [ { "text": "…", "start_x": 20, "start_y": 25, "max_width": 80 } ] }

// two frames == heading box + body box
{ "frames": [
    { "text": "Reisetagebuch",        "start_x": 20, "start_y": 20, "max_width": 120 },
    { "text": "Heute war ein …",       "start_x": 20, "start_y": 45, "max_width": 170 }
] }
```

Per-frame fields: `text` (required), `start_x`, `start_y`, `max_width`
(all mm; default to the document margin / page width as today). Optional
later: `line_height`, `lines_per_page` overrides.

---

## 2. Rendering model — coordinate baking

The current `explicit_scale` render path emits one outer transform:

```
translate(origin_x, origin_y) scale(scale) translate(-content_offset_x, -content_offset_y)
```

i.e. it positions a **single** block by mapping its content-min to one
origin. Multiple origins don't fit that single transform, so we **bake**
each frame's position into glyph coordinates and then render everything
with a neutral outer transform.

For each frame `b` (typeset independently, giving shapes whose content-min
is `(min_x_b, min_y_b)` in glyph units, and a target origin
`(start_x_b, start_y_b)` in mm at the shared `scale`):

```
dx_b = start_x_b / scale - min_x_b
dy_b = start_y_b / scale - min_y_b
```

Translate every point of frame `b` (strokes, bezier control points, and
each `line_info[*].baseline_y` for drift) by `(dx_b, dy_b)`. After baking,
all frames live in one shared glyph-coordinate space already in position.

Then render the concatenation with:

```
translate(0,0) scale(scale) translate(0,0)
```

so `glyph → glyph*scale` mm, and each frame lands where its bake put it.
This is the smallest change to the renderer: the existing single-block
call is just the `len(frames)==1`, `dx=dy` baked-to-origin case.

### What concatenates

- **shapes**: `frame0.shapes + frame1.shapes + …`
- **bezier_data**: same order.
- **line_info**: each frame's lines, baseline_y already translated; used
  for per-line drift exactly as now.
- **shape_source_idx** (Phase 2 click-to-caret): becomes a `(frame, ci)`
  pair. Renderer emits `data-frame="b" data-ci="n"`; the editor keys the
  caret to the right frame's textarea.

---

## 3. Code changes

### Typesetter (`assembler.py`)
- No change to `typeset_text` itself — it already produces one block.
- New `typeset_frames(frames, …)` orchestrator: loops `typeset_text` per
  frame, applies the bake translation, and returns concatenated
  `(shapes, bezier, line_info, source_idx)` plus a parallel
  `shape_frame_idx` list. Keeps per-frame `max_width = max_width_mm/scale`.

### Renderer (`assembler.py`)
- `generate_svg(...)` gains `shape_frame_idx=None`; when present, the
  glyph wrapper becomes `<g data-frame="b" data-ci="n">`. The neutral
  outer transform falls out of passing `content_offset=(0,0)`,
  `origin=(0,0)` — no new transform branch.

### CLI (parity — required)
- `--frames frames.json` reads the frame list (JSON now; YAML if PyYAML
  present, consistent with `--config`). Mutually exclusive with the
  positional `text` / `--file` (which remain the single-frame path).
- `--report` already prints layout; extend it to per-frame fit so CI can
  gate multi-frame overflow.

### Web GUI / editor
- "➕ Add text frame" in the editor toolbar. Each frame renders its own
  draggable box + transparent textarea + handles (the existing overlay
  code becomes per-frame, keyed by frame index).
- The **active** frame is highlighted; its textarea is the typing sink and
  mirrors into a per-frame entry of a frames array (the new single source
  of truth; the sidebar textarea edits frame 0 for back-compat).
- Click-to-caret keys off `data-frame` to focus the right frame.
- Server `/api/generate` accepts either `text` (today) or `frames` (new).

---

## 4. Edge cases & decisions

- **Overlapping frames**: allowed; render in list order (later frames draw
  on top). The editor warns (amber) when two frame boxes intersect, but
  does not forbid it.
- **Per-frame overflow**: each frame's measured ink vs its own column +
  page bottom, surfaced with the Phase-1 overflow chip per frame.
- **Seed / determinism**: one document seed; frames consume the RNG in
  list order so output stays deterministic.
- **Empty frame**: skipped (no shapes), retained in the list so the editor
  box stays draggable.
- **Auto-fit (no paper size)**: multi-frame requires fixed-page mm mode
  (positions are mm). In auto-fit the feature is disabled, matching the
  editor's existing constraint.

---

## 5. Testing

- Typesetter: two frames at different origins → shape counts add up;
  `shape_frame_idx` parallel; frame-1 shapes are offset from frame-0 by
  the expected mm delta after scaling.
- Renderer: `data-frame`/`data-ci` emitted only when the list is supplied;
  CLI output without `--frames` is byte-identical to today.
- CLI: `--frames` round-trips a 2-frame JSON; `--report` shows per-frame
  fit; `--frames` + positional text errors clearly.
- Browser: add/drag/delete a frame; click-to-caret lands in the correct
  frame; per-frame overflow flags independently.

---

## 6. Phased rollout

1. **Backend foundation** — `typeset_frames`, the bake math, renderer
   `data-frame`, and `--frames` CLI with tests. Headless-testable; no UI.
2. **Editor multi-frame** — per-frame overlay boxes, add/delete, active
   frame, per-frame click-to-caret and overflow.
3. **Polish** — overlap warning, per-frame fit in `--report`, optional
   per-frame typography overrides (only if a real need shows up).

Ship 1 first: it is the dependency for everything and stands alone behind
the CLI, so the data model can be validated before any UI work.
