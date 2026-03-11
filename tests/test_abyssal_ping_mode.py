"""Test module for AbyssalPing game mode.

Validates:
- Mode file existence and valid Python syntax
- Manifest registration with correct metadata
- Absence of a METADATA class attribute (centralized in manifest.py)
- Icon presence and size in icons.py and ICON_LIBRARY
- Phase identifier constants
- Hardware index constants (_TOGGLE_COUNT, _SW_ARM, _BTN_FIRE)
- Difficulty parameter table (_DIFF_PARAMS)
- Drift and lock-threshold scaling per difficulty
- Phase method signatures
- Dual-encoder usage in the Hunt phase
- Arm + button requirement in the Execute phase
- _spawn_submarine helper
- Global timer and bonus time constants
"""

import sys
import os
import ast
import re

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

_MODE_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'src', 'modes', 'abyssal_ping.py'
)
_ICONS_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'src', 'utilities', 'icons.py'
)

# ---------------------------------------------------------------------------
# Stub CircuitPython-specific modules before any src imports
# ---------------------------------------------------------------------------
from unittest.mock import MagicMock

_MOCK_MOD_NAMES = [
    'digitalio', 'busio', 'board', 'adafruit_mcp230xx',
    'adafruit_mcp230xx.mcp23017', 'adafruit_ticks', 'audiobusio',
    'audiocore', 'audiomixer', 'analogio', 'microcontroller', 'watchdog',
    'audiopwmio', 'synthio', 'ulab', 'neopixel',
    'adafruit_displayio_ssd1306', 'adafruit_display_text',
    'adafruit_display_text.label', 'adafruit_ht16k33',
    'adafruit_ht16k33.segments', 'displayio', 'terminalio',
]
for _mod in _MOCK_MOD_NAMES:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# Provide ticks_ms / ticks_diff stubs
import time as _time
sys.modules['adafruit_ticks'].ticks_ms = lambda: int(_time.monotonic() * 1000)
sys.modules['adafruit_ticks'].ticks_diff = lambda a, b: a - b


def _source():
    with open(_MODE_PATH, 'r') as f:
        return f.read()


# ---------------------------------------------------------------------------
# File and syntax checks
# ---------------------------------------------------------------------------

def test_abyssal_ping_file_exists():
    """abyssal_ping.py must exist in src/modes/."""
    assert os.path.exists(_MODE_PATH), "abyssal_ping.py does not exist"
    print("✓ abyssal_ping.py exists")


def test_abyssal_ping_valid_syntax():
    """abyssal_ping.py must have valid Python syntax."""
    src = _source()
    try:
        ast.parse(src)
    except SyntaxError as e:
        raise AssertionError(f"Syntax error in abyssal_ping.py: {e}")
    print("✓ Valid Python syntax")


# ---------------------------------------------------------------------------
# Manifest checks
# ---------------------------------------------------------------------------

def test_abyssal_ping_in_manifest():
    """ABYSSAL_PING must be registered in MODE_REGISTRY."""
    from modes.manifest import MODE_REGISTRY
    assert "ABYSSAL_PING" in MODE_REGISTRY, "ABYSSAL_PING not found in MODE_REGISTRY"
    print("✓ ABYSSAL_PING found in MODE_REGISTRY")


def test_abyssal_ping_manifest_metadata():
    """ABYSSAL_PING manifest entry must have all required fields."""
    from modes.manifest import MODE_REGISTRY
    meta = MODE_REGISTRY["ABYSSAL_PING"]

    assert meta["id"]          == "ABYSSAL_PING"
    assert meta["name"]        == "ABYSSAL PING"
    assert meta["module_path"] == "modes.abyssal_ping"
    assert meta["class_name"]  == "AbyssalPing"
    assert meta["icon"]        == "ABYSSAL_PING"
    assert "CORE"       in meta["requires"], "Must require CORE"
    assert "INDUSTRIAL" in meta["requires"], "Must require INDUSTRIAL satellite"
    assert meta.get("menu") == "EXP1", "Should appear in EXP1 menu"
    print("✓ ABYSSAL_PING manifest metadata is correct")


