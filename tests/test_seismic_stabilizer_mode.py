"""Tests for Seismic Stabilizer game mode.

Verifies the manifest registration, physics helpers, and core gameplay
mechanics without importing real CircuitPython hardware modules.
"""

import sys
import os
import math
import ast
import re
from unittest.mock import MagicMock

# Add src to path so we can import from it
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
for _mod in _MOCK_MOD_NAMES:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

import time as _time
sys.modules['adafruit_ticks'].ticks_ms = lambda: int(_time.monotonic() * 1000)
sys.modules['adafruit_ticks'].ticks_diff = lambda a, b: a - b

_MODE_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'src', 'modes', 'seismic_stabilizer.py'
)


def _read_source():
    with open(_MODE_PATH, 'r') as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# File / syntax checks
# ---------------------------------------------------------------------------

def test_file_exists():
    """seismic_stabilizer.py must exist."""
    assert os.path.exists(_MODE_PATH), "seismic_stabilizer.py does not exist"
    print("✓ seismic_stabilizer.py exists")


def test_valid_syntax():
    """seismic_stabilizer.py must have valid Python syntax."""
    src = _read_source()
    try:
        ast.parse(src)
    except SyntaxError as e:
        raise AssertionError(f"Syntax error in seismic_stabilizer.py: {e}")
    print("✓ Valid Python syntax")


# ---------------------------------------------------------------------------
# Manifest / registration checks
# ---------------------------------------------------------------------------

def test_seismic_stabilizer_in_manifest():
    """SEISMIC_STABILIZER must be registered in MODE_REGISTRY."""
    from modes.manifest import MODE_REGISTRY

    assert "SEISMIC_STABILIZER" in MODE_REGISTRY, \
        "SEISMIC_STABILIZER not found in MODE_REGISTRY"
    print("✓ SEISMIC_STABILIZER found in MODE_REGISTRY")


def test_seismic_stabilizer_manifest_metadata():
    """All required manifest fields must be present and correct."""
    from modes.manifest import MODE_REGISTRY

    meta = MODE_REGISTRY["SEISMIC_STABILIZER"]

    assert meta["id"] == "SEISMIC_STABILIZER"
    assert meta["name"] == "SEISMIC STAB"
    assert meta["module_path"] == "modes.seismic_stabilizer"
    assert meta["class_name"] == "SeismicStabilizer"
    assert meta["icon"] == "SEISMIC_STABILIZER"
    assert "CORE" in meta["requires"], "Must require CORE"
    assert "INDUSTRIAL" in meta["requires"], "Must require INDUSTRIAL satellite"
    assert meta.get("menu") == "MAIN", "Should appear in MAIN menu"
    assert meta.get("has_tutorial") is True, "Should have a tutorial"
    print("✓ SEISMIC_STABILIZER manifest metadata is correct")


def test_seismic_stabilizer_difficulty_settings():
    """SEISMIC_STABILIZER must expose NORMAL / HARD / INSANE difficulty options."""
    from modes.manifest import MODE_REGISTRY

    settings = MODE_REGISTRY["SEISMIC_STABILIZER"]["settings"]
    diff = next((s for s in settings if s["key"] == "difficulty"), None)
    assert diff is not None, "Missing difficulty setting"
    assert diff["label"] == "DIFF"
    assert "NORMAL" in diff["options"]
    assert "HARD" in diff["options"]
    assert "INSANE" in diff["options"]
    assert diff["default"] == "NORMAL"
    print("✓ SEISMIC_STABILIZER difficulty settings are correct")


def test_seismic_stabilizer_icon_registered():
    """SEISMIC_STABILIZER icon must be present in the icon library."""
    from utilities.icons import Icons

    assert "SEISMIC_STABILIZER" in Icons.ICON_LIBRARY, \
        "SEISMIC_STABILIZER icon not in ICON_LIBRARY"
    print("✓ SEISMIC_STABILIZER icon registered")


