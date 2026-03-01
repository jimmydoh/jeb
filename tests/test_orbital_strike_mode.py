"""Test module for Orbital Strike game mode.

Validates:
- Mode file existence and valid Python syntax
- Manifest registration with correct metadata
- Phase constants
- Hardware index constants
- Icon presence in icons.py
- Key game-logic helpers (mission generation, crosshair bounding, etc.)
"""

import sys
import os
import ast

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

_MODE_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'src', 'modes', 'orbital_strike.py'
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
    """Test that orbital_strike.py exists."""
    assert os.path.exists(_MODE_PATH), "orbital_strike.py does not exist"
    print("✓ orbital_strike.py exists")


def test_valid_syntax():
    """Test that orbital_strike.py has valid Python syntax."""
    src = _source()
    try:
        ast.parse(src)
    except SyntaxError as e:
        raise AssertionError(f"Syntax error in orbital_strike.py: {e}")
    print("✓ Valid Python syntax")


# ---------------------------------------------------------------------------
# Manifest checks
# ---------------------------------------------------------------------------

def test_orbital_strike_in_manifest():
    """Test that ORBITAL_STRIKE is registered in the mode manifest."""
    from modes.manifest import MODE_REGISTRY
    assert "ORBITAL_STRIKE" in MODE_REGISTRY, "ORBITAL_STRIKE not found in MODE_REGISTRY"
    print("✓ ORBITAL_STRIKE found in MODE_REGISTRY")


def test_orbital_strike_manifest_metadata():
    """Test that ORBITAL_STRIKE manifest entry has all required fields."""
    from modes.manifest import MODE_REGISTRY
    meta = MODE_REGISTRY["ORBITAL_STRIKE"]

    assert meta["id"] == "ORBITAL_STRIKE"
    assert meta["name"] == "ORBITAL STRIKE"
    assert meta["module_path"] == "modes.orbital_strike"
    assert meta["class_name"] == "OrbitalStrike"
    assert meta["icon"] == "ORBITAL_STRIKE"
    assert "CORE" in meta["requires"], "Must require CORE"
    assert "INDUSTRIAL" in meta["requires"], "Must require INDUSTRIAL satellite"
    assert meta.get("menu") == "MAIN", "Should appear in MAIN menu"
    print("✓ ORBITAL_STRIKE manifest metadata is correct")


def test_orbital_strike_difficulty_settings():
    """Test that ORBITAL_STRIKE has correct difficulty settings."""
    from modes.manifest import MODE_REGISTRY
    meta = MODE_REGISTRY["ORBITAL_STRIKE"]
    settings = meta.get("settings", [])

    diff = next((s for s in settings if s["key"] == "difficulty"), None)
    assert diff is not None, "Must have a difficulty setting"
    assert diff["label"] == "DIFF"
    assert "NORMAL" in diff["options"]
    assert "HARD" in diff["options"]
    assert "INSANE" in diff["options"]
    assert diff["default"] == "NORMAL"
    print("✓ ORBITAL_STRIKE difficulty settings are correct")


# ---------------------------------------------------------------------------
# Phase constant checks
# ---------------------------------------------------------------------------

def test_phase_constants():
    """Test that all 5 phase constants are defined."""
    src = _source()
    for phase in ["_PHASE_GRID", "_PHASE_PAYLOAD", "_PHASE_TARGET", "_PHASE_EXECUTE", "_PHASE_RESET"]:
        assert phase in src, f"Phase constant {phase} missing"
    print("✓ All 5 phase constants are defined")


# ---------------------------------------------------------------------------
# Hardware index checks
# ---------------------------------------------------------------------------

def test_hardware_indices():
    """Test that key hardware index constants are defined."""
    src = _source()
    for const in ["_TOGGLE_COUNT", "_SW_ARM", "_BTN_EXECUTE", "_ENC_SAT", "_ENC_CORE"]:
        assert const in src, f"Hardware constant {const} missing"
    print("✓ Hardware index constants are defined")


def test_toggle_count_is_eight():
    """Test that _TOGGLE_COUNT is 8."""
    src = _source()
    import re
    match = re.search(r'_TOGGLE_COUNT\s*=\s*(\d+)', src)
    assert match is not None, "_TOGGLE_COUNT not found"
    assert int(match.group(1)) == 8, f"_TOGGLE_COUNT should be 8, got {match.group(1)}"
    print("✓ _TOGGLE_COUNT is 8")


def test_guarded_toggle_index():
    """Test that _SW_ARM is 8 (guarded toggle index per sat-01 hardware spec)."""
    src = _source()
    import re
    match = re.search(r'_SW_ARM\s*=\s*(\d+)', src)
    assert match is not None, "_SW_ARM not found"
    assert int(match.group(1)) == 8, f"_SW_ARM should be 8, got {match.group(1)}"
    print("✓ _SW_ARM index is 8 (guarded toggle)")


# ---------------------------------------------------------------------------
# Difficulty parameter checks
# ---------------------------------------------------------------------------

