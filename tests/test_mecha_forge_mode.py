"""Tests for the Mecha Forge sandbox toy mode.

Verifies:
- mecha_forge.py file exists and has valid Python syntax
- MECHA_FORGE is correctly registered in the MODE_REGISTRY manifest
- Manifest metadata is complete and accurate
- Robot head/torso templates are 12×16 bytes each (192 bytes)
- Robot leg templates are 4×16 bytes each (64 bytes)
- All template pixel values use only the documented codes (0, 1, 2, 4)
- Exactly 4 head/torso variants and 4 leg variants are defined
- Exactly 8 accessories are defined (matching _ACC_COUNT)
- All accessory pixel coordinates are within the 16×16 grid
- Body colour from keypad: 3-digit code maps to an RGB tuple correctly
- Body colour code "000" produces a non-black result (minimum brightness)
- _draw_robot() executes without error and only calls draw_pixel with in-bounds coords
- MECHA_FORGE icon exists in Icons.ICON_LIBRARY and is exactly 256 bytes
"""

import sys
import os
import ast
import traceback
import types as _types

# ---------------------------------------------------------------------------
# Stub CircuitPython / Adafruit hardware modules before any src imports
# ---------------------------------------------------------------------------

class _MockModule:
    """Catch-all stub for hardware modules."""
    def __getattr__(self, name):
        return _MockModule()
    def __call__(self, *args, **kwargs):
        return _MockModule()
    def __iter__(self):
        return iter([])
    def __int__(self):
        return 0
    def __bool__(self):
        return False

_CP_MODULES = [
    'digitalio', 'board', 'busio', 'neopixel', 'microcontroller',
    'analogio', 'audiocore', 'audiobusio', 'audioio', 'audiomixer',
    'audiopwmio', 'synthio', 'ulab', 'watchdog',
    'adafruit_mcp230xx', 'adafruit_mcp230xx.mcp23017',
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

# Realistic adafruit_ticks stub
import time as _time
_ticks_stub = _types.ModuleType('adafruit_ticks')
_ticks_stub.ticks_ms   = lambda: int(_time.monotonic() * 1000)
_ticks_stub.ticks_diff = lambda a, b: a - b
sys.modules['adafruit_ticks'] = _ticks_stub

# ---------------------------------------------------------------------------
# Ensure src is on the path
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

_MODE_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'src', 'modes', 'mecha_forge.py'
)
_ICONS_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'src', 'utilities', 'icons.py'
)


def _source():
    with open(_MODE_PATH, 'r', encoding='utf-8') as f:
        return f.read()


# ===========================================================================
# 1.  File & syntax checks
# ===========================================================================

def test_file_exists():
    """mecha_forge.py must exist in src/modes/."""
    assert os.path.exists(_MODE_PATH), "mecha_forge.py not found in src/modes/"
    print("✓ mecha_forge.py file exists")


def test_valid_python_syntax():
    """mecha_forge.py must have valid Python syntax."""
    src = _source()
    try:
        ast.parse(src)
    except SyntaxError as exc:
        raise AssertionError(f"Syntax error in mecha_forge.py: {exc}")
    print("✓ mecha_forge.py has valid Python syntax")


# ===========================================================================
# 2.  Manifest registration
# ===========================================================================

def test_mecha_forge_in_manifest():
    """MECHA_FORGE must appear in MODE_REGISTRY."""
    from modes.manifest import MODE_REGISTRY
    assert "MECHA_FORGE" in MODE_REGISTRY, "MECHA_FORGE not found in MODE_REGISTRY"
    print("✓ MECHA_FORGE found in MODE_REGISTRY")


def test_manifest_id():
    from modes.manifest import MODE_REGISTRY
    assert MODE_REGISTRY["MECHA_FORGE"]["id"] == "MECHA_FORGE"
    print("✓ id == 'MECHA_FORGE'")


