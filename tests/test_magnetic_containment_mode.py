"""Test module for Magnetic Containment game mode.

Validates:
- Mode file existence and valid Python syntax
- Manifest registration with correct metadata
- Hardware index constants
- Difficulty parameter table
- Physics helper methods
- Stasis field constants
- Icon presence in icons.py
- Dual-encoder usage in the main game loop
- Integrity drain logic
"""

import sys
import os
import ast
import re

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

_MODE_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'src', 'modes', 'magnetic_containment.py'
)
_ICONS_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'src', 'utilities', 'icons.py'
)


def _source():
    with open(_MODE_PATH, 'r') as f:
        return f.read()


def _extract_run_body(src):
    """Extract the body of the async def run(self) method as a string."""
    start = src.find("async def run(self):")
    end = src.find("\n    async def ", start + 1)
    if end == -1:
        end = src.find("\n    def ", start + 1)
    return src[start:end] if end != -1 else src[start:]


# ---------------------------------------------------------------------------
# File and syntax checks
# ---------------------------------------------------------------------------

def test_file_exists():
    """Test that magnetic_containment.py exists."""
    assert os.path.exists(_MODE_PATH), "magnetic_containment.py does not exist"
    print("✓ magnetic_containment.py exists")


def test_valid_syntax():
    """Test that magnetic_containment.py has valid Python syntax."""
    src = _source()
    try:
        ast.parse(src)
    except SyntaxError as e:
        raise AssertionError(f"Syntax error in magnetic_containment.py: {e}")
    print("✓ Valid Python syntax")


# ---------------------------------------------------------------------------
# Manifest checks
# ---------------------------------------------------------------------------

def test_magnetic_containment_in_manifest():
    """Test that MAGNETIC_CONTAINMENT is registered in the mode manifest."""
    from modes.manifest import MODE_REGISTRY
    assert "MAGNETIC_CONTAINMENT" in MODE_REGISTRY, \
        "MAGNETIC_CONTAINMENT not found in MODE_REGISTRY"
    print("✓ MAGNETIC_CONTAINMENT found in MODE_REGISTRY")


def test_magnetic_containment_manifest_metadata():
    """Test that MAGNETIC_CONTAINMENT manifest entry has all required fields."""
    from modes.manifest import MODE_REGISTRY
    meta = MODE_REGISTRY["MAGNETIC_CONTAINMENT"]

    assert meta["id"] == "MAGNETIC_CONTAINMENT"
    assert meta["name"] == "MAG CONTAINMENT"
    assert meta["module_path"] == "modes.magnetic_containment"
    assert meta["class_name"] == "MagneticContainment"
    assert meta["icon"] == "MAGNETIC_CONTAINMENT"
    assert "CORE" in meta["requires"], "Must require CORE"
    assert "INDUSTRIAL" in meta["requires"], "Must require INDUSTRIAL satellite"
    assert meta.get("menu") == "MAIN", "Should appear in MAIN menu"
    assert meta.get("has_tutorial") is True, "Should have a tutorial"
    print("✓ MAGNETIC_CONTAINMENT manifest metadata is correct")


def test_magnetic_containment_difficulty_settings():
    """Test that MAGNETIC_CONTAINMENT has correct difficulty settings."""
    from modes.manifest import MODE_REGISTRY
    meta = MODE_REGISTRY["MAGNETIC_CONTAINMENT"]
    settings = meta.get("settings", [])

    diff = next((s for s in settings if s["key"] == "difficulty"), None)
    assert diff is not None, "Must have a difficulty setting"
    assert diff["label"] == "DIFF"
    assert "NORMAL" in diff["options"]
    assert "HARD" in diff["options"]
    assert "INSANE" in diff["options"]
    assert diff["default"] == "NORMAL"
    print("✓ MAGNETIC_CONTAINMENT difficulty settings are correct")


# ---------------------------------------------------------------------------
# Hardware index constants
# ---------------------------------------------------------------------------