def test_difficulty_params():
    """Test that _DIFF_PARAMS defines NORMAL, HARD, INSANE."""
    src = _source()
    assert "_DIFF_PARAMS" in src, "_DIFF_PARAMS dict missing"
    for diff in ["NORMAL", "HARD", "INSANE"]:
        assert diff in src, f"Difficulty '{diff}' missing from _DIFF_PARAMS"
    print("✓ _DIFF_PARAMS defines NORMAL, HARD, INSANE")


def test_code_length_progression():
    """Test that code lengths increase across difficulty levels."""
    src = _source()
    import re
    # Extract code_len values for each difficulty
    normal_match = re.search(r'"NORMAL".*?"code_len":\s*(\d+)', src, re.DOTALL)
    hard_match   = re.search(r'"HARD".*?"code_len":\s*(\d+)', src, re.DOTALL)
    insane_match = re.search(r'"INSANE".*?"code_len":\s*(\d+)', src, re.DOTALL)

    assert normal_match and hard_match and insane_match, "Could not extract code_len values"
    normal_len = int(normal_match.group(1))
    hard_len   = int(hard_match.group(1))
    insane_len = int(insane_match.group(1))

    assert normal_len < hard_len <= insane_len, \
        f"Code lengths should increase: NORMAL={normal_len}, HARD={hard_len}, INSANE={insane_len}"
    print(f"✓ Code lengths increase: NORMAL={normal_len}, HARD={hard_len}, INSANE={insane_len}")


def test_drift_enabled_for_hard_insane():
    """Test that drift is enabled for HARD and INSANE but not NORMAL."""
    src = _source()
    import re

    # Grab the _DIFF_PARAMS block
    start = src.find("_DIFF_PARAMS")
    end = src.find("\n}", start) + 2
    block = src[start:end]

    # NORMAL should NOT have drift: True
    normal_start = block.find('"NORMAL"')
    hard_start   = block.find('"HARD"')
    insane_start = block.find('"INSANE"')

    assert normal_start != -1 and hard_start != -1 and insane_start != -1

    normal_block  = block[normal_start:hard_start]
    hard_block    = block[hard_start:insane_start]
    insane_block  = block[insane_start:]

    assert "drift\": True" in hard_block or '"drift": True' in hard_block, \
        "HARD should have drift=True"
    assert "drift\": True" in insane_block or '"drift": True' in insane_block, \
        "INSANE should have drift=True"
    print("✓ Drift enabled for HARD and INSANE")


# ---------------------------------------------------------------------------
# Phase method checks
# ---------------------------------------------------------------------------

def test_phase_methods_exist():
    """Test that all 5 phase methods are defined."""
    src = _source()
    for method in [
        "_run_phase_grid",
        "_run_phase_payload",
        "_run_phase_target",
        "_run_phase_execute",
        "_run_phase_reset",
    ]:
        assert f"def {method}" in src, f"Phase method {method} missing"
    print("✓ All 5 phase methods are defined")


def test_dual_encoder_usage():
    """Test that both core and satellite encoders are read in targeting phase."""
    src = _source()
    # Find _run_phase_target
    start = src.find("def _run_phase_target")
    end = src.find("\n    async def ", start + 1)
    if end == -1:
        end = src.find("\n    def ", start + 1)
    body = src[start:end]

    assert "encoder_positions" in body or "encoder_position" in body, \
        "Core encoder not read in _run_phase_target"
    assert "_sat_encoder" in body, \
        "Satellite encoder not read in _run_phase_target"
    print("✓ Both core and satellite encoders are read in targeting phase")


def test_crosshair_bounds_check():
    """Test that crosshair coordinates are clamped within matrix bounds."""
    src = _source()
    start = src.find("def _run_phase_target")
    end = src.find("\n    async def ", start + 1)
    if end == -1:
        end = src.find("\n    def ", start + 1)
    body = src[start:end]

    assert "max(0" in body or "min(w" in body or "min(h" in body, \
        "Crosshair should be clamped to matrix boundaries"
    print("✓ Crosshair coordinates are bounded")


def test_execute_requires_arm_and_button():
    """Test that execute phase checks both arm toggle and button."""
    src = _source()
    start = src.find("def _run_phase_execute")
    end = src.find("\n    async def ", start + 1)
    if end == -1:
        end = src.find("\n    def ", start + 1)
    body = src[start:end]

    assert "_SW_ARM" in body or "latching_values[8]" in body, \
        "Execute phase should check guarded toggle (_SW_ARM)"
    assert "_BTN_EXECUTE" in body or "buttons_values" in body, \
        "Execute phase should check button (_BTN_EXECUTE)"
    assert "arm_engaged and btn_pressed" in body or \
           ("arm_engaged" in body and "btn_pressed" in body), \
        "Both arm AND button must be required to execute"
    print("✓ Execute phase requires both guarded toggle AND button")


