"""Test module for Maglev Express game mode.

Validates:
- Mode file existence and valid Python syntax
- Manifest registration with correct metadata
- Train state constants
- Hardware index constants
- Physics helper methods (throttle, heat, fault logic)
- Route waypoint structure
- Vanishing-point animation in matrix_animations
- New tone constants in tones.py
- MAGLEV_EXPRESS icon in icons.py
"""

import sys
import os
import ast
import re

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

_MODE_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'src', 'modes', 'maglev_express.py'
)
_ANIM_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'src', 'utilities', 'matrix_animations.py'
)
_TONES_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'src', 'utilities', 'tones.py'
)
_ICONS_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'src', 'utilities', 'icons.py'
)
_MANIFEST_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'src', 'modes', 'manifest.py'
)


def _source():
    with open(_MODE_PATH, 'r') as f:
        return f.read()


# ---------------------------------------------------------------------------
# File and syntax checks
# ---------------------------------------------------------------------------

def test_file_exists():
    """Test that maglev_express.py exists."""
    assert os.path.exists(_MODE_PATH), "maglev_express.py does not exist"
    print("✓ maglev_express.py exists")


def test_valid_syntax():
    """Test that maglev_express.py has valid Python syntax."""
    src = _source()
    try:
        ast.parse(src)
    except SyntaxError as e:
        raise AssertionError(f"Syntax error in maglev_express.py: {e}")
    print("✓ Valid Python syntax")


def test_inherits_game_mode():
    """Test that MaglevExpress inherits from GameMode."""
    src = _source()
    assert "class MaglevExpress(GameMode)" in src, \
        "MaglevExpress must inherit from GameMode"
    print("✓ MaglevExpress inherits from GameMode")


def test_run_method_present():
    """Test that the async run() method is implemented."""
    src = _source()
    assert "async def run(self)" in src, "run() coroutine missing"
    print("✓ async run() method present")


# ---------------------------------------------------------------------------
# Manifest checks
# ---------------------------------------------------------------------------

def test_maglev_express_in_manifest():
    """Test that MAGLEV_EXPRESS is registered in the mode manifest."""
    from modes.manifest import MODE_REGISTRY
    assert "MAGLEV_EXPRESS" in MODE_REGISTRY, "MAGLEV_EXPRESS not found in MODE_REGISTRY"
    print("✓ MAGLEV_EXPRESS found in MODE_REGISTRY")


def test_maglev_express_manifest_metadata():
    """Test that MAGLEV_EXPRESS manifest entry has all required fields."""
    from modes.manifest import MODE_REGISTRY
    meta = MODE_REGISTRY["MAGLEV_EXPRESS"]
    assert meta["id"] == "MAGLEV_EXPRESS"
    assert meta["name"] == "MAGLEV EXPRESS"
    assert meta["module_path"] == "modes.maglev_express"
    assert meta["class_name"] == "MaglevExpress"
    assert meta["icon"] == "MAGLEV_EXPRESS"
    assert "CORE" in meta["requires"], "MAGLEV_EXPRESS must require CORE"
    assert "INDUSTRIAL" in meta["requires"], "MAGLEV_EXPRESS must require INDUSTRIAL satellite"
    assert meta.get("menu") == "MAIN", "MAGLEV_EXPRESS should appear in MAIN menu"
    print("✓ MAGLEV_EXPRESS manifest metadata is correct")


def test_maglev_express_difficulty_settings():
    """Test that MAGLEV_EXPRESS has correct difficulty settings."""
    from modes.manifest import MODE_REGISTRY
    meta = MODE_REGISTRY["MAGLEV_EXPRESS"]
    settings = meta.get("settings", [])
    diff = next((s for s in settings if s["key"] == "difficulty"), None)
    assert diff is not None, "MAGLEV_EXPRESS must have a difficulty setting"
    assert diff["label"] == "DIFF"
    assert "NORMAL" in diff["options"]
    assert "HARD" in diff["options"]
    assert "INSANE" in diff["options"]
    assert diff["default"] == "NORMAL"
    print("✓ MAGLEV_EXPRESS difficulty settings are correct")


