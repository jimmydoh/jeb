"""Tests for Boids Flocking Simulation.

Verifies:
- BoidsMode._reset() creates the correct number of boids with valid positions/velocities
- BoidsMode._step() applies separation, alignment, and cohesion rules
- BoidsMode._step() enforces speed limits (min/max)
- BoidsMode._step() applies soft-boundary avoidance
- BoidsMode._step() increments the tick counter
- BoidsMode._build_frame() renders boid positions into the palette buffer
- manifest.py contains a valid BOIDS entry under ZERO_PLAYER
- icons.py exposes a BOIDS icon that is 256 bytes
"""

import sys
import os
import math
import traceback

# ---------------------------------------------------------------------------
# Mock CircuitPython / Adafruit hardware modules BEFORE importing src code
# ---------------------------------------------------------------------------

class _MockModule:
    """Catch-all stub that satisfies attribute access and call syntax."""
    def __getattr__(self, name):
        return _MockModule()

    def __call__(self, *args, **kwargs):
        return _MockModule()

    def __iter__(self):
        return iter([])

    def __int__(self):
        return 0


_CP_MODULES = [
    'digitalio', 'board', 'busio', 'neopixel', 'microcontroller',
    'analogio', 'audiocore', 'audiobusio', 'audioio', 'audiomixer',
    'audiopwmio', 'synthio', 'ulab', 'watchdog',
    'adafruit_mcp230xx', 'adafruit_mcp230xx.mcp23017',
    'adafruit_ticks',
    'adafruit_displayio_ssd1306',
    'adafruit_display_text', 'adafruit_display_text.label',
    'adafruit_ht16k33', 'adafruit_ht16k33.segments',
    'adafruit_httpserver', 'adafruit_bus_device', 'adafruit_register',
    'sdcardio', 'storage', 'displayio', 'terminalio',
    'adafruit_framebuf', 'framebufferio', 'rgbmatrix', 'supervisor',
]

for _mod in _CP_MODULES:
    if _mod not in sys.modules:
        sys.modules[_mod] = _MockModule()

# Provide a realistic adafruit_ticks so ticks_ms / ticks_diff work
import types as _types
_ticks_mod = _types.ModuleType('adafruit_ticks')
_ticks_mod.ticks_ms = lambda: 0
_ticks_mod.ticks_diff = lambda a, b: a - b
sys.modules['adafruit_ticks'] = _ticks_mod

# ---------------------------------------------------------------------------
# Add src to path
# ---------------------------------------------------------------------------

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# ===========================================================================
# Helpers – lightweight mocks used by multiple tests
# ===========================================================================

def _make_boids(width=16, height=16):
    """Return a BoidsMode instance with buffers initialised."""
    from modes.boids import BoidsMode, _BOID_COUNT
    from unittest.mock import MagicMock

    fake_core = MagicMock()
    boids = BoidsMode(fake_core)
    boids.width = width
    boids.height = height
    boids._frame = bytearray(width * height)
    boids._reset()
    return boids


# ===========================================================================
# 1. _reset() – initial state
# ===========================================================================

def test_reset_creates_correct_boid_count():
    """_reset() creates exactly _BOID_COUNT boids."""
    from modes.boids import _BOID_COUNT
    b = _make_boids()
    assert len(b._boids) == _BOID_COUNT, \
        f"Expected {_BOID_COUNT} boids, got {len(b._boids)}"
    print(f"✓ _reset: creates {_BOID_COUNT} boids")


def test_reset_boids_within_bounds():
    """All boids start within the matrix bounds after _reset()."""
    b = _make_boids(16, 16)
    for i, boid in enumerate(b._boids):
        x, y = boid[0], boid[1]
        assert 0.0 <= x < 16.0, f"Boid {i} x={x} out of bounds"
        assert 0.0 <= y < 16.0, f"Boid {i} y={y} out of bounds"
    print("✓ _reset: all boids within matrix bounds")


def test_reset_boids_have_valid_velocities():
    """All boids start with speed between MIN_SPEED and MAX_SPEED."""
    from modes.boids import _MIN_SPEED, _MAX_SPEED
    b = _make_boids()
    for i, boid in enumerate(b._boids):
        vx, vy = boid[2], boid[3]
        speed = math.sqrt(vx * vx + vy * vy)
        assert speed >= _MIN_SPEED * 0.99, \
            f"Boid {i} speed {speed:.4f} below MIN_SPEED {_MIN_SPEED}"
        assert speed <= _MAX_SPEED * 1.01, \
            f"Boid {i} speed {speed:.4f} above MAX_SPEED {_MAX_SPEED}"
    print("✓ _reset: all boids have valid initial speeds")


