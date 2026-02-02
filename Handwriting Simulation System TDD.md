# **Technical Design Document: Vector-Based Handwriting Simulation (VHS)**

## **1\. Project Overview**

The VHS system provides a deterministic pipeline for generating realistic handwriting for pen plotters. It replaces neural-network-based generation with a stochastic "Shaping Engine" utilizing a custom-captured library of single-stroke vector glyphs.  
**Key Objectives:**

* **True Single-Stroke:** Output paths are 1-pixel wide vectors (no outlines/double-tracking).  
* **Multilingual Native:** Full support for German Umlauts (ä, ö, ü), ß, and special punctuation via raw capture.  
* **Automated Spacing:** Kerning is calculated mathematically from vector bounding boxes, removing the need for manual UI adjustments.

## **2\. System Architecture**

| Module | Component | Technology | Responsibility |
| :---- | :---- | :---- | :---- |
| **Capture** | Batch Glyph Collector | HTML5/JS (Canvas) | Captures raw pointer coordinates ($x,y,p,t$) in a "Filmstrip" UI (5 variants per char). Handles filename sanitization. |
| **Storage** | Glyph Library | JSON Files | Stores strokes as serialized point arrays. Files are named safely (e.g., question.json for ?). |
| **Synthesis** | The Assembler | Python | Performs text shaping, stochastic variant selection, Bounding Box kerning, and jitter simulation. |

## **3\. Data Specification (Glyph JSON)**

To support batching, the JSON schema aggregates all variants of a single character into one "Master Asset."  
{  
  "char": "?",   
  "exported\_at": "2025-11-24T10:00:00Z",  
  "metadata": {  
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

* **Batch Pattern:** Displays 5 horizontal canvas slots to allow rapid repetition (muscle memory).  
* **Sanitization:** Automatically maps filesystem-unsafe characters to safe filenames (e.g., / $\\rightarrow$ slash.json).  
* **Input:** Uses Pointer Events API to capture pressure and tilt where available.  
* **Guides:** \* **Red Solid Line (**$y=250$**):** Absolute Baseline.  
  * **Blue Dashed Line (**$y=150$**):** x-Height reference.

## **5\. Backend Logic: The Assembler (Python)**

### **A. Automated Proportional Spacing (Kerning)**

The UI does not capture width. The Python script calculates it dynamically to prevent "monospaced" look.

1. **Normalization:** For each selected variant, calculate the Bounding Box ($x\_{min}, x\_{max}$).  
2. **Trim:** Shift all points left by subtracting $x\_{min}$ ($NewX \= OldX \- x\_{min}$).  
3. **Advance Width:** The cursor moves by $(x\_{max} \- x\_{min}) \+ \\text{TrackingBuffer}$.  
4. **Overrides:** A kerning.json file handles exceptions:  
   * **Space:** Fixed width (e.g., 10mm).  
   * **Narrow Punctuation:** Enforce min-width for ., ,, '.

### **B. Stochastic Shaping**

1. **Ligature Scan:** Checks input string for defined ligatures (sch, ss, ch) availability in the library.  
2. **Variant Rotation:** Randomly selects variant\_id (0-4) to ensure no two adjacent characters look identical.  
3. **High-Connector Logic:** If the previous letter ends high (o, v, w), the script can vertically shift the entry point of the next letter (if supported by stroke geometry) or select a specific "alt" glyph.

### **C. Quantized Jitter**

Applied post-shaping to simulate mechanical imperfection:

$$P\_{new} \= P\_{old} \+ N(0, \\sigma)$$

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