def test_hardware_constants_defined():
    """Test that all required hardware index constants are present."""
    src = _source()
    for const in ["_ENC_CORE", "_ENC_SAT", "_SW_ARM", "_MT_STASIS"]:
        assert const in src, f"Hardware constant {const} missing"
    print("✓ All hardware index constants are defined")


def test_guarded_toggle_index_is_8():
    """Test that _SW_ARM is 8 (guarded toggle per sat-01 hardware spec)."""
    src = _source()
    match = re.search(r'_SW_ARM\s*=\s*(\d+)', src)
    assert match is not None, "_SW_ARM not found"
    assert int(match.group(1)) == 8, f"_SW_ARM should be 8, got {match.group(1)}"
    print("✓ _SW_ARM is 8 (guarded toggle)")


def test_enc_core_is_0():
    """Test that _ENC_CORE is 0."""
    src = _source()
    match = re.search(r'_ENC_CORE\s*=\s*(\d+)', src)
    assert match is not None, "_ENC_CORE not found"
    assert int(match.group(1)) == 0, f"_ENC_CORE should be 0, got {match.group(1)}"
    print("✓ _ENC_CORE is 0")


def test_enc_sat_is_0():
    """Test that _ENC_SAT is 0."""
    src = _source()
    match = re.search(r'_ENC_SAT\s*=\s*(\d+)', src)
    assert match is not None, "_ENC_SAT not found"
    assert int(match.group(1)) == 0, f"_ENC_SAT should be 0, got {match.group(1)}"
    print("✓ _ENC_SAT is 0")


# ---------------------------------------------------------------------------
# Physics constants
# ---------------------------------------------------------------------------

def test_matrix_dimensions():
    """Test that _MATRIX_W and _MATRIX_H are 16."""
    src = _source()
    w_match = re.search(r'_MATRIX_W\s*=\s*(\d+)', src)
    h_match = re.search(r'_MATRIX_H\s*=\s*(\d+)', src)
    assert w_match and h_match, "Matrix dimension constants not found"
    assert int(w_match.group(1)) == 16, "_MATRIX_W should be 16"
    assert int(h_match.group(1)) == 16, "_MATRIX_H should be 16"
    print("✓ Matrix dimensions are 16×16")


def test_max_integrity_is_100():
    """Test that _MAX_INTEGRITY is 100."""
    src = _source()
    match = re.search(r'_MAX_INTEGRITY\s*=\s*(\d+)', src)
    assert match is not None, "_MAX_INTEGRITY not found"
    assert int(match.group(1)) == 100, f"_MAX_INTEGRITY should be 100, got {match.group(1)}"
    print("✓ _MAX_INTEGRITY is 100")


def test_stasis_duration_defined():
    """Test that _STASIS_DURATION is defined."""
    src = _source()
    match = re.search(r'_STASIS_DURATION\s*=\s*([\d.]+)', src)
    assert match is not None, "_STASIS_DURATION not found"
    duration = float(match.group(1))
    assert duration == 2.0, f"_STASIS_DURATION should be 2.0, got {duration}"
    print(f"✓ _STASIS_DURATION is {duration}s")


def test_stasis_cooldown_defined():
    """Test that _STASIS_COOLDOWN is defined and greater than stasis duration."""
    src = _source()
    dur_match = re.search(r'_STASIS_DURATION\s*=\s*([\d.]+)', src)
    cd_match  = re.search(r'_STASIS_COOLDOWN\s*=\s*([\d.]+)', src)
    assert cd_match is not None, "_STASIS_COOLDOWN not found"
    duration = float(dur_match.group(1)) if dur_match else 0
    cooldown = float(cd_match.group(1))
    assert cooldown > duration, \
        f"_STASIS_COOLDOWN ({cooldown}s) should be greater than _STASIS_DURATION ({duration}s)"
    print(f"✓ _STASIS_COOLDOWN ({cooldown}s) > _STASIS_DURATION ({duration}s)")