def test_reset_clears_tick_counter():
    """_reset() resets the tick counter to zero."""
    b = _make_boids()
    b._tick = 42
    b._reset()
    assert b._tick == 0, f"Expected tick=0 after reset, got {b._tick}"
    print("✓ _reset: tick counter cleared to 0")


# ===========================================================================
# 2. _step() – tick counter
# ===========================================================================

def test_step_increments_tick():
    """Each call to _step() increments _tick by 1."""
    b = _make_boids()
    assert b._tick == 0
    b._step()
    assert b._tick == 1
    b._step()
    assert b._tick == 2
    print("✓ _step: tick counter increments correctly")


# ===========================================================================
# 3. _step() – speed limits
# ===========================================================================

def test_step_enforces_max_speed():
    """After _step(), no boid exceeds MAX_SPEED."""
    from modes.boids import _MAX_SPEED
    b = _make_boids()
    # Give all boids an excessive velocity
    for boid in b._boids:
        boid[2] = _MAX_SPEED * 10.0
        boid[3] = _MAX_SPEED * 10.0
    b._step()
    for i, boid in enumerate(b._boids):
        vx, vy = boid[2], boid[3]
        speed = math.sqrt(vx * vx + vy * vy)
        assert speed <= _MAX_SPEED * 1.01, \
            f"Boid {i} speed {speed:.4f} exceeds MAX_SPEED {_MAX_SPEED}"
    print("✓ _step: max speed enforced")


def test_step_enforces_min_speed():
    """After _step(), no boid is slower than MIN_SPEED (unless stopped)."""
    from modes.boids import _MIN_SPEED
    b = _make_boids()
    # Set all boids to very low velocity (non-zero to avoid random nudge path)
    for boid in b._boids:
        boid[2] = 0.001
        boid[3] = 0.001
    b._step()
    for i, boid in enumerate(b._boids):
        vx, vy = boid[2], boid[3]
        speed = math.sqrt(vx * vx + vy * vy)
        assert speed >= _MIN_SPEED * 0.99, \
            f"Boid {i} speed {speed:.4f} below MIN_SPEED {_MIN_SPEED}"
    print("✓ _step: min speed enforced")


def test_step_positions_stay_within_bounds():
    """After multiple _step() calls, all boid positions stay in [0, width/height)."""
    b = _make_boids(16, 16)
    for _ in range(20):
        b._step()
    for i, boid in enumerate(b._boids):
        x, y = boid[0], boid[1]
        assert 0.0 <= x < 16.0, f"Boid {i} x={x:.4f} out of bounds after steps"
        assert 0.0 <= y < 16.0, f"Boid {i} y={y:.4f} out of bounds after steps"
    print("✓ _step: positions stay within bounds after 20 steps")


# ===========================================================================
# 4. _step() – boundary avoidance
# ===========================================================================

def test_step_boundary_turns_boid_away_from_left_edge():
    """A boid near the left edge gains positive vx (turns right)."""
    from modes.boids import _MARGIN, _TURN_FACTOR
    b = _make_boids(16, 16)
    # Place a single boid near the left edge with leftward velocity
    b._boids = [[0.5, 8.0, -0.5, 0.0]]
    vx_before = b._boids[0][2]
    b._step()
    vx_after = b._boids[0][2]
    assert vx_after > vx_before, \
        f"Boid near left edge should gain positive vx; was {vx_before:.4f}, now {vx_after:.4f}"
    print("✓ _step: boundary avoidance turns boid away from left edge")


def test_step_boundary_turns_boid_away_from_right_edge():
    """A boid near the right edge gains negative vx (turns left)."""
    from modes.boids import _MARGIN, _TURN_FACTOR
    b = _make_boids(16, 16)
    b._boids = [[14.5, 8.0, 0.5, 0.0]]
    vx_before = b._boids[0][2]
    b._step()
    vx_after = b._boids[0][2]
    assert vx_after < vx_before, \
        f"Boid near right edge should gain negative vx; was {vx_before:.4f}, now {vx_after:.4f}"
    print("✓ _step: boundary avoidance turns boid away from right edge")


# ===========================================================================
# 5. _step() – separation rule
# ===========================================================================

def test_step_separation_pushes_boids_apart():
    """Two boids that are too close should have their relative velocity increase."""
    from modes.boids import _SEPARATION_DIST
    b = _make_boids(16, 16)
    # Place exactly two boids very close together, both moving in the same direction
    b._boids = [
        [8.0, 8.0, 0.5, 0.0],
        [8.5, 8.0, 0.5, 0.0],   # distance = 0.5, well within SEPARATION_DIST
    ]
    b._step()
    # After separation, boid 0 should move left and boid 1 should move right
    vx0 = b._boids[0][2]
    vx1 = b._boids[1][2]
    assert vx0 < vx1, \
        f"Separation should push boids apart: vx0={vx0:.4f} should be < vx1={vx1:.4f}"
    print("✓ _step: separation pushes close boids apart")


