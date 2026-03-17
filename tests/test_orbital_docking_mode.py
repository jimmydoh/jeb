"""Tests for Orbital Docking Simulator game mode.

Validates:
- Mode file existence and valid Python syntax
- Manifest registration with correct metadata
- Physics constants and helpers
- Hardware index constants
- Clamp sequence logic
- Icon registration in icons.py
"""

import sys
import os
import ast
import re

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# ---------------------------------------------------------------------------
# Stub out CircuitPython-specific modules before any src imports
# ---------------------------------------------------------------------------
_MOCK_MOD_NAMES = [
    'digitalio', 'busio', 'board', 'adafruit_mcp230xx',
    'adafruit_mcp230xx.mcp23017', 'adafruit_ticks', 'audiobusio',
    'audiocore', 'audiomixer', 'analogio', 'microcontroller', 'watchdog',
    'audiopwmio', 'synthio', 'ulab', 'neopixel',
    'adafruit_displayio_ssd1306', 'adafruit_display_text',
    'adafruit_display_text.label', 'adafruit_ht16k33',
    'adafruit_ht16k33.segments', 'displayio', 'terminalio',
]

from unittest.mock import MagicMock
for _mod in _MOCK_MOD_NAMES:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

import time as _time
sys.modules['adafruit_ticks'].ticks_ms = lambda: int(_time.monotonic() * 1000)
sys.modules['adafruit_ticks'].ticks_diff = lambda a, b: a - b

_MODE_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'src', 'modes', 'orbital_docking.py'
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
    """The orbital_docking.py source file must exist."""
    assert os.path.exists(_MODE_PATH), "orbital_docking.py does not exist"
    print("✓ orbital_docking.py exists")


def test_valid_syntax():
    """orbital_docking.py must have valid Python syntax."""
    src = _source()
    try:
        ast.parse(src)
    except SyntaxError as e:
        raise AssertionError(f"Syntax error in orbital_docking.py: {e}")
    print("✓ Valid Python syntax")


# ---------------------------------------------------------------------------
# Manifest checks
# ---------------------------------------------------------------------------

def test_orbital_docking_in_manifest():
    """ORBITAL_DOCKING must be registered in MODE_REGISTRY."""
    from modes.manifest import MODE_REGISTRY
    assert "ORBITAL_DOCKING" in MODE_REGISTRY, "ORBITAL_DOCKING not found in MODE_REGISTRY"
    print("✓ ORBITAL_DOCKING found in MODE_REGISTRY")


def test_orbital_docking_manifest_metadata():
    """ORBITAL_DOCKING manifest entry must have all required fields."""
    from modes.manifest import MODE_REGISTRY
    meta = MODE_REGISTRY["ORBITAL_DOCKING"]

    assert meta["id"] == "ORBITAL_DOCKING"
    assert meta["name"] == "ORBITAL DOCKING"
    assert meta["module_path"] == "modes.orbital_docking"
    assert meta["class_name"] == "OrbitalDocking"
    assert meta["icon"] == "ORBITAL_DOCKING"
    assert "CORE" in meta["requires"], "Must require CORE"
    assert "INDUSTRIAL" in meta["requires"], "Must require INDUSTRIAL satellite"
    assert meta.get("menu") == "EXP1", "Should appear in EXP1 menu"
    assert meta.get("has_tutorial") is True, "Must declare has_tutorial=True"
    print("✓ ORBITAL_DOCKING manifest metadata is correct")


def test_orbital_docking_difficulty_settings():
    """ORBITAL_DOCKING must expose EASY/NORMAL/HARD/INSANE difficulty options."""
    from modes.manifest import MODE_REGISTRY
    meta = MODE_REGISTRY["ORBITAL_DOCKING"]
    settings = meta.get("settings", [])

    diff = next((s for s in settings if s["key"] == "difficulty"), None)
    assert diff is not None, "Must have a difficulty setting"
    assert diff["label"] == "DIFF"
    for opt in ("EASY", "NORMAL", "HARD", "INSANE"):
        assert opt in diff["options"], f"Difficulty option '{opt}' missing"
    assert diff["default"] == "NORMAL"
    print("✓ ORBITAL_DOCKING difficulty settings are correct")