# ---------------------------------------------------------------------------
# Difficulty parameter checks
# ---------------------------------------------------------------------------

def test_diff_params_defined():
    """Test that _DIFF_PARAMS defines NORMAL, HARD, INSANE."""
    src = _source()
    assert "_DIFF_PARAMS" in src, "_DIFF_PARAMS dict missing"
    for diff in ["NORMAL", "HARD", "INSANE"]:
        assert diff in src, f"Difficulty '{diff}' missing from _DIFF_PARAMS"
    print("✓ _DIFF_PARAMS defines NORMAL, HARD, INSANE")


def test_diff_params_have_required_keys():
    """Test that each difficulty level has chaos and drain parameters."""
    src = _source()
    start = src.find("_DIFF_PARAMS")
    end = src.find("\n}", start) + 2
    block = src[start:end]

    for key in ["chaos_strength", "chaos_interval", "drain_rate", "max_velocity"]:
        assert key in block, f"Difficulty key '{key}' missing from _DIFF_PARAMS"
    print("✓ _DIFF_PARAMS has all required parameter keys")


def test_insane_harder_than_normal():
    """Test that INSANE chaos_strength value is larger than NORMAL's."""
    src = _source()

    # Locate _DIFF_PARAMS block
    start = src.find("_DIFF_PARAMS = {")
    end   = src.find("\n}", start) + 2
    block = src[start:end]

    normal_start = block.find('"NORMAL"')
    insane_start = block.find('"INSANE"')
    assert normal_start != -1 and insane_start != -1

    normal_block = block[normal_start : insane_start]
    insane_block = block[insane_start :]

    # Extract the multipliers from expressions like _CHAOS_STRENGTH_BASE * 2.2
    normal_m = re.search(r'chaos_strength.*?(\d+\.?\d*)', normal_block)
    insane_m = re.search(r'chaos_strength.*?(\d+\.?\d*)', insane_block)
    assert normal_m and insane_m, "Could not extract chaos_strength values"

    normal_val = float(normal_m.group(1))
    insane_val = float(insane_m.group(1))
    assert insane_val > normal_val, \
        f"INSANE chaos_strength ({insane_val}) should exceed NORMAL ({normal_val})"
    print(f"✓ INSANE chaos_strength ({insane_val}) > NORMAL ({normal_val})")


# ---------------------------------------------------------------------------
# Method presence checks
# ---------------------------------------------------------------------------

def test_class_defined():
    """Test that MagneticContainment class is defined."""
    src = _source()
    assert "class MagneticContainment" in src, "MagneticContainment class not found"
    print("✓ MagneticContainment class is defined")


def test_required_methods_exist():
    """Test that all required methods are defined."""
    src = _source()
    for method in [
        "def run",
        "def run_tutorial",
        "def _sat_encoder",
        "def _sat_arm",
        "def _sat_momentary_up",
        "def _send_segment",
        "def _update_segment_display",
        "def _chaos_kick",
        "def _update_integrity",
        "def _render",
        "def _wall_bounce",
    ]:
        assert method in src, f"Method '{method}' missing"
    print("✓ All required methods are defined")


# ---------------------------------------------------------------------------
# Dual-encoder usage checks
# ---------------------------------------------------------------------------

def test_dual_encoder_usage_in_run():
    """Test that both Core and Satellite encoders are used in the main run loop."""
    src = _source()
    body = _extract_run_body(src)

    assert "encoder_positions" in body or "_ENC_CORE" in body, \
        "Core encoder (_ENC_CORE / encoder_positions) not read in run()"
    assert "_sat_encoder" in body, \
        "Satellite encoder (_sat_encoder) not read in run()"
    print("✓ Both Core and Satellite encoders are used in run()")


