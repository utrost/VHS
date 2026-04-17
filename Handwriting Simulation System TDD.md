# **Technical Design Document: Vector-Based Handwriting Simulation (VHS)**

## **1\. Project Overview**

The VHS system provides a deterministic pipeline for generating realistic handwriting for pen plotters. It replaces neural-network-based generation with a stochastic "Shaping Engine" utilizing a custom-captured library of single-stroke vector glyphs.  
**Key Objectives:**

*   **True Single-Stroke:** Output paths are 1-pixel wide vectors (no outlines/double-tracking).  
*   **Multilingual Native:** Full support for German Umlauts (ä, ö, ü), ß, and special punctuation via raw capture.  
*   **Automated Spacing:** Zone-aware kerning is calculated mathematically from vector bounding boxes, with vertical zone classification (upper/ground/lower) for smarter letter-pair spacing.
*   **Fixed Layouts:** Support for standard paper sizes (A4, A3, etc.) with configurable margins and line spacing.
*   **Modern Web Access:** A Flask-powered web interface for real-time preview and generation.

## **2\. System Architecture**

| Module | Component | Technology | Responsibility |
| :---- | :---- | :---- | :---- |
| **Capture** | Batch Glyph Collector | HTML5/JS (Canvas) | Captures raw pointer coordinates ($x,y,p,t$). Output: JSON. |
| **Storage** | Glyph Library | JSON Files | Organized by subdirectory: `glyphs/{FontName}/`. |
| **Synthesis** | The Assembler | Python | Core engine for typesetting, shaping, and SVG rendering. |
| **Interface** | Assembler Web UI | Flask / HTML5 | Browser-based front-end for the Assembler engine. |

## **3\. Data Specification (Glyph JSON)**

To support batching, the JSON schema aggregates all variants of a single character into one "Master Asset."  
{  
  "char": "?",   
  "exported\_at": "2025-11-24T10:00:00Z",  
  "metadata": {  
    "font_family": "UweHandwriting",
    "baseline\_y": 250,  
    "x\_height": 150,  
    "canvas\_size": \[250, 350\]  
  },  
  "variants": \[  
    {   
      "id": 0,   
      "strokes": \[  
        \[ {"x": 102.5, "y": 200.1, "p": 0.45, "t": 1698000}, ... \]  
      \]   
    },  
    { "id": 1, "strokes": \[...\] }  
  \]  
}

## **4\. The Glyph Collector UI (Frontend)**

*   **Batch Pattern:** Displays 5 horizontal canvas slots to allow rapid repetition (muscle memory).  
*   **Sanitization:** Automatically maps input characters to **Unicode Hex filenames** (e.g., `A` $\rightarrow$ `0041.json`, `sch` $\rightarrow$ `007300630068.json`) to prevent case-insensitivity conflicts on Windows.
*   **Smooth Preview:** The canvas applies Catmull-Rom spline interpolation to the display in real time, so the user sees how their strokes will look after smoothing. This is visual-only — raw point data is preserved in the exported JSON. The preview can be toggled off to inspect the raw polygonal capture.
*   **Input:** Uses Pointer Events API to capture pressure and tilt where available.
*   **Guides:** \* **Red Solid Line (**$y=250$**):** Absolute Baseline.  
  * **Blue Dashed Line (**$y=150$**):** x-Height reference.

## **5\. Backend Logic: The Assembler (Python)**

### **A. Automated Proportional Spacing (Kerning)**


1.  **Normalization:** For each selected variant, calculate the Bounding Box ($x\_{min}, x\_{max}$).  
2.  **Trim:** Shift all points left by subtracting $x\_{min}$ ($NewX \= OldX \- x\_{min}$).  
3.  **Advance Width:** The cursor moves by $(x\_{max} \- x\_{min}) \+ \\text{TrackingBuffer}$.  
4.  **Fixed Paper Sizes:** Supports A3, A4, A5, A6, Letter, and Legal. Orientation (Portrait/Landscape) swaps width/height.
5.  **Line Spacing Multiplier:** A multiplier (default 1.0) applied to the base `line_height` to control inter-line gaps.
6.  **Margins:** In fixed-page mode, content is inset by a configurable margin (mm) using a global SVG `translate` transform.
7.  **Millimetre-Based Page Scaling:** Glyph coordinates are in capture-device units (not mm). In fixed-page mode the caller supplies an explicit scale factor $s = \text{line\_height\_mm} / \text{native\_line\_height}$ so that one baseline-to-baseline advance in glyph space equals the requested on-paper line height. The transform chain is `translate(start_x_mm, start_y_mm) scale(s) translate(-content_origin)`, placing the top-left of the text block at `(start_x_mm, start_y_mm)` (default: `margin`). Stroke width is inversely scaled ($w_{svg} = w_{base} / s$) so `--stroke-width` is rendered in millimetres on paper. Content is **not** auto-shrunk to fit the page — short texts keep their real size; long texts can overflow, giving the caller explicit layout control.
8.  **Word Wrapping:** The typesetter accepts an optional `max_width` parameter (glyph units). The CLI exposes it in millimetres as `--max-width-mm` and converts internally. When a word would exceed the available width, the entire word (all glyphs since the last space) is shifted to the next line.
9.  **Zone-Aware Optical Kerning:** When auto-kerning is enabled, the scanline algorithm classifies each glyph's strokes into vertical zones (upper: above `x_height`, ground: between `x_height` and `baseline_y`, lower: below `baseline_y`). Scanlines in zones occupied by both glyphs use strict minimum distance; scanlines in non-shared zones are relaxed by a configurable `kern_aggressiveness` factor (0.0–1.0, default 0.5). This allows pairs like "Te" to kern tighter than "TK", since 'e' occupies only the ground zone and doesn't conflict with T's upper horizontal stroke.
7.  **Overrides:** A `kerning.json` file handles exceptions:  
    *   **Space:** Fixed width (e.g., 25.0).  
    *   **Narrow Punctuation:** Enforce min-width for ., ,, '.
    *   **Location:** `glyphs/{FontName}/kerning.json` (Font-specific configuration).

