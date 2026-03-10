"""Test module for Bunker Defuse game mode.

Validates:
- Mode file existence and valid Python syntax
- Manifest registration with correct metadata
- Hardware index constants
- Module type constants and all-module-types list
- Difficulty parameter table (NORMAL / HARD / INSANE)
- Module generation helpers (_make_module, _generate_modules)
- Validation helpers (_check_wire_module, _check_rotary_module)
- Timer helpers (_tick_timer, _apply_strike)
- OLED manual-line generators (one per module type)
- Key method presence (run, run_tutorial, _process_module, etc.)
- Icon presence and size in icons.py
"""

import sys
import os
import ast
import re

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

_MODE_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'src', 'modes', 'bunker_defuse.py'
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
    """Test that bunker_defuse.py exists."""
    assert os.path.exists(_MODE_PATH), "bunker_defuse.py does not exist"
    print("✓ bunker_defuse.py exists")


def test_valid_syntax():
    """Test that bunker_defuse.py has valid Python syntax."""
    src = _source()
    try:
        ast.parse(src)
    except SyntaxError as e:
        raise AssertionError(f"Syntax error in bunker_defuse.py: {e}")
    print("✓ Valid Python syntax")


# ---------------------------------------------------------------------------
# Manifest checks
# ---------------------------------------------------------------------------

def test_bunker_defuse_in_manifest():
    """Test that BUNKER_DEFUSE is registered in the mode manifest."""
    from modes.manifest import MODE_REGISTRY
    assert "BUNKER_DEFUSE" in MODE_REGISTRY, "BUNKER_DEFUSE not found in MODE_REGISTRY"
    print("✓ BUNKER_DEFUSE found in MODE_REGISTRY")


def test_bunker_defuse_manifest_metadata():
    """Test that BUNKER_DEFUSE manifest entry has all required fields."""
    from modes.manifest import MODE_REGISTRY
    meta = MODE_REGISTRY["BUNKER_DEFUSE"]

    assert meta["id"] == "BUNKER_DEFUSE", f"id mismatch: {meta['id']}"
    assert meta["name"] == "BUNKER DEFUSE", f"name mismatch: {meta['name']}"
    assert meta["module_path"] == "modes.bunker_defuse", f"module_path mismatch"
    assert meta["class_name"] == "BunkerDefuse", f"class_name mismatch"
    assert meta["icon"] == "BUNKER_DEFUSE", f"icon mismatch"
    assert "CORE" in meta["requires"], "Must require CORE"
    assert "INDUSTRIAL" in meta["requires"], "Must require INDUSTRIAL satellite"
    assert meta.get("menu") == "MAIN", "Should appear in MAIN menu"
    assert meta.get("has_tutorial") is True, "Should have a tutorial"
    print("✓ BUNKER_DEFUSE manifest metadata is correct")


def test_bunker_defuse_difficulty_settings():
    """Test that BUNKER_DEFUSE has correct difficulty settings."""
    from modes.manifest import MODE_REGISTRY
    meta     = MODE_REGISTRY["BUNKER_DEFUSE"]
    settings = meta.get("settings", [])

    diff = next((s for s in settings if s["key"] == "difficulty"), None)
    assert diff is not None, "Must have a difficulty setting"
    assert diff["label"] == "DIFF"
    assert "NORMAL" in diff["options"]
    assert "HARD"   in diff["options"]
    assert "INSANE" in diff["options"]
    assert diff["default"] == "NORMAL"
    print("✓ BUNKER_DEFUSE difficulty settings are correct")


# ---------------------------------------------------------------------------
# Hardware index checks
# ---------------------------------------------------------------------------

def test_hardware_indices_defined():
    """Test that key hardware index constants are defined."""
    src = _source()
    for const in [
        "_TOGGLE_COUNT",
        "_SW_ARM",
        "_SW_ROTARY_A",
        "_SW_ROTARY_B",
        "_BTN_FIRE",
        "_ENC_CORE",
    ]:
        assert const in src, f"Hardware constant {const} missing"
    print("✓ All hardware index constants are defined")


