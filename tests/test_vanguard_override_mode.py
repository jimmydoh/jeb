"""Test module for Vanguard Override game mode.

Validates:
- Mode file existence and valid Python syntax
- Manifest registration with correct metadata
- Hardware index constants (toggles, rotary, momentary, button, encoder)
- Weapon type constants
- Difficulty parameter table
- Reactor overload threshold
- Icon presence and size in icons.py
- Key game-logic helpers (toggle reading, weapon type, EMP logic)
"""

import sys
import os
import ast
import re

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

_MODE_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'src', 'modes', 'vanguard_override.py'
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
    """Test that vanguard_override.py exists."""
    assert os.path.exists(_MODE_PATH), "vanguard_override.py does not exist"
    print("✓ vanguard_override.py exists")


def test_valid_syntax():
    """Test that vanguard_override.py has valid Python syntax."""
    src = _source()
    try:
        ast.parse(src)
    except SyntaxError as e:
        raise AssertionError(f"Syntax error in vanguard_override.py: {e}")
    print("✓ Valid Python syntax")


# ---------------------------------------------------------------------------
# Manifest checks
# ---------------------------------------------------------------------------

def test_vanguard_override_in_manifest():
    """Test that VANGUARD_OVERRIDE is registered in the mode manifest."""
    from modes.manifest import MODE_REGISTRY
    assert "VANGUARD_OVERRIDE" in MODE_REGISTRY, "VANGUARD_OVERRIDE not in MODE_REGISTRY"
    print("✓ VANGUARD_OVERRIDE found in MODE_REGISTRY")


def test_vanguard_override_manifest_metadata():
    """Test that VANGUARD_OVERRIDE manifest entry has all required fields."""
    from modes.manifest import MODE_REGISTRY
    meta = MODE_REGISTRY["VANGUARD_OVERRIDE"]

    assert meta["id"] == "VANGUARD_OVERRIDE"
    assert meta["module_path"] == "modes.vanguard_override"
    assert meta["class_name"] == "VanguardOverride"
    assert meta["icon"] == "VANGUARD_OVERRIDE"
    assert "CORE" in meta["requires"], "Must require CORE"
    assert "INDUSTRIAL" in meta["requires"], "Must require INDUSTRIAL satellite"
    assert meta.get("menu") == "EXP1", "Should appear in EXP1 menu"
    assert meta.get("has_tutorial") is True, "Should have a tutorial"
    print("✓ VANGUARD_OVERRIDE manifest metadata is correct")


def test_vanguard_override_difficulty_settings():
    """Test that VANGUARD_OVERRIDE has correct difficulty settings."""
    from modes.manifest import MODE_REGISTRY
    meta = MODE_REGISTRY["VANGUARD_OVERRIDE"]
    settings = meta.get("settings", [])

    diff = next((s for s in settings if s["key"] == "difficulty"), None)
    assert diff is not None, "Must have a difficulty setting"
    assert diff["label"] == "DIFF"
    assert "NORMAL" in diff["options"]
    assert "HARD" in diff["options"]
    assert "INSANE" in diff["options"]
    assert diff["default"] == "NORMAL"
    print("✓ VANGUARD_OVERRIDE difficulty settings are correct")


# ---------------------------------------------------------------------------
# Hardware index constant checks
# ---------------------------------------------------------------------------

def test_shield_toggle_constants():
    """Test that shield toggle start/end constants are defined correctly."""
    src = _source()
    assert "_SHIELD_TOGGLE_START" in src, "_SHIELD_TOGGLE_START missing"
    assert "_SHIELD_TOGGLE_END" in src, "_SHIELD_TOGGLE_END missing"

    start_match = re.search(r'_SHIELD_TOGGLE_START\s*=\s*(\d+)', src)
    end_match   = re.search(r'_SHIELD_TOGGLE_END\s*=\s*(\d+)', src)
    assert start_match and end_match, "Could not extract shield toggle constants"

    start = int(start_match.group(1))
    end   = int(end_match.group(1))
    assert start == 0, f"_SHIELD_TOGGLE_START should be 0, got {start}"
    assert end == 3,   f"_SHIELD_TOGGLE_END should be 3, got {end}"
    assert end - start + 1 == 4, "Shield toggles should span 4 positions"
    print(f"✓ Shield toggles: indices {start}-{end} (4 toggles)")


