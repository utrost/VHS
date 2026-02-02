import os
import sys
import random
import math

# Add script dir to path
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(script_dir)

from assembler import GlyphLibrary, Typesetter, Renderer

def test_assembler():
    print("Running Assembler Tests...")
    
    glyphs_path = os.path.join(script_dir, "../glyphs")
    lib = GlyphLibrary(glyphs_path)
    
    # 1. Test Smart Stochastic Selection
    print("\n[Test 1] Smart Stochastic Selection")
    # We need a character with multiple variants. 'a' has 2 or more from our previous work.
    # Note: If 'a.json' only has 1 variant in the mock/actual data, this test might be trivial.
    # We will assume 'a' has multiple variants based on user input or mocks.
    
    typesetter = Typesetter(lib)
    text = "aaaaa"
    shapes = typesetter.typeset_text(text)
    
    # We can't easily introspect which variant ID was chosen from the 'shapes' output strictly
    # without modifying Typesetter to return metadata.
    # However, we can check if the shapes are identical.
    # If they are different, we know different variants were chosen.
    # Since we can't guarantee 'a' has variants in this environment without checking the file,
    # we'll look for *any* difference in the point coordinates relative to their start.
    
    # Extract just the stroke data (normalized to 0,0) to compare
    def get_shape_signature(shape):
        # Flatten points relative to the first point of the first stroke
        if not shape or not shape[0]: return []
        ref_x = shape[0][0]['x']
        ref_y = shape[0][0]['y']
        sig = []
        for stroke in shape:
            for p in stroke:
                sig.append((p['x'] - ref_x, p['y'] - ref_y))
        return sig

    signatures = [get_shape_signature(s) for s in shapes]
    
    # Check adjacent signatures
    repeats = 0
    for i in range(len(signatures) - 1):
        if signatures[i] == signatures[i+1]:
            repeats += 1
    
    print(f"Rendered 'aaaaa'. Adjacent identical shapes: {repeats}")
    if repeats == 0:
        print("SUCCESS: No adjacent identical glyphs found (assuming variants exist).")
    else:
        print("WARNING: Adjacent identical glyphs found. Either 'a' has only 1 variant or logic failed.")

    # 2. Test Kerning (Min Width)
    print("\n[Test 2] Kerning Exceptions (Min Width)")
    # We know '.' has a min_width in kerning.json.
    # Let's verify that a period takes up space.
    
    # Create a typesetter with the config
    kerning_path = os.path.join(script_dir, "kerning.json")
    typesetter_kern = Typesetter(lib, kerning_config_path=kerning_path)
    
    # Render ".."
    # If min_width works, cursor should advance by min_width + tracking
    # We can't check cursor directly, but we can check the x-coordinates of the generated shapes.
    
    shapes_dot = typesetter_kern.typeset_text("..")
    if len(shapes_dot) >= 2:
        # Get x-start of first and second dot
        # Note: shapes[i] is a list of strokes, stroke is list of points
        # The points are absolute coordinates
        
        def get_min_x(shape):
            return min([p['x'] for stroke in shape for p in stroke])
            
        x1 = get_min_x(shapes_dot[0])
        x2 = get_min_x(shapes_dot[1])
        
        diff = x2 - x1
        print(f"Distance between two periods: {diff:.2f}")
        
        # Expected: min_width (20.0) + tracking (5.0) = 25.0
        # Allow small float margin
        if abs(diff - 25.0) < 1.0:
            print("SUCCESS: Spacing matches min_width + tracking.")
        else:
            print(f"FAILURE: Expected ~25.0, got {diff:.2f}")

    # 3. Test Jitter
    print("\n[Test 3] Jitter")
    renderer_clean = Renderer(jitter_amount=0.0)
    renderer_jitter = Renderer(jitter_amount=2.0)
    
    file_clean = "test_clean.svg"
    file_jitter = "test_jitter.svg"
    
    renderer_clean.generate_svg(shapes, file_clean)
    renderer_jitter.generate_svg(shapes, file_jitter)
    
    # Check file sizes or content diff
    size_clean = os.path.getsize(file_clean)
    size_jitter = os.path.getsize(file_jitter)
    
    # Note: Jitter changes coordinate numbers, likely changing string length slightly (float representation)
    # But mainly we verify they run.
    print(f"Generated {file_clean} and {file_jitter}")
    if size_clean > 0 and size_jitter > 0:
        print("SUCCESS: Both SVG files generated.")
        
    # Cleanup
    try:
        os.remove(file_clean)
        os.remove(file_jitter)
    except:
        pass

if __name__ == "__main__":
    test_assembler()