# ---------------------------------------------------------------------------
# Source-level structural checks
# ---------------------------------------------------------------------------

def test_physics_constants_present():
    """Core physics constants must be defined in the source."""
    src = _read_source()
    assert "_GRAVITY_FACTOR" in src, "Missing _GRAVITY_FACTOR constant"
    assert "_CABLE_STEP" in src,     "Missing _CABLE_STEP constant"
    assert "_CABLE_MAX" in src,      "Missing _CABLE_MAX constant"
    assert "_FALL_ANGLE" in src,     "Missing _FALL_ANGLE constant"
    assert "_SAFE_ANGLE" in src,     "Missing _SAFE_ANGLE constant"
    assert "_WARN_ANGLE" in src,     "Missing _WARN_ANGLE constant"
    print("✓ Physics constants are defined")


def test_seismic_shock_constants_present():
    """Seismic shock parameters must be defined."""
    src = _read_source()
    assert "_SHOCK_INTERVAL_BASE" in src, "Missing _SHOCK_INTERVAL_BASE"
    assert "_SHOCK_INTERVAL_MIN"  in src, "Missing _SHOCK_INTERVAL_MIN"
    assert "_SHOCK_MAGNITUDE"     in src, "Missing _SHOCK_MAGNITUDE"
    print("✓ Seismic shock constants are defined")


def test_coolant_rod_constants_present():
    """Coolant rod constants must be defined."""
    src = _read_source()
    assert "_COOLANT_COUNT"       in src, "Missing _COOLANT_COUNT"
    assert "_COOLANT_SLOW_FACTOR" in src, "Missing _COOLANT_SLOW_FACTOR"
    assert "_COOLANT_MULT_PENALTY" in src, "Missing _COOLANT_MULT_PENALTY"
    print("✓ Coolant rod constants are defined")


def test_overheat_constants_present():
    """Pressure vent / overheat constants must be defined."""
    src = _read_source()
    assert "_OVERHEAT_RATE"  in src, "Missing _OVERHEAT_RATE"
    assert "_OVERHEAT_COOL"  in src, "Missing _OVERHEAT_COOL"
    assert "_OVERHEAT_LIMIT" in src, "Missing _OVERHEAT_LIMIT"
    assert "_VENT_DAMP_RATE" in src, "Missing _VENT_DAMP_RATE"
    print("✓ Overheat/vent constants are defined")


def test_hardware_index_constants_present():
    """Hardware index constants for encoders and toggles must be defined."""
    src = _read_source()
    assert "_ENC_CORE"      in src, "Missing _ENC_CORE"
    assert "_ENC_SAT"       in src, "Missing _ENC_SAT"
    assert "_COOLANT_START" in src, "Missing _COOLANT_START"
    assert "_MT_VENT"       in src, "Missing _MT_VENT"
    print("✓ Hardware index constants are defined")


def test_difficulty_table_present():
    """Difficulty table _DIFF_PARAMS must include NORMAL, HARD, and INSANE."""
    src = _read_source()
    assert "_DIFF_PARAMS" in src, "Missing _DIFF_PARAMS difficulty table"
    assert '"NORMAL"' in src or "'NORMAL'" in src, "Missing NORMAL difficulty entry"
    assert '"HARD"'   in src or "'HARD'"   in src, "Missing HARD difficulty entry"
    assert '"INSANE"' in src or "'INSANE'" in src, "Missing INSANE difficulty entry"
    print("✓ Difficulty table _DIFF_PARAMS is defined")


def test_required_methods_present():
    """Key methods must be present in the source."""
    src = _read_source()
    assert "_update_physics"      in src, "_update_physics method missing"
    assert "_trigger_seismic_shock" in src, "_trigger_seismic_shock method missing"
    assert "_count_coolant_rods"  in src, "_count_coolant_rods method missing"
    assert "_is_vent_held"        in src, "_is_vent_held method missing"
    assert "_get_cable_tensions"  in src, "_get_cable_tensions method missing"
    assert "_get_multiplier"      in src, "_get_multiplier method missing"
    assert "_render"              in src, "_render method missing"
    assert "_send_segment"        in src, "_send_segment method missing"
    assert "run_tutorial"         in src, "run_tutorial method missing"
    print("✓ All required methods are present")


