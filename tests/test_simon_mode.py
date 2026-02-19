"""Test module for Simon game mode.

Tests verify:
- simon.py file exists and has valid syntax
- Simon is correctly registered in the manifest
- MatrixManager.draw_wedge renders a curved ring-sector, not a full quadrant
- draw_wedge uses self.width / self.height (no hardcoded 8 references)
- draw_wedge produces a different (subset) pixel set vs draw_quadrant
- draw_wedge works correctly for both 8x8 and 16x16 matrices
"""

import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# ---------------------------------------------------------------------------
# Stub out CircuitPython-specific modules before any src imports
# ---------------------------------------------------------------------------
class _MockModule:
    def __getattr__(self, name):
        return _MockModule()
    def __call__(self, *args, **kwargs):
        return _MockModule()

for _mod in [
    'digitalio', 'busio', 'board', 'adafruit_mcp230xx',
    'adafruit_mcp230xx.mcp23017', 'adafruit_ticks', 'audiobusio',
    'audiocore', 'audiomixer', 'analogio', 'microcontroller', 'watchdog',
    'audiopwmio', 'synthio', 'ulab', 'neopixel',
    'adafruit_displayio_ssd1306', 'adafruit_display_text',
    'adafruit_display_text.label', 'adafruit_ht16k33',
    'adafruit_ht16k33.segments',
]:
    sys.modules[_mod] = _MockModule()

from managers.matrix_manager import MatrixManager


# ---------------------------------------------------------------------------
# Minimal pixel mocks
# ---------------------------------------------------------------------------

class _MockPixels:
    def __init__(self, n):
        self.n = n
        self._data = [(0, 0, 0)] * n
        self.brightness = 0.3

    def __setitem__(self, idx, color):
        if 0 <= idx < self.n:
            self._data[idx] = color

    def __getitem__(self, idx):
        return self._data[idx]

    def fill(self, color):
        self._data = [color] * self.n

    def show(self):
        pass


class _MockJEBPixel:
    def __init__(self, n):
        self.n = n
        self._pixels = _MockPixels(n)
        self.brightness = 0.3

    def __setitem__(self, idx, color):
        self._pixels[idx] = color

    def __getitem__(self, idx):
        return self._pixels[idx]

    def fill(self, color):
        self._pixels.fill(color)

    def show(self):
        pass


# ---------------------------------------------------------------------------
# Helper: collect lit pixel coordinates after a draw call
# ---------------------------------------------------------------------------

def _lit_pixels(matrix):
    """Return the set of (x, y) coordinates with any active animation slot."""
    lit = set()
    for y in range(matrix.height):
        for x in range(matrix.width):
            idx = matrix._get_idx(x, y)
            slot = matrix.active_animations[idx]
            if slot.active:
                lit.add((x, y))
    return lit


def _make_matrix(width, height):
    n = width * height
    return MatrixManager(_MockJEBPixel(n), width=width, height=height)


# ---------------------------------------------------------------------------
# File / manifest checks
# ---------------------------------------------------------------------------

def test_simon_mode_file_exists():
    """simon.py must exist in src/modes/."""
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'simon.py')
    assert os.path.exists(path), "simon.py does not exist"


def test_simon_mode_valid_syntax():
    """simon.py must have valid Python syntax."""
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'simon.py')
    with open(path) as fh:
        code = fh.read()
    compile(code, path, 'exec')


def test_simon_in_manifest():
    """SIMON must be registered in MODE_REGISTRY."""
    from modes.manifest import MODE_REGISTRY
    assert "SIMON" in MODE_REGISTRY
    entry = MODE_REGISTRY["SIMON"]
    assert entry["id"] == "SIMON"
    assert entry["module_path"] == "modes.simon"
    assert entry["class_name"] == "Simon"


def test_simon_uses_draw_wedge_not_draw_quadrant():
    """simon.py must call draw_wedge, not draw_quadrant, for quadrant flashing."""
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'simon.py')
    with open(path) as fh:
        code = fh.read()
    assert 'draw_wedge' in code, "simon.py must use draw_wedge for quadrant flashing"
    assert 'draw_quadrant' not in code, "simon.py must not reference draw_quadrant"


# ---------------------------------------------------------------------------
# draw_wedge correctness tests
# ---------------------------------------------------------------------------

def test_draw_wedge_method_exists():
    """MatrixManager must expose draw_wedge."""
    matrix = _make_matrix(16, 16)
    assert hasattr(matrix, 'draw_wedge'), "MatrixManager missing draw_wedge method"


def test_draw_wedge_all_four_quadrants_16x16():
    """draw_wedge must light some pixels in each quadrant on a 16x16 matrix."""
    COLOR = (0, 255, 0)
    for quad_idx in range(4):
        matrix = _make_matrix(16, 16)
        matrix.draw_wedge(quad_idx, COLOR)
        lit = _lit_pixels(matrix)
        assert len(lit) > 0, f"draw_wedge(quad={quad_idx}) lit no pixels on 16x16"