def test_maglev_express_has_tutorial():
    """Test that MAGLEV_EXPRESS declares a tutorial."""
    from modes.manifest import MODE_REGISTRY
    meta = MODE_REGISTRY["MAGLEV_EXPRESS"]
    assert meta.get("has_tutorial") is True, "MAGLEV_EXPRESS should have has_tutorial=True"
    print("✓ MAGLEV_EXPRESS has_tutorial is True")


# ---------------------------------------------------------------------------
# Train state constants
# ---------------------------------------------------------------------------

def test_state_constants():
    """Test that all train state constants are defined."""
    src = _source()
    for state in ("STATE_COLD_BOOT", "STATE_RUNNING", "STATE_EMERGENCY",
                  "STATE_SIDING", "STATE_STATION_COAST"):
        assert state in src, f"{state} constant missing"
    print("✓ All train state constants present")


def test_fault_state_constants():
    """Test that fault state constants are defined."""
    src = _source()
    for state in ("FAULT_NONE", "FAULT_PENDING", "FAULT_RESOLVE"):
        assert state in src, f"{state} fault constant missing"
    print("✓ All fault state constants present")


def test_waypoint_type_constants():
    """Test that waypoint type constants are defined."""
    src = _source()
    assert "WP_STATION" in src, "WP_STATION constant missing"
    assert "WP_BRANCH"  in src, "WP_BRANCH constant missing"
    print("✓ WP_STATION and WP_BRANCH constants present")


# ---------------------------------------------------------------------------
# Hardware index constants
# ---------------------------------------------------------------------------

def test_hardware_indices_defined():
    """Test that hardware control indices are defined."""
    src = _source()
    assert "_SW_KEY"     in src, "_SW_KEY (Key Switch index) missing"
    assert "_SW_GUARD"   in src, "_SW_GUARD (Guarded Toggle index) missing"
    assert "_MT_REVERSE" in src, "_MT_REVERSE (Momentary toggle index) missing"
    assert "_BTN_EBRAKE" in src, "_BTN_EBRAKE (Big Red Button index) missing"
    assert "_ENC_THROTTLE" in src, "_ENC_THROTTLE (Core encoder index) missing"
    assert "_ENC_SWITCH"   in src, "_ENC_SWITCH (Satellite encoder index) missing"
    print("✓ All hardware index constants defined")


# ---------------------------------------------------------------------------
# Physics constants
# ---------------------------------------------------------------------------

def test_physics_constants():
    """Test that key physics constants are defined."""
    src = _source()
    assert "MAX_VELOCITY"   in src, "MAX_VELOCITY constant missing"
    assert "THROTTLE_STEP"  in src, "THROTTLE_STEP constant missing"
    assert "ACCEL_RATE"     in src, "ACCEL_RATE constant missing"
    assert "DECEL_RATE"     in src, "DECEL_RATE constant missing"
    assert "EBRAKE_RATE"    in src, "EBRAKE_RATE constant missing"
    print("✓ Physics constants present")


def test_heat_constants():
    """Test that heat and fault timing constants are defined."""
    src = _source()
    assert "HEAT_RISE_RATE"  in src, "HEAT_RISE_RATE constant missing"
    assert "HEAT_DECAY_RATE" in src, "HEAT_DECAY_RATE constant missing"
    assert "HEAT_MAX"        in src, "HEAT_MAX constant missing"
    assert "FAULT_THRESHOLD" in src, "FAULT_THRESHOLD constant missing"
    assert "FAULT_TIMEOUT"   in src, "FAULT_TIMEOUT constant missing"
    print("✓ Heat / fault constants present")


def test_score_constants():
    """Test that score (wage) constants are defined."""
    src = _source()
    assert "SCORE_PERFECT_STOP"     in src, "SCORE_PERFECT_STOP missing"
    assert "SCORE_GOOD_STOP"        in src, "SCORE_GOOD_STOP missing"
    assert "SCORE_OVERSHOOT"        in src, "SCORE_OVERSHOOT missing"
    assert "SCORE_WRONG_BRANCH"     in src, "SCORE_WRONG_BRANCH missing"
    assert "SCORE_FAULT_UNRESOLVED" in src, "SCORE_FAULT_UNRESOLVED missing"
    print("✓ Score (wage) constants present")