# ---------------------------------------------------------------------------
# Physics constant checks
# ---------------------------------------------------------------------------

def test_initial_distance_constant():
    """_INITIAL_DISTANCE must be defined (starting approach distance)."""
    src = _source()
    assert "_INITIAL_DISTANCE" in src, "_INITIAL_DISTANCE constant missing"
    match = re.search(r'_INITIAL_DISTANCE\s*=\s*([\d.]+)', src)
    assert match, "_INITIAL_DISTANCE value not parseable"
    val = float(match.group(1))
    assert val > 0, "_INITIAL_DISTANCE must be positive"
    print(f"✓ _INITIAL_DISTANCE = {val}m")


def test_safe_dock_speed_constant():
    """_SAFE_DOCK_SPEED must be defined as the max speed for hard capture."""
    src = _source()
    assert "_SAFE_DOCK_SPEED" in src, "_SAFE_DOCK_SPEED constant missing"
    match = re.search(r'_SAFE_DOCK_SPEED\s*=\s*([\d.]+)', src)
    assert match, "_SAFE_DOCK_SPEED value not parseable"
    val = float(match.group(1))
    assert val == 0.5, f"_SAFE_DOCK_SPEED should be 0.5 m/s per spec, got {val}"
    print(f"✓ _SAFE_DOCK_SPEED = {val} m/s")


def test_clamp_distance_constant():
    """_CLAMP_DISTANCE must be defined (< 10 m triggers clamp sequence)."""
    src = _source()
    assert "_CLAMP_DISTANCE" in src, "_CLAMP_DISTANCE constant missing"
    match = re.search(r'_CLAMP_DISTANCE\s*=\s*([\d.]+)', src)
    assert match, "_CLAMP_DISTANCE value not parseable"
    val = float(match.group(1))
    assert val == 10.0, f"_CLAMP_DISTANCE should be 10.0 m per spec, got {val}"
    print(f"✓ _CLAMP_DISTANCE = {val}m")


def test_rcs_impulse_constant():
    """_RCS_IMPULSE must be defined (encoder-driven lateral thrust)."""
    src = _source()
    assert "_RCS_IMPULSE" in src, "_RCS_IMPULSE constant missing"
    print("✓ _RCS_IMPULSE defined")


def test_oms_thrust_constant():
    """_OMS_THRUST must be defined (Z-axis main engine thrust)."""
    src = _source()
    assert "_OMS_THRUST" in src, "_OMS_THRUST constant missing"
    print("✓ _OMS_THRUST defined")


def test_sas_decay_constant():
    """_SAS_DECAY must be defined (stability augmentation velocity decay)."""
    src = _source()
    assert "_SAS_DECAY" in src, "_SAS_DECAY constant missing"
    match = re.search(r'_SAS_DECAY\s*=\s*([\d.]+)', src)
    assert match, "_SAS_DECAY value not parseable"
    val = float(match.group(1))
    assert 0.0 < val < 1.0, f"_SAS_DECAY should be between 0 and 1, got {val}"
    print(f"✓ _SAS_DECAY = {val}")


def test_clamp_count_is_four():
    """_CLAMP_COUNT must be 4 as specified in the issue."""
    src = _source()
    match = re.search(r'_CLAMP_COUNT\s*=\s*(\d+)', src)
    assert match, "_CLAMP_COUNT constant missing"
    val = int(match.group(1))
    assert val == 4, f"_CLAMP_COUNT should be 4 per spec, got {val}"
    print(f"✓ _CLAMP_COUNT = {val}")


def test_toggle_count_is_eight():
    """_TOGGLE_COUNT must be 8 (8 latching toggles for clamps)."""
    src = _source()
    match = re.search(r'_TOGGLE_COUNT\s*=\s*(\d+)', src)
    assert match, "_TOGGLE_COUNT constant missing"
    val = int(match.group(1))
    assert val == 8, f"_TOGGLE_COUNT should be 8, got {val}"
    print(f"✓ _TOGGLE_COUNT = {val}")