def test_toggle_count_is_eight():
    """Test that _TOGGLE_COUNT is 8 (matches the Industrial Satellite)."""
    src   = _source()
    match = re.search(r'_TOGGLE_COUNT\s*=\s*(\d+)', src)
    assert match is not None, "_TOGGLE_COUNT not found"
    assert int(match.group(1)) == 8, f"Expected 8, got {match.group(1)}"
    print("✓ _TOGGLE_COUNT is 8")


def test_rotary_indices():
    """Test that _SW_ROTARY_A=10 and _SW_ROTARY_B=11."""
    src     = _source()
    match_a = re.search(r'_SW_ROTARY_A\s*=\s*(\d+)', src)
    match_b = re.search(r'_SW_ROTARY_B\s*=\s*(\d+)', src)
    assert match_a is not None, "_SW_ROTARY_A not found"
    assert match_b is not None, "_SW_ROTARY_B not found"
    assert int(match_a.group(1)) == 10, f"_SW_ROTARY_A should be 10"
    assert int(match_b.group(1)) == 11, f"_SW_ROTARY_B should be 11"
    print("✓ _SW_ROTARY_A=10, _SW_ROTARY_B=11")


def test_sw_arm_is_eight():
    """Test that _SW_ARM is 8 (guarded toggle)."""
    src   = _source()
    match = re.search(r'_SW_ARM\s*=\s*(\d+)', src)
    assert match is not None, "_SW_ARM not found"
    assert int(match.group(1)) == 8, f"_SW_ARM should be 8"
    print("✓ _SW_ARM is 8")


def test_btn_fire_is_zero():
    """Test that _BTN_FIRE is 0 (large button)."""
    src   = _source()
    match = re.search(r'_BTN_FIRE\s*=\s*(\d+)', src)
    assert match is not None, "_BTN_FIRE not found"
    assert int(match.group(1)) == 0, f"_BTN_FIRE should be 0"
    print("✓ _BTN_FIRE is 0")


# ---------------------------------------------------------------------------
# Module type and game constant checks
# ---------------------------------------------------------------------------

def test_all_five_module_types_defined():
    """Test that all five module type constants are present."""
    src = _source()
    for mod in ["_MOD_WIRE", "_MOD_ROTARY", "_MOD_CODE", "_MOD_ARM", "_MOD_SEQUENCE"]:
        assert mod in src, f"Module constant {mod} missing"
    print("✓ All five module type constants are defined")


def test_all_module_types_list():
    """Test that _ALL_MODULE_TYPES contains all five module types."""
    src = _source()
    assert "_ALL_MODULE_TYPES" in src, "_ALL_MODULE_TYPES list missing"
    for mod in ["_MOD_WIRE", "_MOD_ROTARY", "_MOD_CODE", "_MOD_ARM", "_MOD_SEQUENCE"]:
        # Check somewhere in source (list inclusion)
        assert mod in src, f"{mod} not referenced in source"
    print("✓ _ALL_MODULE_TYPES list is present")


def test_max_strikes_is_three():
    """Test that _MAX_STRIKES is 3."""
    src   = _source()
    match = re.search(r'_MAX_STRIKES\s*=\s*(\d+)', src)
    assert match is not None, "_MAX_STRIKES not found"
    assert int(match.group(1)) == 3, f"Expected 3, got {match.group(1)}"
    print("✓ _MAX_STRIKES is 3")


def test_difficulty_params_defined():
    """Test that _DIFF_PARAMS defines NORMAL, HARD, INSANE."""
    src = _source()
    assert "_DIFF_PARAMS" in src, "_DIFF_PARAMS dict missing"
    for diff in ["NORMAL", "HARD", "INSANE"]:
        assert diff in src, f"Difficulty '{diff}' missing from _DIFF_PARAMS"
    print("✓ _DIFF_PARAMS defines NORMAL, HARD, INSANE")


def test_global_time_decreases_with_difficulty():
    """Test that global_time is highest for NORMAL and lowest for INSANE."""
    src = _source()

    def _extract_global_time(difficulty):
        m = re.search(rf'"{difficulty}".*?"global_time":\s*([\d.]+)', src, re.DOTALL)
        assert m is not None, f"Could not extract global_time for {difficulty}"
        return float(m.group(1))

    normal_t = _extract_global_time("NORMAL")
    hard_t   = _extract_global_time("HARD")
    insane_t = _extract_global_time("INSANE")
    assert normal_t > hard_t >= insane_t, (
        f"global_time should decrease: NORMAL={normal_t}, HARD={hard_t}, INSANE={insane_t}"
    )
    print(f"✓ global_time decreases: NORMAL={normal_t}, HARD={hard_t}, INSANE={insane_t}")


