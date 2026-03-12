import json
import os
import random
import glob
import argparse
import logging
import math
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Paper size presets in mm (width, height) — portrait orientation
PAPER_SIZES = {
    "A3": (297, 420),
    "A4": (210, 297),
    "A5": (148, 210),
    "A6": (105, 148),
    "Letter": (216, 279),
    "Legal": (216, 356),
}

class GlyphLibrary:
    def __init__(self, glyphs_dir: str):
        self.glyphs_dir = glyphs_dir
        self.library: Dict[str, Dict[str, Any]] = {}
        self.max_key_length = 1
        self.special_char_map = {
            '.': 'period', ',': 'comma', ':': 'colon', ';': 'semicolon',
            '?': 'question', '!': 'exclamation', '"': 'quote_double',
            "'": 'quote_single', '`': 'backtick', '/': 'slash', '\\': 'backslash',
            '|': 'pipe', '<': 'less', '>': 'greater', '*': 'asterisk',
            ' ': 'space', '@': 'at', '#': 'hash', '$': 'dollar',
            '%': 'percent', '^': 'caret', '&': 'ampersand',
            '(': 'paren_left', ')': 'paren_right', '{': 'brace_left',
            '}': 'brace_right', '[': 'bracket_left', ']': 'bracket_right',
            '=': 'equals', '+': 'plus', '~': 'tilde', '€': 'euro',
            '§': 'section', '°': 'degree'
        }
        self.load_library()

    def load_library(self):
        json_pattern = os.path.join(self.glyphs_dir, "*.json")
        json_files = glob.glob(json_pattern)
        
        if not json_files:
            logger.warning(f"No .json files found in {self.glyphs_dir}")

        for file_path in json_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    char = data.get('char')
                    if char:
                        # Pre-calculate metrics for each variant
                        self._preprocess_variants(data)
                        self.library[char] = data
                        if len(char) > self.max_key_length:
                            self.max_key_length = len(char)
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON in {file_path}")
            except Exception as e:
                logger.error(f"Error loading {file_path}: {e}")
        
        logger.info(f"Loaded {len(self.library)} glyphs from {self.glyphs_dir}")

    def _preprocess_variants(self, glyph_data: Dict[str, Any]):
        """Calculate bounding boxes and widths once upon loading."""
        if 'variants' not in glyph_data:
            return

        baseline_y = 0.0
        if 'metadata' in glyph_data:
             baseline_y = glyph_data['metadata'].get('baseline_y', 0.0)

        for variant in glyph_data['variants']:
            min_x = float('inf')
            max_x = float('-inf')
            has_points = False
            
            # Identify min/max x
            for stroke in variant.get('strokes', []):
                for point in stroke:
                    has_points = True
                    min_x = min(min_x, point['x'])
                    max_x = max(max_x, point['x'])
            
            if has_points:
                variant['metrics'] = {
                    'min_x': min_x,
                    'max_x': max_x,
                    'width': max_x - min_x,
                    'baseline_offset': baseline_y
                }
            else:
                variant['metrics'] = {
                    'min_x': 0.0,
                    'max_x': 0.0,
                    'width': 0.0,
                    'baseline_offset': 0.0
                }

    def get_glyph(self, char: str) -> Optional[Dict[str, Any]]:
        return self.library.get(char)