def test_weapon_toggle_constants():
    """Test that weapon toggle start/end constants are defined correctly."""
    src = _source()
    assert "_WEAPON_TOGGLE_START" in src, "_WEAPON_TOGGLE_START missing"
    assert "_WEAPON_TOGGLE_END" in src, "_WEAPON_TOGGLE_END missing"

    start_match = re.search(r'_WEAPON_TOGGLE_START\s*=\s*(\d+)', src)
    end_match   = re.search(r'_WEAPON_TOGGLE_END\s*=\s*(\d+)', src)
    assert start_match and end_match, "Could not extract weapon toggle constants"

    start = int(start_match.group(1))
    end   = int(end_match.group(1))
    assert start == 4, f"_WEAPON_TOGGLE_START should be 4, got {start}"
    assert end == 7,   f"_WEAPON_TOGGLE_END should be 7, got {end}"
    assert end - start + 1 == 4, "Weapon toggles should span 4 positions"
    print(f"✓ Weapon toggles: indices {start}-{end} (4 toggles)")


def test_rotary_switch_constants():
    """Test that 3-position rotary switch constants are defined at indices 10 and 11."""
    src = _source()
    assert "_SW_ROTARY_A" in src, "_SW_ROTARY_A missing"
    assert "_SW_ROTARY_B" in src, "_SW_ROTARY_B missing"

    a_match = re.search(r'_SW_ROTARY_A\s*=\s*(\d+)', src)
    b_match = re.search(r'_SW_ROTARY_B\s*=\s*(\d+)', src)
    assert a_match and b_match, "Could not extract rotary switch constants"

    assert int(a_match.group(1)) == 10, f"_SW_ROTARY_A should be 10"
    assert int(b_match.group(1)) == 11, f"_SW_ROTARY_B should be 11"
    print("✓ Rotary switch constants at indices 10 and 11")


def test_momentary_emp_constant():
    """Test that the momentary EMP toggle constant is defined."""
    src = _source()
    assert "_MT_EMP" in src, "_MT_EMP missing"
    mt_match = re.search(r'_MT_EMP\s*=\s*(\d+)', src)
    assert mt_match is not None, "_MT_EMP value not found"
    assert int(mt_match.group(1)) == 0, "_MT_EMP should be index 0"
    print("✓ _MT_EMP defined at index 0")


def test_fire_button_constant():
    """Test that the primary fire button constant is defined."""
    src = _source()
    assert "_BTN_FIRE" in src, "_BTN_FIRE missing"
    print("✓ _BTN_FIRE constant defined")


def test_encoder_constant():
    """Test that the ship encoder constant is defined."""
    src = _source()
    assert "_ENC_SHIP" in src, "_ENC_SHIP missing"
    print("✓ _ENC_SHIP constant defined")


# ---------------------------------------------------------------------------
# Weapon type constant checks
# ---------------------------------------------------------------------------

def test_weapon_type_constants():
    """Test that all three weapon type constants are defined."""
    src = _source()
    for const in ["WEAPON_LASER", "WEAPON_SPREAD", "WEAPON_MISSILE"]:
        assert const in src, f"Weapon type constant {const} missing"
    print("✓ All three weapon type constants defined (LASER, SPREAD, MISSILE)")


# ---------------------------------------------------------------------------
# Reactor overload threshold check
# ---------------------------------------------------------------------------

def test_overload_threshold():
    """Test that _OVERLOAD_THRESHOLD is defined and > 6 (max combined toggles without overload)."""
    src = _source()
    assert "_OVERLOAD_THRESHOLD" in src, "_OVERLOAD_THRESHOLD missing"
    match = re.search(r'_OVERLOAD_THRESHOLD\s*=\s*(\d+)', src)
    assert match is not None, "_OVERLOAD_THRESHOLD value not found"
    threshold = int(match.group(1))
    assert 6 <= threshold <= 8, \
        f"_OVERLOAD_THRESHOLD should be 6-8 (got {threshold}) to allow meaningful toggle play"
    print(f"✓ _OVERLOAD_THRESHOLD = {threshold}")


# ---------------------------------------------------------------------------
# EMP charge constants
# ---------------------------------------------------------------------------

def test_emp_charge_constants():
    """Test that EMP charge constants are defined."""
    src = _source()
    assert "_EMP_CHARGE_MAX" in src, "_EMP_CHARGE_MAX missing"
    assert "_EMP_CHARGE_RATE" in src, "_EMP_CHARGE_RATE missing"
    print("✓ EMP charge constants defined")


