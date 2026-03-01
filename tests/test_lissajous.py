"""Tests for Lissajous Curve Generator feature.

Verifies:
- LissajousMode._fade_buf() decays the phosphor buffer correctly
- LissajousMode._plot() distributes brightness across sub-pixel neighbours
- LissajousMode._clear_buf() zeros all cells
- manifest.py contains a valid LISSAJOUS entry in the ZERO_PLAYER submenu
- icons.py exposes a LISSAJOUS icon with the expected 16×16 = 256-byte size
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

def _make_lissajous(width=16, height=16):
    """Return a LissajousMode instance with its buffer initialised."""
    from modes.lissajous import LissajousMode
    from unittest.mock import MagicMock

    fake_core = MagicMock()
    mode = LissajousMode(fake_core)
    mode.width = width
    mode.height = height
    size = width * height
    mode._buf = [[0.0, 0.0, 0.0] for _ in range(size)]
    return mode


# ===========================================================================
# 1. _clear_buf
# ===========================================================================

def test_clear_buf_zeros_all_cells():
    """_clear_buf() sets every cell to [0, 0, 0]."""
    mode = _make_lissajous()
    # Dirty every cell
    for cell in mode._buf:
        cell[0] = 200.0
        cell[1] = 150.0
        cell[2] = 100.0
    mode._clear_buf()
    for i, cell in enumerate(mode._buf):
        assert cell == [0.0, 0.0, 0.0], \
            f"Cell {i} should be [0,0,0] after clear, got {cell}"
    print("✓ _clear_buf: all cells zeroed")


# ===========================================================================
# 2. _fade_buf
# ===========================================================================

def test_fade_buf_reduces_brightness():
    """_fade_buf() multiplies every cell component by _FADE."""
    from modes.lissajous import _FADE
    mode = _make_lissajous(4, 4)
    for cell in mode._buf:
        cell[0] = 200.0
        cell[1] = 100.0
        cell[2] = 50.0
    mode._fade_buf()
    for i, cell in enumerate(mode._buf):
        assert abs(cell[0] - 200.0 * _FADE) < 0.001, \
            f"Cell {i} R should be {200.0 * _FADE}, got {cell[0]}"
        assert abs(cell[1] - 100.0 * _FADE) < 0.001, \
            f"Cell {i} G should be {100.0 * _FADE}, got {cell[1]}"
        assert abs(cell[2] -  50.0 * _FADE) < 0.001, \
            f"Cell {i} B should be {50.0 * _FADE}, got {cell[2]}"
    print(f"✓ _fade_buf: all cells decayed by _FADE={_FADE}")


def test_fade_buf_repeated_decays_to_zero():
    """Applying _fade_buf() many times drives values toward zero."""
    mode = _make_lissajous(2, 2)
    for cell in mode._buf:
        cell[0] = 255.0
    for _ in range(200):
        mode._fade_buf()
    for i, cell in enumerate(mode._buf):
        assert cell[0] < 1.0, \
            f"Cell {i} R should be near 0 after many fades, got {cell[0]}"
    print("✓ _fade_buf: repeated application converges to zero")


def test_fade_buf_does_not_go_negative():
    """_fade_buf() never produces negative component values."""
    mode = _make_lissajous(4, 4)
    # Start with small positive values
    for cell in mode._buf:
        cell[0] = 0.001
    for _ in range(50):
        mode._fade_buf()
    for i, cell in enumerate(mode._buf):
        assert cell[0] >= 0.0, \
            f"Cell {i} R should not go negative, got {cell[0]}"
    print("✓ _fade_buf: values never go negative")


# ===========================================================================
# 3. _plot (sub-pixel anti-aliasing)
# ===========================================================================

def test_plot_exact_integer_position_lights_one_pixel():
    """_plot at an exact integer (x, y) adds full brightness to that single cell."""
    mode = _make_lissajous(8, 8)
    mode._plot(3.0, 4.0, 255.0, 128.0, 64.0)
    cell = mode._buf[4 * 8 + 3]
    assert abs(cell[0] - 255.0) < 0.001, \
        f"Exact-position R should be 255, got {cell[0]}"
    assert abs(cell[1] - 128.0) < 0.001, \
        f"Exact-position G should be 128, got {cell[1]}"
    assert abs(cell[2] -  64.0) < 0.001, \
        f"Exact-position B should be 64, got {cell[2]}"
    # No brightness should spill to neighbours
    assert mode._buf[4 * 8 + 4][0] < 0.001, "Right neighbour should be unlit"
    assert mode._buf[5 * 8 + 3][0] < 0.001, "Bottom neighbour should be unlit"
    print("✓ _plot: exact integer position lights one pixel at full brightness")


def test_plot_half_position_splits_brightness_evenly():
    """_plot at (x+0.5, y+0.5) distributes brightness equally across 4 neighbours."""
    mode = _make_lissajous(8, 8)
    mode._plot(3.5, 4.5, 100.0, 0.0, 0.0)
    cells = [
        mode._buf[4 * 8 + 3],  # (3, 4)
        mode._buf[4 * 8 + 4],  # (4, 4)
        mode._buf[5 * 8 + 3],  # (3, 5)
        mode._buf[5 * 8 + 4],  # (4, 5)
    ]
    for i, cell in enumerate(cells):
        assert abs(cell[0] - 25.0) < 0.1, \
            f"Quarter-cell {i} R should be 25, got {cell[0]}"
    print("✓ _plot: mid-position distributes brightness equally to 4 neighbours")


def test_plot_clamps_at_255():
    """_plot does not allow any cell component to exceed 255."""
    mode = _make_lissajous(4, 4)
    # Pre-fill with 254
    for cell in mode._buf:
        cell[0] = 254.0
    # Add a bright dot at an integer position
    mode._plot(2.0, 2.0, 255.0, 0.0, 0.0)
    assert mode._buf[2 * 4 + 2][0] <= 255.0, \
        f"Cell R should be clamped to 255, got {mode._buf[2*4+2][0]}"
    print("✓ _plot: component clamped at 255")


def test_plot_out_of_bounds_does_not_raise():
    """_plot with coordinates outside the grid is silently ignored."""
    mode = _make_lissajous(8, 8)
    try:
        mode._plot(-1.0, -1.0, 255.0, 0.0, 0.0)
        mode._plot(7.8, 7.8, 255.0, 0.0, 0.0)  # ix0+1 = 8 would be out of bounds
        mode._plot(100.0, 100.0, 255.0, 0.0, 0.0)
    except Exception as exc:
        raise AssertionError(f"_plot raised unexpectedly: {exc}")
    print("✓ _plot: out-of-bounds coordinates are silently ignored")


def test_plot_brightness_sum_equals_full_value():
    """Total brightness deposited by _plot equals the input brightness (within bounds)."""
    mode = _make_lissajous(8, 8)
    # Use a fractional position entirely within the grid
    fx, fy = 3.3, 4.7
    mode._plot(fx, fy, 100.0, 0.0, 0.0)
    total = sum(cell[0] for cell in mode._buf)
    assert abs(total - 100.0) < 0.1, \
        f"Total deposited brightness should be 100, got {total}"
    print("✓ _plot: total deposited brightness equals input value")


# ===========================================================================
# 4. Manifest entry
# ===========================================================================

def test_lissajous_in_manifest():
    """LISSAJOUS entry exists in MODE_REGISTRY with all required fields."""
    from modes.manifest import MODE_REGISTRY

    assert "LISSAJOUS" in MODE_REGISTRY, \
        "LISSAJOUS not found in MODE_REGISTRY"
    meta = MODE_REGISTRY["LISSAJOUS"]

    required_fields = ["id", "name", "module_path", "class_name", "icon", "menu", "requires", "settings"]
    for field in required_fields:
        assert field in meta, \
            f"LISSAJOUS manifest entry missing required field '{field}'"

    assert meta["id"] == "LISSAJOUS"
    assert meta["module_path"] == "modes.lissajous", \
        "LISSAJOUS module_path should be 'modes.lissajous'"
    assert meta["class_name"] == "LissajousMode", \
        "LISSAJOUS class_name should be 'LissajousMode'"
    assert meta["menu"] == "ZERO_PLAYER", \
        "LISSAJOUS should belong to the ZERO_PLAYER submenu"
    assert meta["icon"] == "LISSAJOUS", \
        "LISSAJOUS should reference the LISSAJOUS icon"
    assert "CORE" in meta["requires"], \
        "LISSAJOUS should require CORE"
    print("✓ manifest: LISSAJOUS entry is complete and correct")


# ===========================================================================
# 5. Icon entry
# ===========================================================================

def test_lissajous_icon_in_icons():
    """icons.py exposes a LISSAJOUS icon that is a non-empty bytes object."""
    from utilities.icons import Icons

    icon = Icons.get("LISSAJOUS")
    assert icon is not None, "Icons library should contain a LISSAJOUS icon"
    assert isinstance(icon, (bytes, bytearray)), \
        "LISSAJOUS icon should be bytes or bytearray"
    assert len(icon) > 0, "LISSAJOUS icon should not be empty"
    print(f"✓ icons: LISSAJOUS icon present ({len(icon)} bytes)")


def test_lissajous_icon_correct_size():
    """LISSAJOUS icon has the expected 16×16 = 256-byte size."""
    from utilities.icons import Icons

    icon = Icons.get("LISSAJOUS")
    assert len(icon) == 256, \
        f"LISSAJOUS icon should be 256 bytes (16×16), got {len(icon)}"
    print("✓ icons: LISSAJOUS icon is 256 bytes (16×16)")


# ===========================================================================
# 6. ZERO_PLAYER menu now includes LISSAJOUS
# ===========================================================================

def test_zero_player_modes_include_lissajous():
    """LISSAJOUS is registered under the ZERO_PLAYER submenu."""
    from modes.manifest import MODE_REGISTRY

    zero_player_modes = {k: v for k, v in MODE_REGISTRY.items()
                         if v.get("menu") == "ZERO_PLAYER"}
    assert "LISSAJOUS" in zero_player_modes, \
        "LISSAJOUS should appear in the ZERO_PLAYER submenu"
    print(f"✓ manifest: LISSAJOUS is present in ZERO_PLAYER submenu "
          f"(total {len(zero_player_modes)} modes)")


# ===========================================================================
# 7. Module importability
# ===========================================================================

def test_lissajous_module_is_importable():
    """modes.lissajous can be imported and LissajousMode class is accessible."""
    from modes.lissajous import LissajousMode
    assert LissajousMode is not None, "LissajousMode class should be importable"
    print("✓ modes.lissajous: module importable, LissajousMode class accessible")


def test_lissajous_inherits_from_base_mode():
    """LissajousMode inherits from BaseMode."""
    from modes.lissajous import LissajousMode
    from modes.base import BaseMode
    assert issubclass(LissajousMode, BaseMode), \
        "LissajousMode should inherit from BaseMode"
    print("✓ LissajousMode inherits from BaseMode")


def test_lissajous_constants_are_valid():
    """Key module constants have sensible values."""
    from modes.lissajous import _RATIOS, _RATIO_NAMES, _PHASE_SPEEDS_MS, _PHASE_SPEED_NAMES, _FADE, _PLOT_STEPS

    assert len(_RATIOS) == len(_RATIO_NAMES), \
        "_RATIOS and _RATIO_NAMES must have the same length"
    assert len(_PHASE_SPEEDS_MS) == len(_PHASE_SPEED_NAMES), \
        "_PHASE_SPEEDS_MS and _PHASE_SPEED_NAMES must have the same length"
    assert 0.0 < _FADE < 1.0, \
        f"_FADE should be in (0, 1), got {_FADE}"
    assert _PLOT_STEPS > 0, \
        f"_PLOT_STEPS should be positive, got {_PLOT_STEPS}"
    for a, b in _RATIOS:
        assert a > 0 and b > 0, f"Ratio ({a},{b}) contains non-positive value"
    print(f"✓ constants: {len(_RATIOS)} ratios, {len(_PHASE_SPEEDS_MS)} speeds, "
          f"fade={_FADE}, plot_steps={_PLOT_STEPS}")


# ===========================================================================
# Standalone runner
# ===========================================================================

if __name__ == "__main__":
    print("Running Lissajous Curve Generator feature tests...\n")

    tests = [
        # _clear_buf
        test_clear_buf_zeros_all_cells,
        # _fade_buf
        test_fade_buf_reduces_brightness,
        test_fade_buf_repeated_decays_to_zero,
        test_fade_buf_does_not_go_negative,
        # _plot
        test_plot_exact_integer_position_lights_one_pixel,
        test_plot_half_position_splits_brightness_evenly,
        test_plot_clamps_at_255,
        test_plot_out_of_bounds_does_not_raise,
        test_plot_brightness_sum_equals_full_value,
        # manifest
        test_lissajous_in_manifest,
        # icons
        test_lissajous_icon_in_icons,
        test_lissajous_icon_correct_size,
        # menu
        test_zero_player_modes_include_lissajous,
        # module
        test_lissajous_module_is_importable,
        test_lissajous_inherits_from_base_mode,
        test_lissajous_constants_are_valid,
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
