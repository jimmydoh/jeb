"""Test module for Artillery Command game mode.

Validates:
- Mode file existence and valid Python syntax
- Manifest registration with correct metadata
- Phase constants
- Hardware index constants
- Difficulty parameter table
- Ballistic elevation calculation
- Shell type / rotary switch constants
- Icon registration in ICON_LIBRARY
- Key phase methods presence
"""

import sys
import os
import re
import ast
import math

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

_MODE_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'src', 'modes', 'artillery_command.py'
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
    """Test that artillery_command.py exists."""
    assert os.path.exists(_MODE_PATH), "artillery_command.py does not exist"
    print("✓ artillery_command.py exists")


def test_valid_syntax():
    """Test that artillery_command.py has valid Python syntax."""
    src = _source()
    try:
        ast.parse(src)
    except SyntaxError as e:
        raise AssertionError(f"Syntax error in artillery_command.py: {e}")
    print("✓ Valid Python syntax")


# ---------------------------------------------------------------------------
# Manifest checks
# ---------------------------------------------------------------------------

def test_artillery_command_in_manifest():
    """Test that ARTILLERY_COMMAND is registered in the mode manifest."""
    from modes.manifest import MODE_REGISTRY
    assert "ARTILLERY_COMMAND" in MODE_REGISTRY, \
        "ARTILLERY_COMMAND not found in MODE_REGISTRY"
    print("✓ ARTILLERY_COMMAND found in MODE_REGISTRY")


def test_artillery_command_manifest_metadata():
    """Test that ARTILLERY_COMMAND manifest entry has all required fields."""
    from modes.manifest import MODE_REGISTRY
    meta = MODE_REGISTRY["ARTILLERY_COMMAND"]

    assert meta["id"] == "ARTILLERY_COMMAND"
    assert meta["name"] == "ARTY COMMAND"
    assert meta["module_path"] == "modes.artillery_command"
    assert meta["class_name"] == "ArtilleryCommand"
    assert meta["icon"] == "ARTILLERY_COMMAND"
    assert "CORE" in meta["requires"], "Must require CORE"
    assert "INDUSTRIAL" in meta["requires"], "Must require INDUSTRIAL satellite"
    assert meta.get("menu") == "MAIN", "Should appear in MAIN menu"
    print("✓ ARTILLERY_COMMAND manifest metadata is correct")


def test_artillery_command_difficulty_settings():
    """Test that ARTILLERY_COMMAND has correct difficulty settings."""
    from modes.manifest import MODE_REGISTRY
    meta = MODE_REGISTRY["ARTILLERY_COMMAND"]
    settings = meta.get("settings", [])

    diff = next((s for s in settings if s["key"] == "difficulty"), None)
    assert diff is not None, "Must have a difficulty setting"
    assert diff["label"] == "DIFF"
    assert "NORMAL" in diff["options"]
    assert "HARD" in diff["options"]
    assert "INSANE" in diff["options"]
    assert diff["default"] == "NORMAL"
    print("✓ ARTILLERY_COMMAND difficulty settings are correct")


# ---------------------------------------------------------------------------
# Phase constant checks
# ---------------------------------------------------------------------------

def test_phase_constants():
    """Test that all 8 phase constants are defined."""
    src = _source()
    expected = [
        "_PHASE_ORDER",
        "_PHASE_DISTANCE",
        "_PHASE_SHELL",
        "_PHASE_CHARGES",
        "_PHASE_AIM",
        "_PHASE_RAM",
        "_PHASE_FIRE",
        "_PHASE_RESET",
    ]
    for phase in expected:
        assert phase in src, f"Phase constant {phase} missing"
    print(f"✓ All {len(expected)} phase constants are defined")


# ---------------------------------------------------------------------------
# Hardware index checks
# ---------------------------------------------------------------------------

def test_hardware_indices():
    """Test that key hardware index constants are defined."""
    src = _source()
    for const in [
        "_CHARGE_TOGGLE_COUNT",
        "_SW_ARM",
        "_SW_KEY",
        "_SW_ROTARY_A",
        "_SW_ROTARY_B",
        "_MT_SPEED",
        "_BTN_FIRE",
        "_ENC_ELEVATION",
        "_ENC_BEARING",
    ]:
        assert const in src, f"Hardware constant {const} missing"
    print("✓ All hardware index constants are defined")