# ===========================================================================
# 6. _step() – cohesion rule
# ===========================================================================

def test_step_cohesion_reduces_separation_over_time():
    """Cohesion should reduce the distance between boids with the same heading."""
    from modes.boids import _VISUAL_RANGE
    # Use a large grid to avoid edge interference.
    b = _make_boids(32, 32)
    b._frame = bytearray(32 * 32)
    # Two boids within visual range, moving in the same direction.
    # Cohesion should gradually pull them closer together.
    b._boids = [
        [10.0, 16.0, 0.3, 0.0],   # left boid
        [13.0, 16.0, 0.3, 0.0],   # right boid – distance 3.0 < VISUAL_RANGE
    ]
    initial_dist = abs(b._boids[1][0] - b._boids[0][0])
    for _ in range(30):
        b._step()
    final_dist = abs(b._boids[1][0] - b._boids[0][0])
    assert final_dist < initial_dist, \
        f"Cohesion should reduce separation; initial={initial_dist:.3f}, final={final_dist:.3f}"
    print(f"✓ _step: cohesion reduces boid separation ({initial_dist:.3f} → {final_dist:.3f})")


# ===========================================================================
# 7. _build_frame() – rendering
# ===========================================================================

def test_build_frame_marks_boid_positions():
    """_build_frame() sets pixels at boid positions to the current colour."""
    from modes.boids import _BOID_COLOR_INDICES
    b = _make_boids(8, 8)
    b._frame = bytearray(64)
    b._color_idx = 0
    expected_color = _BOID_COLOR_INDICES[0]

    # Override boids with known positions
    b._boids = [[2.0, 3.0, 0.0, 0.0], [5.0, 6.0, 0.0, 0.0]]
    b._build_frame()

    assert b._frame[3 * 8 + 2] == expected_color, \
        f"Pixel (2,3) should be {expected_color}, got {b._frame[3*8+2]}"
    assert b._frame[6 * 8 + 5] == expected_color, \
        f"Pixel (5,6) should be {expected_color}, got {b._frame[6*8+5]}"
    print("✓ _build_frame: boid pixels set to correct colour")


def test_build_frame_clears_background():
    """_build_frame() sets all non-boid pixels to 0 (black)."""
    from modes.boids import _BOID_COUNT
    b = _make_boids(8, 8)
    b._frame = bytearray(64)
    # Pre-fill frame with non-zero values
    for i in range(64):
        b._frame[i] = 99

    # Place all boids at a single pixel to make it easy to check others
    b._boids = [[4.0, 4.0, 0.0, 0.0]] * _BOID_COUNT
    b._build_frame()

    for idx in range(64):
        if idx != 4 * 8 + 4:
            assert b._frame[idx] == 0, \
                f"Background pixel {idx} should be 0, got {b._frame[idx]}"
    print("✓ _build_frame: background pixels cleared to 0")


def test_build_frame_uses_current_color_index():
    """_build_frame() uses _BOID_COLOR_INDICES[_color_idx] for the boid colour."""
    from modes.boids import _BOID_COLOR_INDICES
    b = _make_boids(8, 8)
    b._frame = bytearray(64)
    b._boids = [[3.0, 3.0, 0.0, 0.0]]

    for idx in range(len(_BOID_COLOR_INDICES)):
        b._color_idx = idx
        b._build_frame()
        pixel = b._frame[3 * 8 + 3]
        assert pixel == _BOID_COLOR_INDICES[idx], \
            f"color_idx={idx}: expected {_BOID_COLOR_INDICES[idx]}, got {pixel}"
    print("✓ _build_frame: respects _color_idx for all colour options")


# ===========================================================================
# 8. manifest.py – BOIDS registration
# ===========================================================================

def test_manifest_boids_entry_exists():
    """manifest.py contains a BOIDS entry."""
    from modes.manifest import MODE_REGISTRY
    assert "BOIDS" in MODE_REGISTRY, "BOIDS not found in MODE_REGISTRY"
    print("✓ manifest: BOIDS entry exists")


def test_manifest_boids_required_fields():
    """The BOIDS manifest entry has all required fields."""
    from modes.manifest import MODE_REGISTRY
    entry = MODE_REGISTRY["BOIDS"]
    for field in ("id", "name", "module_path", "class_name", "icon", "menu", "requires"):
        assert field in entry, f"BOIDS manifest entry missing field '{field}'"
    print("✓ manifest: BOIDS entry has all required fields")