def test_guarded_toggle_index():
    """_SW_GUARD must be 8 (guarded toggle index per sat-01 spec)."""
    src = _source()
    match = re.search(r'_SW_GUARD\s*=\s*(\d+)', src)
    assert match, "_SW_GUARD constant missing"
    val = int(match.group(1))
    assert val == 8, f"_SW_GUARD should be 8, got {val}"
    print(f"✓ _SW_GUARD = {val}")


# ---------------------------------------------------------------------------
# Difficulty parameter checks
# ---------------------------------------------------------------------------

def test_diff_params_all_difficulties():
    """_DIFF_PARAMS must define all four difficulty levels."""
    src = _source()
    assert "_DIFF_PARAMS" in src, "_DIFF_PARAMS dict missing"
    for diff in ("EASY", "NORMAL", "HARD", "INSANE"):
        assert diff in src, f"Difficulty '{diff}' missing from _DIFF_PARAMS"
    print("✓ _DIFF_PARAMS defines EASY, NORMAL, HARD, INSANE")


def test_drift_enabled_for_hard_insane():
    """HARD and INSANE difficulties must enable station drift."""
    from modes.orbital_docking import _DIFF_PARAMS
    assert _DIFF_PARAMS["HARD"]["drift"] is True, "HARD should have drift=True"
    assert _DIFF_PARAMS["INSANE"]["drift"] is True, "INSANE should have drift=True"
    assert _DIFF_PARAMS["EASY"]["drift"] is False, "EASY should have drift=False"
    assert _DIFF_PARAMS["NORMAL"]["drift"] is False, "NORMAL should have drift=False"
    print("✓ Station drift enabled for HARD and INSANE")


def test_fuel_mult_decreases_with_difficulty():
    """Fuel multiplier must decrease as difficulty increases."""
    from modes.orbital_docking import _DIFF_PARAMS
    easy   = _DIFF_PARAMS["EASY"]["fuel_mult"]
    normal = _DIFF_PARAMS["NORMAL"]["fuel_mult"]
    hard   = _DIFF_PARAMS["HARD"]["fuel_mult"]
    insane = _DIFF_PARAMS["INSANE"]["fuel_mult"]
    assert easy >= normal, "EASY fuel should be >= NORMAL"
    assert normal >= hard, "NORMAL fuel should be >= HARD"
    assert hard >= insane, "HARD fuel should be >= INSANE"
    print(f"✓ fuel_mult decreases: EASY={easy}, NORMAL={normal}, HARD={hard}, INSANE={insane}")


# ---------------------------------------------------------------------------
# Phase constant checks
# ---------------------------------------------------------------------------

def test_phase_constants():
    """All three phase constants must be defined."""
    src = _source()
    for phase in ("_PHASE_APPROACH", "_PHASE_CLAMP_SEQ", "_PHASE_HARD_CAPTURE"):
        assert phase in src, f"Phase constant {phase} missing"
    print("✓ All phase constants defined")


# ---------------------------------------------------------------------------
# Key method checks
# ---------------------------------------------------------------------------

def test_physics_methods_exist():
    """Core physics methods must be defined."""
    src = _source()
    for method in ("_apply_rcs_x", "_apply_rcs_y", "_apply_sas", "_update_physics"):
        assert f"def {method}" in src, f"Method {method} missing"
    print("✓ Physics methods defined")


def test_rendering_methods_exist():
    """Rendering methods must be defined."""
    src = _source()
    for method in ("_draw_ring", "_render", "_render_telemetry"):
        assert f"def {method}" in src, f"Method {method} missing"
    print("✓ Rendering methods defined")


def test_clamp_methods_exist():
    """Clamp sequence methods must be defined."""
    src = _source()
    for method in ("_generate_clamp_sequence", "_check_clamp_progress"):
        assert f"def {method}" in src, f"Method {method} missing"
    print("✓ Clamp sequence methods defined")