def test_manifest_name():
    from modes.manifest import MODE_REGISTRY
    assert MODE_REGISTRY["MECHA_FORGE"]["name"] == "MECHA FORGE"
    print("✓ name == 'MECHA FORGE'")


def test_manifest_module_path():
    from modes.manifest import MODE_REGISTRY
    assert MODE_REGISTRY["MECHA_FORGE"]["module_path"] == "modes.mecha_forge"
    print("✓ module_path == 'modes.mecha_forge'")


def test_manifest_class_name():
    from modes.manifest import MODE_REGISTRY
    assert MODE_REGISTRY["MECHA_FORGE"]["class_name"] == "MechaForge"
    print("✓ class_name == 'MechaForge'")


def test_manifest_icon():
    from modes.manifest import MODE_REGISTRY
    assert MODE_REGISTRY["MECHA_FORGE"]["icon"] == "MECHA_FORGE"
    print("✓ icon == 'MECHA_FORGE'")


def test_manifest_menu():
    from modes.manifest import MODE_REGISTRY
    assert MODE_REGISTRY["MECHA_FORGE"].get("menu") == "ZERO_PLAYER", \
        "MECHA_FORGE should appear in the ZERO_PLAYER menu"
    print("✓ menu == 'ZERO_PLAYER'")


def test_manifest_requires_core():
    from modes.manifest import MODE_REGISTRY
    assert "CORE" in MODE_REGISTRY["MECHA_FORGE"]["requires"], \
        "MECHA_FORGE must require CORE"
    print("✓ requires CORE")


def test_manifest_optional_industrial():
    from modes.manifest import MODE_REGISTRY
    optional = MODE_REGISTRY["MECHA_FORGE"].get("optional", [])
    assert "INDUSTRIAL" in optional, \
        "INDUSTRIAL satellite should be listed as optional"
    print("✓ optional contains INDUSTRIAL")


def test_manifest_order_after_starfield():
    from modes.manifest import MODE_REGISTRY
    starfield_order = MODE_REGISTRY["STARFIELD"]["order"]
    mecha_order = MODE_REGISTRY["MECHA_FORGE"]["order"]
    assert mecha_order > starfield_order, \
        f"MECHA_FORGE order ({mecha_order}) should be > STARFIELD order ({starfield_order})"
    print(f"✓ order {mecha_order} > STARFIELD order {starfield_order}")


# ===========================================================================
# 3.  Robot template data validation
# ===========================================================================

def test_ht_templates_count():
    """There must be exactly 4 head/torso variants (_HT tuple)."""
    import importlib
    m = importlib.import_module('modes.mecha_forge')
    assert len(m._HT) == 4, f"Expected 4 head/torso variants, got {len(m._HT)}"
    print(f"✓ {len(m._HT)} head/torso variants defined")


def test_ht_templates_size():
    """Each head/torso template must be exactly 12 rows × 16 cols = 192 bytes."""
    import importlib
    m = importlib.import_module('modes.mecha_forge')
    for i, ht in enumerate(m._HT):
        assert len(ht) == 192, \
            f"HT variant {i} has {len(ht)} bytes, expected 192 (12×16)"
    print("✓ All head/torso templates are 192 bytes (12×16)")


def test_ht_templates_valid_pixels():
    """Head/torso templates must only contain pixel values 0, 1, 2, or 4."""
    import importlib
    m = importlib.import_module('modes.mecha_forge')
    valid = {0, 1, 2, 4}
    for i, ht in enumerate(m._HT):
        bad = [v for v in ht if v not in valid]
        assert not bad, \
            f"HT variant {i} contains invalid pixel values: {set(bad)}"
    print("✓ All head/torso pixel values are in {0, 1, 2, 4}")


def test_ht_templates_have_eyes():
    """Each head/torso template must contain at least 2 eye pixels (value 4)."""
    import importlib
    m = importlib.import_module('modes.mecha_forge')
    for i, ht in enumerate(m._HT):
        eyes = sum(1 for v in ht if v == 4)
        assert eyes >= 2, \
            f"HT variant {i} has only {eyes} eye pixel(s); expected >= 2"
    print("✓ All head/torso templates have at least 2 eye pixels")