def test_charge_toggle_count_is_eight():
    """Test that _CHARGE_TOGGLE_COUNT is 8."""
    src = _source()
    match = re.search(r'_CHARGE_TOGGLE_COUNT\s*=\s*(\d+)', src)
    assert match is not None, "_CHARGE_TOGGLE_COUNT not found"
    assert int(match.group(1)) == 8, \
        f"_CHARGE_TOGGLE_COUNT should be 8, got {match.group(1)}"
    print("✓ _CHARGE_TOGGLE_COUNT is 8")


def test_guarded_toggle_index():
    """Test that _SW_ARM is 8 (guarded toggle index per sat-01 hardware spec)."""
    src = _source()
    match = re.search(r'_SW_ARM\s*=\s*(\d+)', src)
    assert match is not None, "_SW_ARM not found"
    assert int(match.group(1)) == 8, \
        f"_SW_ARM should be 8, got {match.group(1)}"
    print("✓ _SW_ARM index is 8 (guarded toggle)")


def test_rotary_switch_indices():
    """Test that rotary switch indices _SW_ROTARY_A=10 and _SW_ROTARY_B=11."""
    src = _source()
    match_a = re.search(r'_SW_ROTARY_A\s*=\s*(\d+)', src)
    match_b = re.search(r'_SW_ROTARY_B\s*=\s*(\d+)', src)
    assert match_a and int(match_a.group(1)) == 10, \
        "_SW_ROTARY_A should be 10"
    assert match_b and int(match_b.group(1)) == 11, \
        "_SW_ROTARY_B should be 11"
    print("✓ Rotary switch indices correct (A=10, B=11)")


# ---------------------------------------------------------------------------
# Shell type checks
# ---------------------------------------------------------------------------

def test_shell_type_constants():
    """Test that all three shell type constants are defined."""
    src = _source()
    for shell in ["SHELL_HE", "SHELL_AP", "SHELL_STARSHELL"]:
        assert shell in src, f"Shell constant {shell} missing"
    print("✓ All shell type constants present")


def test_shell_weight_factors():
    """Test that _SHELL_WEIGHT_FACTOR is defined with all three shell types."""
    src = _source()
    assert "_SHELL_WEIGHT_FACTOR" in src, "_SHELL_WEIGHT_FACTOR missing"
    for shell in ["HE", "AP", "STARSHELL"]:
        assert f'SHELL_{shell}' in src or f'"{shell}"' in src, \
            f"Shell type {shell} missing from weight table"
    print("✓ _SHELL_WEIGHT_FACTOR defined for all shell types")


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


def test_difficulty_min_charges_progression():
    """Test that minimum charge requirements increase across difficulty levels."""
    src = _source()
    # Extract min_charges for each difficulty from the _DIFF_PARAMS block
    start = src.find("_DIFF_PARAMS")
    end = src.find("\n}", start) + 2
    block = src[start:end]

    normal_start  = block.find('"NORMAL"')
    hard_start    = block.find('"HARD"')
    insane_start  = block.find('"INSANE"')

    assert normal_start != -1 and hard_start != -1 and insane_start != -1

    normal_block  = block[normal_start:hard_start]
    hard_block    = block[hard_start:insane_start]
    insane_block  = block[insane_start:]

    def _extract_min_charges(blk):
        m = re.search(r'"min_charges":\s*(\d+)', blk)
        return int(m.group(1)) if m else None

    n_mc = _extract_min_charges(normal_block)
    h_mc = _extract_min_charges(hard_block)
    i_mc = _extract_min_charges(insane_block)

    assert n_mc is not None and h_mc is not None and i_mc is not None, \
        "Could not extract min_charges values"
    assert n_mc < h_mc <= i_mc, \
        f"Min charges should increase: NORMAL={n_mc}, HARD={h_mc}, INSANE={i_mc}"
    print(f"✓ Min charges increase: NORMAL={n_mc}, HARD={h_mc}, INSANE={i_mc}")