class Typesetter:
    def __init__(self, library: GlyphLibrary, kerning_config_path: Optional[str] = None):
        self.library = library
        
        # Defaults
        self.tracking_buffer = 5.0 
        self.space_width = 30.0
        self.line_height = 200.0 # Default line height
        self.kerning_exceptions: Dict[str, Dict[str, float]] = {}

        if kerning_config_path and os.path.exists(kerning_config_path):
            try:
                with open(kerning_config_path, 'r') as f:
                    config = json.load(f)
                    self.space_width = config.get('space_width', self.space_width)
                    self.tracking_buffer = config.get('tracking_buffer', self.tracking_buffer)
                    self.line_height = config.get('line_height', self.line_height)
                    self.kerning_exceptions = config.get('exceptions', {})
                logger.info(f"Loaded kerning config from {kerning_config_path}")
            except Exception as e:
                logger.error(f"Failed to load kerning config: {e}")

        self.last_variant_indices: Dict[str, int] = {} 

    
    def calculate_optical_kerning(self, shapes_a: List[List[Dict[str, float]]], shapes_b: List[List[Dict[str, float]]], resolution: int = 50) -> float:
        """
        Calculates the minimum horizontal distance between two shapes.
        Positive value means they are apart, negative means they overlap.
        """
        if not shapes_a or not shapes_b:
            return 0.0

        # Flatten points to find vertical bounds
        all_points_a = [p for stroke in shapes_a for p in stroke]
        all_points_b = [p for stroke in shapes_b for p in stroke]
        
        if not all_points_a or not all_points_b:
            return 0.0

        min_y = min(p['y'] for p in all_points_a + all_points_b)
        max_y = max(p['y'] for p in all_points_a + all_points_b)
        
        height = max_y - min_y
        if height <= 0:
            return 0.0
            
        step = height / resolution
        
        # Buckets for rightmost X of A and leftmost X of B
        # Initialize with extreme values
        # buckets_a[i] = max x found in slice i
        # buckets_b[i] = min x found in slice i
        buckets_a = {i: float('-inf') for i in range(resolution + 1)}
        buckets_b = {i: float('inf') for i in range(resolution + 1)}
        
        def fill_buckets(shapes, buckets, is_max):
            for stroke in shapes:
                for i in range(len(stroke) - 1):
                    p1 = stroke[i]
                    p2 = stroke[i+1]
                    
                    # Segment Y range
                    seg_min_y = min(p1['y'], p2['y'])
                    seg_max_y = max(p1['y'], p2['y'])
                    
                    start_idx = max(0, int((seg_min_y - min_y) / step))
                    end_idx = min(resolution, int((seg_max_y - min_y) / step) + 1)
                    
                    for idx in range(start_idx, end_idx):
                        y_scan = min_y + (idx * step)
                        
                        # Check INTERSECTION with scanline y_scan
                        # Avoid division by zero for horizontal lines
                        if abs(p1['y'] - p2['y']) < 1e-9:
                            continue
                            
                        # Linear interpolation for X
                        t = (y_scan - p1['y']) / (p2['y'] - p1['y'])
                        if 0 <= t <= 1:
                            x_intersect = p1['x'] + t * (p2['x'] - p1['x'])
                            
                            if is_max:
                                buckets[idx] = max(buckets[idx], x_intersect)
                            else:
                                buckets[idx] = min(buckets[idx], x_intersect)

        fill_buckets(shapes_a, buckets_a, is_max=True)
        fill_buckets(shapes_b, buckets_b, is_max=False)
        
        min_distance = float('inf')
        
        for i in range(resolution + 1):
            if buckets_a[i] != float('-inf') and buckets_b[i] != float('inf'):
                dist = buckets_b[i] - buckets_a[i]
                if dist < min_distance:
                    min_distance = dist
                    
        if min_distance == float('inf'):
            # No vertical overlap
            return 0.0
            
        return min_distance

    def typeset_text(self, text: str, override_line_height: Optional[float] = None, auto_kern: bool = False, line_spacing: float = 1.0) -> List[List[List[Dict[str, float]]]]:
        """
        Returns a list of 'shapes'.
        Each shape is a list of 'strokes'.
        Each stroke is a list of 'points' (dicts with x, y, p).
        
        line_spacing: multiplier applied to line_height for the vertical
                      distance between baselines (e.g. 1.5 = 150% spacing).
        """
        
        current_line_height = override_line_height if override_line_height is not None else self.line_height
        effective_line_advance = current_line_height * line_spacing
        
        compiled_shapes = []
        # Store raw shapes for optical kerning calculation (before final placement)
        # But wait, we need them placed relative to 0,0 of the CHAR to calculate distance?
        # Actually, best to store the LAST placed shape to compare against.
        
        cursor_x = 0.0
        cursor_y = 0.0 # Baseline

        last_shape_placed = None # List of strokes of the previous character (in absolute coords)

        i = 0
        while i < len(text):
            char_at_i = text[i]

            if char_at_i == '\n':
                cursor_x = 0
                cursor_y += effective_line_advance
                last_shape_placed = None
                i += 1
                continue

            if char_at_i == ' ':
                cursor_x += self.space_width
                last_shape_placed = None
                i += 1
                continue

            # Greedy Matching for Ligatures
            match_found = False
            max_lookahead = min(self.library.max_key_length, len(text) - i)
            
            for length in range(max_lookahead, 0, -1):
                candidate = text[i : i + length]
                glyph_data = self.library.get_glyph(candidate)
                
                if glyph_data and glyph_data.get('variants'):
                    # Match found! Use this glyph
                    
                    # 1. First, calculate where it WOULD go naturally
                    # This adds the strokes to compiled_shapes
                    width, placed_strokes = self._process_glyph(glyph_data, candidate, cursor_x, cursor_y, compiled_shapes)
                    
                    # 2. Optical Kerning
                    manual_tracking_offset = 0.0
                    if candidate in self.kerning_exceptions:
                        manual_tracking_offset = self.kerning_exceptions[candidate].get('tracking_offset', 0.0)

                    if auto_kern and last_shape_placed:
                        # Calculate gap between last_shape_placed and placed_strokes
                        gap = self.calculate_optical_kerning(last_shape_placed, placed_strokes)
                        
                        # We want the gap to be exactly self.tracking_buffer
                        # Current gap is 'gap'. Target is 'self.tracking_buffer'.
                        # Shift needed = gap - self.tracking_buffer
                        
                        shift = gap - self.tracking_buffer
                        
                        # Apply shift to both cursor_x AND the points of the just-placed glyph
                        cursor_x -= shift
                        for stroke in placed_strokes:
                            for p in stroke:
                                p['x'] -= shift
                    
                    # Update for next loop
                    cursor_x += width + self.tracking_buffer + manual_tracking_offset
                    last_shape_placed = placed_strokes
                    
                    i += length
                    match_found = True
                    break
            
            if not match_found:
                logger.warning(f"No glyph found for '{text[i]}', skipping.")
                cursor_x += self.space_width # Placeholder advance
                last_shape_placed = None
                i += 1

        return compiled_shapes

    def _process_glyph(self, glyph_data: Dict[str, Any], char_key: str, cursor_x: float, cursor_y: float, compiled_shapes: List) -> Tuple[float, List[List[Dict[str, float]]]]:
        # Stochastic Selection
        variants = glyph_data['variants']
        num_variants = len(variants)
        
        if num_variants > 1:
            last_idx = self.last_variant_indices.get(char_key)
            available_indices = [i for i in range(num_variants) if i != last_idx]
            
            if not available_indices:
                available_indices = list(range(num_variants))
            
            selected_idx = random.choice(available_indices)
            self.last_variant_indices[char_key] = selected_idx
            selected_variant = variants[selected_idx]
        else:
            selected_variant = variants[0]
        
        # Use Pre-calculated Metrics
        metrics = selected_variant.get('metrics', {'min_x': 0.0, 'width': 0.0, 'baseline_offset': 0.0})
        content_width = metrics['width']
        min_x_original = metrics['min_x']
        baseline_offset = metrics['baseline_offset']
        
        # Kerning Exceptions (min_width)
        min_width = 0.0
        if char_key in self.kerning_exceptions:
            min_width = self.kerning_exceptions[char_key].get('min_width', 0.0)
        
        final_width = max(content_width, min_width)
        
        # Centering if content is smaller than min_width
        x_offset = cursor_x
        if content_width < min_width:
            centering = (min_width - content_width) / 2.0
            x_offset += centering

        # Normalize and Place Points
        strokes = selected_variant['strokes']
        placed_strokes = []
        
        for stroke in strokes:
            new_stroke = []
            for point in stroke:
                # Generic shift: (x - min_x) + offset
                # Y shift: (y - baseline_offset) + cursor_y
                new_x = (point['x'] - min_x_original) + x_offset
                new_y = (point['y'] - baseline_offset) + cursor_y
                new_stroke.append({'x': new_x, 'y': new_y, 'p': point.get('p', 0.5)})
            placed_strokes.append(new_stroke)

        compiled_shapes.append(placed_strokes)
        
        return final_width, placed_strokes