# ---------------------------------------------------------------------------
# Difficulty parameter table check
# ---------------------------------------------------------------------------

def test_difficulty_params():
    """Test that _DIFF_PARAMS defines NORMAL, HARD, INSANE."""
    src = _source()
    assert "_DIFF_PARAMS" in src, "_DIFF_PARAMS dict missing"
    for diff in ["NORMAL", "HARD", "INSANE"]:
        assert diff in src, f"Difficulty '{diff}' missing from _DIFF_PARAMS"
    print("✓ _DIFF_PARAMS defines NORMAL, HARD, INSANE")


def test_difficulty_lives_decrease():
    """Test that lives/starting HP decrease across difficulty levels."""
    src = _source()
    # Extract lives values for each difficulty
    normal_match = re.search(r'"NORMAL".*?"lives":\s*(\d+)', src, re.DOTALL)
    hard_match   = re.search(r'"HARD".*?"lives":\s*(\d+)', src, re.DOTALL)
    insane_match = re.search(r'"INSANE".*?"lives":\s*(\d+)', src, re.DOTALL)

    assert normal_match and hard_match and insane_match, "Could not extract 'lives' values"
    normal_lives = int(normal_match.group(1))
    hard_lives   = int(hard_match.group(1))
    insane_lives = int(insane_match.group(1))

    assert normal_lives >= hard_lives >= insane_lives, \
        f"Lives should decrease: NORMAL={normal_lives}, HARD={hard_lives}, INSANE={insane_lives}"
    assert insane_lives >= 1, "INSANE should have at least 1 life"
    print(f"✓ Lives decrease: NORMAL={normal_lives}, HARD={hard_lives}, INSANE={insane_lives}")


def test_difficulty_speed_increases():
    """Test that enemy speed scale increases across difficulty levels."""
    src = _source()
    normal_match = re.search(r'"NORMAL".*?"speed_scale":\s*([\d.]+)', src, re.DOTALL)
    hard_match   = re.search(r'"HARD".*?"speed_scale":\s*([\d.]+)', src, re.DOTALL)
    insane_match = re.search(r'"INSANE".*?"speed_scale":\s*([\d.]+)', src, re.DOTALL)

    assert normal_match and hard_match and insane_match, "Could not extract speed_scale values"
    normal_speed = float(normal_match.group(1))
    hard_speed   = float(hard_match.group(1))
    insane_speed = float(insane_match.group(1))

    assert normal_speed <= hard_speed <= insane_speed, \
        f"Speed should increase: NORMAL={normal_speed}, HARD={hard_speed}, INSANE={insane_speed}"
    print(f"✓ Speed increases: NORMAL={normal_speed}, HARD={hard_speed}, INSANE={insane_speed}")


# ---------------------------------------------------------------------------
# Key method existence checks
# ---------------------------------------------------------------------------

def test_required_methods_exist():
    """Test that all key game methods are defined."""
    src = _source()
    required = [
        "run",
        "run_tutorial",
        "_render",
        "_update_ship_position",
        "_update_bullets",
        "_update_enemies",
        "_update_enemy_bullets",
        "_spawn_player_bullets",
        "_spawn_enemy",
        "_read_power_toggles",
        "_read_weapon_type",
        "_is_emp_triggered",
        "_fire_emp",
        "_update_segment_display",
        "_send_segment",
        "_update_sat_leds",
        "_check_bullet_enemy_collisions",
        "_check_enemy_bullet_ship_collision",
        "_check_enemy_breach",
    ]
    for method in required:
        assert f"def {method}" in src, f"Method {method} missing"
    print(f"✓ All {len(required)} required methods are defined")


# ---------------------------------------------------------------------------
# Logic checks
# ---------------------------------------------------------------------------

def test_render_draws_all_entity_types():
    """Test that _render draws enemies, enemy bullets, player bullets, and ship."""
    src = _source()
    start = src.find("def _render")
    end = src.find("\n    def ", start + 1)
    if end == -1:
        end = src.find("\n    async def ", start + 1)
    body = src[start:end]

    assert "self.enemies" in body, "_render should draw enemies"
    assert "self.enemy_bullets" in body, "_render should draw enemy bullets"
    assert "self.bullets" in body, "_render should draw player bullets"
    assert "self.ship_x" in body, "_render should draw the player ship"
    print("✓ _render draws all entity types")