def test_satellite_helper_methods():
    """Satellite HID helper methods must be defined."""
    src = _source()
    for method in ("_sat_latching", "_sat_guard", "_sat_encoder",
                   "_sat_momentary_up", "_sat_momentary_down", "_send_segment"):
        assert f"def {method}" in src, f"Satellite helper {method} missing"
    print("✓ Satellite HID helper methods defined")


def test_dual_encoder_usage():
    """Both core and satellite encoders must be read in run()."""
    src = _source()
    start = src.find("async def run(")
    assert start != -1, "run() method not found"
    body = src[start:]
    assert "encoder_positions" in body, "Core encoder not read in run()"
    assert "_sat_encoder" in body, "Satellite encoder not read in run()"
    print("✓ Both core and satellite encoders read in run()")


def test_momentary_toggle_usage():
    """Both OMS forward and brake must be checked in run()."""
    src = _source()
    start = src.find("async def run(")
    body = src[start:]
    assert "_sat_momentary_up" in body, "OMS forward (momentary UP) not checked"
    assert "_sat_momentary_down" in body, "OMS brake (momentary DOWN) not checked"
    print("✓ Both OMS momentary directions checked in run()")


def test_sas_button_usage():
    """SAS (core button 0) must be checked in run()."""
    src = _source()
    start = src.find("async def run(")
    body = src[start:]
    assert "is_button_pressed" in body, "SAS button not checked in run()"
    print("✓ SAS button checked in run()")


def test_guarded_toggle_checked():
    """Guarded toggle must be checked for hard capture."""
    src = _source()
    assert "_sat_guard" in src, "_sat_guard not called for hard capture"
    print("✓ Guarded toggle checked for hard capture")


def test_run_tutorial_defined():
    """run_tutorial() method must be defined."""
    src = _source()
    assert "async def run_tutorial" in src, "run_tutorial() method missing"
    print("✓ run_tutorial() defined")


# ---------------------------------------------------------------------------
# Physics logic unit tests
# ---------------------------------------------------------------------------

def _make_mode():
    """Create an OrbitalDocking instance with a minimal mocked core."""
    core = MagicMock()
    core.satellites = {}
    core.data.get_setting.return_value = "NORMAL"
    core.data.get_high_score.return_value = 0
    core.data.save_high_score.return_value = False
    core.hid.encoder_positions = [0]
    core.hid.is_button_pressed.return_value = False

    from modes.orbital_docking import OrbitalDocking
    return OrbitalDocking(core)


def test_rcs_x_applies_velocity():
    """apply_rcs_x must change vel_x by RCS_IMPULSE * delta."""
    from modes.orbital_docking import _RCS_IMPULSE
    mode = _make_mode()
    mode._vel_x = 0.0
    mode._fuel = 100.0
    mode._apply_rcs_x(1)
    assert mode._vel_x > 0.0, "Positive encoder delta should increase vel_x"
    assert abs(mode._vel_x - _RCS_IMPULSE) < 1e-9, \
        f"vel_x should be {_RCS_IMPULSE}, got {mode._vel_x}"
    print(f"✓ RCS X impulse applied: vel_x = {mode._vel_x:.4f}")


def test_rcs_x_negative_delta():
    """Negative encoder delta (left) should decrease vel_x."""
    from modes.orbital_docking import _RCS_IMPULSE
    mode = _make_mode()
    mode._vel_x = 0.0
    mode._fuel = 100.0
    mode._apply_rcs_x(-1)
    assert mode._vel_x < 0.0, "Negative encoder delta should decrease vel_x"
    assert abs(mode._vel_x - (-_RCS_IMPULSE)) < 1e-9, \
        f"vel_x should be -{_RCS_IMPULSE}, got {mode._vel_x}"
    print(f"✓ RCS X negative impulse: vel_x = {mode._vel_x:.4f}")


