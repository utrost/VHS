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

            # Identify min/max x from raw strokes
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

            # Pre-calculate metrics from normalized_strokes if present
            if 'normalized_strokes' in variant:
                norm_min_x = float('inf')
                norm_max_x = float('-inf')
                norm_has_points = False
                for stroke in variant['normalized_strokes']:
                    for point in stroke:
                        norm_has_points = True
                        norm_min_x = min(norm_min_x, point['x'])
                        norm_max_x = max(norm_max_x, point['x'])
                if norm_has_points:
                    variant['normalized_metrics'] = {
                        'min_x': norm_min_x,
                        'max_x': norm_max_x,
                        'width': norm_max_x - norm_min_x,
                        'baseline_offset': baseline_y
                    }

    def get_glyph(self, char: str) -> Optional[Dict[str, Any]]:
        return self.library.get(char)

def _minimum_raggedness_breaks(widths: List[float], space_width: float,
                               max_width: float) -> List[int]:
    """Return line-start indices that minimise total squared slack.

    `widths` is a list of word widths (glyph units). `space_width` is added
    between adjacent words on the same line. `max_width` is the hard wrap
    limit. The last line is not penalised for being short.

    Returns a list `boundaries` of length (n_lines + 1); line k contains
    widths[boundaries[k]:boundaries[k+1]].
    """
    n = len(widths)
    if n == 0:
        return [0]

    prefix = [0.0] * (n + 1)
    for k in range(n):
        prefix[k + 1] = prefix[k] + widths[k]

    def line_width(i: int, j: int) -> float:
        return prefix[j] - prefix[i] + max(0, j - i - 1) * space_width

    INF = float('inf')
    # dp[i] = min cost of wrapping widths[i:]; back[i] = chosen line end.
    dp = [0.0] * (n + 1)
    back = [n] * (n + 1)
    for i in range(n - 1, -1, -1):
        best = INF
        best_j = i + 1
        j = i + 1
        while j <= n:
            lw = line_width(i, j)
            if lw > max_width:
                # Single oversized word has to be placed alone; otherwise stop.
                if j == i + 1:
                    total = dp[j]
                    if total < best:
                        best = total
                        best_j = j
                break
            slack = max_width - lw
            cost = 0.0 if j == n else slack * slack
            total = cost + dp[j]
            if total < best:
                best = total
                best_j = j
            j += 1
        dp[i] = best
        back[i] = best_j

    boundaries = [0]
    i = 0
    while i < n:
        i = back[i]
        boundaries.append(i)
    return boundaries