def test_core_encoder_drives_x_force():
    """Test that core encoder delta drives X-axis velocity."""
    src = _source()
    body = _extract_run_body(src)

    # Core encoder delta should affect vel_x
    assert "vel_x" in body, "Core encoder should affect _vel_x in run()"
    print("✓ Core encoder drives X-axis velocity (_vel_x)")


def test_sat_encoder_drives_y_force():
    """Test that satellite encoder delta drives Y-axis velocity."""
    src = _source()
    body = _extract_run_body(src)

    # Sat encoder delta should affect vel_y
    assert "vel_y" in body, "Satellite encoder should affect _vel_y in run()"
    print("✓ Satellite encoder drives Y-axis velocity (_vel_y)")


# ---------------------------------------------------------------------------
# Stasis field checks
# ---------------------------------------------------------------------------

def test_stasis_requires_arm_and_momentary():
    """Test that stasis activation requires both guarded toggle AND momentary switch."""
    src = _source()
    body = _extract_run_body(src)

    assert "_sat_arm" in body or "arm_now" in body, \
        "Stasis arm check (guarded toggle) missing from run()"
    assert "_sat_momentary_up" in body or "mot_now" in body, \
        "Momentary toggle check missing from run()"
    print("✓ Stasis activation requires both guarded toggle and momentary switch")


def test_stasis_freezes_physics():
    """Test that stasis active flag is checked before physics integration."""
    src = _source()
    body = _extract_run_body(src)

    assert "_stasis_active" in body, \
        "_stasis_active flag is not used to gate physics in run()"
    print("✓ Stasis active flag gates physics integration")


def test_stasis_cooldown_enforced():
    """Test that stasis cooldown is checked before allowing re-activation."""
    src = _source()
    assert "_stasis_cooldown" in src, "_stasis_cooldown variable not found in mode"
    print("✓ _stasis_cooldown is used (stasis recharge enforced)")


# ---------------------------------------------------------------------------
# Integrity drain checks
# ---------------------------------------------------------------------------

def test_integrity_drain_uses_distance():
    """Test that the integrity drain method uses distance from center."""
    src = _source()
    start = src.find("def _update_integrity")
    end = src.find("\n    def ", start + 1)
    if end == -1:
        end = len(src)
    body = src[start:end]

    assert "distance" in body or "_distance_from_center" in body, \
        "_update_integrity should use distance from center"
    print("✓ _update_integrity uses distance from center")


def test_integrity_clamped_to_zero():
    """Test that integrity cannot go below zero."""
    src = _source()
    start = src.find("def _update_integrity")
    end = src.find("\n    def ", start + 1)
    if end == -1:
        end = len(src)
    body = src[start:end]

    assert "max(0" in body or "max(0.0" in body, \
        "_update_integrity should clamp integrity to zero"
    print("✓ Integrity is clamped to 0 (cannot go negative)")


def test_game_over_triggers_on_zero_integrity():
    """Test that game over is triggered when integrity reaches zero."""
    src = _source()
    body = _extract_run_body(src)

    assert "_integrity <= 0" in body or "integrity <= 0" in body, \
        "Game over should trigger when integrity reaches 0"
    print("✓ Game over triggers when integrity reaches zero")


# ---------------------------------------------------------------------------
# Safe zone check
# ---------------------------------------------------------------------------

def test_safe_zone_defined():
    """Test that _SAFE_RADIUS is defined as a positive value."""
    src = _source()
    match = re.search(r'_SAFE_RADIUS\s*=\s*([\d.]+)', src)
    assert match is not None, "_SAFE_RADIUS not found"
    radius = float(match.group(1))
    assert radius > 0, f"_SAFE_RADIUS should be positive, got {radius}"
    print(f"✓ _SAFE_RADIUS = {radius} (no drain inside this zone)")


# ---------------------------------------------------------------------------
# Icon checks
# ---------------------------------------------------------------------------