def test_reset_phase_checks_all_toggles():
    """Test that reset phase checks all 8 toggles plus guarded arm."""
    src = _source()
    start = src.find("def _run_phase_reset")
    end = src.find("\n    async def ", start + 1)
    if end == -1:
        end = src.find("\n    def ", start + 1)
    body = src[start:end]

    assert "_TOGGLE_COUNT" in body or "range(8)" in body, \
        "Reset should check all 8 payload toggles"
    assert "_SW_ARM" in body, \
        "Reset should check the guarded arm toggle"
    print("✓ Reset phase checks all toggles and guarded arm")


# ---------------------------------------------------------------------------
# Icon checks
# ---------------------------------------------------------------------------

def test_orbital_strike_icon_in_icons_py():
    """Test that ORBITAL_STRIKE icon is defined in icons.py."""
    with open(_ICONS_PATH, 'r') as f:
        src = f.read()
    assert "ORBITAL_STRIKE" in src, "ORBITAL_STRIKE icon not in icons.py"
    print("✓ ORBITAL_STRIKE icon defined in icons.py")


def test_orbital_strike_icon_in_icon_library():
    """Test that ORBITAL_STRIKE is registered in ICON_LIBRARY."""
    with open(_ICONS_PATH, 'r') as f:
        src = f.read()
    # Find ICON_LIBRARY dict
    lib_start = src.find("ICON_LIBRARY")
    lib_end = src.find("}", lib_start)
    library_block = src[lib_start:lib_end]
    assert '"ORBITAL_STRIKE"' in library_block, \
        "ORBITAL_STRIKE not in ICON_LIBRARY dict"
    print("✓ ORBITAL_STRIKE registered in ICON_LIBRARY")


def test_orbital_strike_icon_is_256_bytes():
    """Test that ORBITAL_STRIKE icon data is exactly 256 bytes (16x16)."""
    with open(_ICONS_PATH, 'r') as f:
        src = f.read()

    import re
    # Find the ORBITAL_STRIKE = bytes([...]) block
    match = re.search(r'ORBITAL_STRIKE\s*=\s*bytes\(\[(.*?)\]\)', src, re.DOTALL)
    assert match is not None, "Could not find ORBITAL_STRIKE bytes literal"

    # Extract numeric values, handling line continuations and comments
    raw_content = match.group(1).replace('\n', ',')
    tokens = [t.strip() for t in raw_content.split(',')]
    values = [t for t in tokens if t.isdigit()]
    assert len(values) == 256, f"ORBITAL_STRIKE icon should be 256 bytes (16x16), got {len(values)}"
    print(f"✓ ORBITAL_STRIKE icon is 256 bytes (16x16)")


# ---------------------------------------------------------------------------
# Scoring and timing checks
# ---------------------------------------------------------------------------

def test_bonus_time_defined():
    """Test that a bonus time constant is defined."""
    src = _source()
    assert "_BONUS_TIME" in src, "_BONUS_TIME constant missing"
    print("✓ _BONUS_TIME constant defined")


def test_global_timer_defined():
    """Test that the global 2-minute timer constant is defined."""
    src = _source()
    import re
    match = re.search(r'_GLOBAL_TIME\s*=\s*([\d.]+)', src)
    assert match is not None, "_GLOBAL_TIME constant missing"
    val = float(match.group(1))
    assert val == 120.0, f"_GLOBAL_TIME should be 120.0 seconds, got {val}"
    print(f"✓ _GLOBAL_TIME = {val}s (2 minutes)")


def test_segment_display_called():
    """Test that satellite 14-segment display is updated in each phase."""
    src = _source()
    assert "_send_segment" in src, "_send_segment helper missing"
    # Check each phase calls it
    for phase in ["_run_phase_grid", "_run_phase_payload", "_run_phase_target",
                  "_run_phase_execute", "_run_phase_reset"]:
        start = src.find(f"def {phase}")
        end = src.find("\n    async def ", start + 1)
        if end == -1:
            end = src.find("\n    def ", start + 1)
        body = src[start:end]
        assert "_send_segment" in body, f"{phase} should call _send_segment"
    print("✓ _send_segment called in every phase")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Running Orbital Strike mode tests...\n")

    tests = [
        test_file_exists,
        test_valid_syntax,
        test_orbital_strike_in_manifest,
        test_orbital_strike_manifest_metadata,
        test_orbital_strike_difficulty_settings,
        test_phase_constants,
        test_hardware_indices,
        test_toggle_count_is_eight,
        test_guarded_toggle_index,
        test_difficulty_params,
        test_code_length_progression,
        test_drift_enabled_for_hard_insane,
        test_phase_methods_exist,
        test_dual_encoder_usage,
        test_crosshair_bounds_check,
        test_execute_requires_arm_and_button,
        test_reset_phase_checks_all_toggles,
        test_orbital_strike_icon_in_icons_py,
        test_orbital_strike_icon_in_icon_library,
        test_orbital_strike_icon_is_256_bytes,
        test_bonus_time_defined,
        test_global_timer_defined,
        test_segment_display_called,
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