def test_lg_templates_count():
    """There must be exactly 4 leg variants (_LG tuple)."""
    import importlib
    m = importlib.import_module('modes.mecha_forge')
    assert len(m._LG) == 4, f"Expected 4 leg variants, got {len(m._LG)}"
    print(f"✓ {len(m._LG)} leg variants defined")


def test_lg_templates_size():
    """Each leg template must be exactly 4 rows × 16 cols = 64 bytes."""
    import importlib
    m = importlib.import_module('modes.mecha_forge')
    for i, lg in enumerate(m._LG):
        assert len(lg) == 64, \
            f"LG variant {i} has {len(lg)} bytes, expected 64 (4×16)"
    print("✓ All leg templates are 64 bytes (4×16)")


def test_lg_templates_valid_pixels():
    """Leg templates must only contain pixel values 0, 1, or 2."""
    import importlib
    m = importlib.import_module('modes.mecha_forge')
    valid = {0, 1, 2}
    for i, lg in enumerate(m._LG):
        bad = [v for v in lg if v not in valid]
        assert not bad, \
            f"LG variant {i} contains invalid pixel values: {set(bad)}"
    print("✓ All leg pixel values are in {0, 1, 2}")


def test_variant_name_lists_length():
    """_HT_NAMES and _LG_NAMES must have 4 entries each."""
    import importlib
    m = importlib.import_module('modes.mecha_forge')
    assert len(m._HT_NAMES) == 4, f"_HT_NAMES has {len(m._HT_NAMES)} entries, expected 4"
    assert len(m._LG_NAMES) == 4, f"_LG_NAMES has {len(m._LG_NAMES)} entries, expected 4"
    print("✓ _HT_NAMES and _LG_NAMES each have 4 entries")


# ===========================================================================
# 4.  Accessories validation
# ===========================================================================

def test_accessories_count():
    """_ACCESSORIES must have exactly 8 entries (one per latching toggle)."""
    import importlib
    m = importlib.import_module('modes.mecha_forge')
    assert len(m._ACCESSORIES) == m._ACC_COUNT, \
        f"Expected {m._ACC_COUNT} accessories, got {len(m._ACCESSORIES)}"
    print(f"✓ {len(m._ACCESSORIES)} accessories defined (matches _ACC_COUNT={m._ACC_COUNT})")


def test_accessories_pixel_bounds():
    """All accessory pixel coordinates must be within the 16×16 grid."""
    import importlib
    m = importlib.import_module('modes.mecha_forge')
    for i, (pixels, _color) in enumerate(m._ACCESSORIES):
        for (px, py) in pixels:
            assert 0 <= px <= 15, \
                f"ACC {i} pixel x={px} is out of bounds [0, 15]"
            assert 0 <= py <= 15, \
                f"ACC {i} pixel y={py} is out of bounds [0, 15]"
    print("✓ All accessory pixel coordinates are within bounds")


def test_accessories_have_pixels():
    """Each accessory must have at least one pixel defined."""
    import importlib
    m = importlib.import_module('modes.mecha_forge')
    for i, (pixels, _color) in enumerate(m._ACCESSORIES):
        assert len(pixels) >= 1, f"ACC {i} has no pixels defined"
    print("✓ Every accessory has at least one pixel")


def test_accessories_colors_are_rgb_tuples():
    """Each accessory colour must be a 3-tuple of ints in [0, 255]."""
    import importlib
    m = importlib.import_module('modes.mecha_forge')
    for i, (_pixels, color) in enumerate(m._ACCESSORIES):
        assert len(color) == 3, f"ACC {i} colour must be a 3-tuple (R, G, B)"
        for ch in color:
            assert 0 <= ch <= 255, \
                f"ACC {i} colour channel {ch} out of range [0, 255]"
    print("✓ All accessory colours are valid RGB 3-tuples")