def test_abyssal_ping_manifest_settings():
    """ABYSSAL_PING must have a difficulty setting with NORMAL, HARD, INSANE."""
    from modes.manifest import MODE_REGISTRY
    meta     = MODE_REGISTRY["ABYSSAL_PING"]
    settings = meta.get("settings", [])

    diff = next((s for s in settings if s["key"] == "difficulty"), None)
    assert diff is not None, "Missing 'difficulty' setting"
    assert diff["label"] == "DIFF"
    assert "NORMAL" in diff["options"]
    assert "HARD"   in diff["options"]
    assert "INSANE" in diff["options"]
    assert diff["default"] == "NORMAL"
    print("✓ ABYSSAL_PING difficulty settings are correct")


def test_abyssal_ping_no_metadata_in_class():
    """AbyssalPing must NOT define a METADATA class attribute (use manifest.py)."""
    from modes.abyssal_ping import AbyssalPing
    assert not hasattr(AbyssalPing, 'METADATA'), (
        "AbyssalPing should not define METADATA; it is centralized in manifest.py"
    )
    print("✓ No METADATA class attribute")


# ---------------------------------------------------------------------------
# Icon checks
# ---------------------------------------------------------------------------

def test_abyssal_ping_icon_in_icons_py():
    """ABYSSAL_PING icon must be defined in icons.py."""
    with open(_ICONS_PATH, 'r', encoding='utf-8') as f:
        src = f.read()
    assert "ABYSSAL_PING" in src, "ABYSSAL_PING icon not in icons.py"
    print("✓ ABYSSAL_PING icon defined in icons.py")


def test_abyssal_ping_icon_in_icon_library():
    """ABYSSAL_PING must be registered in the ICON_LIBRARY dict."""
    with open(_ICONS_PATH, 'r', encoding='utf-8') as f:
        src = f.read()
    lib_start     = src.find("ICON_LIBRARY")
    lib_end        = src.find("}", lib_start)
    library_block  = src[lib_start:lib_end]
    assert '"ABYSSAL_PING"' in library_block, \
        "ABYSSAL_PING not in ICON_LIBRARY dict"
    print("✓ ABYSSAL_PING registered in ICON_LIBRARY")


def test_abyssal_ping_icon_is_256_bytes():
    """ABYSSAL_PING icon must be exactly 256 bytes (16×16)."""
    with open(_ICONS_PATH, 'r', encoding='utf-8') as f:
        src = f.read()

    match = re.search(r'ABYSSAL_PING\s*=\s*bytes\(\[(.*?)\]\)', src, re.DOTALL)
    assert match is not None, "Could not find ABYSSAL_PING bytes literal in icons.py"

    raw_content = match.group(1).replace('\n', ',')
    tokens      = [t.strip() for t in raw_content.split(',')]
    values      = [t for t in tokens if t.isdigit()]
    assert len(values) == 256, \
        f"ABYSSAL_PING icon should be 256 bytes (16×16), got {len(values)}"
    print(f"✓ ABYSSAL_PING icon is 256 bytes (16×16)")


def test_abyssal_ping_icon_registered_in_library_class():
    """ABYSSAL_PING must be retrievable via Icons.ICON_LIBRARY."""
    from utilities.icons import Icons
    assert "ABYSSAL_PING" in Icons.ICON_LIBRARY, \
        "ABYSSAL_PING not in Icons.ICON_LIBRARY"
    assert len(Icons.ICON_LIBRARY["ABYSSAL_PING"]) == 256, \
        "ABYSSAL_PING icon is not 256 bytes"
    print("✓ ABYSSAL_PING retrievable from Icons.ICON_LIBRARY with correct size")


# ---------------------------------------------------------------------------
# Phase identifier checks
# ---------------------------------------------------------------------------

def test_phase_identifiers():
    """_PHASE_HUNT, _PHASE_PAYLOAD, and _PHASE_EXECUTE must be defined."""
    src = _source()
    for phase in ["_PHASE_HUNT", "_PHASE_PAYLOAD", "_PHASE_EXECUTE"]:
        assert phase in src, f"Phase constant {phase} missing"
    print("✓ All 3 phase identifiers defined")


# ---------------------------------------------------------------------------
# Hardware index checks
# ---------------------------------------------------------------------------

def test_hardware_indices():
    """_TOGGLE_COUNT, _SW_ARM, and _BTN_FIRE must be defined."""
    src = _source()
    for const in ["_TOGGLE_COUNT", "_SW_ARM", "_BTN_FIRE", "_ENC_SAT", "_ENC_CORE"]:
        assert const in src, f"Hardware constant {const} missing"
    print("✓ Hardware index constants are defined")