def test_rcs_y_applies_velocity():
    """apply_rcs_y must change vel_y by RCS_IMPULSE * delta."""
    from modes.orbital_docking import _RCS_IMPULSE
    mode = _make_mode()
    mode._vel_y = 0.0
    mode._fuel = 100.0
    mode._apply_rcs_y(2)
    assert mode._vel_y > 0.0, "Positive sat encoder delta should increase vel_y"
    assert abs(mode._vel_y - 2 * _RCS_IMPULSE) < 1e-9, \
        f"vel_y should be {2 * _RCS_IMPULSE}, got {mode._vel_y}"
    print(f"✓ RCS Y impulse applied: vel_y = {mode._vel_y:.4f}")


def test_no_thrust_when_fuel_empty():
    """RCS impulse must not change velocity when fuel is exhausted."""
    mode = _make_mode()
    mode._vel_x = 0.0
    mode._fuel = 0.0
    mode._apply_rcs_x(5)
    assert mode._vel_x == 0.0, "No thrust should be applied with zero fuel"
    print("✓ No thrust when fuel is 0")


def test_rcs_consumes_fuel():
    """RCS impulse must consume RCS fuel."""
    mode = _make_mode()
    initial_fuel = 100.0
    mode._fuel = initial_fuel
    mode._apply_rcs_x(1)
    assert mode._fuel < initial_fuel, "Fuel should decrease after RCS impulse"
    print(f"✓ RCS consumes fuel: {initial_fuel:.1f} → {mode._fuel:.4f}")


def test_oms_forward_increases_vel_z():
    """OMS forward must increase vel_z (approach) each tick."""
    from modes.orbital_docking import _OMS_THRUST
    mode = _make_mode()
    mode._vel_z = 0.0
    mode._fuel = 100.0
    mode._update_physics(1.0, oms_forward=True, oms_brake=False, sas_active=False)
    assert mode._vel_z > 0.0, "OMS forward should increase vel_z"
    assert abs(mode._vel_z - _OMS_THRUST) < 1e-9, \
        f"vel_z should be {_OMS_THRUST}, got {mode._vel_z}"
    print(f"✓ OMS forward increases vel_z: {mode._vel_z:.4f}")


def test_oms_brake_decreases_vel_z():
    """OMS retro-rockets must decrease vel_z each tick."""
    mode = _make_mode()
    mode._vel_z = 0.5
    mode._fuel = 100.0
    prev_vz = mode._vel_z
    mode._update_physics(1.0, oms_forward=False, oms_brake=True, sas_active=False)
    assert mode._vel_z < prev_vz, "OMS brake should reduce vel_z"
    print(f"✓ OMS brake decreases vel_z: {prev_vz:.2f} → {mode._vel_z:.4f}")


def test_sas_decays_lateral_velocity():
    """SAS must decay X/Y velocity toward zero."""
    import math
    _DELTA_S = 1.0
    mode = _make_mode()
    mode._vel_x = 1.0
    mode._vel_y = -0.8
    mode._fuel = 100.0
    mode._update_physics(_DELTA_S, oms_forward=False, oms_brake=False, sas_active=True)
    assert abs(mode._vel_x) < 1.0, "SAS should reduce |vel_x|"
    assert abs(mode._vel_y) < 0.8, "SAS should reduce |vel_y|"
    expected_vel_x = 1.0 * math.exp(-4.0 * _DELTA_S)
    assert abs(mode._vel_x - expected_vel_x) < 1e-9, \
        f"vel_x after SAS should be {expected_vel_x}"
    print(f"✓ SAS decays velocity: vel_x = {mode._vel_x:.4f}")


def test_sas_consumes_fuel():
    """SAS must consume fuel each tick it is active."""
    mode = _make_mode()
    mode._vel_x = 0.5
    mode._fuel = 50.0
    initial_fuel = mode._fuel
    mode._update_physics(1.0, oms_forward=False, oms_brake=False, sas_active=True)
    assert mode._fuel < initial_fuel, "SAS should consume fuel"
    print(f"✓ SAS consumes fuel: {initial_fuel:.1f} → {mode._fuel:.4f}")