# ---------------------------------------------------------------------------
# Route definition
# ---------------------------------------------------------------------------

def test_route_defined():
    """Test that the ROUTE list is defined and non-empty."""
    src = _source()
    assert "ROUTE = [" in src or "ROUTE=[" in src, "ROUTE list missing"
    assert "WP_STATION" in src, "ROUTE must contain at least one station"
    assert "WP_BRANCH"  in src, "ROUTE must contain at least one branch"
    print("✓ ROUTE list defined with stations and branches")


def test_route_waypoint_fields():
    """Test that branch waypoints include a direction field."""
    src = _source()
    # Both LEFT and RIGHT directions must appear in the route
    assert '"direction": "RIGHT"' in src or "'direction': 'RIGHT'" in src, \
        "ROUTE must have a RIGHT branch"
    assert '"direction": "LEFT"' in src or "'direction': 'LEFT'" in src, \
        "ROUTE must have a LEFT branch"
    print("✓ ROUTE branch waypoints have direction fields")


# ---------------------------------------------------------------------------
# Hardware accessor methods
# ---------------------------------------------------------------------------

def test_hardware_accessor_methods():
    """Test that hardware state reader methods are present."""
    src = _source()
    assert "_key_is_on"        in src, "_key_is_on method missing"
    assert "_guard_is_up"      in src, "_guard_is_up method missing"
    assert "_ebrake_pressed"   in src, "_ebrake_pressed method missing"
    assert "_reverse_held"     in src, "_reverse_held method missing"
    assert "_toggle_state"     in src, "_toggle_state method missing"
    assert "_sat_encoder_pos"  in src, "_sat_encoder_pos method missing"
    print("✓ Hardware accessor methods present")


def test_throttle_encoder_method():
    """Test that throttle encoder reading is implemented."""
    src = _source()
    assert "_read_throttle_encoder" in src, "_read_throttle_encoder method missing"
    assert "encoder_positions"      in src, "encoder_positions access missing"
    print("✓ Throttle encoder reading implemented")


# ---------------------------------------------------------------------------
# Game logic methods
# ---------------------------------------------------------------------------

def test_physics_update_method():
    """Test that physics update method is present."""
    src = _source()
    assert "_update_physics" in src, "_update_physics method missing"
    print("✓ _update_physics method present")


def test_fault_methods():
    """Test that fault management methods are present."""
    src = _source()
    assert "_tick_faults"    in src, "_tick_faults method missing"
    assert "_trigger_fault"  in src, "_trigger_fault method missing"
    print("✓ Fault management methods present")


def test_branch_methods():
    """Test that branch-switching methods are present."""
    src = _source()
    assert "_check_branch"   in src, "_check_branch method missing"
    assert "_resolve_branch" in src, "_resolve_branch method missing"
    print("✓ Branch switch methods present")


def test_station_methods():
    """Test that station approach/scoring methods are present."""
    src = _source()
    assert "_check_station_coast" in src, "_check_station_coast method missing"
    assert "_score_station_stop"  in src, "_score_station_stop method missing"
    print("✓ Station approach / scoring methods present")


def test_cold_boot_method():
    """Test that the cold-boot startup sequence is implemented."""
    src = _source()
    assert "_run_cold_boot"       in src, "_run_cold_boot method missing"
    assert "STATE_COLD_BOOT"      in src, "STATE_COLD_BOOT used in run() loop"
    print("✓ Cold-boot startup sequence present")


def test_emergency_disarm_method():
    """Test that the emergency-brake disarm sequence is implemented."""
    src = _source()
    assert "_run_emergency_disarm" in src, "_run_emergency_disarm method missing"
    assert "STATE_EMERGENCY"       in src, "STATE_EMERGENCY used in run() loop"
    print("✓ Emergency-brake disarm sequence present")


def test_siding_method():
    """Test that the siding reverse-out sequence is implemented."""
    src = _source()
    assert "_run_siding"   in src, "_run_siding method missing"
    assert "STATE_SIDING"  in src or "_run_siding" in src, \
        "Siding must be referenced in game logic"
    print("✓ Siding reverse-out sequence present")


