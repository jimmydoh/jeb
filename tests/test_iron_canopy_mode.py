"""Test module for Iron Canopy game mode.

Validates:
- Mode file existence and valid Python syntax
- Manifest registration with correct metadata
- Tube state machine constants
- Power routing mode constants
- Radar sweep animation presence in matrix_animations
"""

import sys
import os
import re
import ast

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

_MODE_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'src', 'modes', 'iron_canopy.py'
)
_ANIM_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'src', 'utilities', 'matrix_animations.py'
)


def _source():
    with open(_MODE_PATH, 'r') as f:
        return f.read()


# ---------------------------------------------------------------------------
# File and syntax checks
# ---------------------------------------------------------------------------

def test_file_exists():
    """Test that iron_canopy.py exists."""
    assert os.path.exists(_MODE_PATH), "iron_canopy.py does not exist"
    print("✓ iron_canopy.py exists")


def test_valid_syntax():
    """Test that iron_canopy.py has valid Python syntax."""
    src = _source()
    try:
        ast.parse(src)
    except SyntaxError as e:
        raise AssertionError(f"Syntax error in iron_canopy.py: {e}")
    print("✓ Valid Python syntax")


# ---------------------------------------------------------------------------
# Manifest checks
# ---------------------------------------------------------------------------

def test_iron_canopy_in_manifest():
    """Test that IRON_CANOPY is registered in the mode manifest."""
    from modes.manifest import MODE_REGISTRY

    assert "IRON_CANOPY" in MODE_REGISTRY, "IRON_CANOPY not found in MODE_REGISTRY"
    print("✓ IRON_CANOPY found in MODE_REGISTRY")


def test_iron_canopy_manifest_metadata():
    """Test that IRON_CANOPY manifest entry has all required fields."""
    from modes.manifest import MODE_REGISTRY

    meta = MODE_REGISTRY["IRON_CANOPY"]

    assert meta["id"] == "IRON_CANOPY"
    assert meta["name"] == "IRON CANOPY"
    assert meta["module_path"] == "modes.iron_canopy"
    assert meta["class_name"] == "IronCanopy"
    assert meta["icon"] == "IRON_CANOPY"
    assert "CORE" in meta["requires"], "IRON_CANOPY must require CORE"
    assert "INDUSTRIAL" in meta["requires"], "IRON_CANOPY must require INDUSTRIAL satellite"
    assert meta.get("menu") == "MAIN", "IRON_CANOPY should appear in MAIN menu"
    print("✓ IRON_CANOPY manifest metadata is correct")


def test_iron_canopy_difficulty_settings():
    """Test that IRON_CANOPY has correct difficulty settings."""
    from modes.manifest import MODE_REGISTRY

    meta = MODE_REGISTRY["IRON_CANOPY"]
    settings = meta.get("settings", [])

    diff_setting = next((s for s in settings if s["key"] == "difficulty"), None)
    assert diff_setting is not None, "IRON_CANOPY must have a difficulty setting"
    assert diff_setting["label"] == "DIFF"
    assert "NORMAL" in diff_setting["options"]
    assert "HARD" in diff_setting["options"]
    assert "INSANE" in diff_setting["options"]
    assert diff_setting["default"] == "NORMAL"
    print("✓ IRON_CANOPY difficulty settings are correct")


# ---------------------------------------------------------------------------
# Tube state machine checks
# ---------------------------------------------------------------------------

def test_tube_state_constants():
    """Test that all four tube state constants are defined."""
    src = _source()
    assert "TUBE_READY" in src, "TUBE_READY constant missing"
    assert "TUBE_ARMED" in src, "TUBE_ARMED constant missing"
    assert "TUBE_FIRED" in src, "TUBE_FIRED constant missing"
    assert "TUBE_RELOADING" in src, "TUBE_RELOADING constant missing"
    print("✓ All tube state constants present")


def test_tube_state_machine_logic():
    """Test that tube state transitions are implemented in the source."""
    src = _source()
    # Verify actual assignment patterns for each state transition
    assert "= TUBE_ARMED" in src, "Missing assignment to TUBE_ARMED"
    assert "= TUBE_FIRED" in src, "Missing assignment to TUBE_FIRED"
    assert "= TUBE_RELOADING" in src, "Missing assignment to TUBE_RELOADING"
    assert "= TUBE_READY" in src, "Missing assignment to TUBE_READY"
    print("✓ Tube state machine transitions (assignments) present")


# ---------------------------------------------------------------------------
# Power routing checks
# ---------------------------------------------------------------------------

def test_power_mode_constants():
    """Test that all three power routing modes are defined."""
    src = _source()
    assert "POWER_ACTIVE_RADAR" in src, "POWER_ACTIVE_RADAR constant missing"
    assert "POWER_AUTO_LOADER" in src, "POWER_AUTO_LOADER constant missing"
    assert "POWER_ECM_JAMMING" in src, "POWER_ECM_JAMMING constant missing"
    print("✓ All power routing mode constants present")