def test_physics_integrates_z_distance():
    """Z-distance must decrease by vel_z each physics tick."""
    mode = _make_mode()
    mode._z_dist = 100.0
    mode._vel_z = 1.0
    mode._update_physics(1.0, oms_forward=False, oms_brake=False, sas_active=False)
    assert abs(mode._z_dist - 99.0) < 1e-9, \
        f"z_dist should be 99.0 after one tick, got {mode._z_dist}"
    print(f"✓ Z-distance integrated: {mode._z_dist:.4f}")


def test_physics_integrates_lateral_position():
    """Lateral alignment error must integrate vel_x/vel_y each tick."""
    mode = _make_mode()
    mode._align_x = 0.0
    mode._align_y = 0.0
    mode._vel_x = 0.5
    mode._vel_y = -0.3
    mode._update_physics(1.0, oms_forward=False, oms_brake=False, sas_active=False)
    assert abs(mode._align_x - 0.5) < 1e-9, \
        f"align_x should be 0.5, got {mode._align_x}"
    assert abs(mode._align_y - (-0.3)) < 1e-9, \
        f"align_y should be -0.3, got {mode._align_y}"
    print(f"✓ Lateral positions integrated correctly")


def test_velocity_capped_at_max():
    """_update_physics must cap vel_z at _MAX_Z_VELOCITY."""
    from modes.orbital_docking import _MAX_Z_VELOCITY, _OMS_THRUST
    mode = _make_mode()
    # Set vel_z very close to the cap and apply one more OMS forward tick
    mode._vel_z = _MAX_Z_VELOCITY - 0.001
    mode._fuel = 100.0
    mode._update_physics(1.0, oms_forward=True, oms_brake=False, sas_active=False)
    assert mode._vel_z <= _MAX_Z_VELOCITY, \
        f"vel_z {mode._vel_z} exceeded cap {_MAX_Z_VELOCITY}"
    print(f"✓ Z velocity capped at {_MAX_Z_VELOCITY} (got {mode._vel_z:.4f})")


def test_is_aligned_within_tolerance():
    """_is_aligned must return True when within alignment tolerance."""
    mode = _make_mode()
    mode._align_tol = 1.5
    mode._align_x = 0.5
    mode._align_y = -0.5
    assert mode._is_aligned(), "Should be aligned when within tolerance"
    print("✓ _is_aligned returns True within tolerance")


def test_is_aligned_outside_tolerance():
    """_is_aligned must return False when outside alignment tolerance."""
    mode = _make_mode()
    mode._align_tol = 1.5
    mode._align_x = 2.0
    mode._align_y = 0.0
    assert not mode._is_aligned(), "Should not be aligned when outside tolerance"
    mode._align_x = 0.0
    mode._align_y = -2.0
    assert not mode._is_aligned(), "Should not be aligned with large Y error"
    print("✓ _is_aligned returns False outside tolerance")


def test_approach_speed_magnitude():
    """_approach_speed must return the 3D velocity magnitude."""
    import math
    mode = _make_mode()
    mode._vel_x = 3.0
    mode._vel_y = 4.0
    mode._vel_z = 0.0
    expected = 5.0  # 3-4-5 triangle
    assert abs(mode._approach_speed() - expected) < 1e-9, \
        f"3D speed should be {expected}, got {mode._approach_speed()}"
    print(f"✓ _approach_speed = {mode._approach_speed():.4f} (3-4-5 triangle)")


# ---------------------------------------------------------------------------
# Clamp sequence tests
# ---------------------------------------------------------------------------

def test_generate_clamp_sequence_length():
    """Clamp sequence must contain exactly _CLAMP_COUNT entries."""
    from modes.orbital_docking import _CLAMP_COUNT
    mode = _make_mode()
    mode._generate_clamp_sequence()
    assert len(mode._clamp_sequence) == _CLAMP_COUNT, \
        f"Clamp sequence should have {_CLAMP_COUNT} entries"
    print(f"✓ Clamp sequence has {_CLAMP_COUNT} entries")