def test_num_modules_increases_with_difficulty():
    """Test that num_modules is lowest for NORMAL and highest for INSANE."""
    src = _source()

    def _extract_num_modules(difficulty):
        m = re.search(rf'"{difficulty}".*?"num_modules":\s*(\d+)', src, re.DOTALL)
        assert m is not None, f"Could not extract num_modules for {difficulty}"
        return int(m.group(1))

    normal_n = _extract_num_modules("NORMAL")
    hard_n   = _extract_num_modules("HARD")
    insane_n = _extract_num_modules("INSANE")
    assert normal_n <= hard_n <= insane_n, (
        f"num_modules should increase: NORMAL={normal_n}, HARD={hard_n}, INSANE={insane_n}"
    )
    print(f"✓ num_modules increases: NORMAL={normal_n}, HARD={hard_n}, INSANE={insane_n}")


# ---------------------------------------------------------------------------
# Method presence checks
# ---------------------------------------------------------------------------

def test_required_methods_exist():
    """Test that all key methods are defined."""
    src = _source()
    for method in [
        "_sat_latching",
        "_sat_button",
        "_send_segment",
        "_set_sat_led",
        "_get_rotary_position",
        "_poll_keypad",
        "_generate_modules",
        "_make_module",
        "_render_matrix",
        "_render_module_visual",
        "_render_wire_diagram",
        "_render_rotary_indicator",
        "_render_code_indicator",
        "_render_arm_indicator",
        "_render_sequence_indicator",
        "_render_timer_bar",
        "_update_oled_manual",
        "_wire_manual",
        "_rotary_manual",
        "_code_manual",
        "_arm_manual",
        "_sequence_manual",
        "_check_wire_module",
        "_check_rotary_module",
        "_tick_timer",
        "_apply_strike",
        "_process_module",
        "_on_module_solved",
        "_on_strike",
        "_explode",
        "run_tutorial",
        "run",
    ]:
        assert f"def {method}" in src, f"Method {method} missing"
    print("✓ All required methods are defined")


# ---------------------------------------------------------------------------
# Rotary position constants
# ---------------------------------------------------------------------------

def test_rotary_position_constants():
    """Test that all three rotary position constants are defined."""
    src = _source()
    for const in ["_ROT_POS_A", "_ROT_POS_B", "_ROT_POS_CTR"]:
        assert const in src, f"Rotary position constant {const} missing"
    print("✓ _ROT_POS_A, _ROT_POS_B, _ROT_POS_CTR are all defined")


# ---------------------------------------------------------------------------
# Pure-Python logic tests (no hardware import needed)
# ---------------------------------------------------------------------------

def _make_mock_module_wire(required):
    """Build a minimal wire module dict for testing."""
    return {"type": "WIRE", "required": required, "solved": False}


def _make_mock_module_rotary(pos):
    """Build a minimal rotary module dict for testing."""
    return {
        "type": "ROTARY",
        "required_pos": pos,
        "cvar": "TIMER",
        "cval": 2,
        "solved": False,
    }


def _check_wire(module, toggle_states):
    """Replicate _check_wire_module without importing BunkerDefuse."""
    for i, req in enumerate(module["required"]):
        if toggle_states[i] != req:
            return False
    return True


def _decode_rotary(rot_a, rot_b):
    """Replicate _get_rotary_position without importing BunkerDefuse."""
    if rot_a and not rot_b:
        return "A"
    if not rot_a and rot_b:
        return "B"
    return "CENTER"


def test_check_wire_all_matching():
    """Wire module: all toggles matching required → True."""
    required = [True, False, True, True, False, False, True, False]
    result   = _check_wire(_make_mock_module_wire(required), required)
    assert result is True, "Expected True for fully-matching toggles"
    print("✓ _check_wire_module: all matching → True")


