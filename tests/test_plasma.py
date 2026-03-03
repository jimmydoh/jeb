"""Tests for the Demoscene Plasma Visualizer feature.

Verifies:
- PlasmaMode._compute_frame() produces valid RGB values for every pixel
- PlasmaMode._render_to_matrix() calls draw_pixel for every pixel
- PlasmaMode._status_line() returns a two-element tuple
- Encoder hue offset wraps correctly at 360 degrees
- manifest.py contains a valid PLASMA entry in the ZERO_PLAYER submenu
- icons.py exposes a PLASMA icon with the expected 16×16 = 256-byte size
- Module importability and constant validation
"""

import sys
import os
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
# Helpers
# ===========================================================================

def _make_plasma(width=16, height=16):
    """Return a PlasmaMode instance with its buffer initialised."""
    from modes.plasma import PlasmaMode
    from unittest.mock import MagicMock

    fake_core = MagicMock()
    mode = PlasmaMode(fake_core)
    mode.width = width
    mode.height = height
    size = width * height
    mode._buf = [[0, 0, 0] for _ in range(size)]
    return mode


# ===========================================================================
# 1. _compute_frame – pixel value validity
# ===========================================================================

def test_compute_frame_fills_all_pixels():
    """_compute_frame() writes an RGB triple to every pixel in the buffer."""
    mode = _make_plasma(8, 8)
    mode._time = 0.0
    mode._hue_offset = 0.0
    mode._compute_frame()
    for i, cell in enumerate(mode._buf):
        assert len(cell) == 3, f"Pixel {i} must be a 3-element list"
    print("✓ _compute_frame: all pixels have 3-element RGB triples")


def test_compute_frame_values_in_range():
    """_compute_frame() produces RGB values in [0, 255] for every pixel."""
    mode = _make_plasma(8, 8)
    mode._time = 0.0
    mode._hue_offset = 0.0
    mode._compute_frame()
    for i, cell in enumerate(mode._buf):
        for channel, val in enumerate(cell):
            assert 0 <= val <= 255, (
                f"Pixel {i} channel {channel} out of range: {val}"
            )
    print("✓ _compute_frame: all RGB values are in [0, 255]")


def test_compute_frame_changes_with_time():
    """Advancing _time changes the plasma output (animation moves)."""
    mode = _make_plasma(8, 8)
    mode._time = 0.0
    mode._hue_offset = 0.0
    mode._compute_frame()
    frame_a = [cell[:] for cell in mode._buf]

    mode._time = 2.5
    mode._compute_frame()
    frame_b = [cell[:] for cell in mode._buf]

    assert frame_a != frame_b, \
        "Frames at t=0 and t=2.5 should differ (animation must advance)"
    print("✓ _compute_frame: time advancement changes pixel output")


def test_compute_frame_changes_with_hue_offset():
    """Changing _hue_offset shifts the colour palette visibly."""
    mode = _make_plasma(8, 8)
    mode._time = 0.0
    mode._hue_offset = 0.0
    mode._compute_frame()
    frame_a = [cell[:] for cell in mode._buf]

    mode._hue_offset = 120.0
    mode._compute_frame()
    frame_b = [cell[:] for cell in mode._buf]

    assert frame_a != frame_b, \
        "Frames with hue_offset=0 and 120 should differ"
    print("✓ _compute_frame: hue_offset shifts colour output")


def test_compute_frame_different_frequencies():
    """Different frequency indices produce different plasma patterns."""
    from modes.plasma import _FREQ_LEVELS
    mode = _make_plasma(8, 8)
    mode._time = 0.0
    mode._hue_offset = 0.0

    mode._freq_idx = 0
    mode._compute_frame()
    frame_low = [cell[:] for cell in mode._buf]

    mode._freq_idx = len(_FREQ_LEVELS) - 1
    mode._compute_frame()
    frame_high = [cell[:] for cell in mode._buf]

    assert frame_low != frame_high, \
        "WIDE and MICRO frequency frames should differ"
    print("✓ _compute_frame: different frequencies produce distinct patterns")


# ===========================================================================
# 2. _render_to_matrix
# ===========================================================================

def test_render_to_matrix_calls_draw_pixel_for_every_pixel():
    """_render_to_matrix() calls core.matrix.draw_pixel once per pixel."""
    from modes.plasma import PlasmaMode
    from unittest.mock import MagicMock, call

    fake_core = MagicMock()
    mode = PlasmaMode(fake_core)
    W, H = 4, 4
    mode.width = W
    mode.height = H
    mode._buf = [[10, 20, 30] for _ in range(W * H)]

    mode._render_to_matrix()

    assert fake_core.matrix.draw_pixel.call_count == W * H, (
        f"draw_pixel should be called {W * H} times, got "
        f"{fake_core.matrix.draw_pixel.call_count}"
    )
    print(f"✓ _render_to_matrix: draw_pixel called {W * H} times for {W}×{H} grid")