def test_render_and_display_helpers():
    """Test that rendering and display helper methods are present."""
    src = _source()
    assert "_render_windshield"      in src, "_render_windshield method missing"
    assert "_update_oled_running"    in src, "_update_oled_running method missing"
    assert "_update_segment_display" in src, "_update_segment_display method missing"
    print("✓ Render and display helpers present")


# ---------------------------------------------------------------------------
# Vanishing-point animation
# ---------------------------------------------------------------------------

def test_animate_vanishing_point_in_matrix_animations():
    """Test that animate_vanishing_point is defined in matrix_animations.py."""
    assert os.path.exists(_ANIM_PATH), "matrix_animations.py does not exist"
    with open(_ANIM_PATH, 'r') as f:
        anim_src = f.read()
    assert "def animate_vanishing_point" in anim_src, \
        "animate_vanishing_point not in matrix_animations.py"
    print("✓ animate_vanishing_point defined in matrix_animations.py")


def test_animate_vanishing_point_signature():
    """Test that animate_vanishing_point accepts required parameters."""
    with open(_ANIM_PATH, 'r') as f:
        anim_src = f.read()
    match = re.search(r'def animate_vanishing_point\(([^)]+)\)', anim_src)
    assert match is not None, "Could not find animate_vanishing_point signature"
    sig = match.group(1)
    assert "matrix_manager" in sig, "matrix_manager parameter missing"
    assert "arch_offset"    in sig, "arch_offset parameter missing"
    assert "speed_fraction" in sig, "speed_fraction parameter missing"
    assert "fault_flash"    in sig, "fault_flash parameter missing"
    print("✓ animate_vanishing_point has correct signature")


def test_vanishing_point_draws_rails():
    """Test that animate_vanishing_point renders converging track rails."""
    with open(_ANIM_PATH, 'r') as f:
        anim_src = f.read()
    start = anim_src.find("def animate_vanishing_point")
    end   = anim_src.find("\ndef ", start + 1)
    body  = anim_src[start:end] if end != -1 else anim_src[start:]
    assert "left_x"  in body, "Left rail not drawn in animate_vanishing_point"
    assert "right_x" in body, "Right rail not drawn in animate_vanishing_point"
    assert "arch"     in body.lower(), "Support arches missing from vanishing-point"
    print("✓ animate_vanishing_point draws rails and arches")


def test_vanishing_point_fault_flash():
    """Test that animate_vanishing_point handles fault_flash border."""
    with open(_ANIM_PATH, 'r') as f:
        anim_src = f.read()
    start = anim_src.find("def animate_vanishing_point")
    end   = anim_src.find("\ndef ", start + 1)
    body  = anim_src[start:end] if end != -1 else anim_src[start:]
    assert "fault_flash" in body, "fault_flash not used inside animate_vanishing_point"
    assert "Palette.RED"  in body, "Red border missing for fault_flash"
    print("✓ animate_vanishing_point handles fault_flash border")


def test_vanishing_point_logic():
    """Test the vanishing-point pixel math with a mock matrix manager."""

    class _MockMM:
        def __init__(self, w=16, h=16):
            self.width  = w
            self.height = h
            self.pixels = {}
            self.cleared = False

        def fill(self, color, show=False, cancel_tasks=False):
            self.pixels = {}
            self.cleared = True

        def draw_pixel(self, x, y, color, brightness=1.0):
            if 0 <= x < self.width and 0 <= y < self.height:
                self.pixels[(x, y)] = color

    # Import the animation function directly via source exec to avoid
    # circular-import issues with CircuitPython-specific modules.
    import importlib.util
    import types

    # Provide stub modules required by matrix_animations
    palette_stub = types.ModuleType("utilities.palette")

    class _Palette:
        OFF   = (0, 0, 0)
        RED   = (255, 0, 0)
        WHITE = (255, 255, 255)
        BLUE  = (0, 0, 255)
        GREEN = (0, 255, 0)

    palette_stub.Palette = _Palette
    sys.modules.setdefault("utilities", types.ModuleType("utilities"))
    sys.modules["utilities.palette"] = palette_stub
    sys.modules.setdefault("adafruit_ticks", types.ModuleType("adafruit_ticks"))
    sys.modules["adafruit_ticks"].ticks_ms   = lambda: 0
    sys.modules["adafruit_ticks"].ticks_diff = lambda a, b: a - b

    spec = importlib.util.spec_from_file_location("matrix_animations", _ANIM_PATH)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    mm = _MockMM(16, 16)
    mod.animate_vanishing_point(mm, arch_offset=0.0, speed_fraction=0.5, fault_flash=False)

    assert mm.cleared, "animate_vanishing_point should call fill() to clear the frame"
    assert len(mm.pixels) > 0, "No pixels drawn by animate_vanishing_point"

    # With fault_flash=False no pixel should be at the top-left corner (0, 0)
    # unless the border is drawn.  Test fault_flash=True draws border pixel.
    mm2 = _MockMM(16, 16)
    mod.animate_vanishing_point(mm2, arch_offset=0.0, speed_fraction=0.5, fault_flash=True)
    assert (0, 0) in mm2.pixels, "Red border pixel (0,0) missing when fault_flash=True"
    print("✓ animate_vanishing_point pixel math validated")