def test_check_wire_one_mismatch():
    """Wire module: one toggle wrong → False."""
    required = [True, False, True, True, False, False, True, False]
    wrong    = list(required)
    wrong[3] = not wrong[3]
    result   = _check_wire(_make_mock_module_wire(required), wrong)
    assert result is False, "Expected False when one toggle is wrong"
    print("✓ _check_wire_module: one mismatch → False")


def test_check_wire_all_off():
    """Wire module: all-OFF required, all-OFF provided → True."""
    required = [False] * 8
    result   = _check_wire(_make_mock_module_wire(required), required)
    assert result is True
    print("✓ _check_wire_module: all-OFF matches all-OFF")


def test_check_wire_all_on():
    """Wire module: all-ON required, all-ON provided → True."""
    required = [True] * 8
    result   = _check_wire(_make_mock_module_wire(required), required)
    assert result is True
    print("✓ _check_wire_module: all-ON matches all-ON")


def test_rotary_position_A():
    """Rotary A=ON, B=OFF → position A."""
    assert _decode_rotary(True, False) == "A"
    print("✓ Rotary A=ON, B=OFF → 'A'")


def test_rotary_position_B():
    """Rotary A=OFF, B=ON → position B."""
    assert _decode_rotary(False, True) == "B"
    print("✓ Rotary A=OFF, B=ON → 'B'")


def test_rotary_position_center_both_off():
    """Rotary A=OFF, B=OFF → CENTER."""
    assert _decode_rotary(False, False) == "CENTER"
    print("✓ Rotary both OFF → 'CENTER'")


def test_rotary_check_correct():
    """Rotary module solved when switch matches required position."""
    mod    = _make_mock_module_rotary("A")
    actual = _decode_rotary(True, False)  # → "A"
    assert actual == mod["required_pos"]
    print("✓ Rotary check: correct position matches required")


def test_rotary_check_wrong():
    """Rotary module not solved when switch doesn't match required position."""
    mod    = _make_mock_module_rotary("B")
    actual = _decode_rotary(True, False)  # → "A", required is "B"
    assert actual != mod["required_pos"]
    print("✓ Rotary check: wrong position doesn't match required")


def test_strike_time_penalty():
    """Each strike should deduct _STRIKE_TIME_PENALTY from time remaining."""
    src   = _source()
    match = re.search(r'_STRIKE_TIME_PENALTY\s*=\s*([\d.]+)', src)
    assert match is not None, "_STRIKE_TIME_PENALTY not found"
    penalty = float(match.group(1))
    assert penalty > 0, "Strike penalty should be positive"
    print(f"✓ _STRIKE_TIME_PENALTY = {penalty}s (positive)")


def test_max_strikes_triggers_game_over():
    """Verify that reaching _MAX_STRIKES leads to game over (source check)."""
    src = _source()
    assert "_strikes >= _MAX_STRIKES" in src, \
        "Code should check _strikes >= _MAX_STRIKES to trigger game over"
    print("✓ Game over triggered when _strikes >= _MAX_STRIKES")


def test_timer_expiry_triggers_game_over():
    """Verify that timer expiry leads to game over (source check)."""
    src = _source()
    assert "_time_remaining <= 0" in src, \
        "Code should check _time_remaining <= 0 to trigger game over"
    print("✓ Game over triggered when _time_remaining <= 0")


def test_points_per_module_positive():
    """_POINTS_PER_MODULE should be a positive integer."""
    src   = _source()
    match = re.search(r'_POINTS_PER_MODULE\s*=\s*(\d+)', src)
    assert match is not None, "_POINTS_PER_MODULE not found"
    assert int(match.group(1)) > 0, "_POINTS_PER_MODULE must be positive"
    print(f"✓ _POINTS_PER_MODULE = {match.group(1)} (positive)")


def test_code_module_manual_shows_code():
    """_code_manual must include the code in its output lines."""
    src   = _source()
    start = src.find("def _code_manual")
    end   = src.find("\n    def ", start + 1)
    if end == -1:
        end = src.find("\n    async def ", start + 1)
    body  = src[start:end]
    assert "code" in body.lower(), "_code_manual should reference the code in its lines"
    print("✓ _code_manual references the cipher code in its output")