def test_overload_disables_weapons():
    """Test that the overload state disables weapon firing."""
    src = _source()
    # In the run() loop, firing should be gated on _overloaded
    run_start = src.find("async def run(")
    run_end   = src.find("\n    async def ", run_start + 1)
    if run_end == -1:
        run_end = src.find("\n    def ", run_start + 1)
    run_body = src[run_start:run_end]

    assert "_overloaded" in run_body, \
        "run() should check _overloaded before allowing fire"
    assert "not self._overloaded" in run_body or "if not self._overloaded" in run_body, \
        "Weapons must be disabled when overloaded"
    print("✓ Weapon firing is disabled during reactor overload")


def test_emp_requires_full_charge():
    """Test that EMP trigger requires emp_charge == max before firing."""
    src = _source()
    run_start = src.find("async def run(")
    run_end   = src.find("\n    async def ", run_start + 1)
    if run_end == -1:
        run_end = src.find("\n    def ", run_start + 1)
    run_body = src[run_start:run_end]

    assert "_is_emp_triggered" in run_body, \
        "run() should call _is_emp_triggered()"
    assert "emp_charge >= _EMP_CHARGE_MAX" in run_body or \
           "emp_charge >=" in run_body, \
        "EMP should only fire when charge is full"
    print("✓ EMP requires full charge to trigger")


def test_emp_clears_screen():
    """Test that _fire_emp clears both enemies and enemy_bullets."""
    src = _source()
    start = src.find("def _fire_emp")
    end   = src.find("\n    def ", start + 1)
    if end == -1:
        end = src.find("\n    async def ", start + 1)
    body = src[start:end]

    assert "self.enemies.clear()" in body, "_fire_emp should clear enemies"
    assert "self.enemy_bullets.clear()" in body, "_fire_emp should clear enemy_bullets"
    assert "self.emp_charge = 0" in body, "_fire_emp should reset emp_charge"
    print("✓ _fire_emp clears enemies, enemy bullets, and resets charge")


def test_shield_absorbs_hits():
    """Test that the run loop checks shield_power before applying damage."""
    src = _source()
    run_start = src.find("async def run(")
    run_end   = src.find("\n    async def ", run_start + 1)
    if run_end == -1:
        run_end = src.find("\n    def ", run_start + 1)
    run_body = src[run_start:run_end]

    assert "shield_power" in run_body, "run() should read shield_power"
    assert "shield_power > 0" in run_body or "shield_power >= 1" in run_body, \
        "Shields should absorb hits when shield_power > 0"
    print("✓ Shield power is checked when handling incoming hits")


def test_weapon_type_uses_rotary():
    """Test that _read_weapon_type reads from _SW_ROTARY_A and _SW_ROTARY_B."""
    src = _source()
    start = src.find("def _read_weapon_type")
    end   = src.find("\n    def ", start + 1)
    if end == -1:
        end = src.find("\n    async def ", start + 1)
    body = src[start:end]

    assert "_SW_ROTARY_A" in body, "_read_weapon_type should read _SW_ROTARY_A"
    assert "_SW_ROTARY_B" in body, "_read_weapon_type should read _SW_ROTARY_B"
    assert "WEAPON_LASER" in body and "WEAPON_SPREAD" in body and "WEAPON_MISSILE" in body, \
        "_read_weapon_type should return all three weapon types"
    print("✓ _read_weapon_type reads from both rotary constants and returns all 3 weapon types")


def test_segment_display_shows_emp():
    """Test that _update_segment_display reflects EMP charge."""
    src = _source()
    start = src.find("def _update_segment_display")
    end   = src.find("\n    def ", start + 1)
    if end == -1:
        end = src.find("\n    async def ", start + 1)
    body = src[start:end]

    assert "emp_charge" in body, "_update_segment_display should reference emp_charge"
    assert "_send_segment" in body, "_update_segment_display should call _send_segment"
    print("✓ _update_segment_display shows EMP charge level")


def test_sat_leds_updated_for_toggles():
    """Test that _update_sat_leds sends LED updates for shield and weapon toggles."""
    src = _source()
    start = src.find("def _update_sat_leds")
    end   = src.find("\n    def ", start + 1)
    if end == -1:
        end = src.find("\n    async def ", start + 1)
    body = src[start:end]

    assert "_SHIELD_TOGGLE_START" in body, "LEDs for shield toggles not updated"
    assert "_WEAPON_TOGGLE_START" in body, "LEDs for weapon toggles not updated"
    assert "sat.send" in body, "_update_sat_leds should send LED commands to satellite"
    print("✓ _update_sat_leds sends LED updates for both shield and weapon toggles")