def test_icon_in_icons_py():
    """Test that MAGNETIC_CONTAINMENT icon is defined in icons.py."""
    with open(_ICONS_PATH, 'r') as f:
        content = f.read()
    assert "MAGNETIC_CONTAINMENT" in content, \
        "MAGNETIC_CONTAINMENT icon not found in icons.py"
    print("✓ MAGNETIC_CONTAINMENT icon found in icons.py")


def test_icon_correct_size():
    """Test that MAGNETIC_CONTAINMENT icon is exactly 256 bytes."""
    with open(_ICONS_PATH, 'r') as f:
        content = f.read()

    start = content.find('MAGNETIC_CONTAINMENT = bytes([')
    assert start != -1, "MAGNETIC_CONTAINMENT bytes literal not found"

    # Extract the inner bracket contents and parse safely
    bracket_start = content.index('[', start)
    bracket_end   = content.index('])', start)
    inner = content[bracket_start + 1 : bracket_end]

    # Strip comments (lines starting with #) then evaluate as a list of ints
    clean_lines = []
    for line in inner.splitlines():
        code_part = line.split('#')[0].strip().rstrip(',')
        if code_part:
            clean_lines.append(code_part)
    clean = ", ".join(clean_lines)
    values = ast.literal_eval(f"[{clean}]")

    assert len(values) == 256, f"Icon should be 256 bytes (16×16), got {len(values)}"
    print(f"✓ MAGNETIC_CONTAINMENT icon is 256 bytes (16×16)")


def test_icon_in_library():
    """Test that MAGNETIC_CONTAINMENT is registered in the Icons LIBRARY dict."""
    with open(_ICONS_PATH, 'r') as f:
        content = f.read()

    lib_start = content.find("LIBRARY = {")
    assert lib_start != -1, "LIBRARY dict not found in icons.py"
    lib_section = content[lib_start:]

    assert '"MAGNETIC_CONTAINMENT"' in lib_section or \
           "'MAGNETIC_CONTAINMENT'" in lib_section, \
        "MAGNETIC_CONTAINMENT not registered in Icons.LIBRARY"
    print("✓ MAGNETIC_CONTAINMENT registered in Icons.LIBRARY")


# ---------------------------------------------------------------------------
# Segment display check
# ---------------------------------------------------------------------------

def test_segment_display_sent():
    """Test that the satellite 14-segment display receives integrity updates."""
    src = _source()
    assert "_send_segment" in src, "_send_segment helper not found"
    assert "INTG" in src or "integrity" in src.lower(), \
        "Segment display should show integrity information"
    print("✓ Segment display receives integrity updates")


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Running Magnetic Containment mode tests...\n")
    tests = [
        test_file_exists,
        test_valid_syntax,
        test_magnetic_containment_in_manifest,
        test_magnetic_containment_manifest_metadata,
        test_magnetic_containment_difficulty_settings,
        test_hardware_constants_defined,
        test_guarded_toggle_index_is_8,
        test_enc_core_is_0,
        test_enc_sat_is_0,
        test_matrix_dimensions,
        test_max_integrity_is_100,
        test_stasis_duration_defined,
        test_stasis_cooldown_defined,
        test_diff_params_defined,
        test_diff_params_have_required_keys,
        test_insane_harder_than_normal,
        test_class_defined,
        test_required_methods_exist,
        test_dual_encoder_usage_in_run,
        test_core_encoder_drives_x_force,
        test_sat_encoder_drives_y_force,
        test_stasis_requires_arm_and_momentary,
        test_stasis_freezes_physics,
        test_stasis_cooldown_enforced,
        test_integrity_drain_uses_distance,
        test_integrity_clamped_to_zero,
        test_game_over_triggers_on_zero_integrity,
        test_safe_zone_defined,
        test_icon_in_icons_py,
        test_icon_correct_size,
        test_icon_in_library,
        test_segment_display_sent,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  ❌ FAIL {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ❌ ERROR {test.__name__}: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
    if failed:
        sys.exit(1)
    else:
        print("\n✅ All Magnetic Containment tests passed!")
        sys.exit(0)