def test_toggle_count_is_eight():
    """_TOGGLE_COUNT must equal 8."""
    src   = _source()
    match = re.search(r'_TOGGLE_COUNT\s*=\s*(\d+)', src)
    assert match is not None, "_TOGGLE_COUNT not found"
    assert int(match.group(1)) == 8, \
        f"_TOGGLE_COUNT should be 8, got {match.group(1)}"
    print("✓ _TOGGLE_COUNT is 8")


def test_sw_arm_index_is_eight():
    """_SW_ARM must equal 8 (guarded toggle index per sat-01 hardware spec)."""
    src   = _source()
    match = re.search(r'_SW_ARM\s*=\s*(\d+)', src)
    assert match is not None, "_SW_ARM not found"
    assert int(match.group(1)) == 8, \
        f"_SW_ARM should be 8, got {match.group(1)}"
    print("✓ _SW_ARM index is 8")


# ---------------------------------------------------------------------------
# Difficulty parameter checks
# ---------------------------------------------------------------------------

def test_diff_params_defines_all_difficulties():
    """_DIFF_PARAMS must define NORMAL, HARD, and INSANE."""
    src = _source()
    assert "_DIFF_PARAMS" in src, "_DIFF_PARAMS dict missing"
    for diff in ["NORMAL", "HARD", "INSANE"]:
        assert diff in src, f"Difficulty '{diff}' not defined in _DIFF_PARAMS"
    print("✓ _DIFF_PARAMS defines NORMAL, HARD, INSANE")


def test_drift_enabled_for_hard_insane():
    """HARD and INSANE must have drift=True; NORMAL must have drift=False."""
    src = _source()
    start = src.find("_DIFF_PARAMS")
    end   = src.find("\n}", start) + 2
    block = src[start:end]

    normal_start = block.find('"NORMAL"')
    hard_start   = block.find('"HARD"')
    insane_start = block.find('"INSANE"')

    assert normal_start != -1 and hard_start != -1 and insane_start != -1

    normal_block = block[normal_start:hard_start]
    hard_block   = block[hard_start:insane_start]
    insane_block = block[insane_start:]

    assert '"drift": False' in normal_block, \
        "NORMAL should have drift=False"
    assert '"drift": True' in hard_block, \
        "HARD should have drift=True"
    assert '"drift": True' in insane_block, \
        "INSANE should have drift=True"
    print("✓ Drift disabled for NORMAL, enabled for HARD and INSANE")


def test_lock_threshold_stricter_on_hard():
    """HARD / INSANE lock_threshold must be >= NORMAL lock_threshold."""
    src = _source()

    normal_match = re.search(r'_LOCK_THRESHOLD_NORMAL\s*=\s*([\d.]+)', src)
    hard_match   = re.search(r'_LOCK_THRESHOLD_HARD\s*=\s*([\d.]+)', src)

    assert normal_match, "_LOCK_THRESHOLD_NORMAL not found"
    assert hard_match,   "_LOCK_THRESHOLD_HARD not found"

    normal_val = float(normal_match.group(1))
    hard_val   = float(hard_match.group(1))

    assert 0.0 < normal_val < 1.0, "NORMAL lock threshold must be in (0, 1)"
    assert 0.0 < hard_val   < 1.0, "HARD lock threshold must be in (0, 1)"
    assert hard_val >= normal_val, \
        f"HARD threshold ({hard_val}) should be >= NORMAL ({normal_val})"
    print(f"✓ Lock thresholds: NORMAL={normal_val}, HARD={hard_val}")


# ---------------------------------------------------------------------------
# Phase method checks
# ---------------------------------------------------------------------------

def test_phase_methods_exist():
    """_run_phase_hunt, _run_phase_payload, and _run_phase_execute must be defined."""
    src = _source()
    for method in ["_run_phase_hunt", "_run_phase_payload", "_run_phase_execute"]:
        assert f"def {method}" in src, f"Phase method {method} missing"
    print("✓ All 3 phase methods are defined")


def test_dual_encoder_usage_in_hunt():
    """Both the Core encoder and the Satellite encoder must be read in _run_phase_hunt."""
    src   = _source()
    start = src.find("def _run_phase_hunt")
    end   = src.find("\n    async def ", start + 1)
    if end == -1:
        end = src.find("\n    def ", start + 1)
    body = src[start:end]

    assert "encoder_positions" in body or "encoder_position" in body, \
        "Core encoder not read in _run_phase_hunt"
    assert "_sat_encoder" in body, \
        "Satellite encoder (_sat_encoder) not read in _run_phase_hunt"
    print("✓ Both Core and Satellite encoders are read in _run_phase_hunt")