def test_generate_clamp_sequence_unique():
    """Clamp sequence entries must all be unique toggle indices."""
    mode = _make_mode()
    mode._generate_clamp_sequence()
    assert len(set(mode._clamp_sequence)) == len(mode._clamp_sequence), \
        "Clamp sequence must have no duplicate indices"
    print("✓ Clamp sequence indices are unique")


def test_generate_clamp_sequence_valid_indices():
    """All clamp indices must be in range 0.._TOGGLE_COUNT-1."""
    from modes.orbital_docking import _TOGGLE_COUNT
    mode = _make_mode()
    for _ in range(20):
        mode._generate_clamp_sequence()
        for idx in mode._clamp_sequence:
            assert 0 <= idx < _TOGGLE_COUNT, \
                f"Clamp index {idx} out of range [0, {_TOGGLE_COUNT})"
    print("✓ Clamp indices are always valid")


def test_clamp_sequence_resets_progress():
    """_generate_clamp_sequence must reset clamp_progress to 0."""
    mode = _make_mode()
    mode._clamp_progress = 3
    mode._generate_clamp_sequence()
    assert mode._clamp_progress == 0, "Clamp progress should be reset"
    print("✓ Clamp progress reset on new sequence")


# ---------------------------------------------------------------------------
# Ring renderer test
# ---------------------------------------------------------------------------

def test_draw_ring_zero_radius_draws_centre():
    """draw_ring with radius 0 should draw only the centre pixel."""
    mode = _make_mode()
    pixels = {}

    def _draw_pixel(x, y, color):
        pixels[(x, y)] = color

    mode.core.matrix.draw_pixel.side_effect = _draw_pixel

    mode._draw_ring(8, 8, 0, MagicMock())

    assert len(pixels) == 1, f"Radius 0 should draw 1 pixel, drew {len(pixels)}"
    assert (8, 8) in pixels, "Centre pixel should be drawn for radius 0"
    print("✓ Ring radius=0 draws only centre pixel")


def test_draw_ring_nonzero_draws_pixels():
    """draw_ring with radius > 0 must draw multiple pixels."""
    mode = _make_mode()
    pixels = {}

    def _draw_pixel(x, y, color):
        pixels[(x, y)] = color

    mode.core.matrix.draw_pixel.side_effect = _draw_pixel

    mode._draw_ring(8, 8, 3, MagicMock())

    assert len(pixels) > 4, \
        f"Ring with radius 3 should draw multiple pixels, got {len(pixels)}"
    print(f"✓ Ring radius=3 draws {len(pixels)} pixels")


def test_render_draws_crosshair_centre():
    """_render must draw the crosshair centre pixel at (8, 8)."""
    mode = _make_mode()
    mode._z_dist = 100.0
    mode._align_x = 0.0
    mode._align_y = 0.0
    mode._vel_x = 0.0
    mode._vel_y = 0.0
    mode._phase = "_PHASE_APPROACH"

    pixels = {}

    def _draw_pixel(x, y, color, **kwargs):
        pixels[(x, y)] = color

    mode.core.matrix.clear.side_effect = lambda: pixels.clear()
    mode.core.matrix.draw_pixel.side_effect = _draw_pixel

    mode._render()

    assert (8, 8) in pixels, "Crosshair centre (8, 8) should always be drawn"
    print("✓ Crosshair centre rendered at (8, 8)")


# ---------------------------------------------------------------------------
# Icon checks
# ---------------------------------------------------------------------------

def test_orbital_docking_icon_in_icons_py():
    """ORBITAL_DOCKING icon must be defined in icons.py."""
    with open(_ICONS_PATH, 'r', encoding='utf-8') as f:
        src = f.read()
    assert "ORBITAL_DOCKING" in src, "ORBITAL_DOCKING icon not in icons.py"
    print("✓ ORBITAL_DOCKING icon defined in icons.py")


