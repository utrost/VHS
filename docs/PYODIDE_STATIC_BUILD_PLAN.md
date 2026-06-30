# P1 — Static in-browser build (Pyodide)

Implementation plan for running VHS **100 % in the browser** by executing
the existing Python engine under [Pyodide](https://pyodide.org) (CPython
compiled to WebAssembly). The goal is a static site — hostable on GitHub
Pages — that needs **no install, no server, and works offline**, while
keeping a **single source of truth** (the same `assembler.py` that powers
the CLI and the local server).

Status: **Proposed.** Nothing below is built yet.

---

## 1. Why Pyodide (and not a rewrite)

Two stated product goals drive this: *simple to maintain* and *simple to
share / install for non-technical users*.

- **Maintainability** rules out forking the engine into JavaScript (two
  engines that must stay byte-identical) and rules out a near-term Rust
  rewrite (a full reimplementation of ~1450 tested lines, plus a smaller
  contributor pool). Pyodide runs the **unmodified** Python engine, so
  there is **one engine, no divergence**, and the existing 74 tests stay
  authoritative.
- **Shareability** is exactly what a static site delivers: a URL, nothing
  to install, runs offline once cached.

The engine is well-suited to this: the text→SVG core
(`GlyphLibrary → Typesetter → Renderer.generate_svg`, ~1450 lines) imports
only the **standard library** (`json, math, random, glob, xml.etree`).
No numpy, no native extensions — it loads in Pyodide essentially as-is.

Rust→WASM remains the better *end state* for bundle size / mobile / a
unified native+web engine, and is captured as a separate, later option;
it is explicitly out of scope here.

---

## 2. Architecture

```
┌─────────────────────────── Browser (static files) ───────────────────────────┐
│  index.html (existing UI)                                                     │
│      │  vhsApi.generate(payload) / .coverage() / .saveGlyph() …               │
│      ▼                                                                         │
│  api-layer.js  ──(static mode)──►  Pyodide (CPython WASM)                      │
│      │                                  └── assembler.py  (UNCHANGED engine)   │
│      └──(server mode)──►  fetch('/api/*')  (existing Flask, for local use)     │
│                                                                                │
│  Glyph store:  bundled fonts via manifest.json fetch  +                        │
│                user fonts in OPFS / IndexedDB                                  │
└────────────────────────────────────────────────────────────────────────────┘
```

The key idea: **abstract the four `/api/*` calls the front-end makes
behind a small `vhsApi` layer**, with two backends —

- **server mode** → today's `fetch('/api/...')` (kept for the local
  launcher, the CLI, and batch work), and
- **static mode** → calls into Pyodide running `assembler.py` directly.

The *same* `index.html` UI then runs in both worlds, so there is no
second front-end to maintain either.

---

## 3. What ports cleanly vs. what needs an adapter

**Ports unchanged (the engine):** `GlyphLibrary`, `Typesetter`,
`Renderer.generate_svg` / `generate_svg_string`, all the typesetting,
kerning, bezier metrics, balanced-wrap DP, and `typeset_frames`. These are
pure-stdlib and run under Pyodide untouched. `PyYAML` is pure-Python and
loads in Pyodide if presets are wanted.

**Needs an adapter layer (the real work):**

1. **Glyph loading.** `GlyphLibrary` currently does
   `glob.glob(glyphs/<font>/*.json)` against a real filesystem. A browser
   can't list a directory over HTTP, so:
   - **Bundled fonts** ship with a generated `manifest.json`
     (`{font: [filenames…]}`); the loader `fetch`es each listed file into
     Pyodide's in-memory FS (or passes the parsed JSON straight to
     `GlyphLibrary`).
   - A tiny build script regenerates the manifest from `glyphs/`.
2. **User glyph persistence.** Captured glyphs can't go to
   `glyphs/<font>/` (no server FS). They live in **OPFS or IndexedDB**:
   the collector writes there; the assembler reads from there. This
   replaces `/api/save-glyph` in static mode.
3. **Font export / import.** Because there's no shared filesystem, sharing
   a font becomes **download / upload a font bundle** (a zip or single
   JSON of all glyphs). New, small UI.
4. **PNG / PDF.** Drop `cairosvg` / `pypdf` in static mode:
   - PNG via the browser: render the SVG to a `<canvas>` → `toBlob()`.
   - PDF via a small JS lib (`svg2pdf.js` / `jsPDF`) or browser print.

**Dropped from the static bundle:** Flask, `cairosvg`, `pypdf`. (All
remain available in the local-server path — see §2.)

---

## 4. Front-end abstraction (keeps one UI)

Introduce `assembler/static/js/vhs-api.js` exporting:

```js
vhsApi.generate(payload)   // → SVG string
vhsApi.coverage(payload)   // → coverage report
vhsApi.listFonts()         // → [names]
vhsApi.saveGlyph(font, filename, glyph)
```