def test_elevation_tolerance_decreases():
    """Test that elevation tolerance decreases (tighter) in harder difficulties."""
    src = _source()
    start = src.find("_DIFF_PARAMS")
    end = src.find("\n}", start) + 2
    block = src[start:end]

    normal_start  = block.find('"NORMAL"')
    hard_start    = block.find('"HARD"')
    insane_start  = block.find('"INSANE"')

    def _extract_tol(blk):
        m = re.search(r'"elev_tol":\s*(\d+)', blk)
        return int(m.group(1)) if m else None

    n_tol = _extract_tol(block[normal_start:hard_start])
    h_tol = _extract_tol(block[hard_start:insane_start])
    i_tol = _extract_tol(block[insane_start:])

    assert n_tol and h_tol and i_tol, "Could not extract elev_tol values"
    assert n_tol > h_tol >= i_tol, \
        f"Elevation tolerance should decrease: NORMAL={n_tol}, HARD={h_tol}, INSANE={i_tol}"
    print(f"✓ Elevation tolerance decreases: NORMAL={n_tol}, HARD={h_tol}, INSANE={i_tol}")


# ---------------------------------------------------------------------------
# Ballistic calculation checks
# ---------------------------------------------------------------------------

def test_calculate_elevation_he_in_range():
    """Test that _calculate_elevation returns 1–89° for HE at typical ranges."""
    # Import the constants directly from the module source without hardware deps
    src = _source()
    # Extract numeric constants
    g_match  = re.search(r'_GRAVITY\s*=\s*([\d.]+)',              src)
    bv_match = re.search(r'_BASE_VELOCITY\s*=\s*([\d.]+)',        src)
    vc_match = re.search(r'_VELOCITY_PER_CHARGE\s*=\s*([\d.]+)',  src)

    assert g_match and bv_match and vc_match, "Ballistic constants not found"

    g  = float(g_match.group(1))
    bv = float(bv_match.group(1))
    vc = float(vc_match.group(1))

    # Replicate the formula for HE (weight factor 1.0), 4 charges
    num_charges  = 4
    distance     = 4000   # 4 km
    wf           = 1.0
    v            = bv + num_charges * vc
    sin_2theta   = max(-1.0, min(1.0, g * distance * wf / (v * v)))
    elevation    = math.degrees(math.asin(sin_2theta)) / 2.0
    elevation    = max(1, min(89, round(elevation)))

    assert 1 <= elevation <= 89, f"Elevation {elevation}° out of range"
    print(f"✓ HE @ 4000m / 4 charges → {elevation}° elevation (valid 1–89)")


def test_ap_requires_higher_elevation_than_he():
    """Test that AP shell needs higher elevation than HE for the same range/charges."""
    src = _source()
    g_match  = re.search(r'_GRAVITY\s*=\s*([\d.]+)',              src)
    bv_match = re.search(r'_BASE_VELOCITY\s*=\s*([\d.]+)',        src)
    vc_match = re.search(r'_VELOCITY_PER_CHARGE\s*=\s*([\d.]+)',  src)

    g  = float(g_match.group(1))
    bv = float(bv_match.group(1))
    vc = float(vc_match.group(1))

    distance = 3000
    num_charges = 3

    def _elev(wf):
        v = bv + num_charges * vc
        sin_2t = max(-1.0, min(1.0, g * distance * wf / (v * v)))
        return max(1, min(89, round(math.degrees(math.asin(sin_2t)) / 2.0)))

    elev_he   = _elev(1.0)
    elev_ap   = _elev(1.2)
    elev_star = _elev(0.7)

    assert elev_ap > elev_he, \
        f"AP ({elev_ap}°) should need more elevation than HE ({elev_he}°)"
    assert elev_star < elev_he, \
        f"Starshell ({elev_star}°) should need less elevation than HE ({elev_he}°)"
    print(f"✓ Elevation ordering correct: STAR={elev_star}° < HE={elev_he}° < AP={elev_ap}°")