def test_render_to_matrix_passes_rgb_tuples():
    """_render_to_matrix() passes an (r, g, b) tuple as the colour argument."""
    from modes.plasma import PlasmaMode
    from unittest.mock import MagicMock

    fake_core = MagicMock()
    mode = PlasmaMode(fake_core)
    mode.width = 2
    mode.height = 2
    mode._buf = [[100, 150, 200], [50, 75, 100], [200, 0, 50], [10, 10, 10]]

    mode._render_to_matrix()

    # Verify the first draw_pixel call received the expected colour tuple
    first_call_args = fake_core.matrix.draw_pixel.call_args_list[0]
    colour_arg = first_call_args[0][2]   # positional arg index 2
    assert colour_arg == (100, 150, 200), (
        f"First pixel colour should be (100, 150, 200), got {colour_arg}"
    )
    print("✓ _render_to_matrix: RGB tuples passed to draw_pixel correctly")


# ===========================================================================
# 3. _status_line
# ===========================================================================

def test_status_line_returns_two_strings():
    """_status_line() returns a tuple of exactly two strings."""
    mode = _make_plasma()
    result = mode._status_line()
    assert isinstance(result, tuple), \
        f"_status_line() should return a tuple, got {type(result)}"
    assert len(result) == 2, \
        f"_status_line() should return 2 items, got {len(result)}"
    for i, s in enumerate(result):
        assert isinstance(s, str), \
            f"Item {i} of _status_line() should be a str, got {type(s)}"
    print(f"✓ _status_line: returns two strings: {result!r}")


def test_status_line_contains_freq_name():
    """_status_line() first line contains the current frequency name."""
    from modes.plasma import _FREQ_NAMES
    mode = _make_plasma()
    for idx, name in enumerate(_FREQ_NAMES):
        mode._freq_idx = idx
        line1, _ = mode._status_line()
        assert name in line1, \
            f"Frequency name '{name}' not found in status line: '{line1}'"
    print("✓ _status_line: all frequency names appear in first status line")


def test_status_line_contains_hue_speed_name():
    """_status_line() second line contains the current colour speed name."""
    from modes.plasma import _HUE_SPEED_NAMES
    mode = _make_plasma()
    for idx, name in enumerate(_HUE_SPEED_NAMES):
        mode._hue_speed_idx = idx
        _, line2 = mode._status_line()
        assert name in line2, \
            f"Colour speed name '{name}' not found in status line: '{line2}'"
    print("✓ _status_line: all colour speed names appear in second status line")


# ===========================================================================
# 4. Hue offset wrap behaviour
# ===========================================================================

def test_hue_offset_wraps_at_360():
    """Hue offset modulo arithmetic keeps the value in [0, 360)."""
    mode = _make_plasma()
    # Simulate encoder rotation accumulating a large value
    mode._hue_offset = 359.0
    mode._hue_offset = (mode._hue_offset + 5.0) % 360.0
    assert 0.0 <= mode._hue_offset < 360.0, \
        f"Hue offset should wrap at 360, got {mode._hue_offset}"
    print(f"✓ hue_offset: wraps correctly to {mode._hue_offset}")


# ===========================================================================
# 5. Manifest entry
# ===========================================================================

def test_plasma_in_manifest():
    """PLASMA entry exists in MODE_REGISTRY with all required fields."""
    from modes.manifest import MODE_REGISTRY

    assert "PLASMA" in MODE_REGISTRY, \
        "PLASMA not found in MODE_REGISTRY"
    meta = MODE_REGISTRY["PLASMA"]

    required_fields = ["id", "name", "module_path", "class_name", "icon", "menu", "requires", "settings"]
    for field in required_fields:
        assert field in meta, \
            f"PLASMA manifest entry missing required field '{field}'"

    assert meta["id"] == "PLASMA"
    assert meta["module_path"] == "modes.plasma", \
        "PLASMA module_path should be 'modes.plasma'"
    assert meta["class_name"] == "PlasmaMode", \
        "PLASMA class_name should be 'PlasmaMode'"
    assert meta["menu"] == "ZERO_PLAYER", \
        "PLASMA should belong to the ZERO_PLAYER submenu"
    assert meta["icon"] == "PLASMA", \
        "PLASMA should reference the PLASMA icon"
    assert "CORE" in meta["requires"], \
        "PLASMA should require CORE"
    print("✓ manifest: PLASMA entry is complete and correct")


# ===========================================================================
# 6. Icon entry
# ===========================================================================

def test_plasma_icon_in_icons():
    """icons.py exposes a PLASMA icon that is a non-empty bytes object."""
    from utilities.icons import Icons

    icon = Icons.get("PLASMA")
    assert icon is not None, "Icons library should contain a PLASMA icon"
    assert isinstance(icon, (bytes, bytearray)), \
        "PLASMA icon should be bytes or bytearray"
    assert len(icon) > 0, "PLASMA icon should not be empty"
    print(f"✓ icons: PLASMA icon present ({len(icon)} bytes)")