def test_rotary_switch_indices():
    """Test that rotary switch pin indices are defined."""
    src = _source()
    assert "_SW_ROTARY_A" in src, "_SW_ROTARY_A not defined"
    assert "_SW_ROTARY_B" in src, "_SW_ROTARY_B not defined"
    print("✓ Rotary switch indices defined")


def test_power_mode_reader():
    """Test that _get_power_mode reads from the satellite HID."""
    src = _source()
    assert "_get_power_mode" in src, "_get_power_mode method missing"
    assert "latching_values" in src, "Power routing should read latching_values"
    print("✓ _get_power_mode method reads satellite HID")


# ---------------------------------------------------------------------------
# Entity system checks
# ---------------------------------------------------------------------------

def test_bogey_spawner():
    """Test that bogey spawning logic exists."""
    src = _source()
    assert "_spawn_bogey" in src, "_spawn_bogey method missing"
    assert "'x'" in src and "'y'" in src, "Bogeys must track x/y coordinates"
    assert "'speed'" in src, "Bogeys must track speed"
    assert "'jammed'" in src, "Bogeys must track jammed state"
    print("✓ Bogey spawner with x/y/speed/jammed present")


def test_firing_protocol():
    """Test that the dual-action firing protocol is implemented."""
    src = _source()
    assert "_attempt_fire" in src, "_attempt_fire method missing"
    assert "_is_arm_engaged" in src, "Master Arm check missing"
    assert "_is_fire_rail_hot" in src, "Fire rail check missing"
    print("✓ Dual-action firing protocol present")


def test_ciws_panic():
    """Test that the CIWS panic button mechanic exists."""
    src = _source()
    assert "_check_ciws" in src, "_check_ciws method missing"
    assert "_CIWS_HEALTH_DRAIN" in src, "CIWS health drain constant missing"
    assert "_CIWS_RADIUS" in src, "CIWS blast radius constant missing"
    print("✓ CIWS panic button mechanic present")


def test_decryption_mechanic():
    """Test that keypad-based signal decryption exists."""
    src = _source()
    assert "_check_decryption" in src, "_check_decryption method missing"
    assert "_DECRYPT_CODE_LEN" in src, "Decrypt code length constant missing"
    print("✓ Decryption mechanic present")


# ---------------------------------------------------------------------------
# Radar animation check
# ---------------------------------------------------------------------------

def test_animate_radar_sweep_in_matrix_animations():
    """Test that animate_radar_sweep is defined in matrix_animations.py."""
    assert os.path.exists(_ANIM_PATH), "matrix_animations.py does not exist"
    with open(_ANIM_PATH, 'r') as f:
        anim_src = f.read()
    assert "def animate_radar_sweep" in anim_src, "animate_radar_sweep not in matrix_animations.py"
    print("✓ animate_radar_sweep defined in matrix_animations.py")


def test_animate_radar_sweep_signature():
    """Test that animate_radar_sweep accepts required parameters."""
    with open(_ANIM_PATH, 'r') as f:
        anim_src = f.read()

    # Check for key parameters
    match = re.search(r'def animate_radar_sweep\(([^)]+)\)', anim_src)
    assert match is not None, "Could not find animate_radar_sweep signature"

    sig = match.group(1)
    assert "matrix_manager" in sig
    assert "sweep_angle" in sig
    assert "bogeys" in sig
    assert "interceptors" in sig
    print("✓ animate_radar_sweep has correct signature")


def test_radar_draws_bogeys_and_interceptors():
    """Test that animate_radar_sweep renders bogeys as red and interceptors as blue."""
    with open(_ANIM_PATH, 'r') as f:
        anim_src = f.read()

    # Find the animate_radar_sweep function body
    start = anim_src.find("def animate_radar_sweep")
    end = anim_src.find("\ndef ", start + 1)
    body = anim_src[start:end]

    assert "Palette.RED" in body, "Bogeys should be drawn in red"
    assert "Palette.BLUE" in body, "Interceptors should be drawn in blue"
    assert "trail" in body.lower(), "Sweep should have fading trail"
    print("✓ Radar sweep draws bogeys (red), interceptors (blue), and fading trail")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Running Iron Canopy mode tests...\n")

    tests = [
        test_file_exists,
        test_valid_syntax,
        test_iron_canopy_in_manifest,
        test_iron_canopy_manifest_metadata,
        test_iron_canopy_difficulty_settings,
        test_tube_state_constants,
        test_tube_state_machine_logic,
        test_power_mode_constants,
        test_rotary_switch_indices,
        test_power_mode_reader,
        test_bogey_spawner,
        test_firing_protocol,
        test_ciws_panic,
        test_decryption_mechanic,
        test_animate_radar_sweep_in_matrix_animations,
        test_animate_radar_sweep_signature,
        test_radar_draws_bogeys_and_interceptors,
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