def test_draw_wedge_pixels_inside_correct_quadrant_16x16():
    """All lit pixels must lie within the correct half of the 16x16 matrix."""
    COLOR = (255, 0, 0)
    w, h = 16, 16
    half_x, half_y = w // 2, h // 2

    bounds = [
        (range(0, half_x),   range(0, half_y)),   # 0: Top-left
        (range(half_x, w),   range(0, half_y)),   # 1: Top-right
        (range(0, half_x),   range(half_y, h)),   # 2: Bottom-left
        (range(half_x, w),   range(half_y, h)),   # 3: Bottom-right
    ]

    for quad_idx, (x_range, y_range) in enumerate(bounds):
        matrix = _make_matrix(w, h)
        matrix.draw_wedge(quad_idx, COLOR)
        lit = _lit_pixels(matrix)
        for (x, y) in lit:
            assert x in x_range and y in y_range, (
                f"Pixel ({x},{y}) outside expected quadrant {quad_idx} bounds"
            )


def test_draw_wedge_is_subset_of_draw_quadrant_16x16():
    """Wedge pixels must be a strict subset of the full quadrant pixels."""
    COLOR = (0, 0, 255)
    for quad_idx in range(4):
        matrix_w = _make_matrix(16, 16)
        matrix_q = _make_matrix(16, 16)

        matrix_w.draw_wedge(quad_idx, COLOR)
        matrix_q.draw_quadrant(quad_idx, COLOR)

        wedge_lit = _lit_pixels(matrix_w)
        quad_lit = _lit_pixels(matrix_q)

        # Every wedge pixel must also appear in the full quadrant
        assert wedge_lit.issubset(quad_lit), (
            f"Wedge contains pixels outside quadrant {quad_idx}"
        )
        # The wedge must cover fewer pixels (curved, not full rectangle)
        assert len(wedge_lit) < len(quad_lit), (
            f"Wedge should be smaller than full quadrant {quad_idx} on 16x16"
        )


def test_draw_wedge_inner_gap_exists_16x16():
    """Pixels very close to the matrix centre must NOT be lit (inner gap)."""
    COLOR = (255, 255, 0)
    w, h = 16, 16
    cx, cy = w / 2, h / 2
    half = min(cx, cy)
    inner_r = half * 0.3   # must match the production formula
    inner_r_sq = inner_r * inner_r

    for quad_idx in range(4):
        matrix = _make_matrix(w, h)
        matrix.draw_wedge(quad_idx, COLOR)
        lit = _lit_pixels(matrix)
        for (x, y) in lit:
            d_sq = (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2
            assert d_sq >= inner_r_sq - 1e-12, (
                f"Pixel ({x},{y}) is inside the inner gap (d_sq={d_sq:.4f} < inner_r_sq={inner_r_sq:.4f})"
            )


def test_draw_wedge_outer_arc_clips_corners_16x16():
    """Pixels farther than the outer radius must NOT be lit."""
    COLOR = (0, 255, 255)
    w, h = 16, 16
    cx, cy = w / 2, h / 2
    half = min(cx, cy)
    outer_r = half   # must match the production formula
    outer_r_sq = outer_r * outer_r

    for quad_idx in range(4):
        matrix = _make_matrix(w, h)
        matrix.draw_wedge(quad_idx, COLOR)
        lit = _lit_pixels(matrix)
        for (x, y) in lit:
            d_sq = (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2
            assert d_sq <= outer_r_sq + 1e-12, (
                f"Pixel ({x},{y}) is beyond outer arc (d_sq={d_sq:.4f} > outer_r_sq={outer_r_sq:.4f})"
            )


def test_draw_wedge_works_on_8x8():
    """draw_wedge must light some pixels and respect bounds on an 8x8 matrix."""
    COLOR = (255, 0, 255)
    w, h = 8, 8
    half_x, half_y = w // 2, h // 2

    bounds = [
        (range(0, half_x),  range(0, half_y)),
        (range(half_x, w),  range(0, half_y)),
        (range(0, half_x),  range(half_y, h)),
        (range(half_x, w),  range(half_y, h)),
    ]

    for quad_idx, (x_range, y_range) in enumerate(bounds):
        matrix = _make_matrix(w, h)
        matrix.draw_wedge(quad_idx, COLOR)
        lit = _lit_pixels(matrix)
        assert len(lit) > 0, f"draw_wedge(quad={quad_idx}) lit no pixels on 8x8"
        for (x, y) in lit:
            assert x in x_range and y in y_range, (
                f"Pixel ({x},{y}) outside quadrant {quad_idx} on 8x8"
            )


def test_draw_wedge_no_hardcoded_width():
    """draw_wedge must use self.width / self.height; verify 8x8 ≠ 16x16 pixel counts."""
    COLOR = (100, 100, 100)
    m8  = _make_matrix(8, 8)
    m16 = _make_matrix(16, 16)

    m8.draw_wedge(0, COLOR)
    m16.draw_wedge(0, COLOR)

    count_8  = len(_lit_pixels(m8))
    count_16 = len(_lit_pixels(m16))

    # 16x16 should produce significantly more lit pixels than 8x8
    assert count_16 > count_8, (
        "16x16 draw_wedge should light more pixels than 8x8 (scales with matrix size)"
    )


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