def test_uses_both_encoders():
    """Source must read from both Core and Satellite encoders."""
    src = _read_source()
    assert "encoder_positions[_ENC_CORE]" in src, "Should read Core encoder via _ENC_CORE"
    assert "_sat_encoder_raw" in src, "Should use satellite encoder via _sat_encoder_raw"
    print("✓ Both encoders are referenced")


def test_satellite_required_in_manifest():
    """Seismic Stabilizer must require both CORE and INDUSTRIAL in manifest."""
    from modes.manifest import MODE_REGISTRY

    requires = MODE_REGISTRY["SEISMIC_STABILIZER"]["requires"]
    assert "CORE" in requires,       "Should require CORE"
    assert "INDUSTRIAL" in requires, "Should require INDUSTRIAL satellite"
    print("✓ Requires CORE and INDUSTRIAL satellite")


# ---------------------------------------------------------------------------
# Physics logic tests (instantiation with mocked core)
# ---------------------------------------------------------------------------

def _make_mode():
    """Create a SeismicStabilizer instance with a minimal mocked core."""
    core = MagicMock()
    core.data.get_setting.return_value = "NORMAL"
    core.data.get_high_score.return_value = 0
    core.data.save_high_score.return_value = False
    core.hid.encoder_positions = [0]
    core.satellites = {}

    from modes.seismic_stabilizer import SeismicStabilizer
    return SeismicStabilizer(core)


def test_physics_gravity_destabilises():
    """Gravity must increase |angle| each frame when no cable control is applied."""
    mode = _make_mode()
    mode._angle = 0.3          # rod tilted right
    mode._angular_velocity = 0.0
    mode._update_physics(0.033, 0.0, 0.0, False)
    assert mode._angular_velocity > 0.0, \
        "Gravity should accelerate the rod further to the right"
    print(f"✓ Gravity destabilises: angular_vel = {mode._angular_velocity:.4f}")


def test_physics_left_cable_corrects_right_tilt():
    """A strong left cable must reduce angular velocity when rod leans right."""
    mode = _make_mode()
    mode._angle = 0.3
    mode._angular_velocity = 0.0
    mode._update_physics(0.033, 3.0, 0.0, False)  # high left tension, no right
    assert mode._angular_velocity < 0.0, \
        "Left cable dominance should push rod back toward vertical"
    print(f"✓ Left cable corrects right tilt: angular_vel = {mode._angular_velocity:.4f}")


def test_physics_vent_damps_angle():
    """Vent must reduce both angle and angular velocity."""
    mode = _make_mode()
    mode._angle = 0.5
    mode._angular_velocity = 0.8
    mode._update_physics(0.1, 0.0, 0.0, vent_held=True)
    assert abs(mode._angle) < 0.5, "Vent should reduce angle magnitude"
    print(f"✓ Vent damps angle: angle = {mode._angle:.4f}")


def test_multiplier_decreases_with_coolant_rods():
    """Each active coolant rod must reduce the score multiplier."""
    mode = _make_mode()
    mult_0 = mode._get_multiplier(0)
    mult_4 = mode._get_multiplier(4)
    mult_8 = mode._get_multiplier(8)

    assert mult_0 > mult_4,  "4 rods should reduce multiplier vs 0 rods"
    assert mult_4 > mult_8,  "8 rods should reduce multiplier vs 4 rods"
    assert mult_0 == 1.0,    "0 rods should give full ×1.0 multiplier"
    assert mult_8 >= 0.10,   "Multiplier must not drop below minimum 0.10"
    print(f"✓ Multiplier: 0 rods={mult_0:.2f}, 4 rods={mult_4:.2f}, 8 rods={mult_8:.2f}")