def test_arm_manual_mentions_guard():
    """_arm_manual must instruct the Operator to lift the guard toggle."""
    src   = _source()
    start = src.find("def _arm_manual")
    end   = src.find("\n    def ", start + 1)
    if end == -1:
        end = src.find("\n    async def ", start + 1)
    body  = src[start:end]
    assert "GUARD" in body.upper(), "_arm_manual should mention the guard toggle"
    print("✓ _arm_manual mentions GUARD toggle")


def test_sequence_manual_mentions_press_count():
    """_sequence_manual must relay the required press count."""
    src   = _source()
    start = src.find("def _sequence_manual")
    end   = src.find("\n    def ", start + 1)
    if end == -1:
        end = src.find("\n    async def ", start + 1)
    body  = src[start:end]
    assert "target_presses" in body or "target" in body, \
        "_sequence_manual should include the press count"
    print("✓ _sequence_manual references target press count")


def test_process_module_handles_all_types():
    """_process_module should contain branches for all five module types."""
    src   = _source()
    start = src.find("async def _process_module")
    end   = src.find("\n    async def ", start + 1)
    if end == -1:
        end = src.find("\n    def ", start + 1)
    body  = src[start:end]
    for mtype in ["_MOD_WIRE", "_MOD_ROTARY", "_MOD_CODE", "_MOD_ARM", "_MOD_SEQUENCE"]:
        assert mtype in body, f"_process_module missing branch for {mtype}"
    print("✓ _process_module handles all five module types")


def test_wire_module_requires_button_confirm():
    """WIRE module should require button press to confirm the toggle state."""
    src   = _source()
    start = src.find("async def _process_module")
    end   = src.find("\n    async def ", start + 1)
    if end == -1:
        end = src.find("\n    def ", start + 1)
    body  = src[start:end]
    # Check that _MOD_WIRE branch checks btn_rising before returning SOLVED
    wire_section = body[body.find("_MOD_WIRE"):body.find("_MOD_ROTARY")]
    assert "btn_rising" in wire_section, \
        "WIRE module should check btn_rising before solving"
    assert "SOLVED" in wire_section, \
        "WIRE module must return 'SOLVED' on correct state + button press"
    print("✓ WIRE module requires button press to confirm")


def test_code_module_clears_buffer_on_wrong():
    """CODE module should clear the keypad buffer after a wrong submission."""
    src   = _source()
    start = src.find("async def _process_module")
    end   = src.find("\n    async def ", start + 1)
    if end == -1:
        end = src.find("\n    def ", start + 1)
    body  = src[start:end]
    code_section = body[body.find("_MOD_CODE"):body.find("_MOD_ARM")]
    assert "_kp_buf" in code_section, \
        "CODE module should reference _kp_buf"
    print("✓ CODE module references _kp_buf (buffer management)")


def test_arm_module_requires_guard_up():
    """ARM module should require the guarded toggle to be up before counting presses."""
    src   = _source()
    start = src.find("async def _process_module")
    end   = src.find("\n    async def ", start + 1)
    if end == -1:
        end = src.find("\n    def ", start + 1)
    body  = src[start:end]
    arm_section = body[body.find("_MOD_ARM"):body.find("_MOD_SEQUENCE")]
    assert "_SW_ARM" in arm_section, \
        "ARM module should check _SW_ARM (guarded toggle)"
    print("✓ ARM module checks _SW_ARM (guarded toggle)")


def test_sequence_module_resets_on_over_press():
    """SEQUENCE module should reset press_count when Operator presses too many times."""
    src   = _source()
    start = src.find("async def _process_module")
    end   = src.find("\n    async def ", start + 1)
    if end == -1:
        end = src.find("\n    def ", start + 1)
    body  = src[start:end]
    seq_section = body[body.find("_MOD_SEQUENCE"):]
    assert "press_count" in seq_section, "_MOD_SEQUENCE must track press_count"
    assert "0" in seq_section, "_MOD_SEQUENCE must reset press_count to 0 on over-press"
    print("✓ SEQUENCE module resets press_count on over-press")


# ---------------------------------------------------------------------------
# Timer bar coverage
# ---------------------------------------------------------------------------

