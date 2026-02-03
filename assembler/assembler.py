import json
import os
import random
import math
import glob
import argparse

class GlyphLibrary:
    def __init__(self, glyphs_dir):
        self.glyphs_dir = glyphs_dir
        self.library = {}
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
        json_files = glob.glob(os.path.join(self.glyphs_dir, "*.json"))
        for file_path in json_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    char = data.get('char')
                    if char:
                        self.library[char] = data
            except Exception as e:
                print(f"Error loading {file_path}: {e}")
        print(f"Loaded {len(self.library)} glyphs.")

    def get_glyph(self, char):
        return self.library.get(char)

    def get_filename_for_char(self, char):
        name = self.special_char_map.get(char, char)
        return f"{name}.json"

class Typesetter:
    def __init__(self, library, kerning_config_path=None):
        self.library = library
        
        # Defaults
        self.tracking_buffer = 5.0 
        self.space_width = 30.0 
        self.kerning_exceptions = {}

        if kerning_config_path and os.path.exists(kerning_config_path):
            try:
                with open(kerning_config_path, 'r') as f:
                    config = json.load(f)
                    self.space_width = config.get('space_width', self.space_width)
                    self.tracking_buffer = config.get('tracking_buffer', self.tracking_buffer)
                    self.kerning_exceptions = config.get('exceptions', {})
                print(f"Loaded kerning config from {kerning_config_path}")
            except Exception as e:
                print(f"Failed to load kerning config: {e}")

        self.last_variant_indices = {} # History to avoid repeats: {char: last_idx}

    def typeset_text(self, text):
        compiled_shapes = []
        cursor_x = 0.0
        cursor_y = 0.0 # Baseline

        for char in text:
            if char == '\n':
                cursor_x = 0
                cursor_y += 200 # Line height, todo: get from metadata
                # Reset variant history on new line? Optional. Let's keep it global for now.
                continue

            # Handle Space specifically if not in library (or override)
            if char == ' ':
                cursor_x += self.space_width
                continue

            glyph_data = self.library.get_glyph(char)
            if not glyph_data or not glyph_data.get('variants'):
                print(f"Warning: No glyph found for '{char}'")
                cursor_x += self.space_width # Placeholder advance
                continue

            # Stochastic Selection (Smart)
            variants = glyph_data['variants']
            num_variants = len(variants)
            
            if num_variants > 1:
                last_idx = self.last_variant_indices.get(char)
                available_indices = [i for i in range(num_variants) if i != last_idx]
                
                # If for some reason filtering removed everything (e.g. only 1 variant but logic failed), fallback
                if not available_indices:
                    available_indices = range(num_variants)
                
                selected_idx = random.choice(available_indices)
                self.last_variant_indices[char] = selected_idx
                selected_variant = variants[selected_idx]
            else:
                selected_variant = variants[0]
            
            # Kerning / Spacing Logic
            strokes = selected_variant['strokes']
            
            # Calculate Bounding Box for this variant to determine width and offset
            min_x = float('inf')
            max_x = float('-inf')
            has_points = False

            flat_points = []
            for stroke in strokes:
                for point in stroke:
                    has_points = True
                    min_x = min(min_x, point['x'])
                    max_x = max(max_x, point['x'])
                    flat_points.append(point)
            
            if not has_points:
                cursor_x += self.space_width
                continue

            # Calculate effective width
            content_width = max_x - min_x
            
            # Check for min_width exception
            min_width = 0.0
            if char in self.kerning_exceptions:
                min_width = self.kerning_exceptions[char].get('min_width', 0.0)
            
            final_width = max(content_width, min_width)
            
            # Spacing logic:
            # We shift points so (min_x) aligns with current cursor (+ centering offset if min_width applied?)
            # TDD says: "Trim: Shift all points left by subtracting min_x".
            # If min_width is used, we might want to center the content within that min_width.
            
            x_offset = cursor_x
            if content_width < min_width:
                # Center it
                centering = (min_width - content_width) / 2.0
                x_offset += centering

            # Normalize and Place
            placed_strokes = []
            for stroke in strokes:
                new_stroke = []
                for point in stroke:
                    # Shift to 0 relative to min_x, then add placement offset
                    new_x = (point['x'] - min_x) + x_offset
                    new_y = point['y'] + cursor_y
                    new_stroke.append({'x': new_x, 'y': new_y, 'p': point.get('p', 0.5)})
                placed_strokes.append(new_stroke)

            compiled_shapes.append(placed_strokes)

            # Advance Cursor
            cursor_x += final_width + self.tracking_buffer
        
        return compiled_shapes

class Renderer:
    def __init__(self, jitter_amount=0.0):
        self.jitter_amount = jitter_amount

    def generate_svg(self, compiled_shapes, output_file):
        # Calculate full bounding box for SVG viewbox
        all_x = []
        all_y = []
        
        for shape in compiled_shapes:
            for stroke in shape:
                for point in stroke:
                    all_x.append(point['x'])
                    all_y.append(point['y'])
        
        if not all_x:
            min_x, min_y, width, height = 0, 0, 100, 100
        else:
            padding = 10
            min_x = min(all_x) - padding
            min_y = min(all_y) - padding
            max_x = max(all_x) + padding
            max_y = max(all_y) + padding
            width = max_x - min_x
            height = max_y - min_y

        svg_content = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{min_x} {min_y} {width} {height}" width="{width}mm" height="{height}mm">',
            '<g fill="none" stroke="black" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        ]

        for shape in compiled_shapes:
            for stroke in shape:
                if len(stroke) < 2:
                    continue
                
                # Apply Jitter if needed
                points_str = ""
                for i, p in enumerate(stroke):
                    px = p['x']
                    py = p['y']
                    
                    if self.jitter_amount > 0:
                        px += random.gauss(0, self.jitter_amount)
                        py += random.gauss(0, self.jitter_amount)
                    
                    cmd = "M" if i == 0 else "L"
                    points_str += f"{cmd} {px:.2f} {py:.2f} "
                
                svg_content.append(f'<path d="{points_str.strip()}" />')

        svg_content.append('</g>')
        svg_content.append('</svg>')

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(svg_content))
        print(f"SVG saved to {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VHS Assembler: Convert text to vector handwriting SVG.")
    parser.add_argument("text", help="Text to render")
    parser.add_argument("output", help="Output SVG filename")
    parser.add_argument("--font", help="Name of the font subdirectory in glyphs/ folder", default=None)
    
    args = parser.parse_args()
    
    # Assume glyphs are in ../glyphs relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_glyphs_dir = os.path.join(script_dir, "../glyphs")
    
    if args.font:
        glyphs_path = os.path.join(base_glyphs_dir, args.font)
        # Check for font-specific kerning
        font_kerning = os.path.join(glyphs_path, "kerning.json")
        if os.path.exists(font_kerning):
            kerning_path = font_kerning
        else:
            kerning_path = os.path.join(script_dir, "kerning.json")
    else:
        glyphs_path = base_glyphs_dir
        kerning_path = os.path.join(script_dir, "kerning.json")
    
    if not os.path.exists(glyphs_path):
        print(f"Error: Glyphs directory not found: {glyphs_path}")
        exit(1)

    print(f"Loading glyphs from: {glyphs_path}")
    lib = GlyphLibrary(glyphs_path)
    
    typesetter = Typesetter(lib, kerning_config_path=kerning_path)
    shapes = typesetter.typeset_text(args.text)
    
    renderer = Renderer(jitter_amount=args.jitter)
    renderer.generate_svg(shapes, args.output)
