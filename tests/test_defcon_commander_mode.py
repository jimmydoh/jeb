"""Test module for DEFCON Commander game mode.

Validates:
- Mode file existence and valid Python syntax
- Manifest registration with correct metadata
- Silo state machine constants
- Hardware index constants
- Key protocol method presence
- Icon registration in Icons library
- New tone constants (LAUNCH, DANGER, CHARGING) in tones.py
"""

import sys
import os
import ast

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

_MODE_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'src', 'modes', 'defcon_commander.py'
)
_TONES_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'src', 'utilities', 'tones.py'
)
_ICONS_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'src', 'utilities', 'icons.py'
)


def _source():
    with open(_MODE_PATH, 'r') as f:
        return f.read()


# ---------------------------------------------------------------------------
# File and syntax checks
# ---------------------------------------------------------------------------

def test_file_exists():
    """Test that defcon_commander.py exists."""
    assert os.path.exists(_MODE_PATH), "defcon_commander.py does not exist"
    print("✓ defcon_commander.py exists")


def test_valid_syntax():
    """Test that defcon_commander.py has valid Python syntax."""
    src = _source()
    try:
        ast.parse(src)
    except SyntaxError as e:
        raise AssertionError(f"Syntax error in defcon_commander.py: {e}")
    print("✓ Valid Python syntax")


# ---------------------------------------------------------------------------
# Manifest checks
# ---------------------------------------------------------------------------

def test_defcon_commander_in_manifest():
    """Test that DEFCON_COMMANDER is registered in the mode manifest."""
    from modes.manifest import MODE_REGISTRY
    assert "DEFCON_COMMANDER" in MODE_REGISTRY, "DEFCON_COMMANDER not found in MODE_REGISTRY"
    print("✓ DEFCON_COMMANDER found in MODE_REGISTRY")


def test_defcon_commander_manifest_metadata():
    """Test that DEFCON_COMMANDER manifest entry has all required fields."""
    from modes.manifest import MODE_REGISTRY
    meta = MODE_REGISTRY["DEFCON_COMMANDER"]
    assert meta["id"] == "DEFCON_COMMANDER"
    assert meta["name"] == "DEFCON CMDR"
    assert meta["module_path"] == "modes.defcon_commander"
    assert meta["class_name"] == "DefconCommander"
    assert meta["icon"] == "DEFCON_COMMANDER"
    assert "CORE" in meta["requires"], "DEFCON_COMMANDER must require CORE"
    assert "INDUSTRIAL" in meta["requires"], "DEFCON_COMMANDER must require INDUSTRIAL satellite"
    assert meta.get("menu") == "MAIN", "DEFCON_COMMANDER should appear in MAIN menu"
    print("✓ DEFCON_COMMANDER manifest metadata is correct")


def test_defcon_commander_difficulty_settings():
    """Test that DEFCON_COMMANDER has correct difficulty settings."""
    from modes.manifest import MODE_REGISTRY
    meta = MODE_REGISTRY["DEFCON_COMMANDER"]
    settings = meta.get("settings", [])
    diff_setting = next((s for s in settings if s["key"] == "difficulty"), None)
    assert diff_setting is not None, "DEFCON_COMMANDER must have a difficulty setting"
    assert diff_setting["label"] == "DIFF"
    assert "NORMAL" in diff_setting["options"]
    assert "HARD" in diff_setting["options"]
    assert "INSANE" in diff_setting["options"]
    assert diff_setting["default"] == "NORMAL"
    print("✓ DEFCON_COMMANDER difficulty settings are correct")


# ---------------------------------------------------------------------------
# Silo state machine checks
# ---------------------------------------------------------------------------

def test_silo_state_constants():
    """Test that all silo state constants are defined."""
    src = _source()
    for state in ("SILO_IDLE", "SILO_ORDERED", "SILO_AUTH", "SILO_ARMING",
                  "SILO_OPEN", "SILO_PREP", "SILO_READY", "SILO_LAUNCHED"):
        assert state in src, f"{state} constant missing"
    print("✓ All silo state constants present")


def test_silo_state_transitions():
    """Test that silo state transition assignments are implemented."""
    src = _source()
    for state in ("SILO_AUTH", "SILO_ARMING", "SILO_OPEN",
                  "SILO_PREP", "SILO_READY", "SILO_LAUNCHED"):
        assert f"= {state}" in src, f"Missing assignment to {state}"
    print("✓ Silo state machine transitions present")


def test_num_silos_constant():
    """Test that _NUM_SILOS is defined and equals 10."""
    src = _source()
    assert "_NUM_SILOS" in src, "_NUM_SILOS constant missing"
    assert "_NUM_SILOS        = 10" in src or "_NUM_SILOS = 10" in src, \
        "_NUM_SILOS must be 10"
    print("✓ _NUM_SILOS = 10 defined")


# ---------------------------------------------------------------------------
# Hardware index checks
# ---------------------------------------------------------------------------

def test_hardware_indices_defined():
    """Test that hardware control indices are defined."""
    src = _source()
    assert "_SW_KEY" in src,      "_SW_KEY (Key Switch index) missing"
    assert "_SW_ARM" in src,      "_SW_ARM (Guarded Toggle index) missing"
    assert "_MT_DOOR" in src,     "_MT_DOOR (Momentary toggle index) missing"
    assert "_BTN_LAUNCH" in src,  "_BTN_LAUNCH (Giant Red Button index) missing"
    print("✓ All hardware index constants defined")


# ---------------------------------------------------------------------------
# Protocol method checks
# ---------------------------------------------------------------------------