def test_orbital_docking_icon_in_icon_library():
    """ORBITAL_DOCKING must be registered in ICON_LIBRARY."""
    with open(_ICONS_PATH, 'r', encoding='utf-8') as f:
        src = f.read()
    lib_start = src.find("ICON_LIBRARY")
    lib_end = src.find("}", lib_start)
    library_block = src[lib_start:lib_end]
    assert '"ORBITAL_DOCKING"' in library_block, \
        "ORBITAL_DOCKING not registered in ICON_LIBRARY"
    print("✓ ORBITAL_DOCKING registered in ICON_LIBRARY")


def test_orbital_docking_icon_is_256_bytes():
    """ORBITAL_DOCKING icon data must be exactly 256 bytes (16×16)."""
    from utilities.icons import Icons
    icon = Icons.ICON_LIBRARY["ORBITAL_DOCKING"]
    assert len(icon) == 256, \
        f"ORBITAL_DOCKING icon should be 256 bytes (16×16), got {len(icon)}"
    print(f"✓ ORBITAL_DOCKING icon is exactly 256 bytes")


def test_orbital_docking_icon_in_library_class():
    """ORBITAL_DOCKING must be accessible via the Icons class."""
    from utilities.icons import Icons
    assert "ORBITAL_DOCKING" in Icons.ICON_LIBRARY, \
        "ORBITAL_DOCKING not accessible in Icons.ICON_LIBRARY"
    icon = Icons.ICON_LIBRARY["ORBITAL_DOCKING"]
    assert len(icon) == 256, f"Icon should be 256 bytes, got {len(icon)}"
    print("✓ ORBITAL_DOCKING accessible via Icons.ICON_LIBRARY")


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Running Orbital Docking Simulator mode tests...\n")

    tests = [
        test_file_exists,
        test_valid_syntax,
        test_orbital_docking_in_manifest,
        test_orbital_docking_manifest_metadata,
        test_orbital_docking_difficulty_settings,
        test_initial_distance_constant,
        test_safe_dock_speed_constant,
        test_clamp_distance_constant,
        test_rcs_impulse_constant,
        test_oms_thrust_constant,
        test_sas_decay_constant,
        test_clamp_count_is_four,
        test_toggle_count_is_eight,
        test_guarded_toggle_index,
        test_diff_params_all_difficulties,
        test_drift_enabled_for_hard_insane,
        test_fuel_mult_decreases_with_difficulty,
        test_phase_constants,
        test_physics_methods_exist,
        test_rendering_methods_exist,
        test_clamp_methods_exist,
        test_satellite_helper_methods,
        test_dual_encoder_usage,
        test_momentary_toggle_usage,
        test_sas_button_usage,
        test_guarded_toggle_checked,
        test_run_tutorial_defined,
        test_rcs_x_applies_velocity,
        test_rcs_x_negative_delta,
        test_rcs_y_applies_velocity,
        test_no_thrust_when_fuel_empty,
        test_rcs_consumes_fuel,
        test_oms_forward_increases_vel_z,
        test_oms_brake_decreases_vel_z,
        test_sas_decays_lateral_velocity,
        test_sas_consumes_fuel,
        test_physics_integrates_z_distance,
        test_physics_integrates_lateral_position,
        test_velocity_capped_at_max,
        test_is_aligned_within_tolerance,
        test_is_aligned_outside_tolerance,
        test_approach_speed_magnitude,
        test_generate_clamp_sequence_length,
        test_generate_clamp_sequence_unique,
        test_generate_clamp_sequence_valid_indices,
        test_clamp_sequence_resets_progress,
        test_draw_ring_zero_radius_draws_centre,
        test_draw_ring_nonzero_draws_pixels,
        test_render_draws_crosshair_centre,
        test_orbital_docking_icon_in_icons_py,
        test_orbital_docking_icon_in_icon_library,
        test_orbital_docking_icon_is_256_bytes,
        test_orbital_docking_icon_in_library_class,
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