def test_manifest_boids_in_zero_player_menu():
    """The BOIDS entry is in the ZERO_PLAYER menu."""
    from modes.manifest import MODE_REGISTRY
    assert MODE_REGISTRY["BOIDS"]["menu"] == "ZERO_PLAYER", \
        "BOIDS should be in the ZERO_PLAYER menu"
    print("✓ manifest: BOIDS is in the ZERO_PLAYER menu")


def test_manifest_boids_class_importable():
    """The BoidsMode class can be imported via the manifest's module_path."""
    from modes.manifest import MODE_REGISTRY
    import importlib
    entry = MODE_REGISTRY["BOIDS"]
    mod = importlib.import_module(entry["module_path"])
    cls = getattr(mod, entry["class_name"])
    assert cls is not None
    print(f"✓ manifest: {entry['class_name']} importable from {entry['module_path']}")


# ===========================================================================
# 9. icons.py – BOIDS icon
# ===========================================================================

def test_icons_boids_exists():
    """icons.py exposes a BOIDS icon."""
    from utilities.icons import Icons
    assert "BOIDS" in Icons.ICON_LIBRARY, "BOIDS not found in Icons.ICON_LIBRARY"
    print("✓ icons: BOIDS icon registered in ICON_LIBRARY")


def test_icons_boids_correct_size():
    """The BOIDS icon is exactly 256 bytes (16x16)."""
    from utilities.icons import Icons
    icon = Icons.ICON_LIBRARY["BOIDS"]
    assert len(icon) == 256, f"BOIDS icon should be 256 bytes, got {len(icon)}"
    print("✓ icons: BOIDS icon is 256 bytes")


def test_icons_boids_has_boid_pixels():
    """The BOIDS icon contains at least one non-zero (boid) pixel."""
    from utilities.icons import Icons
    icon = Icons.ICON_LIBRARY["BOIDS"]
    non_zero = sum(1 for b in icon if b != 0)
    assert non_zero > 0, "BOIDS icon should have at least one non-zero pixel"
    print(f"✓ icons: BOIDS icon has {non_zero} non-zero pixels")


def test_icons_get_boids():
    """Icons.get('BOIDS') returns the BOIDS icon data."""
    from utilities.icons import Icons
    icon = Icons.get("BOIDS")
    assert icon is not None, "Icons.get('BOIDS') returned None"
    assert len(icon) == 256, f"Returned icon should be 256 bytes, got {len(icon)}"
    print("✓ icons: Icons.get('BOIDS') works correctly")


# ===========================================================================
# 10. _status_line() helper
# ===========================================================================

def test_status_line_returns_two_strings():
    """_status_line() returns a tuple of two non-empty strings."""
    b = _make_boids()
    line1, line2 = b._status_line()
    assert isinstance(line1, str) and len(line1) > 0
    assert isinstance(line2, str) and len(line2) > 0
    print("✓ _status_line: returns two non-empty strings")


def test_status_line_reflects_speed_index():
    """_status_line() reflects the current speed setting."""
    from modes.boids import _SPEED_NAMES, _SPEED_LEVELS_MS
    b = _make_boids()
    for idx in range(len(_SPEED_NAMES)):
        b._speed_idx = idx
        line1, _ = b._status_line()
        assert _SPEED_NAMES[idx] in line1, \
            f"speed_idx={idx}: expected '{_SPEED_NAMES[idx]}' in '{line1}'"
    print("✓ _status_line: correctly reflects all speed settings")


# ===========================================================================
# Runner
# ===========================================================================

def run_all_tests():
    tests = [
        test_reset_creates_correct_boid_count,
        test_reset_boids_within_bounds,
        test_reset_boids_have_valid_velocities,
        test_reset_clears_tick_counter,
        test_step_increments_tick,
        test_step_enforces_max_speed,
        test_step_enforces_min_speed,
        test_step_positions_stay_within_bounds,
        test_step_boundary_turns_boid_away_from_left_edge,
        test_step_boundary_turns_boid_away_from_right_edge,
        test_step_separation_pushes_boids_apart,
        test_step_cohesion_reduces_separation_over_time,
        test_build_frame_marks_boid_positions,
        test_build_frame_clears_background,
        test_build_frame_uses_current_color_index,
        test_manifest_boids_entry_exists,
        test_manifest_boids_required_fields,
        test_manifest_boids_in_zero_player_menu,
        test_manifest_boids_class_importable,
        test_icons_boids_exists,
        test_icons_boids_correct_size,
        test_icons_boids_has_boid_pixels,
        test_icons_get_boids,
        test_status_line_returns_two_strings,
        test_status_line_reflects_speed_index,
    ]

    print("=" * 60)
    print("Running Boids Tests")
    print("=" * 60)

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"\n✗ {test.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"\n✗ {test.__name__} ERROR: {e}")
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