- In **server mode** these are thin `fetch` wrappers (current behaviour).
- In **static mode** they call a Pyodide-resident Python shim that imports
  the engine and returns the same shapes the Flask endpoints return today
  (e.g. `generate_svg_string(...)`).

`index.html` is refactored once to call `vhsApi.*` instead of `fetch`
directly. After that, both deployments share the identical UI and the
identical engine — the whole point.

---

## 5. Phased rollout

**Phase 0 — Proof of concept (validate feasibility).**
A single static HTML page that loads Pyodide, fetches `font1` via a
generated manifest, and runs the **unmodified** `typeset_text` +
`generate_svg_string` to render a line to the page. Answers the three real
unknowns: (a) does the core run untouched in Pyodide, (b) real cold-start
time and bundle size, (c) is the fetch-glyph approach sound. Small,
reversible, no commitment.

**Phase 1 — Static Assembler MVP.**
- `vhs-api.js` abstraction (§4); refactor `index.html` to use it.
- Pyodide static shim implementing `generate` / `coverage` / `listFonts`.
- Bundled-font manifest + build script.
- SVG download + canvas PNG export.
- Deploy a first cut to GitHub Pages (assemble-only, bundled font).

**Phase 2 — Glyph persistence + round trip (offline).**
- OPFS/IndexedDB glyph store; `saveGlyph` writes there.
- Collector (already in-browser) saves to the store; the assembler reads
  from it — the capture→assemble round trip with **no server at all**.
- Font **export / import** (bundle download/upload).

**Phase 3 — Polish & offline-first.**
- Service worker: cache Pyodide + app shell for true offline + instant
  repeat loads; lazy-load Pyodide so first paint isn't blocked.
- PDF export (JS lib).
- Mobile pass (Pyodide memory footprint).

Ship Phase 0 first; its numbers decide whether to proceed and how to
sequence Phases 1–3.

---

## 6. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| **Bundle weight** — Pyodide runtime is ~6–10 MB. | Lazy-load after first paint; cache via service worker so it's a one-time cost; show a small "warming up" state. |
| **Cold-start latency** (seconds). | Pre-warm in a worker; cache aggressively; keep the local-server path for users who want instant heavy use. |
| **Mobile memory.** | Test early (Phase 0/3); document minimum; the local server remains for heavy/batch work. |
| **Server↔static behaviour drift.** | Both call the *same* engine, so outputs match by construction. Guard with a golden-SVG test: same input → identical SVG from CLI, Flask, and Pyodide. |
| **Glyph-manifest staleness.** | Generate it in the same build step that publishes the site; add a check to CI. |
| **Two delivery targets to keep working.** | Only the thin `vhsApi` layer differs; the engine and UI are shared, so the surface is small. |

---

## 7. Testing strategy

- **Golden parity:** a fixed corpus of inputs rendered by the Python
  engine (CLI/server) produces reference SVGs; a headless browser test
  loads the static page, runs the same inputs through Pyodide, and asserts
  byte-identical SVG. Because it's one engine, any mismatch is an adapter
  bug, not an engine fork — easy to localise.
- **Adapter unit tests:** manifest generation, OPFS/IndexedDB read/write,
  export/import round-trip, canvas-PNG smoke.
- **Load-budget check:** automated measurement of cold-start time and
  transferred bytes, tracked over time.

---

## 8. Effort (rough)

- Phase 0 (PoC): **small** — a few hours; high information value.
- Phase 1 (static MVP): **medium** — mostly the `vhsApi` refactor, the
  Pyodide shim, and the manifest/build step.
- Phase 2 (persistence + round trip): **medium** — the genuinely new part
  (browser storage + export/import).
- Phase 3 (offline/polish/PDF/mobile): **medium**.

---

## 9. Relationship to existing work

- The **local launcher / server** (frictionless `vhs-gui.sh`/`.bat`,
  safe defaults) is **not** superseded — it stays the path for power
  users, the CLI, batch/plotter output, and large PDF generation. The two
  share one engine.
- The **CLI/GUI parity** ground rule extends naturally: a feature lands in
  the engine once, and both the server and the Pyodide shim expose it.
- The **GlyphCollector** is already in-browser; Phase 2 simply repoints its
  save from the server endpoint to the browser glyph store.

---

## 10. Open decisions

- **Storage:** OPFS (file-like, larger, newer) vs IndexedDB (broadest
  support). Likely IndexedDB for reach, OPFS where available.
- **Bundle format for export/import:** single JSON vs zip of per-glyph
  files (matching the on-disk layout).
- **Hosting:** GitHub Pages vs any static host; custom domain.
- **Do we keep one `index.html` for both modes** (recommended) **or fork a
  slimmer static page?** Keeping one preserves the single-UI benefit.
