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

class GlyphLibrary:
    def __init__(self, glyphs_dir: str):
        self.glyphs_dir = glyphs_dir
        self.library: Dict[str, Dict[str, Any]] = {}
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
        self.kerning_exceptions: Dict[str, Dict[str, float]] = {}

        if kerning_config_path and os.path.exists(kerning_config_path):
            try:
                with open(kerning_config_path, 'r') as f:
                    config = json.load(f)
                    self.space_width = config.get('space_width', self.space_width)
                    self.tracking_buffer = config.get('tracking_buffer', self.tracking_buffer)
                    self.kerning_exceptions = config.get('exceptions', {})
                logger.info(f"Loaded kerning config from {kerning_config_path}")
            except Exception as e:
                logger.error(f"Failed to load kerning config: {e}")

        self.last_variant_indices: Dict[str, int] = {} 

    def typeset_text(self, text: str) -> List[List[List[Dict[str, float]]]]:
        """
        Returns a list of 'shapes'.
        Each shape is a list of 'strokes'.
        Each stroke is a list of 'points' (dicts with x, y, p).
        """
        compiled_shapes = []
        cursor_x = 0.0
        cursor_y = 0.0 # Baseline

        for char in text:
            if char == '\n':
                cursor_x = 0
                cursor_y += 200 # Fixed Line Height for now
                continue

            if char == ' ':
                cursor_x += self.space_width
                continue

            glyph_data = self.library.get_glyph(char)
            if not glyph_data or not glyph_data.get('variants'):
                logger.warning(f"No glyph found for '{char}', skipping.")
                cursor_x += self.space_width # Placeholder advance
                continue

            # Stochastic Selection
            variants = glyph_data['variants']
            num_variants = len(variants)
            
            if num_variants > 1:
                last_idx = self.last_variant_indices.get(char)
                available_indices = [i for i in range(num_variants) if i != last_idx]
                
                if not available_indices:
                    available_indices = list(range(num_variants))
                
                selected_idx = random.choice(available_indices)
                self.last_variant_indices[char] = selected_idx
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
            if char in self.kerning_exceptions:
                min_width = self.kerning_exceptions[char].get('min_width', 0.0)
            
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

            # Advance Cursor
            cursor_x += final_width + self.tracking_buffer
        
        return compiled_shapes

class Renderer:
    def __init__(self, jitter_amount: float = 0.0, smoothing: bool = False):
        self.jitter_amount = jitter_amount
        self.smoothing = smoothing

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

    def generate_svg(self, compiled_shapes: List[List[List[Dict[str, float]]]], output_file: str):
        # Calculate full bounding box
        all_x = []
        all_y = []
        
        for shape in compiled_shapes:
            for stroke in shape:
                for point in stroke:
                    all_x.append(point['x'])
                    all_y.append(point['y'])
        
        if not all_x:
            min_x, min_y, width, height = 0.0, 0.0, 100.0, 100.0
        else:
            padding = 10.0
            min_x = min(all_x) - padding
            min_y = min(all_y) - padding
            max_x = max(all_x) + padding
            max_y = max(all_y) + padding
            width = max_x - min_x
            height = max_y - min_y

        # Build SVG using ElementTree
        ET.register_namespace("", "http://www.w3.org/2000/svg")
        
        svg = ET.Element("svg", {
            "xmlns": "http://www.w3.org/2000/svg",
            "viewBox": f"{min_x:.2f} {min_y:.2f} {width:.2f} {height:.2f}",
            "width": f"{width}mm",
            "height": f"{height}mm" 
        })

        g = ET.SubElement(svg, "g", {
            "fill": "none",
            "stroke": "black",
            "stroke-width": "2",
            "stroke-linecap": "round",
            "stroke-linejoin": "round"
        })

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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VHS Assembler: Convert text to vector handwriting SVG.")
    parser.add_argument("text", help="Text to render")
    parser.add_argument("output", help="Output SVG filename")
    parser.add_argument("--jitter", type=float, default=0.0, help="Amount of gaussian jitter to apply (default: 0.0)")
    parser.add_argument("--font", help="Name of the font subdirectory in glyphs/ folder", default=None)
    parser.add_argument("--smooth", action="store_true", help="Enable spline smoothing for curves")
    
    args = parser.parse_args()
    
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
    shapes = typesetter.typeset_text(args.text)
    
    renderer = Renderer(jitter_amount=args.jitter, smoothing=args.smooth)
    renderer.generate_svg(shapes, args.output)