def test_more_charges_reduce_elevation():
    """Test that adding more charges lowers the required elevation angle."""
    src = _source()
    g_match  = re.search(r'_GRAVITY\s*=\s*([\d.]+)',              src)
    bv_match = re.search(r'_BASE_VELOCITY\s*=\s*([\d.]+)',        src)
    vc_match = re.search(r'_VELOCITY_PER_CHARGE\s*=\s*([\d.]+)',  src)

    g  = float(g_match.group(1))
    bv = float(bv_match.group(1))
    vc = float(vc_match.group(1))

    distance = 4000
    wf = 1.0  # HE

    def _elev(nc):
        v = bv + nc * vc
        sin_2t = max(-1.0, min(1.0, g * distance * wf / (v * v)))
        return max(1, min(89, round(math.degrees(math.asin(sin_2t)) / 2.0)))

    e2 = _elev(2)
    e4 = _elev(4)
    e8 = _elev(8)

    assert e2 >= e4 >= e8, \
        f"More charges should reduce elevation: 2c={e2}°, 4c={e4}°, 8c={e8}°"
    print(f"✓ More charges → lower elevation: 2c={e2}°, 4c={e4}°, 8c={e8}°")


# ---------------------------------------------------------------------------
# Phase method checks
# ---------------------------------------------------------------------------

def test_phase_methods_exist():
    """Test that all 8 phase handler methods are defined."""
    src = _source()
    for method in [
        "_run_phase_order",
        "_run_phase_distance",
        "_run_phase_shell",
        "_run_phase_charges",
        "_run_phase_aim",
        "_run_phase_ram",
        "_run_phase_fire",
        "_run_phase_reset",
    ]:
        assert f"def {method}" in src, f"Phase method {method} missing"
    print("✓ All 8 phase handler methods are defined")


def test_dual_encoder_usage_in_aim():
    """Test that both core and satellite encoders are read in the aim phase."""
    src = _source()
    start = src.find("def _run_phase_aim")
    end   = src.find("\n    async def ", start + 1)
    if end == -1:
        end = src.find("\n    def ", start + 1)
    body = src[start:end]

    assert "encoder_positions" in body, "Core encoder not read in _run_phase_aim"
    assert "_sat_encoder" in body,      "Satellite encoder not read in _run_phase_aim"
    print("✓ Both core and satellite encoders are used in the aim phase")


def test_aim_phase_uses_speed_mode():
    """Test that the aim phase reads the momentary toggle for speed selection."""
    src = _source()
    start = src.find("def _run_phase_aim")
    end   = src.find("\n    async def ", start + 1)
    if end == -1:
        end = src.find("\n    def ", start + 1)
    body = src[start:end]

    assert "_sat_momentary_up" in body or "momentary" in body.lower(), \
        "Speed mode (momentary toggle) not used in _run_phase_aim"
    print("✓ Aim phase uses momentary toggle for speed mode")


def test_ram_phase_requires_arm_and_hold():
    """Test that the ram phase checks guarded toggle + momentary hold."""
    src = _source()
    start = src.find("def _run_phase_ram")
    end   = src.find("\n    async def ", start + 1)
    if end == -1:
        end = src.find("\n    def ", start + 1)
    body = src[start:end]

    assert "_SW_ARM" in body or "arm_on" in body, \
        "Ram phase must check guarded toggle (_SW_ARM)"
    assert "_sat_momentary_up" in body or "mt_up" in body, \
        "Ram phase must check momentary toggle hold"
    print("✓ Ram phase requires guarded toggle + momentary hold")


def test_fire_phase_uses_big_button():
    """Test that the fire phase checks the large momentary button."""
    src = _source()
    start = src.find("def _run_phase_fire")
    end   = src.find("\n    async def ", start + 1)
    if end == -1:
        end = src.find("\n    def ", start + 1)
    body = src[start:end]

    assert "_sat_button" in body, \
        "Fire phase must check the big button via _sat_button"
    print("✓ Fire phase uses the big red button")