def test_execute_requires_arm_and_button():
    """Execute phase must check both _SW_ARM (guarded toggle) and _BTN_FIRE."""
    src   = _source()
    start = src.find("def _run_phase_execute")
    end   = src.find("\n    async def ", start + 1)
    if end == -1:
        end = src.find("\n    def ", start + 1)
    body = src[start:end]

    assert "_SW_ARM" in body, \
        "Execute phase should check the guarded toggle (_SW_ARM)"
    assert "_BTN_FIRE" in body or "_sat_button" in body, \
        "Execute phase should check the big button (_BTN_FIRE / _sat_button)"
    assert "arm_engaged and btn_pressed" in body or \
           ("arm_engaged" in body and "btn_pressed" in body), \
        "Both arm_engaged AND btn_pressed must be required to fire"
    print("✓ Execute phase requires both guarded toggle AND big button")


# ---------------------------------------------------------------------------
# Spawn / helper checks
# ---------------------------------------------------------------------------

def test_spawn_submarine_method_exists():
    """_spawn_submarine must be defined in AbyssalPing."""
    src = _source()
    assert "def _spawn_submarine" in src, "_spawn_submarine method missing"
    print("✓ _spawn_submarine method defined")


def test_render_sweep_method_exists():
    """_render_sweep must be defined for the cosmetic matrix sweep line."""
    src = _source()
    assert "def _render_sweep" in src, "_render_sweep method missing"
    print("✓ _render_sweep method defined")


# ---------------------------------------------------------------------------
# Timer and scoring checks
# ---------------------------------------------------------------------------

def test_global_time_defined():
    """_GLOBAL_TIME must be defined."""
    src   = _source()
    match = re.search(r'_GLOBAL_TIME\s*=\s*([\d.]+)', src)
    assert match is not None, "_GLOBAL_TIME constant missing"
    val = float(match.group(1))
    assert val > 0, "_GLOBAL_TIME must be positive"
    print(f"✓ _GLOBAL_TIME = {val}s")


def test_bonus_time_defined():
    """_BONUS_TIME must be defined."""
    src = _source()
    assert "_BONUS_TIME" in src, "_BONUS_TIME constant missing"
    print("✓ _BONUS_TIME constant defined")


def test_lock_flash_ms_defined():
    """_LOCK_FLASH_MS must be defined (controls 33ms red-pixel flash)."""
    src   = _source()
    match = re.search(r'_LOCK_FLASH_MS\s*=\s*(\d+)', src)
    assert match is not None, "_LOCK_FLASH_MS constant missing"
    val = int(match.group(1))
    assert val == 33, f"_LOCK_FLASH_MS should be 33 (ms), got {val}"
    print(f"✓ _LOCK_FLASH_MS = {val}ms")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Running Abyssal Ping mode tests...\n")

    tests = [
        test_abyssal_ping_file_exists,
        test_abyssal_ping_valid_syntax,
        test_abyssal_ping_in_manifest,
        test_abyssal_ping_manifest_metadata,
        test_abyssal_ping_manifest_settings,
        test_abyssal_ping_no_metadata_in_class,
        test_abyssal_ping_icon_in_icons_py,
        test_abyssal_ping_icon_in_icon_library,
        test_abyssal_ping_icon_is_256_bytes,
        test_abyssal_ping_icon_registered_in_library_class,
        test_phase_identifiers,
        test_hardware_indices,
        test_toggle_count_is_eight,
        test_sw_arm_index_is_eight,
        test_diff_params_defines_all_difficulties,
        test_drift_enabled_for_hard_insane,
        test_lock_threshold_stricter_on_hard,
        test_phase_methods_exist,
        test_dual_encoder_usage_in_hunt,
        test_execute_requires_arm_and_button,
        test_spawn_submarine_method_exists,
        test_render_sweep_method_exists,
        test_global_time_defined,
        test_bonus_time_defined,
        test_lock_flash_ms_defined,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"  ❌ FAILED: {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ❌ ERROR:  {t.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'✅' if failed == 0 else '❌'} {passed}/{passed + failed} tests passed")
    sys.exit(0 if failed == 0 else 1)
