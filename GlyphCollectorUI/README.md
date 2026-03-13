# VHS Glyph Collector

A browser-based tool for capturing handwriting glyph variants with pressure sensitivity. Part of the VHS (Virtual Handwriting System) project.

## Features

-   **Variant Capture**: Draw multiple variants of a single character (default: 10).
-   **Pressure Sensitivity**: Captures pressure data (if supported by input device/tablet).
-   **Undo/Redo**: Per-stroke undo (Ctrl+Z / Cmd+Z) and redo (Ctrl+Shift+Z / Cmd+Shift+Z). Buttons also available in the header.
-   **Smooth Preview**: Live Catmull-Rom spline smoothing applied to the canvas display. Toggle with the **Smooth** button in the header. This is visual-only — raw capture data is preserved in the exported JSON.
-   **Auto-Save**: Drawing sessions are automatically saved to localStorage after every stroke. If the browser is closed accidentally, work is restored on the next page load.
-   **JSON Export**: Exports drawings as JSON files compatible with the VHS Assembler.
-   **Configurable Grid**:
    -   Adjust the number of variants.
    -   Customize box width and height.
    -   Set custom Baseline and x-Height positions.
-   **Multi-Font Support**: Specify a "Font Family" (e.g., "UweHandwriting") to organize your exports.
-   **Ligature Support**:
    -   Type multiple characters (e.g., "sch", "tt").
    -   Filenames are automatically sanitized (e.g., "1/4" -> `1slash4.json`).

## Usage

1.  Open `GlyphCollectorUI.html` in a modern web browser.
2.  **Draw**: Use a stylus or mouse to draw characters in the boxes.
3.  **Label**: Enter the character or ligature you are drawing in the input field (e.g., "a", "B", "sch").
4.  **Save**: Click **Save JSON** or press **Enter**.
    -   The file will be downloaded automatically.
    -   The grid will be cleared for the next character.

## Configuration

Click the **Settings (⚙️)** button in the header to open the configuration panel:

-   **Font Name**: The unique name of the font family (e.g., "MyScript"). Use this to keep sets of glyphs separate.
-   **Anzahl Varianten**: Number of boxes to display.
-   **Breite / Höhe**: Dimensions of each drawing box in pixels.
-   **Baseline Y**: Vertical position of the red baseline.
-   **x-Height Y**: Vertical position of the blue dashed x-height line.

> **Note**: Applying new settings will regenerate the grid and clear any current drawings.

## Keyboard Shortcuts

-   **Enter**: Save JSON and reset
-   **Ctrl+Z** / **Cmd+Z**: Undo last stroke (on the last-drawn variant)
-   **Ctrl+Shift+Z** / **Cmd+Shift+Z**: Redo last undone stroke