class Typesetter:
    def __init__(self, library: GlyphLibrary, kerning_config_path: Optional[str] = None,
                 use_bezier: bool = True, use_normalized: bool = True):
        self.library = library
        self.use_bezier = use_bezier
        self.use_normalized = use_normalized

        # Defaults
        self.tracking_buffer = 5.0
        self.space_width = 30.0
        self.line_height = 100.0 # Default line height
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
        self._compiled_beziers: List[Optional[List[List[Dict[str, Any]]]]] = []
        self._line_info: List[Dict[str, Any]] = []
        self._word_info: List[Dict[str, Any]] = []


    @staticmethod
    def _get_zone(y: float, x_height_y: float, baseline_y: float) -> str:
        """Classify a y-coordinate into a vertical zone.

        Canvas coordinates: y increases downward.
        - upper: above x-height line (y < x_height_y)
        - ground: between x-height and baseline (x_height_y <= y <= baseline_y)
        - lower: below baseline (y > baseline_y)
        """
        if y < x_height_y:
            return 'upper'
        elif y > baseline_y:
            return 'lower'
        return 'ground'

    @staticmethod
    def _nearest_pressure(raw_points: List[Dict[str, float]], target_x: float, target_y: float) -> float:
        """Find pressure of the nearest raw point to the given target coordinates."""
        if not raw_points:
            return 0.5
        best_dist = float('inf')
        best_p = 0.5
        for pt in raw_points:
            d = (pt['x'] - target_x) ** 2 + (pt['y'] - target_y) ** 2
            if d < best_dist:
                best_dist = d
                best_p = pt.get('p', 0.5)
        return best_p

    def calculate_optical_kerning(self, shapes_a: List[List[Dict[str, float]]],
                                  shapes_b: List[List[Dict[str, float]]],
                                  baseline_y: Optional[float] = None,
                                  x_height_y: Optional[float] = None,
                                  kern_aggressiveness: float = 0.5,
                                  resolution: int = 50) -> float:
        """
        Calculates the minimum horizontal distance between two shapes,
        with zone-aware weighting.

        When baseline_y and x_height_y are provided, scanlines are classified
        into vertical zones (upper / ground / lower). Scanlines where both
        glyphs have ink in the same zone use the strict minimum distance.
        Scanlines where the glyphs occupy different zones allow tighter
        kerning, controlled by kern_aggressiveness (0.0 = no extra tightening,
        1.0 = ignore non-shared zone scanlines entirely).
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

        zone_aware = baseline_y is not None and x_height_y is not None

        # Buckets for rightmost X of A and leftmost X of B
        buckets_a = {i: float('-inf') for i in range(resolution + 1)}
        buckets_b = {i: float('inf') for i in range(resolution + 1)}

        def fill_buckets(shapes, buckets, is_max):
            for stroke in shapes:
                for i in range(len(stroke) - 1):
                    p1 = stroke[i]
                    p2 = stroke[i+1]

                    seg_min_y = min(p1['y'], p2['y'])
                    seg_max_y = max(p1['y'], p2['y'])

                    start_idx = max(0, int((seg_min_y - min_y) / step))
                    end_idx = min(resolution, int((seg_max_y - min_y) / step) + 1)

                    for idx in range(start_idx, end_idx):
                        y_scan = min_y + (idx * step)

                        if abs(p1['y'] - p2['y']) < 1e-9:
                            continue

                        t = (y_scan - p1['y']) / (p2['y'] - p1['y'])
                        if 0 <= t <= 1:
                            x_intersect = p1['x'] + t * (p2['x'] - p1['x'])

                            if is_max:
                                buckets[idx] = max(buckets[idx], x_intersect)
                            else:
                                buckets[idx] = min(buckets[idx], x_intersect)

        fill_buckets(shapes_a, buckets_a, is_max=True)
        fill_buckets(shapes_b, buckets_b, is_max=False)

        # Determine which zones each glyph occupies (from actual stroke data)
        if zone_aware:
            zones_a = set()
            zones_b = set()
            for p in all_points_a:
                zones_a.add(self._get_zone(p['y'], x_height_y, baseline_y))
            for p in all_points_b:
                zones_b.add(self._get_zone(p['y'], x_height_y, baseline_y))
            shared_zones = zones_a & zones_b

        min_distance_shared = float('inf')
        min_distance_unshared = float('inf')
        has_shared = False

        for i in range(resolution + 1):
            if buckets_a[i] != float('-inf') and buckets_b[i] != float('inf'):
                dist = buckets_b[i] - buckets_a[i]

                if zone_aware:
                    y_scan = min_y + (i * step)
                    zone = self._get_zone(y_scan, x_height_y, baseline_y)
                    if zone in shared_zones:
                        has_shared = True
                        if dist < min_distance_shared:
                            min_distance_shared = dist
                    else:
                        if dist < min_distance_unshared:
                            min_distance_unshared = dist
                else:
                    if dist < min_distance_shared:
                        min_distance_shared = dist
                        has_shared = True

        if not has_shared and min_distance_unshared == float('inf'):
            return 0.0

        if not zone_aware or not has_shared:
            # No zone info or no shared zones — use overall minimum
            final = min(min_distance_shared, min_distance_unshared)
            if final == float('inf'):
                return 0.0
            return final

        # Blend: in shared zones use strict distance; for unshared zones,
        # kern_aggressiveness controls how much we ignore the unshared
        # constraint. At 1.0 we fully ignore unshared scanlines; at 0.0
        # we treat them the same as shared.
        if min_distance_unshared == float('inf'):
            return min_distance_shared

        blended_unshared = min_distance_unshared * (1.0 - kern_aggressiveness)
        return min(min_distance_shared, blended_unshared) if blended_unshared < min_distance_shared else min_distance_shared

    def typeset_text(self, text: str, override_line_height: Optional[float] = None,
                     auto_kern: bool = False, line_spacing: float = 1.0,
                     max_width: Optional[float] = None,
                     kern_aggressiveness: float = 0.5,
                     wrap_mode: str = 'balanced',
                     space_width_override: Optional[float] = None,
                     space_jitter: float = 0.0,
                     seed: Optional[int] = None) -> List[List[List[Dict[str, float]]]]:
        """
        Returns a list of 'shapes'.
        Each shape is a list of 'strokes'.
        Each stroke is a list of 'points' (dicts with x, y, p).

        line_spacing: multiplier applied to line_height for the vertical
                      distance between baselines (e.g. 1.5 = 150% spacing).
        max_width:    if set, automatically wrap lines that exceed this width.
        wrap_mode:    'greedy' (first-fit, legacy) or 'balanced' (minimum
                      raggedness — lines are chosen globally to minimise
                      line-to-line length variance).
        space_width_override: override the kerning config's space width
                      (glyph units).
        space_jitter: max ± variation applied to each space width (glyph units).
                      Deterministic when `seed` is set.

        As a side effect, populates self._line_info (one dict per rendered line:
        {start_idx, end_idx, baseline_y}) and self._word_info (one dict per
        word placed in the unwrapped layout: {start_idx, end_idx, start_x,
        end_x, line_break_after}).
        """
        current_line_height = override_line_height if override_line_height is not None else self.line_height
        effective_line_advance = current_line_height * line_spacing
        base_space_width = space_width_override if space_width_override is not None else self.space_width
        rng = random.Random(seed) if seed is not None else random

        compiled_shapes: List = []
        self._compiled_beziers = []
        self._line_info = []
        self._word_info = []

        # Balanced wrap is a two-pass flow: first lay out unwrapped (so we
        # know every word's true width), then run minimum-raggedness DP,
        # then shift words into their assigned lines.
        placement_max_width = max_width if wrap_mode != 'balanced' else None

        cursor_x = 0.0
        cursor_y = 0.0  # Baseline
        last_shape_placed = None
        last_glyph_data = None

        # Per-word state (index + x at first glyph of the current word)
        word_start_x = 0.0
        word_shape_start_idx = 0
        word_active = False  # True once we've placed at least one glyph in the current word

        # Per-line state (index of first shape on the current line)
        line_shape_start_idx = 0
        line_baseline_y = cursor_y

        def finalize_word(end_x: float, break_after: bool):
            """Close out the currently-open word (if any)."""
            nonlocal word_active, word_shape_start_idx, word_start_x
            if not word_active:
                return
            self._word_info.append({
                'start_idx': word_shape_start_idx,
                'end_idx': len(compiled_shapes),
                'start_x': word_start_x,
                'end_x': end_x,
                'line_break_after': break_after,
            })
            word_active = False

        def finalize_line():
            """Close out the current line's shape range."""
            nonlocal line_shape_start_idx, line_baseline_y
            self._line_info.append({
                'start_idx': line_shape_start_idx,
                'end_idx': len(compiled_shapes),
                'baseline_y': line_baseline_y,
            })
            line_shape_start_idx = len(compiled_shapes)
            line_baseline_y = cursor_y

        i = 0
        while i < len(text):
            char_at_i = text[i]

            if char_at_i == '\n':
                finalize_word(cursor_x, break_after=True)
                finalize_line()
                cursor_x = 0.0
                cursor_y += effective_line_advance
                line_baseline_y = cursor_y
                last_shape_placed = None
                last_glyph_data = None
                word_start_x = 0.0
                word_shape_start_idx = len(compiled_shapes)
                i += 1
                continue

            if char_at_i == ' ':
                finalize_word(cursor_x, break_after=False)
                # Per-space jitter (deterministic via rng)
                jitter = rng.uniform(-space_jitter, space_jitter) if space_jitter > 0 else 0.0
                cursor_x += max(0.0, base_space_width + jitter)
                last_shape_placed = None
                last_glyph_data = None
                word_start_x = cursor_x
                word_shape_start_idx = len(compiled_shapes)
                i += 1
                continue

            # Greedy Matching for Ligatures
            match_found = False
            max_lookahead = min(self.library.max_key_length, len(text) - i)

            for length in range(max_lookahead, 0, -1):
                candidate = text[i: i + length]
                glyph_data = self.library.get_glyph(candidate)

                if glyph_data and glyph_data.get('variants'):
                    # Starting a new word? (first glyph after a space / newline / start)
                    if not word_active:
                        word_active = True
                        word_start_x = cursor_x
                        word_shape_start_idx = len(compiled_shapes)

                    width, placed_strokes = self._process_glyph(
                        glyph_data, candidate, cursor_x, cursor_y, compiled_shapes)

                    # Optical Kerning
                    manual_tracking_offset = 0.0
                    if candidate in self.kerning_exceptions:
                        manual_tracking_offset = self.kerning_exceptions[candidate].get('tracking_offset', 0.0)

                    if auto_kern and last_shape_placed:
                        bl_a = last_glyph_data.get('metadata', {}).get('baseline_y') if last_glyph_data else None
                        xh_a = last_glyph_data.get('metadata', {}).get('x_height') if last_glyph_data else None
                        bl_b = glyph_data.get('metadata', {}).get('baseline_y')
                        xh_b = glyph_data.get('metadata', {}).get('x_height')

                        bl = None
                        xh = None
                        if bl_a is not None and bl_b is not None and xh_a is not None and xh_b is not None:
                            bl = cursor_y
                            xh = ((xh_a - bl_a) + (xh_b - bl_b)) / 2.0 + cursor_y

                        gap = self.calculate_optical_kerning(
                            last_shape_placed, placed_strokes,
                            baseline_y=bl, x_height_y=xh,
                            kern_aggressiveness=kern_aggressiveness)
                        shift = gap - self.tracking_buffer
                        cursor_x -= shift
                        for stroke in placed_strokes:
                            for p in stroke:
                                p['x'] -= shift
                        bezier_entry = self._compiled_beziers[-1]
                        if bezier_entry is not None:
                            for bstroke in bezier_entry:
                                for seg in bstroke:
                                    for key in ('p0', 'p1', 'p2', 'p3'):
                                        seg[key]['x'] -= shift

                    cursor_x += width + self.tracking_buffer + manual_tracking_offset
                    last_shape_placed = placed_strokes
                    last_glyph_data = glyph_data

                    # Greedy wrap (only active when placement_max_width is set)
                    if placement_max_width is not None and cursor_x > placement_max_width and word_start_x > 0:
                        finalize_line()
                        shift_x = word_start_x
                        shift_y = effective_line_advance
                        for si in range(word_shape_start_idx, len(compiled_shapes)):
                            for stroke in compiled_shapes[si]:
                                for p in stroke:
                                    p['x'] -= shift_x
                                    p['y'] += shift_y
                            if si < len(self._compiled_beziers) and self._compiled_beziers[si] is not None:
                                for bstroke in self._compiled_beziers[si]:
                                    for seg in bstroke:
                                        for key in ('p0', 'p1', 'p2', 'p3'):
                                            seg[key]['x'] -= shift_x
                                            seg[key]['y'] += shift_y
                        cursor_x -= shift_x
                        cursor_y += shift_y
                        line_baseline_y = cursor_y
                        # The wrapped word remains the "current" word
                        word_start_x = 0.0

                    i += length
                    match_found = True
                    break

            if not match_found:
                logger.warning(f"No glyph found for '{text[i]}', skipping.")
                cursor_x += base_space_width  # Placeholder advance
                last_shape_placed = None
                last_glyph_data = None
                self._compiled_beziers.append(None)
                i += 1

        # Flush the trailing word / line
        finalize_word(cursor_x, break_after=False)
        finalize_line()

        # Balanced wrap pass
        if wrap_mode == 'balanced' and max_width is not None and self._word_info:
            self._apply_balanced_wrap(compiled_shapes, self._compiled_beziers,
                                      max_width, base_space_width,
                                      effective_line_advance)

        return compiled_shapes

    def _apply_balanced_wrap(self, compiled_shapes, bezier_data, max_width,
                             space_width, line_advance):
        """Rewrite line breaks using a minimum-raggedness DP.

        Words are grouped into paragraphs by explicit \\n breaks (the
        `line_break_after` flag set in _word_info). Each paragraph is
        wrapped independently. After this pass, self._line_info is rebuilt.
        """
        # Split words into paragraphs
        paragraphs: List[List[int]] = []
        current: List[int] = []
        for idx, w in enumerate(self._word_info):
            current.append(idx)
            if w['line_break_after']:
                paragraphs.append(current)
                current = []
        if current:
            paragraphs.append(current)

        new_lines: List[Dict[str, Any]] = []
        line_y = 0.0

        for para in paragraphs:
            widths = [self._word_info[i]['end_x'] - self._word_info[i]['start_x']
                      for i in para]
            if not widths:
                # Empty paragraph (consecutive \n) — still advances a line
                new_lines.append({'start_idx': None, 'end_idx': None,
                                  'baseline_y': line_y})
                line_y += line_advance
                continue

            boundaries = _minimum_raggedness_breaks(widths, space_width, max_width)

            for k in range(len(boundaries) - 1):
                i0_local = boundaries[k]
                i1_local = boundaries[k + 1]
                i0 = para[i0_local]
                i1_last = para[i1_local - 1]

                first_word_start_x = self._word_info[i0]['start_x']
                shift_x = -first_word_start_x
                shift_y = line_y  # absolute y for this line

                shape_start = self._word_info[i0]['start_idx']
                shape_end = self._word_info[i1_last]['end_idx']

                # Shift all shapes in this line into position.
                # Original shapes were placed at y = 0 (single line) with
                # offsets from descenders etc. We translate by shift_y.
                for si in range(shape_start, shape_end):
                    for stroke in compiled_shapes[si]:
                        for p in stroke:
                            p['x'] += shift_x
                            p['y'] += shift_y
                    if si < len(bezier_data) and bezier_data[si] is not None:
                        for bstroke in bezier_data[si]:
                            for seg in bstroke:
                                for key in ('p0', 'p1', 'p2', 'p3'):
                                    seg[key]['x'] += shift_x
                                    seg[key]['y'] += shift_y

                new_lines.append({'start_idx': shape_start,
                                  'end_idx': shape_end,
                                  'baseline_y': line_y})
                line_y += line_advance

        self._line_info = new_lines

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

        # Choose data source: normalized_strokes preferred when available and enabled
        use_norm = self.use_normalized and 'normalized_strokes' in selected_variant
        if use_norm and 'normalized_metrics' in selected_variant:
            metrics = selected_variant['normalized_metrics']
            strokes = selected_variant['normalized_strokes']
        else:
            metrics = selected_variant.get('metrics', {'min_x': 0.0, 'width': 0.0, 'baseline_offset': 0.0})
            strokes = selected_variant['strokes']

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

        # Handle Bezier curves: transform control points the same way
        bezier_strokes = None
        if self.use_bezier and 'bezier_curves' in selected_variant:
            # For bezier coordinate transform, use raw stroke metrics (bezier is in raw coordinate space)
            raw_metrics = selected_variant.get('metrics', {'min_x': 0.0, 'baseline_offset': 0.0})
            raw_min_x = raw_metrics['min_x']
            raw_baseline = raw_metrics['baseline_offset']
            # If content was centered for min_width, apply same offset
            bz_x_offset = x_offset if not use_norm else cursor_x
            if use_norm and content_width < min_width:
                bz_x_offset = cursor_x + (min_width - content_width) / 2.0

            raw_strokes = selected_variant['strokes']
            bezier_strokes = []
            for s_idx, bezier_stroke in enumerate(selected_variant['bezier_curves']):
                raw_pts = raw_strokes[s_idx] if s_idx < len(raw_strokes) else []
                transformed_stroke = []
                for seg in bezier_stroke:
                    new_seg = {}
                    for key in ('p0', 'p1', 'p2', 'p3'):
                        pt = seg[key]
                        new_seg[key] = {
                            'x': (pt['x'] - raw_min_x) + bz_x_offset,
                            'y': (pt['y'] - raw_baseline) + cursor_y
                        }
                    # Interpolate pressure from raw stroke points
                    new_seg['pressure_start'] = self._nearest_pressure(raw_pts, seg['p0']['x'], seg['p0']['y'])
                    new_seg['pressure_end'] = self._nearest_pressure(raw_pts, seg['p3']['x'], seg['p3']['y'])
                    transformed_stroke.append(new_seg)
                bezier_strokes.append(transformed_stroke)

        self._compiled_beziers.append(bezier_strokes)

        return final_width, placed_strokes