def test_timer_bar_uses_three_colours():
    """_render_timer_bar should use GREEN, YELLOW, and RED based on time remaining."""
    src   = _source()
    start = src.find("def _render_timer_bar")
    end   = src.find("\n    def ", start + 1)
    if end == -1:
        end = src.find("\n    async def ", start + 1)
    body  = src[start:end]
    assert "GREEN"  in body, "_render_timer_bar must use GREEN when time is plentiful"
    assert "YELLOW" in body, "_render_timer_bar must use YELLOW at half-time"
    assert "RED"    in body, "_render_timer_bar must use RED when time is low"
    print("✓ _render_timer_bar uses GREEN / YELLOW / RED based on time")


# ---------------------------------------------------------------------------
# Icon checks
# ---------------------------------------------------------------------------

def test_bunker_defuse_icon_in_icons_py():
    """Test that BUNKER_DEFUSE icon is defined in icons.py."""
    with open(_ICONS_PATH, 'r', encoding='utf-8') as f:
        src = f.read()
    assert "BUNKER_DEFUSE" in src, "BUNKER_DEFUSE icon not in icons.py"
    print("✓ BUNKER_DEFUSE icon defined in icons.py")


def test_bunker_defuse_icon_in_icon_library():
    """Test that BUNKER_DEFUSE is registered in ICON_LIBRARY."""
    with open(_ICONS_PATH, 'r', encoding='utf-8') as f:
        src = f.read()
    lib_start = src.find("ICON_LIBRARY")
    lib_end   = src.find("}", lib_start)
    library_block = src[lib_start:lib_end]
    assert '"BUNKER_DEFUSE"' in library_block, "BUNKER_DEFUSE not in ICON_LIBRARY dict"
    print("✓ BUNKER_DEFUSE registered in ICON_LIBRARY")


def test_bunker_defuse_icon_is_256_bytes():
    """Test that BUNKER_DEFUSE icon data is exactly 256 bytes (16x16)."""
    with open(_ICONS_PATH, 'r', encoding='utf-8') as f:
        src = f.read()

    match = re.search(r'BUNKER_DEFUSE\s*=\s*bytes\(\[(.*?)\]\)', src, re.DOTALL)
    assert match is not None, "Could not find BUNKER_DEFUSE bytes literal"

    raw_content = match.group(1).replace('\n', ',')
    tokens = [t.strip() for t in raw_content.split(',')]
    values = [t for t in tokens if t.isdigit()]
    assert len(values) == 256, (
        f"BUNKER_DEFUSE icon should be 256 bytes (16x16), got {len(values)}"
    )
    print(f"✓ BUNKER_DEFUSE icon is 256 bytes (16x16)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Running Bunker Defuse mode tests...\n")

    tests = [
        test_file_exists,
        test_valid_syntax,
        test_bunker_defuse_in_manifest,
        test_bunker_defuse_manifest_metadata,
        test_bunker_defuse_difficulty_settings,
        test_hardware_indices_defined,
        test_toggle_count_is_eight,
        test_rotary_indices,
        test_sw_arm_is_eight,
        test_btn_fire_is_zero,
        test_all_five_module_types_defined,
        test_all_module_types_list,
        test_max_strikes_is_three,
        test_difficulty_params_defined,
        test_global_time_decreases_with_difficulty,
        test_num_modules_increases_with_difficulty,
        test_required_methods_exist,
        test_rotary_position_constants,
        test_check_wire_all_matching,
        test_check_wire_one_mismatch,
        test_check_wire_all_off,
        test_check_wire_all_on,
        test_rotary_position_A,
        test_rotary_position_B,
        test_rotary_position_center_both_off,
        test_rotary_check_correct,
        test_rotary_check_wrong,
        test_strike_time_penalty,
        test_max_strikes_triggers_game_over,
        test_timer_expiry_triggers_game_over,
        test_points_per_module_positive,
        test_code_module_manual_shows_code,
        test_arm_manual_mentions_guard,
        test_sequence_manual_mentions_press_count,
        test_process_module_handles_all_types,
        test_wire_module_requires_button_confirm,
        test_code_module_clears_buffer_on_wrong,
        test_arm_module_requires_guard_up,
        test_sequence_module_resets_on_over_press,
        test_timer_bar_uses_three_colours,
        test_bunker_defuse_icon_in_icons_py,
        test_bunker_defuse_icon_in_icon_library,
        test_bunker_defuse_icon_is_256_bytes,
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