def test_hardware_reader_methods():
    """Test that hardware state reader methods are implemented."""
    src = _source()
    assert "_key_is_on" in src,      "_key_is_on method missing"
    assert "_arm_is_up" in src,      "_arm_is_up method missing"
    assert "_door_held" in src,      "_door_held method missing"
    assert "_launch_pressed" in src, "_launch_pressed method missing"
    print("✓ Hardware reader methods present")


def test_protocol_methods():
    """Test that core protocol step methods are present."""
    src = _source()
    assert "_try_auth" in src,        "_try_auth method missing"
    assert "_trigger_fault" in src,   "_trigger_fault method missing"
    assert "_fault_cleared" in src,   "_fault_cleared method missing"
    assert "_apply_penalty" in src,   "_apply_penalty method missing"
    assert "_tick_active_silo" in src,"_tick_active_silo method missing"
    print("✓ Protocol step methods present")


def test_keypad_input():
    """Test that keypad polling is implemented."""
    src = _source()
    assert "_poll_keypad" in src,    "_poll_keypad method missing"
    assert "_clear_keypad_buf" in src,"_clear_keypad_buf method missing"
    assert "keypad_values" in src,   "Keypad buffer polling not implemented"
    print("✓ Keypad input methods present")


def test_order_management():
    """Test that order issuance is implemented."""
    src = _source()
    assert "_issue_order" in src,    "_issue_order method missing"
    assert "_update_orders" in src,  "_update_orders method missing"
    assert "SILO_ORDERED" in src,    "SILO_ORDERED state must be set in _issue_order"
    print("✓ Order management methods present")


# ---------------------------------------------------------------------------
# Matrix rendering checks
# ---------------------------------------------------------------------------

def test_matrix_rendering_methods():
    """Test that matrix rendering methods are present."""
    src = _source()
    assert "_render_silo_field" in src,  "_render_silo_field method missing"
    assert "_render_schematic" in src,   "_render_schematic method missing"
    assert "_render_matrix" in src,      "_render_matrix method missing"
    assert "_silo_pixel_pos" in src,     "_silo_pixel_pos helper missing"
    assert "_silo_color" in src,         "_silo_color helper missing"
    print("✓ Matrix rendering methods present")


def test_schematic_constants():
    """Test that schematic layout constants are defined."""
    src = _source()
    assert "_SCHEMATIC_X" in src, "_SCHEMATIC_X (schematic column offset) missing"
    assert "_SCHEMATIC_W" in src, "_SCHEMATIC_W (schematic width) missing"
    print("✓ Schematic layout constants defined")


# ---------------------------------------------------------------------------
# Icon library check
# ---------------------------------------------------------------------------

def test_defcon_commander_icon_in_library():
    """Test that DEFCON_COMMANDER icon is in ICON_LIBRARY."""
    with open(_ICONS_PATH, 'r') as f:
        icons_src = f.read()
    assert "DEFCON_COMMANDER" in icons_src, \
        "DEFCON_COMMANDER not registered in icons.py"
    assert "\"DEFCON_COMMANDER\":" in icons_src, \
        "DEFCON_COMMANDER not in ICON_LIBRARY dict"
    print("✓ DEFCON_COMMANDER icon defined and registered")


# ---------------------------------------------------------------------------
# Tones checks
# ---------------------------------------------------------------------------

def test_new_tone_constants():
    """Test that LAUNCH, DANGER, and CHARGING tone constants are defined."""
    with open(_TONES_PATH, 'r') as f:
        tones_src = f.read()
    assert "LAUNCH = {" in tones_src,   "LAUNCH tone constant missing"
    assert "DANGER = {" in tones_src,   "DANGER tone constant missing"
    assert "CHARGING = {" in tones_src, "CHARGING tone constant missing"
    print("✓ LAUNCH, DANGER, and CHARGING tone constants defined")


def test_tones_valid_syntax():
    """Test that tones.py still has valid Python syntax after additions."""
    with open(_TONES_PATH, 'r') as f:
        tones_src = f.read()
    try:
        ast.parse(tones_src)
    except SyntaxError as e:
        raise AssertionError(f"Syntax error in tones.py: {e}")
    print("✓ tones.py valid syntax")


# ---------------------------------------------------------------------------
# Class structure check
# ---------------------------------------------------------------------------

def test_inherits_game_mode():
    """Test that DefconCommander inherits from GameMode."""
    src = _source()
    assert "class DefconCommander(GameMode)" in src, \
        "DefconCommander must inherit from GameMode"
    print("✓ DefconCommander inherits from GameMode")


def test_run_method_present():
    """Test that the async run() method is implemented."""
    src = _source()
    assert "async def run(self)" in src, "run() coroutine missing"
    print("✓ async run() method present")


def test_reset_guard_logic():
    """Test that the reset guard (key OFF + arm DOWN after launch) is implemented."""
    src = _source()
    assert "_reset_needed" in src, "_reset_needed state variable missing"
    print("✓ Reset guard logic (_reset_needed) present")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Running DEFCON Commander mode tests...\n")

    tests = [
        test_file_exists,
        test_valid_syntax,
        test_defcon_commander_in_manifest,
        test_defcon_commander_manifest_metadata,
        test_defcon_commander_difficulty_settings,
        test_silo_state_constants,
        test_silo_state_transitions,
        test_num_silos_constant,
        test_hardware_indices_defined,
        test_hardware_reader_methods,
        test_protocol_methods,
        test_keypad_input,
        test_order_management,
        test_matrix_rendering_methods,
        test_schematic_constants,
        test_defcon_commander_icon_in_library,
        test_new_tone_constants,
        test_tones_valid_syntax,
        test_inherits_game_mode,
        test_run_method_present,
        test_reset_guard_logic,
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
            failed += 1

    print(f"\n{'✅' if failed == 0 else '❌'} {passed}/{passed + failed} tests passed")
    sys.exit(0 if failed == 0 else 1)