class Renderer:
    def __init__(self, jitter_amount: float = 0.0, smoothing: bool = False, color: str = "black"):
        self.jitter_amount = jitter_amount
        self.smoothing = smoothing
        self.color = color

    def _catmull_rom_spline(self, points: List[Dict[str, float]], steps: int = 5) -> List[Tuple[float, float]]:
        """
        Interpolates points using Catmull-Rom splines.
        """
        if len(points) < 2:
            return [(p['x'], p['y']) for p in points]

        # Extract coords
        P = [(p['x'], p['y']) for p in points]
        
        # Duplicate endpoints to handle open curves
        P = [P[0]] + P + [P[-1]]
        
        smoothed_path = []
        
        def lerp(a, b, t):
            return a + (b - a) * t

        for i in range(len(P) - 3):
            p0, p1, p2, p3 = P[i], P[i+1], P[i+2], P[i+3]
            
            for s in range(steps):
                t = s / steps
                t2 = t * t
                t3 = t2 * t
                
                # Catmull-Rom Matrix calculation
                # q(t) = 0.5 * [ (2*p1) + (-p0 + p2)*t + (2*p0 - 5*p1 + 4*p2 - p3)*t2 + (-p0 + 3*p1 - 3*p2 + p3)*t3 ]
                
                x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
                y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
                
                smoothed_path.append((x, y))
        
        # Add the very last point explicitly
        smoothed_path.append(P[-2]) 
        
        return smoothed_path

    def generate_svg(self, compiled_shapes: List[List[List[Dict[str, float]]]], output_file: str,
                     page_width_mm: Optional[float] = None, page_height_mm: Optional[float] = None,
                     margin_mm: float = 20.0):
        """
        Generate an SVG file from compiled shapes.
        
        When page_width_mm/page_height_mm are set, the SVG is sized to that
        fixed page and content is offset by margin_mm on all sides.
        Otherwise the SVG auto-fits to the content bounding box (original behaviour).
        """
        fixed_page = page_width_mm is not None and page_height_mm is not None

        # Calculate full bounding box
        all_x = []
        all_y = []
        
        for shape in compiled_shapes:
            for stroke in shape:
                for point in stroke:
                    all_x.append(point['x'])
                    all_y.append(point['y'])
        
        if fixed_page:
            # Fixed page mode — dimensions come from paper preset
            width = page_width_mm
            height = page_height_mm
            vb_x = 0.0
            vb_y = 0.0
        elif not all_x:
            vb_x, vb_y, width, height = 0.0, 0.0, 100.0, 100.0
        else:
            padding = 10.0
            vb_x = min(all_x) - padding
            vb_y = min(all_y) - padding
            max_x = max(all_x) + padding
            max_y = max(all_y) + padding
            width = max_x - vb_x
            height = max_y - vb_y

        # Build SVG using ElementTree
        ET.register_namespace("", "http://www.w3.org/2000/svg")
        
        svg = ET.Element("svg", {
            "xmlns": "http://www.w3.org/2000/svg",
            "viewBox": f"{vb_x:.2f} {vb_y:.2f} {width:.2f} {height:.2f}",
            "width": f"{width}mm",
            "height": f"{height}mm" 
        })

        g_attrs = {
            "fill": "none",
            "stroke": self.color,
            "stroke-width": "2",
            "stroke-linecap": "round",
            "stroke-linejoin": "round"
        }
        if fixed_page:
            g_attrs["transform"] = f"translate({margin_mm:.2f},{margin_mm:.2f})"

        g = ET.SubElement(svg, "g", g_attrs)

        for shape in compiled_shapes:
            for stroke in shape:
                if len(stroke) < 2:
                    continue
                
                if self.smoothing:
                    path_coords = self._catmull_rom_spline(stroke)
                else:
                    path_coords = [(p['x'], p['y']) for p in stroke]

                points_str = ""
                for i, (px, py) in enumerate(path_coords):
                    
                    if self.jitter_amount > 0:
                        px += random.gauss(0, self.jitter_amount)
                        py += random.gauss(0, self.jitter_amount)
                    
                    cmd = "M" if i == 0 else "L"
                    points_str += f"{cmd} {px:.2f} {py:.2f} "
                
                ET.SubElement(g, "path", {"d": points_str.strip()})

        tree = ET.ElementTree(svg)
        try:
            try:
                ET.indent(tree, space="  ", level=0)
            except AttributeError:
                pass 
                
            tree.write(output_file, encoding="utf-8", xml_declaration=True)
            logger.info(f"SVG saved to {output_file}")
        except Exception as e:
            logger.error(f"Failed to write SVG: {e}")

    def generate_svg_string(self, compiled_shapes, page_width_mm=None, page_height_mm=None, margin_mm=20.0):
        """Generate SVG and return it as a UTF-8 string (for web serving)."""
        import io
        buf = io.BytesIO()
        self.generate_svg(compiled_shapes, buf, page_width_mm=page_width_mm,
                          page_height_mm=page_height_mm, margin_mm=margin_mm)
        buf.seek(0)
        return buf.read().decode("utf-8")