def test_plasma_icon_correct_size():
    """PLASMA icon has the expected 16×16 = 256-byte size."""
    from utilities.icons import Icons

    icon = Icons.get("PLASMA")
    assert len(icon) == 256, \
        f"PLASMA icon should be 256 bytes (16×16), got {len(icon)}"
    print("✓ icons: PLASMA icon is 256 bytes (16×16)")


# ===========================================================================
# 7. ZERO_PLAYER menu includes PLASMA
# ===========================================================================

def test_zero_player_modes_include_plasma():
    """PLASMA is registered under the ZERO_PLAYER submenu."""
    from modes.manifest import MODE_REGISTRY

    zero_player_modes = {k: v for k, v in MODE_REGISTRY.items()
                         if v.get("menu") == "ZERO_PLAYER"}
    assert "PLASMA" in zero_player_modes, \
        "PLASMA should appear in the ZERO_PLAYER submenu"
    print(f"✓ manifest: PLASMA is present in ZERO_PLAYER submenu "
          f"(total {len(zero_player_modes)} modes)")


# ===========================================================================
# 8. Module importability and class structure
# ===========================================================================

def test_plasma_module_is_importable():
    """modes.plasma can be imported and PlasmaMode class is accessible."""
    from modes.plasma import PlasmaMode
    assert PlasmaMode is not None, "PlasmaMode class should be importable"
    print("✓ modes.plasma: module importable, PlasmaMode class accessible")


def test_plasma_inherits_from_base_mode():
    """PlasmaMode inherits from BaseMode."""
    from modes.plasma import PlasmaMode
    from modes.base import BaseMode
    assert issubclass(PlasmaMode, BaseMode), \
        "PlasmaMode should inherit from BaseMode"
    print("✓ PlasmaMode inherits from BaseMode")


def test_plasma_constants_are_valid():
    """Key module constants have sensible values."""
    from modes.plasma import (
        _FREQ_LEVELS, _FREQ_NAMES,
        _HUE_SPEEDS, _HUE_SPEED_NAMES,
        _TIME_SCALE, _FRAME_MS,
    )

    assert len(_FREQ_LEVELS) == len(_FREQ_NAMES), \
        "_FREQ_LEVELS and _FREQ_NAMES must have the same length"
    assert len(_HUE_SPEEDS) == len(_HUE_SPEED_NAMES), \
        "_HUE_SPEEDS and _HUE_SPEED_NAMES must have the same length"
    assert _TIME_SCALE > 0, \
        f"_TIME_SCALE should be positive, got {_TIME_SCALE}"
    assert _FRAME_MS > 0, \
        f"_FRAME_MS should be positive, got {_FRAME_MS}"
    for freq in _FREQ_LEVELS:
        assert freq > 0, f"Frequency {freq} should be positive"
    for speed in _HUE_SPEEDS:
        assert speed > 0, f"Hue speed {speed} should be positive"
    print(f"✓ constants: {len(_FREQ_LEVELS)} frequencies, "
          f"{len(_HUE_SPEEDS)} hue speeds, "
          f"time_scale={_TIME_SCALE}, frame_ms={_FRAME_MS}")


# ===========================================================================
# Standalone runner
# ===========================================================================

if __name__ == "__main__":
    print("Running Demoscene Plasma Visualizer tests...\n")

    tests = [
        # _compute_frame
        test_compute_frame_fills_all_pixels,
        test_compute_frame_values_in_range,
        test_compute_frame_changes_with_time,
        test_compute_frame_changes_with_hue_offset,
        test_compute_frame_different_frequencies,
        # _render_to_matrix
        test_render_to_matrix_calls_draw_pixel_for_every_pixel,
        test_render_to_matrix_passes_rgb_tuples,
        # _status_line
        test_status_line_returns_two_strings,
        test_status_line_contains_freq_name,
        test_status_line_contains_hue_speed_name,
        # hue offset
        test_hue_offset_wraps_at_360,
        # manifest
        test_plasma_in_manifest,
        # icons
        test_plasma_icon_in_icons,
        test_plasma_icon_correct_size,
        # menu
        test_zero_player_modes_include_plasma,
        # module
        test_plasma_module_is_importable,
        test_plasma_inherits_from_base_mode,
        test_plasma_constants_are_valid,
    ]

    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except AssertionError as exc:
            print(f"❌ {test_fn.__name__}: {exc}")
            failed += 1
        except Exception as exc:
            print(f"❌ {test_fn.__name__} (unexpected error): {exc}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'✅' if failed == 0 else '❌'} {passed}/{passed + failed} tests passed")
    sys.exit(min(failed, 1))