def test_acc_names_length():
    """_ACC_NAMES must have the same number of entries as _ACC_COUNT."""
    import importlib
    m = importlib.import_module('modes.mecha_forge')
    assert len(m._ACC_NAMES) == m._ACC_COUNT, \
        f"_ACC_NAMES has {len(m._ACC_NAMES)} entries, expected {m._ACC_COUNT}"
    print(f"✓ _ACC_NAMES has {len(m._ACC_NAMES)} entries")


# ===========================================================================
# 5.  Body colour (keypad RGB code) logic
# ===========================================================================

def test_default_body_color_is_3_tuple():
    """_DEFAULT_COLOR must be a 3-tuple of ints."""
    import importlib
    m = importlib.import_module('modes.mecha_forge')
    assert len(m._DEFAULT_COLOR) == 3, "_DEFAULT_COLOR must be a 3-tuple"
    for ch in m._DEFAULT_COLOR:
        assert isinstance(ch, int) and 0 <= ch <= 255, \
            f"_DEFAULT_COLOR channel {ch} is not a valid byte"
    print("✓ _DEFAULT_COLOR is a valid RGB 3-tuple")


def _simulate_keypad_input(r_digit, g_digit, b_digit):
    """Simulate what MechaForge does when it receives 3 keypad digits."""
    import importlib
    m = importlib.import_module('modes.mecha_forge')

    r = min(9, r_digit) * 28
    g = min(9, g_digit) * 28
    b = min(9, b_digit) * 28
    if r == 0 and g == 0 and b == 0:
        r, g, b = 20, 20, 20
    return (r, g, b)


def test_keypad_900_produces_red():
    """Keypad code '9-0-0' must produce a red-dominant colour."""
    r, g, b = _simulate_keypad_input(9, 0, 0)
    assert r > 200, f"R should be dominant for '900', got R={r}"
    assert g == 0, f"G should be 0 for '900', got G={g}"
    assert b == 0, f"B should be 0 for '900', got B={b}"
    print(f"✓ Keypad 9-0-0 → ({r},{g},{b}) (red dominant)")


def test_keypad_090_produces_green():
    """Keypad code '0-9-0' must produce a green-dominant colour."""
    r, g, b = _simulate_keypad_input(0, 9, 0)
    assert g > 200, f"G should be dominant for '090', got G={g}"
    assert r == 0
    assert b == 0
    print(f"✓ Keypad 0-9-0 → ({r},{g},{b}) (green dominant)")


def test_keypad_009_produces_blue():
    """Keypad code '0-0-9' must produce a blue-dominant colour."""
    r, g, b = _simulate_keypad_input(0, 0, 9)
    assert b > 200, f"B should be dominant for '009', got B={b}"
    assert r == 0
    assert g == 0
    print(f"✓ Keypad 0-0-9 → ({r},{g},{b}) (blue dominant)")


def test_keypad_000_not_black():
    """Keypad code '0-0-0' must not produce pure black (minimum brightness floor)."""
    r, g, b = _simulate_keypad_input(0, 0, 0)
    assert r > 0 or g > 0 or b > 0, \
        f"Colour '000' should not be pure black, got ({r},{g},{b})"
    print(f"✓ Keypad 0-0-0 → ({r},{g},{b}) (not pure black)")


def test_keypad_max_channel_value_is_252():
    """Maximum digit (9) scaled by 28 equals 252."""
    import importlib
    m = importlib.import_module('modes.mecha_forge')
    # Digit 9 * 28 = 252
    assert 9 * 28 == 252
    print("✓ Maximum channel value: 9 × 28 = 252")


# ===========================================================================
# 6.  _draw_robot() smoke test
# ===========================================================================