class Renderer:
    def __init__(self, jitter_amount: float = 0.0, smoothing: bool = False, color: str = "black",
                 stroke_width: float = 2.0, seed: Optional[int] = None, use_bezier: bool = True):
        self.jitter_amount = jitter_amount
        self.smoothing = smoothing
        self.color = color
        self.stroke_width = stroke_width
        self.seed = seed
        self.use_bezier = use_bezier

    def _catmull_rom_spline(self, points: List[Dict[str, float]]) -> List[Tuple[float, float]]:
        """
        Interpolates points using Catmull-Rom splines with adaptive step count.
        Short segments get fewer interpolation steps; long segments get more.
        """
        if len(points) < 2:
            return [(p['x'], p['y']) for p in points]

        # Extract coords
        P = [(p['x'], p['y']) for p in points]

        # Duplicate endpoints to handle open curves
        P = [P[0]] + P + [P[-1]]

        smoothed_path = []

        for i in range(len(P) - 3):
            p0, p1, p2, p3 = P[i], P[i+1], P[i+2], P[i+3]

            # Adaptive step count based on segment length
            seg_len = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
            steps = max(2, min(12, int(seg_len / 3)))

            for s in range(steps):
                t = s / steps
                t2 = t * t
                t3 = t2 * t

                x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
                y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)

                smoothed_path.append((x, y))

        # Add the very last point explicitly
        smoothed_path.append(P[-2])

        return smoothed_path

    def _bezier_to_svg_path(self, bezier_segments: List[Dict[str, Any]]) -> str:
        """Convert a list of cubic Bezier segments to an SVG path d-string using C commands."""
        if not bezier_segments:
            return ""
        seg0 = bezier_segments[0]
        p0 = seg0['p0']
        px, py = p0['x'], p0['y']
        if self.jitter_amount > 0:
            px += random.gauss(0, self.jitter_amount)
            py += random.gauss(0, self.jitter_amount)
        path = f"M {px:.2f} {py:.2f} "
        for seg in bezier_segments:
            coords = []
            for key in ('p1', 'p2', 'p3'):
                cx, cy = seg[key]['x'], seg[key]['y']
                if self.jitter_amount > 0:
                    cx += random.gauss(0, self.jitter_amount)
                    cy += random.gauss(0, self.jitter_amount)
                coords.append(f"{cx:.2f} {cy:.2f}")
            path += f"C {coords[0]} {coords[1]} {coords[2]} "
        return path.strip()

    def generate_svg(self, compiled_shapes: List[List[List[Dict[str, float]]]], output_file: str,
                     page_width_mm: Optional[float] = None, page_height_mm: Optional[float] = None,
                     margin_mm: float = 20.0, bezier_data: Optional[List] = None,
                     explicit_scale: Optional[float] = None,
                     start_x_mm: Optional[float] = None,
                     start_y_mm: Optional[float] = None,
                     line_info: Optional[List[Dict[str, Any]]] = None,
                     line_drift_angle_deg: float = 0.0,
                     line_drift_y: float = 0.0,
                     drift_seed: Optional[int] = None):
        """
        Generate an SVG file from compiled shapes.

        When page_width_mm/page_height_mm are set, the SVG is sized to that
        fixed page and content is offset by margin_mm on all sides.
        Otherwise the SVG auto-fits to the content bounding box (original behaviour).

        When explicit_scale is set (mm-based layout), glyph coordinates are
        multiplied by this factor (mm per glyph unit) instead of being
        scale-to-fit. start_x_mm/start_y_mm override the page origin of the
        text block (default: margin_mm).

        bezier_data: optional parallel list to compiled_shapes. Each entry is either
                     None (no bezier data) or a list of bezier strokes for that shape.
        """
        fixed_page = page_width_mm is not None and page_height_mm is not None

        # Seed RNG for deterministic jitter (same input → same output)
        if self.jitter_amount > 0:
            if self.seed is not None:
                random.seed(self.seed)
            else:
                # Derive a stable seed from the content itself
                content_hash = 0
                for shape in compiled_shapes:
                    for stroke in shape:
                        for point in stroke:
                            content_hash ^= hash((round(point['x'], 2), round(point['y'], 2)))
                random.seed(content_hash)

        # Calculate full bounding box
        all_x = []
        all_y = []

        for shape in compiled_shapes:
            for stroke in shape:
                for point in stroke:
                    all_x.append(point['x'])
                    all_y.append(point['y'])

        # Include bezier control points in bounding box
        if bezier_data and self.use_bezier:
            for shape_bezier in bezier_data:
                if shape_bezier is not None:
                    for bstroke in shape_bezier:
                        for seg in bstroke:
                            for key in ('p0', 'p1', 'p2', 'p3'):
                                all_x.append(seg[key]['x'])
                                all_y.append(seg[key]['y'])

        if fixed_page:
            # Fixed page mode — dimensions come from paper preset
            width = page_width_mm
            height = page_height_mm
            vb_x = 0.0
            vb_y = 0.0

            if explicit_scale is not None:
                # mm-based layout: caller supplies the scale (mm per glyph unit)
                # and optional page origin. No scale-to-fit.
                scale = explicit_scale
                origin_x = start_x_mm if start_x_mm is not None else margin_mm
                origin_y = start_y_mm if start_y_mm is not None else margin_mm
                content_offset_x = min(all_x) if all_x else 0.0
                content_offset_y = min(all_y) if all_y else 0.0
            else:
                # Compute scale factor to fit content within the available area
                avail_w = page_width_mm - 2 * margin_mm
                avail_h = page_height_mm - 2 * margin_mm
                origin_x = margin_mm
                origin_y = margin_mm
                if all_x and avail_w > 0 and avail_h > 0:
                    content_w = max(all_x) - min(all_x)
                    content_h = max(all_y) - min(all_y)
                    content_offset_x = min(all_x)
                    content_offset_y = min(all_y)
                    if content_w > 0 and content_h > 0:
                        scale = min(avail_w / content_w, avail_h / content_h)
                    elif content_w > 0:
                        scale = avail_w / content_w
                    elif content_h > 0:
                        scale = avail_h / content_h
                    else:
                        scale = 1.0
                else:
                    scale = 1.0
                    content_offset_x = 0.0
                    content_offset_y = 0.0
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
            "stroke-linecap": "round",
            "stroke-linejoin": "round"
        }
        if fixed_page:
            # Scale content to fit (or explicitly) and translate to page origin
            g_attrs["stroke-width"] = f"{self.stroke_width / scale:.4f}"
            g_attrs["transform"] = (
                f"translate({origin_x:.2f},{origin_y:.2f}) "
                f"scale({scale:.6f}) "
                f"translate({-content_offset_x:.2f},{-content_offset_y:.2f})"
            )
        else:
            g_attrs["stroke-width"] = str(self.stroke_width)

        g = ET.SubElement(svg, "g", g_attrs)

        def emit_shape(parent, shape_idx: int):
            shape = compiled_shapes[shape_idx]
            shape_bezier = None
            if self.use_bezier and bezier_data and shape_idx < len(bezier_data):
                shape_bezier = bezier_data[shape_idx]

            for stroke_idx, stroke in enumerate(shape):
                stroke_bezier = None
                if shape_bezier is not None and stroke_idx < len(shape_bezier):
                    stroke_bezier = shape_bezier[stroke_idx]

                if stroke_bezier:
                    points_str = self._bezier_to_svg_path(stroke_bezier)
                    if points_str:
                        ET.SubElement(parent, "path", {"d": points_str})
                    continue

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

                ET.SubElement(parent, "path", {"d": points_str.strip()})

        drift_enabled = (line_info and
                         (line_drift_angle_deg > 0.0 or line_drift_y > 0.0))

        if drift_enabled:
            # Each line gets its own <g> with a rotate(θ 0 baseline) translate(0 dy).
            # Shapes outside any line (shouldn't happen) go in the parent group.
            drift_rng = random.Random(drift_seed) if drift_seed is not None else random
            shape_to_line = [-1] * len(compiled_shapes)
            for li, info in enumerate(line_info):
                s, e = info.get('start_idx'), info.get('end_idx')
                if s is None or e is None:
                    continue
                for si in range(s, e):
                    if 0 <= si < len(shape_to_line):
                        shape_to_line[si] = li

            # Precompute one transform per line
            line_transforms: List[str] = []
            for info in line_info:
                theta = (drift_rng.uniform(-line_drift_angle_deg, line_drift_angle_deg)
                         if line_drift_angle_deg > 0 else 0.0)
                dy = (drift_rng.uniform(-line_drift_y, line_drift_y)
                      if line_drift_y > 0 else 0.0)
                baseline = float(info.get('baseline_y') or 0.0)
                parts = []
                if theta != 0.0:
                    parts.append(f"rotate({theta:.3f} 0 {baseline:.2f})")
                if dy != 0.0:
                    parts.append(f"translate(0 {dy:.3f})")
                line_transforms.append(" ".join(parts))

            # Emit per-line groups, skipping empty lines
            for li, info in enumerate(line_info):
                s, e = info.get('start_idx'), info.get('end_idx')
                if s is None or e is None or s == e:
                    continue
                tf = line_transforms[li]
                parent = ET.SubElement(g, "g", {"transform": tf}) if tf else g
                for si in range(s, e):
                    emit_shape(parent, si)

            # Any unassigned shape (rare) goes directly on the main group
            for si in range(len(compiled_shapes)):
                if shape_to_line[si] == -1:
                    emit_shape(g, si)
        else:
            for si in range(len(compiled_shapes)):
                emit_shape(g, si)

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

    def generate_svg_string(self, compiled_shapes, page_width_mm=None, page_height_mm=None,
                            margin_mm=20.0, bezier_data=None,
                            explicit_scale=None, start_x_mm=None, start_y_mm=None,
                            line_info=None, line_drift_angle_deg=0.0,
                            line_drift_y=0.0, drift_seed=None):
        """Generate SVG and return it as a UTF-8 string (for web serving)."""
        import io
        buf = io.BytesIO()
        self.generate_svg(compiled_shapes, buf, page_width_mm=page_width_mm,
                          page_height_mm=page_height_mm, margin_mm=margin_mm,
                          bezier_data=bezier_data,
                          explicit_scale=explicit_scale,
                          start_x_mm=start_x_mm, start_y_mm=start_y_mm,
                          line_info=line_info,
                          line_drift_angle_deg=line_drift_angle_deg,
                          line_drift_y=line_drift_y,
                          drift_seed=drift_seed)
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
    parser.add_argument("--no-smooth", action="store_true", help="Disable spline smoothing (smoothing is on by default)")
    parser.add_argument("--no-bezier", action="store_true",
                        help="Ignore bezier_curves from glyph JSON even if present")
    parser.add_argument("--no-normalize", action="store_true",
                        help="Ignore normalized_strokes from glyph JSON even if present")
    parser.add_argument("--line-spacing", type=float, default=1.0,
                        help="Multiplier applied to line height (e.g. 1.5 = 150%% spacing). Default: 1.0")
    parser.add_argument("--auto-kern", action="store_true", help="Enable automatic optical kerning to reduce whitespace")
    parser.add_argument("--kern-aggressiveness", type=float, default=0.5,
                        help="How aggressively zone-aware kerning tightens non-overlapping zones (0.0–1.0). "
                             "0.0 = no extra tightening, 1.0 = fully ignore non-shared zones. Default: 0.5")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed for deterministic jitter. If omitted, seed is derived from content.")
    parser.add_argument("--color", default="black", help="Hex code or color name for the stroke (default: black)")
    parser.add_argument("--stroke-width", type=float, default=2.0,
                        help="Stroke width in SVG units (default: 2.0). Automatically scaled in fixed-page mode.")
    parser.add_argument("--paper-size", choices=paper_choices, default=None,
                        help=f"Fixed paper size for the output SVG. Choices: {', '.join(paper_choices)}")
    parser.add_argument("--orientation", choices=["portrait", "landscape"], default="portrait",
                        help="Page orientation when --paper-size is set (default: portrait)")
    parser.add_argument("--margin", type=float, default=20.0,
                        help="Page margin in mm on all sides when --paper-size is set (default: 20.0)")
    parser.add_argument("--line-height-mm", type=float, default=None,
                        help="Baseline-to-baseline line height in mm. One of "
                             "--line-height-mm or --lines-per-page is required "
                             "with --paper-size.")
    parser.add_argument("--lines-per-page", type=int, default=None,
                        help="Derive --line-height-mm so this many lines "
                             "(multiplied by --line-spacing) fit in the writable "
                             "page area. Requires --paper-size.")
    parser.add_argument("--start-x", type=float, default=None,
                        help="X coordinate of the top-left of the text block in mm "
                             "(default: --margin).")
    parser.add_argument("--start-y", type=float, default=None,
                        help="Y coordinate of the top-left of the text block in mm "
                             "(default: --margin).")
    parser.add_argument("--wrap-mode", choices=["greedy", "balanced"], default="balanced",
                        help="Line-break algorithm. 'balanced' (default) runs a minimum-"
                             "raggedness DP across the whole paragraph for uniform line "
                             "lengths; 'greedy' is the older first-fit wrap.")
    parser.add_argument("--space-width-mm", type=float, default=None,
                        help="Width of a space in mm. Overrides the font's kerning config.")
    parser.add_argument("--space-jitter-mm", type=float, default=0.0,
                        help="Max ± random variation applied to each space (mm). "
                             "Default: 0 (uniform). Deterministic when --seed is set.")
    parser.add_argument("--line-drift-angle", type=float, default=0.0,
                        help="Max ± per-line rotation in degrees to simulate a drifting "
                             "hand. Default: 0 (perfectly straight). Try 0.2–0.5.")
    parser.add_argument("--line-drift-y", type=float, default=0.0,
                        help="Max ± per-line baseline wobble in mm. Default: 0. Try 0.2–0.6.")
    parser.add_argument("--paginate", action="store_true",
                        help="Split content that overflows the page height into multiple "
                             "files (output-01.svg, output-02.svg, ...). Requires --paper-size.")
    parser.add_argument("--max-width-mm", type=float, default=None,
                        help="Word-wrap width in mm "
                             "(default: page_width - margin - start-x).")

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

    # Resolve paper dimensions
    page_w, page_h = None, None
    if args.paper_size:
        pw, ph = PAPER_SIZES[args.paper_size]
        if args.orientation == "landscape":
            pw, ph = ph, pw
        page_w, page_h = float(pw), float(ph)
        logger.info(f"Page: {args.paper_size} {args.orientation} ({page_w}×{page_h} mm), margin {args.margin} mm")

    use_bezier = not args.no_bezier
    use_normalized = not args.no_normalize

    lib = GlyphLibrary(glyphs_path)
    typesetter = Typesetter(lib, kerning_config_path=kerning_path,
                            use_bezier=use_bezier, use_normalized=use_normalized)

    explicit_scale = None
    start_x_mm = None
    start_y_mm = None
    max_width = None

    if page_w is not None:
        # Fixed-page (mm-based) layout
        line_height_mm = args.line_height_mm
        if args.lines_per_page is not None:
            avail_h = page_h - 2 * args.margin
            line_height_mm = avail_h / (args.lines_per_page * args.line_spacing)
            logger.info(f"--lines-per-page {args.lines_per_page} → line-height-mm {line_height_mm:.2f}")

        if line_height_mm is None:
            logger.error("--paper-size requires --line-height-mm or --lines-per-page")
            exit(1)
        if line_height_mm <= 0:
            logger.error("Line height must be positive")
            exit(1)

        native_lh = typesetter.line_height
        mm_per_glyph = line_height_mm / native_lh
        explicit_scale = mm_per_glyph

        start_x_mm = args.start_x if args.start_x is not None else args.margin
        start_y_mm = args.start_y if args.start_y is not None else args.margin

        max_width_mm = (args.max_width_mm
                        if args.max_width_mm is not None
                        else page_w - args.margin - start_x_mm)
        max_width = (max_width_mm / mm_per_glyph) if max_width_mm and max_width_mm > 0 else None

        wrap_desc = f"{max_width_mm:.1f}mm" if max_width_mm and max_width_mm > 0 else "off"
        logger.info(
            f"mm layout: line {line_height_mm:.2f}mm, scale {mm_per_glyph:.4f}mm/unit, "
            f"origin ({start_x_mm:.1f},{start_y_mm:.1f})mm, wrap {wrap_desc}"
        )

    # Convert mm-valued whitespace/drift controls into glyph units.
    space_width_override = None
    space_jitter = 0.0
    line_drift_y_glyph = 0.0
    if explicit_scale is not None:
        if args.space_width_mm is not None:
            space_width_override = args.space_width_mm / explicit_scale
        if args.space_jitter_mm > 0:
            space_jitter = args.space_jitter_mm / explicit_scale
        if args.line_drift_y > 0:
            line_drift_y_glyph = args.line_drift_y / explicit_scale
    else:
        if args.space_width_mm is not None:
            logger.warning("--space-width-mm ignored without --paper-size "
                           "(no mm → glyph-unit conversion available).")
        if args.space_jitter_mm > 0:
            logger.warning("--space-jitter-mm ignored without --paper-size.")
        if args.line_drift_y > 0:
            logger.warning("--line-drift-y ignored without --paper-size.")

    shapes = typesetter.typeset_text(input_text,
                                     auto_kern=args.auto_kern, line_spacing=args.line_spacing,
                                     max_width=max_width,
                                     kern_aggressiveness=args.kern_aggressiveness,
                                     wrap_mode=args.wrap_mode,
                                     space_width_override=space_width_override,
                                     space_jitter=space_jitter,
                                     seed=args.seed)

    renderer = Renderer(jitter_amount=args.jitter, smoothing=not args.no_smooth, color=args.color,
                        stroke_width=args.stroke_width, seed=args.seed, use_bezier=use_bezier)

    # Pagination: split content into pages if --paginate is active.
    pages: List[Tuple[str, List, List, List]] = []  # (output_path, shapes, bezier, line_info)

    if args.paginate and page_h is not None and explicit_scale is not None:
        effective_line_advance_mm = line_height_mm * args.line_spacing
        avail_h = page_h - start_y_mm - args.margin
        lines_per_page = max(1, int(avail_h // effective_line_advance_mm))

        line_info = typesetter._line_info
        if not line_info:
            pages.append((args.output, shapes, typesetter._compiled_beziers, line_info))
        else:
            # Build the page filename template.
            root, ext = os.path.splitext(args.output)
            total_pages = (len(line_info) + lines_per_page - 1) // lines_per_page or 1
            for p in range(total_pages):
                first_line = p * lines_per_page
                last_line = min(first_line + lines_per_page, len(line_info))
                page_lines = line_info[first_line:last_line]
                # Shape index range for this page
                page_shapes_start = next((li['start_idx'] for li in page_lines
                                          if li.get('start_idx') is not None), None)
                page_shapes_end = next((li['end_idx'] for li in reversed(page_lines)
                                        if li.get('end_idx') is not None), None)
                if page_shapes_start is None or page_shapes_end is None:
                    continue  # empty page (only blank lines)
                page_shape_slice = shapes[page_shapes_start:page_shapes_end]
                page_bezier_slice = typesetter._compiled_beziers[page_shapes_start:page_shapes_end]
                # Re-index line_info entries so they point into the slice
                adjusted = [{
                    'start_idx': (li['start_idx'] - page_shapes_start) if li.get('start_idx') is not None else None,
                    'end_idx': (li['end_idx'] - page_shapes_start) if li.get('end_idx') is not None else None,
                    'baseline_y': li.get('baseline_y'),
                } for li in page_lines]
                page_path = f"{root}-{p+1:02d}{ext}"
                pages.append((page_path, page_shape_slice, page_bezier_slice, adjusted))
            logger.info(f"Pagination: {len(pages)} page(s) "
                        f"({lines_per_page} lines × {effective_line_advance_mm:.2f}mm per page)")
    else:
        if args.paginate:
            logger.warning("--paginate requires --paper-size; emitting a single file.")
        pages.append((args.output, shapes, typesetter._compiled_beziers, typesetter._line_info))

    for page_path, page_shapes, page_bezier, page_lines in pages:
        renderer.generate_svg(page_shapes, page_path,
                              page_width_mm=page_w, page_height_mm=page_h,
                              margin_mm=args.margin, bezier_data=page_bezier,
                              explicit_scale=explicit_scale,
                              start_x_mm=start_x_mm, start_y_mm=start_y_mm,
                              line_info=page_lines,
                              line_drift_angle_deg=args.line_drift_angle,
                              line_drift_y=line_drift_y_glyph,
                              drift_seed=args.seed)