# ---------------------------------------------------------------------------
# Icon checks
# ---------------------------------------------------------------------------

def test_vanguard_override_icon_in_icons_py():
    """Test that VANGUARD_OVERRIDE icon is defined in icons.py."""
    with open(_ICONS_PATH, 'r', encoding='utf-8') as f:
        src = f.read()
    assert "VANGUARD_OVERRIDE" in src, "VANGUARD_OVERRIDE icon not in icons.py"
    print("✓ VANGUARD_OVERRIDE icon defined in icons.py")


def test_vanguard_override_icon_in_icon_library():
    """Test that VANGUARD_OVERRIDE is registered in ICON_LIBRARY."""
    with open(_ICONS_PATH, 'r', encoding='utf-8') as f:
        src = f.read()
    lib_start = src.find("ICON_LIBRARY")
    lib_end   = src.find("}", lib_start)
    library_block = src[lib_start:lib_end]
    assert '"VANGUARD_OVERRIDE"' in library_block, \
        "VANGUARD_OVERRIDE not in ICON_LIBRARY dict"
    print("✓ VANGUARD_OVERRIDE registered in ICON_LIBRARY")


def test_vanguard_override_icon_is_256_bytes():
    """Test that VANGUARD_OVERRIDE icon data is exactly 256 bytes (16×16)."""
    with open(_ICONS_PATH, 'r', encoding='utf-8') as f:
        src = f.read()

    match = re.search(r'VANGUARD_OVERRIDE\s*=\s*bytes\(\[(.*?)\]\)', src, re.DOTALL)
    assert match is not None, "Could not find VANGUARD_OVERRIDE bytes literal"

    raw_content = match.group(1)
    # Strip inline comments
    raw_content = re.sub(r'#[^\n]*', '', raw_content)
    tokens = [t.strip() for t in raw_content.replace('\n', ',').split(',')]
    values = [t for t in tokens if t.isdigit()]
    assert len(values) == 256, \
        f"VANGUARD_OVERRIDE icon should be 256 bytes (16×16), got {len(values)}"
    print(f"✓ VANGUARD_OVERRIDE icon is 256 bytes (16×16)")


# ---------------------------------------------------------------------------
# Matrix / scoring constants check
# ---------------------------------------------------------------------------

def test_matrix_size_constants():
    """Test that matrix width/height are 16×16."""
    src = _source()
    w_match = re.search(r'_MATRIX_WIDTH\s*=\s*(\d+)', src)
    h_match = re.search(r'_MATRIX_HEIGHT\s*=\s*(\d+)', src)
    assert w_match and h_match, "_MATRIX_WIDTH/_MATRIX_HEIGHT not found"
    assert int(w_match.group(1)) == 16, "_MATRIX_WIDTH should be 16"
    assert int(h_match.group(1)) == 16, "_MATRIX_HEIGHT should be 16"
    print("✓ Matrix is 16×16")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Running Vanguard Override mode tests...\n")

    tests = [
        test_file_exists,
        test_valid_syntax,
        test_vanguard_override_in_manifest,
        test_vanguard_override_manifest_metadata,
        test_vanguard_override_difficulty_settings,
        test_shield_toggle_constants,
        test_weapon_toggle_constants,
        test_rotary_switch_constants,
        test_momentary_emp_constant,
        test_fire_button_constant,
        test_encoder_constant,
        test_weapon_type_constants,
        test_overload_threshold,
        test_emp_charge_constants,
        test_difficulty_params,
        test_difficulty_lives_decrease,
        test_difficulty_speed_increases,
        test_required_methods_exist,
        test_render_draws_all_entity_types,
        test_overload_disables_weapons,
        test_emp_requires_full_charge,
        test_emp_clears_screen,
        test_shield_absorbs_hits,
        test_weapon_type_uses_rotary,
        test_segment_display_shows_emp,
        test_sat_leds_updated_for_toggles,
        test_vanguard_override_icon_in_icons_py,
        test_vanguard_override_icon_in_icon_library,
        test_vanguard_override_icon_is_256_bytes,
        test_matrix_size_constants,
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