# ---------------------------------------------------------------------------
# Tone constants
# ---------------------------------------------------------------------------

def test_maglev_tone_constants():
    """Test that MAGLEV_HORN, MAGLEV_BRAKE, and MAGLEV_FAULT tone constants are defined."""
    with open(_TONES_PATH, 'r') as f:
        tones_src = f.read()
    assert "MAGLEV_HORN = {"  in tones_src, "MAGLEV_HORN tone constant missing"
    assert "MAGLEV_BRAKE = {" in tones_src, "MAGLEV_BRAKE tone constant missing"
    assert "MAGLEV_FAULT = {" in tones_src, "MAGLEV_FAULT tone constant missing"
    print("✓ MAGLEV_HORN, MAGLEV_BRAKE, and MAGLEV_FAULT tone constants defined")


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
# Icon library
# ---------------------------------------------------------------------------

def test_maglev_express_icon_in_library():
    """Test that MAGLEV_EXPRESS icon is defined in icons.py."""
    with open(_ICONS_PATH, 'r', encoding='utf-8') as f:
        icons_src = f.read()
    assert "MAGLEV_EXPRESS" in icons_src, \
        "MAGLEV_EXPRESS not registered in icons.py"
    assert '"MAGLEV_EXPRESS":' in icons_src, \
        "MAGLEV_EXPRESS not in ICON_LIBRARY dict"
    print("✓ MAGLEV_EXPRESS icon defined and registered")


def test_icons_valid_syntax():
    """Test that icons.py still has valid Python syntax after additions."""
    with open(_ICONS_PATH, 'r', encoding='utf-8') as f:
        icons_src = f.read()
    try:
        ast.parse(icons_src)
    except SyntaxError as e:
        raise AssertionError(f"Syntax error in icons.py: {e}")
    print("✓ icons.py valid syntax")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Running Maglev Express mode tests...\n")

    tests = [
        test_file_exists,
        test_valid_syntax,
        test_inherits_game_mode,
        test_run_method_present,
        test_maglev_express_in_manifest,
        test_maglev_express_manifest_metadata,
        test_maglev_express_difficulty_settings,
        test_maglev_express_has_tutorial,
        test_state_constants,
        test_fault_state_constants,
        test_waypoint_type_constants,
        test_hardware_indices_defined,
        test_physics_constants,
        test_heat_constants,
        test_score_constants,
        test_route_defined,
        test_route_waypoint_fields,
        test_hardware_accessor_methods,
        test_throttle_encoder_method,
        test_physics_update_method,
        test_fault_methods,
        test_branch_methods,
        test_station_methods,
        test_cold_boot_method,
        test_emergency_disarm_method,
        test_siding_method,
        test_render_and_display_helpers,
        test_animate_vanishing_point_in_matrix_animations,
        test_animate_vanishing_point_signature,
        test_vanishing_point_draws_rails,
        test_vanishing_point_fault_flash,
        test_vanishing_point_logic,
        test_maglev_tone_constants,
        test_tones_valid_syntax,
        test_maglev_express_icon_in_library,
        test_icons_valid_syntax,
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