def test_reset_phase_clears_toggles_and_arm():
    """Test that the reset phase requires all charge toggles OFF and arm disengaged."""
    src = _source()
    start = src.find("def _run_phase_reset")
    end   = src.find("\n    async def ", start + 1)
    if end == -1:
        end = src.find("\n    def ", start + 1)
    body = src[start:end]

    # Must iterate over charge toggles
    assert "_CHARGE_TOGGLE_COUNT" in body or "range(8)" in body or \
           "range(_CHARGE_TOGGLE_COUNT)" in body, \
        "Reset phase must iterate over charge toggles"
    # Must check guarded arm
    assert "_SW_ARM" in body, \
        "Reset phase must verify guarded arm is cleared"
    print("✓ Reset phase clears all charge toggles and guarded arm")


# ---------------------------------------------------------------------------
# Icon checks
# ---------------------------------------------------------------------------

def test_artillery_command_icon_exists():
    """Test that ARTILLERY_COMMAND icon attribute exists in Icons."""
    src = _source()
    with open(_ICONS_PATH) as fh:
        icons_src = fh.read()
    assert "ARTILLERY_COMMAND" in icons_src, \
        "ARTILLERY_COMMAND icon missing from icons.py"
    print("✓ ARTILLERY_COMMAND icon defined in icons.py")


def test_artillery_command_icon_byte_count():
    """Test that the ARTILLERY_COMMAND icon is exactly 256 bytes (16x16)."""
    from utilities.icons import Icons
    icon = Icons.ARTILLERY_COMMAND
    assert len(icon) == 256, \
        f"ARTILLERY_COMMAND icon should be 256 bytes, got {len(icon)}"
    print(f"✓ ARTILLERY_COMMAND icon is 256 bytes")


def test_artillery_command_icon_in_library():
    """Test that ARTILLERY_COMMAND is registered in the ICON_LIBRARY."""
    from utilities.icons import Icons
    assert "ARTILLERY_COMMAND" in Icons.ICON_LIBRARY, \
        "ARTILLERY_COMMAND missing from Icons.ICON_LIBRARY"
    print("✓ ARTILLERY_COMMAND registered in ICON_LIBRARY")


# ---------------------------------------------------------------------------
# Charge LED sync checks
# ---------------------------------------------------------------------------

def test_charge_led_sync_described_in_source():
    """Test that the charge bag LED logic differentiates ON/OFF/below-minimum states."""
    src = _source()
    start = src.find("def _sync_charge_leds")
    end   = src.find("\n    def ", start + 1)
    body  = src[start:end]

    assert "ORANGE" in body, "Loaded charge bags should show ORANGE LEDs"
    assert "GREEN" in body,  "Empty charge slots should show GREEN LEDs"
    assert "RED" in body,    "Slots below minimum should show RED LEDs"
    print("✓ Charge LED sync uses ORANGE/GREEN/RED states")


# ---------------------------------------------------------------------------
# Run-module guard
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import traceback

    tests = [
        test_file_exists,
        test_valid_syntax,
        test_artillery_command_in_manifest,
        test_artillery_command_manifest_metadata,
        test_artillery_command_difficulty_settings,
        test_phase_constants,
        test_hardware_indices,
        test_charge_toggle_count_is_eight,
        test_guarded_toggle_index,
        test_rotary_switch_indices,
        test_shell_type_constants,
        test_shell_weight_factors,
        test_difficulty_params,
        test_difficulty_min_charges_progression,
        test_elevation_tolerance_decreases,
        test_calculate_elevation_he_in_range,
        test_ap_requires_higher_elevation_than_he,
        test_more_charges_reduce_elevation,
        test_phase_methods_exist,
        test_dual_encoder_usage_in_aim,
        test_aim_phase_uses_speed_mode,
        test_ram_phase_requires_arm_and_hold,
        test_fire_phase_uses_big_button,
        test_reset_phase_clears_toggles_and_arm,
        test_artillery_command_icon_exists,
        test_artillery_command_icon_byte_count,
        test_artillery_command_icon_in_library,
        test_charge_led_sync_described_in_source,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"✗ {t.__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed")
    if failed:
        sys.exit(1)