if __name__ == "__main__":
    paper_choices = list(PAPER_SIZES.keys())

    parser = argparse.ArgumentParser(description="VHS Assembler: Convert text to vector handwriting SVG.")
    parser.add_argument("text", nargs="?", help="Text to render (optional if --file is used)")
    parser.add_argument("output", help="Output SVG filename")
    parser.add_argument("--file", "-f", help="Read text from file instead of command line argument")
    parser.add_argument("--jitter", type=float, default=0.0, help="Amount of gaussian jitter to apply (default: 0.0)")
    parser.add_argument("--font", help="Name of the font subdirectory in glyphs/ folder", default=None)
    parser.add_argument("--smooth", action="store_true", help="Enable spline smoothing for curves")
    parser.add_argument("--line-height", type=float, help="Override line height for multiline text")
    parser.add_argument("--line-spacing", type=float, default=1.0,
                        help="Multiplier for line height (e.g. 1.5 = 150%% spacing). Default: 1.0")
    parser.add_argument("--auto-kern", action="store_true", help="Enable automatic optical kerning to reduce whitespace")
    parser.add_argument("--color", default="black", help="Hex code or color name for the stroke (default: black)")
    parser.add_argument("--paper-size", choices=paper_choices, default=None,
                        help=f"Fixed paper size for the output SVG. Choices: {', '.join(paper_choices)}")
    parser.add_argument("--orientation", choices=["portrait", "landscape"], default="portrait",
                        help="Page orientation when --paper-size is set (default: portrait)")
    parser.add_argument("--margin", type=float, default=20.0,
                        help="Page margin in mm on all sides when --paper-size is set (default: 20.0)")
    
    args = parser.parse_args()
    
    input_text = ""
    if args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                input_text = f.read()
        except Exception as e:
            logger.error(f"Failed to read input file: {e}")
            exit(1)
    elif args.text:
        input_text = args.text
    else:
        logger.error("No input provided. Use 'text' argument or --file.")
        exit(1)
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_glyphs_dir = os.path.join(script_dir, "../glyphs")
    
    kerning_path = os.path.join(script_dir, "kerning.json")
    glyphs_path = base_glyphs_dir
    
    if args.font:
        glyphs_path = os.path.join(base_glyphs_dir, args.font)
        font_kerning = os.path.join(glyphs_path, "kerning.json")
        if os.path.exists(font_kerning):
            kerning_path = font_kerning
    
    if not os.path.exists(glyphs_path):
        logger.error(f"Glyphs directory not found: {glyphs_path}")
        exit(1)

    lib = GlyphLibrary(glyphs_path)
    typesetter = Typesetter(lib, kerning_config_path=kerning_path)
    shapes = typesetter.typeset_text(input_text, override_line_height=args.line_height,
                                     auto_kern=args.auto_kern, line_spacing=args.line_spacing)
    
    renderer = Renderer(jitter_amount=args.jitter, smoothing=args.smooth, color=args.color)

    # Resolve paper dimensions
    page_w, page_h = None, None
    if args.paper_size:
        pw, ph = PAPER_SIZES[args.paper_size]
        if args.orientation == "landscape":
            pw, ph = ph, pw
        page_w, page_h = float(pw), float(ph)
        logger.info(f"Page: {args.paper_size} {args.orientation} ({page_w}×{page_h} mm), margin {args.margin} mm")

    renderer.generate_svg(shapes, args.output, page_width_mm=page_w, page_height_mm=page_h, margin_mm=args.margin)