### **B. Stochastic Shaping**

1.  **Ligature Scan (Greedy Matching):** The assembler looks ahead in the text stream. If a multi-character glyph (e.g., `tt`, `sch`) exists in the library, it consumes those characters and renders the single ligature glyph instead.
2.  **Variant Rotation:** Randomly selects variant\_id (0-4) to ensure no two adjacent characters look identical.  
3.  **High-Connector Logic:** If the previous letter ends high (o, v, w), the script can vertically shift the entry point of the next letter (if supported by stroke geometry) or select a specific "alt" glyph.

### **C. Quantized Jitter**

Applied post-shaping to simulate mechanical imperfection:

$$P\_{new} \= P\_{old} \+ N(0, \\sigma)$$

Jitter is **deterministic**: the RNG is seeded from a hash of the content, so the same input always produces the same output. An explicit `--seed` parameter allows overriding the auto-derived seed.

### **D. Curve Smoothing**
Raw capture data is polygonal. The renderer uses **Catmull-Rom Spline Interpolation** with **adaptive step counts** (2–12 per segment, based on segment length) to generate fluid curves. Short segments get fewer interpolation steps to avoid over-smoothing; long curves get more for smoother results.

### **E. Baseline Normalization**
Reference metadata (`baseline_y`) is used to vertically align glyphs. All Y-coordinates are normalized relative to this baseline ($y=0$), ensuring correct alignment of ascenders and descenders regardless of the capture canvas position.

## **7\. Web UI Architecture**

The Web UI provides a bridge between the browser and the Python Assembler engine.

*   **Backend (Flask):** A lightweight server (`server.py`) that imports the Assembler classes directly. It exposes a JSON API for font listing and SVG generation.
*   **Frontend (Single-Page App):** A modern dark-themed interface (`index.html`) using vanilla CSS for layout and interactivity (no heavy frameworks).
*   **Live Preview:** SVG data is returned directly as a string and rendered inline in the browser.

## **8\. Verification & Testing**

System robustness is maintained via a multi-layered testing strategy:

*   **Core Unit Tests (`test_assembler.py`):** 11 tests verifying low-level logic like kerning clusters, zone-aware kerning, ligature recognition, and basic SVG sizing.
*   **CLI Integration Tests (`test_cli.py`):** 30 tests executing the `assembler.py` script via subprocess. These tests use a temporary mock font to verify all CLI flags (paper sizes, margins, kerning aggressiveness, deterministic jitter, smoothing, error handling) in a clean environment.
*   **Manual Validation Scripts:** A library of 10 human-executable scripts (`Validation Scripts/`) for subjective quality assessment.

## **6\. Appendix: Capture Inventory Checklist**

**Standard:**  
a \- z (Lowercase), A \- Z (Uppercase)  
0 \- 9 (Digits)  
**German:**  
ä, ö, ü (Lowercase & Uppercase)  
ß (Eszett)  
**Punctuation (Baseline Critical):**  
. (Period \- on line), , (Comma \- hangs), : (Colon), ; (Semicolon)  
\! (Exclamation), ? (Question)  
\- (Hyphen), \_ (Underscore), – (En-Dash)  
' (Single Quote \- high), " (Double Quote \- high)  
„ (German Open Quote \- low), “ (German Close Quote \- high)  
**Symbols:**  
@, \#, &, \+, \=, %, \~, \*  
( ), \[ \], { } (Full height)  
€, $, §, °  
\\ (Backslash), / (Slash), | (Pipe), \< \>