def test_cable_tension_clamped():
    """Cable tension must not exceed ±_CABLE_MAX regardless of encoder position."""
    from modes.seismic_stabilizer import _CABLE_MAX

    mode = _make_mode()
    # Force a very large encoder position
    mode.core.hid.encoder_positions = [9999]
    mode._sat_enc_offset = 0

    left, right = mode._get_cable_tensions()
    assert abs(left) <= _CABLE_MAX, f"Left tension {left} exceeds ±{_CABLE_MAX}"
    print(f"✓ Cable tension clamped: left={left:.2f}, right={right:.2f}")


def test_cable_tension_offset_calibration():
    """Right cable tension must be 0 when satellite encoder is at the initial offset."""
    mode = _make_mode()

    # Simulate satellite with encoder at position 50 at game start
    sat = MagicMock()
    sat.sat_type_name = "INDUSTRIAL"
    sat.hid.encoder_positions = [50]
    mode.sat = sat
    mode._sat_enc_offset = 50   # calibrated offset

    left, right = mode._get_cable_tensions()
    assert right == 0.0, f"Right tension should be 0 after calibration, got {right}"
    print("✓ Right cable tension is 0 after offset calibration")


def test_rod_color_by_angle():
    """Rod colour must reflect angle severity: green → yellow → red."""
    mode = _make_mode()

    from modes.seismic_stabilizer import _SAFE_ANGLE, _WARN_ANGLE
    from utilities.palette import Palette

    mode._angle = _SAFE_ANGLE * 0.5    # safely within safe zone
    assert mode._rod_color() == Palette.GREEN, "Should be GREEN in safe zone"

    mode._angle = (_SAFE_ANGLE + _WARN_ANGLE) / 2.0  # between safe and warn
    assert mode._rod_color() == Palette.YELLOW, "Should be YELLOW in warning zone"

    mode._angle = _WARN_ANGLE + 0.1    # beyond warn angle
    assert mode._rod_color() == Palette.RED, "Should be RED in critical zone"

    print("✓ Rod colour matches angle severity")


def test_count_coolant_rods_no_satellite():
    """_count_coolant_rods must return 0 when no satellite is present."""
    mode = _make_mode()
    mode.sat = None
    assert mode._count_coolant_rods() == 0, \
        "Should return 0 when satellite is absent"
    print("✓ _count_coolant_rods returns 0 without satellite")


def test_count_coolant_rods_with_satellite():
    """_count_coolant_rods must count active toggles correctly."""
    mode = _make_mode()
    sat = MagicMock()
    sat.sat_type_name = "INDUSTRIAL"
    # 4 of 8 coolant toggles are active
    sat.hid.latching_values = [True, False, True, False, True, True, False, False,
                                False, False, False, False]
    mode.sat = sat
    count = mode._count_coolant_rods()
    assert count == 4, f"Expected 4 active rods, got {count}"
    print(f"✓ _count_coolant_rods correctly counted {count} active rods")


def test_is_vent_held_no_satellite():
    """_is_vent_held must return False when no satellite is present."""
    mode = _make_mode()
    mode.sat = None
    assert not mode._is_vent_held(), "Should return False when satellite absent"
    print("✓ _is_vent_held returns False without satellite")


def test_send_segment_cached():
    """_send_segment must not send duplicate messages to the satellite."""
    mode = _make_mode()
    sat = MagicMock()
    sat.sat_type_name = "INDUSTRIAL"
    mode.sat = sat
    mode._last_segment_text = ""

    mode._send_segment("ANG   0d")
    mode._send_segment("ANG   0d")   # duplicate – should NOT send again

    assert sat.send.call_count == 1, \
        f"send() should be called once (cached), got {sat.send.call_count}"
    print("✓ _send_segment caches and avoids duplicate UART writes")