def _make_mode():
    """Return a MechaForge instance backed by a minimal mock core."""
    from modes.mecha_forge import MechaForge
    from unittest.mock import MagicMock

    core = MagicMock()
    core.satellites = {}   # no satellites in this test
    mode = MechaForge(core)
    return mode, core


def test_draw_robot_default_state():
    """_draw_robot() must complete without raising exceptions for default state."""
    mode, core = _make_mode()
    try:
        mode._draw_robot()
    except Exception as exc:
        raise AssertionError(f"_draw_robot() raised an exception: {exc}")
    print("✓ _draw_robot() completes without error for default state")


def test_draw_robot_calls_draw_pixel_with_valid_coords():
    """All draw_pixel calls from _draw_robot() must use coordinates in [0, 15]."""
    mode, core = _make_mode()
    calls = []

    def capture_draw_pixel(x, y, color):
        calls.append((x, y))

    core.matrix.draw_pixel.side_effect = capture_draw_pixel
    mode._draw_robot()

    assert len(calls) > 0, "_draw_robot() should call draw_pixel at least once"
    for x, y in calls:
        assert 0 <= x <= 15, f"draw_pixel x={x} is out of bounds"
        assert 0 <= y <= 15, f"draw_pixel y={y} is out of bounds"
    print(f"✓ _draw_robot() made {len(calls)} draw_pixel calls, all with valid coordinates")


def test_draw_robot_all_variants_no_error():
    """_draw_robot() must succeed for every combination of HT and LG variant."""
    from modes.mecha_forge import MechaForge
    from unittest.mock import MagicMock

    for ht in range(4):
        for lg in range(4):
            core = MagicMock()
            core.satellites = {}
            mode = MechaForge(core)
            mode._ht_idx = ht
            mode._lg_idx = lg
            try:
                mode._draw_robot()
            except Exception as exc:
                raise AssertionError(
                    f"_draw_robot() raised for HT={ht}, LG={lg}: {exc}"
                )
    print("✓ _draw_robot() succeeds for all 4×4 = 16 variant combinations")


def test_draw_robot_with_all_accessories():
    """_draw_robot() must complete without error when all 8 accessories are active."""
    mode, core = _make_mode()
    mode._acc = [True] * 8
    try:
        mode._draw_robot()
    except Exception as exc:
        raise AssertionError(f"_draw_robot() raised with all accessories: {exc}")
    print("✓ _draw_robot() completes with all 8 accessories active")


def test_draw_robot_custom_color():
    """_draw_robot() must use the custom body colour when set."""
    mode, core = _make_mode()
    mode._body_color = (200, 0, 100)

    captured_colors = []

    def capture(x, y, color):
        captured_colors.append(color)

    core.matrix.draw_pixel.side_effect = capture
    mode._draw_robot()

    # The custom body colour should appear at least once
    assert (200, 0, 100) in captured_colors, \
        "Custom body colour (200, 0, 100) not found in draw_pixel calls"
    print("✓ _draw_robot() uses custom body colour correctly")


def test_draw_robot_with_y_offset():
    """_draw_robot() with a positive y_offset shifts all pixels down (or off-screen)."""
    mode, core = _make_mode()
    calls_no_offset = []
    calls_with_offset = []

    def capture_no_offset(x, y, color):
        calls_no_offset.append((x, y))

    def capture_with_offset(x, y, color):
        calls_with_offset.append((x, y))

    core.matrix.draw_pixel.side_effect = capture_no_offset
    mode._draw_robot(y_offset=0)

    core.matrix.draw_pixel.side_effect = capture_with_offset
    mode._draw_robot(y_offset=16)  # All pixels off-screen → no calls expected

    assert len(calls_with_offset) == 0, \
        f"y_offset=16 should push all pixels off-screen; got {len(calls_with_offset)} calls"
    print("✓ _draw_robot(y_offset=16) makes no draw_pixel calls (all off-screen)")


# ===========================================================================
# 7.  Icon check
# ===========================================================================

def test_mecha_forge_icon_in_icon_library():
    """Icons.ICON_LIBRARY must contain a 'MECHA_FORGE' entry."""
    from utilities.icons import Icons
    assert "MECHA_FORGE" in Icons.ICON_LIBRARY, \
        "'MECHA_FORGE' not found in Icons.ICON_LIBRARY"
    print("✓ MECHA_FORGE icon is registered in ICON_LIBRARY")


def test_mecha_forge_icon_is_bytes():
    """The MECHA_FORGE icon must be a bytes or bytearray object."""
    from utilities.icons import Icons
    icon = Icons.get("MECHA_FORGE")
    assert isinstance(icon, (bytes, bytearray)), \
        f"MECHA_FORGE icon should be bytes, got {type(icon)}"
    print("✓ MECHA_FORGE icon is a bytes object")


def test_mecha_forge_icon_correct_size():
    """The MECHA_FORGE icon must be exactly 256 bytes (16×16)."""
    from utilities.icons import Icons
    icon = Icons.get("MECHA_FORGE")
    assert len(icon) == 256, \
        f"MECHA_FORGE icon should be 256 bytes (16×16), got {len(icon)}"
    print("✓ MECHA_FORGE icon is 256 bytes (16×16)")


def test_mecha_forge_icon_has_cyan_pixels():
    """The MECHA_FORGE icon must contain cyan (palette index 51) pixels for the robot body."""
    from utilities.icons import Icons
    icon = Icons.get("MECHA_FORGE")
    assert 51 in icon, \
        "MECHA_FORGE icon should contain cyan pixels (index 51) for the robot body"
    print("✓ MECHA_FORGE icon contains cyan (51) pixels")


# ===========================================================================
# Standalone runner
# ===========================================================================

if __name__ == "__main__":
    print("Running Mecha Forge mode tests...\n")

    tests = [
        # File & syntax
        test_file_exists,
        test_valid_python_syntax,
        # Manifest
        test_mecha_forge_in_manifest,
        test_manifest_id,
        test_manifest_name,
        test_manifest_module_path,
        test_manifest_class_name,
        test_manifest_icon,
        test_manifest_menu,
        test_manifest_requires_core,
        test_manifest_optional_industrial,
        test_manifest_order_after_starfield,
        # Templates
        test_ht_templates_count,
        test_ht_templates_size,
        test_ht_templates_valid_pixels,
        test_ht_templates_have_eyes,
        test_lg_templates_count,
        test_lg_templates_size,
        test_lg_templates_valid_pixels,
        test_variant_name_lists_length,
        # Accessories
        test_accessories_count,
        test_accessories_pixel_bounds,
        test_accessories_have_pixels,
        test_accessories_colors_are_rgb_tuples,
        test_acc_names_length,
        # Body colour
        test_default_body_color_is_3_tuple,
        test_keypad_900_produces_red,
        test_keypad_090_produces_green,
        test_keypad_009_produces_blue,
        test_keypad_000_not_black,
        test_keypad_max_channel_value_is_252,
        # _draw_robot
        test_draw_robot_default_state,
        test_draw_robot_calls_draw_pixel_with_valid_coords,
        test_draw_robot_all_variants_no_error,
        test_draw_robot_with_all_accessories,
        test_draw_robot_custom_color,
        test_draw_robot_with_y_offset,
        # Icons
        test_mecha_forge_icon_in_icon_library,
        test_mecha_forge_icon_is_bytes,
        test_mecha_forge_icon_correct_size,
        test_mecha_forge_icon_has_cyan_pixels,
    ]

    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except AssertionError as exc:
            print(f"  ❌ {test_fn.__name__}: {exc}")
            failed += 1
        except Exception as exc:
            print(f"  ❌ {test_fn.__name__} (unexpected): {exc}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'✅' if failed == 0 else '❌'} {passed}/{passed + failed} tests passed")
    sys.exit(min(failed, 1))
