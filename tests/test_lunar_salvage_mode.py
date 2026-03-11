"""Tests for Lunar Salvage game mode.

Verifies the manifest registration, physics helpers, and core gameplay
logic without importing real CircuitPython hardware modules.
"""

import sys
import os
import math
import re
import asyncio
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


# ---------------------------------------------------------------------------
# Manifest / registration tests
# ---------------------------------------------------------------------------

def test_lunar_salvage_mode_file_exists():
    """The lunar_salvage.py source file must exist."""
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'lunar_salvage.py')
    assert os.path.exists(path), "lunar_salvage.py does not exist"
    print("✓ lunar_salvage.py exists")


def test_lunar_salvage_in_manifest():
    """LUNAR_SALVAGE must be registered in MODE_REGISTRY."""
    from modes.manifest import MODE_REGISTRY

    assert "LUNAR_SALVAGE" in MODE_REGISTRY, "LUNAR_SALVAGE not found in MODE_REGISTRY"
    print("✓ LUNAR_SALVAGE found in MODE_REGISTRY")


def test_lunar_salvage_manifest_fields():
    """All required manifest fields must be present and correct."""
    from modes.manifest import MODE_REGISTRY

    meta = MODE_REGISTRY["LUNAR_SALVAGE"]
    assert meta["id"] == "LUNAR_SALVAGE"
    assert meta["name"] == "LUNAR SALVAGE"
    assert meta["module_path"] == "modes.lunar_salvage"
    assert meta["class_name"] == "LunarSalvage"
    assert meta["icon"] == "LUNAR_SALVAGE"
    assert "CORE" in meta["requires"], "LUNAR_SALVAGE should only require CORE"
    assert meta["menu"] == "CORE", "LUNAR_SALVAGE should appear in the CORE menu"
    print("✓ LUNAR_SALVAGE manifest fields are correct")


def test_lunar_salvage_difficulty_settings():
    """LUNAR_SALVAGE must expose a difficulty setting with EASY/NORMAL/HARD/INSANE."""
    from modes.manifest import MODE_REGISTRY

    settings = MODE_REGISTRY["LUNAR_SALVAGE"]["settings"]
    diff = next((s for s in settings if s["key"] == "difficulty"), None)
    assert diff is not None, "Missing difficulty setting"
    assert diff["label"] == "DIFF"
    assert "EASY" in diff["options"]
    assert "NORMAL" in diff["options"]
    assert "HARD" in diff["options"]
    assert "INSANE" in diff["options"]
    assert diff["default"] == "NORMAL"
    print("✓ LUNAR_SALVAGE difficulty settings are correct")


def test_lunar_salvage_icon_registered():
    """LUNAR_SALVAGE icon must be present in the icon library."""
    from utilities.icons import Icons

    assert "LUNAR_SALVAGE" in Icons.ICON_LIBRARY, "LUNAR_SALVAGE icon not in ICON_LIBRARY"
    icon = Icons.ICON_LIBRARY["LUNAR_SALVAGE"]
    assert len(icon) in (64, 256), f"Icon should be 64 or 256 pixels, got {len(icon)}"
    print(f"✓ LUNAR_SALVAGE icon registered ({len(icon)} pixels)")


# ---------------------------------------------------------------------------
# Source-level structural tests (no hardware import needed)
# ---------------------------------------------------------------------------

def _read_source():
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'lunar_salvage.py')
    with open(path) as fh:
        return fh.read()


def test_lunar_salvage_matrix_dimensions():
    """lunar_salvage.py must declare MATRIX_WIDTH and MATRIX_HEIGHT as 16."""
    src = _read_source()
    assert re.search(r'MATRIX_WIDTH\s*=\s*16', src), "MATRIX_WIDTH should be 16"
    assert re.search(r'MATRIX_HEIGHT\s*=\s*16', src), "MATRIX_HEIGHT should be 16"
    print("✓ MATRIX_WIDTH/HEIGHT are both 16")


def test_lunar_salvage_physics_constants():
    """Physics constants must be present in the source."""
    src = _read_source()
    assert "GRAVITY_BASE" in src, "Missing GRAVITY_BASE constant"
    assert "THRUST_FORCE" in src, "Missing THRUST_FORCE constant"
    assert "CRASH_SPEED" in src, "Missing CRASH_SPEED constant"
    assert "DEGREES_PER_TICK" in src, "Missing DEGREES_PER_TICK constant"
    print("✓ Physics constants are defined")


def test_lunar_salvage_pad_width():
    """The landing pad must be 2 pixels wide as specified in the issue."""
    src = _read_source()
    assert re.search(r'PAD_WIDTH\s*=\s*2', src), "PAD_WIDTH should be 2 (issue spec)"
    print("✓ PAD_WIDTH is 2")


def test_lunar_salvage_uses_encoder_and_buttons():
    """Source must use the encoder and both buttons (0 and 1)."""
    src = _read_source()
    assert "encoder_positions" in src, "Should read encoder_positions for rotation"
    assert re.search(r'is_button_pressed\(0\)', src), "Should read Button 0 (thruster)"
    assert re.search(r'is_button_pressed\(1\)', src), "Should read Button 1 (tractor beam)"
    print("✓ Encoder and both buttons are used")


def test_lunar_salvage_core_only():
    """LUNAR_SALVAGE must only require CORE (no satellite hardware)."""
    from modes.manifest import MODE_REGISTRY

    requires = MODE_REGISTRY["LUNAR_SALVAGE"]["requires"]
    assert requires == ["CORE"], f"Should only require CORE, got {requires}"
    print("✓ LUNAR_SALVAGE is Core-only")


# ---------------------------------------------------------------------------
# Physics logic tests
# ---------------------------------------------------------------------------

def _make_mode():
    """Create a LunarSalvage instance with a minimal mocked core."""
    core = MagicMock()
    core.data.get_setting.return_value = "NORMAL"
    core.data.get_high_score.return_value = 0
    core.data.save_high_score.return_value = False
    core.hid.encoder_positions = [0]
    core.hid.is_button_pressed.return_value = False
    from modes.lunar_salvage import LunarSalvage
    return LunarSalvage(core)


def test_physics_gravity_applied():
    """Gravity must increase vel_y each frame even without thrust."""
    mode = _make_mode()
    mode.vel_y = 0.0
    mode._update_physics(thrust_on=False)
    assert mode.vel_y > 0, "Gravity should pull ship downward (increase vel_y)"
    print(f"✓ Gravity applied: vel_y = {mode.vel_y:.4f}")


def test_physics_thrust_up_at_90_degrees():
    """Thrust at 90° (pointing up) should reduce vel_y by THRUST_FORCE."""
    mode = _make_mode()
    mode.angle = 90.0    # pointing straight up in screen coords
    mode.vel_y = 0.0
    mode.vel_x = 0.0
    mode._update_physics(thrust_on=True)
    # vel_y = gravity() - THRUST_FORCE  (thrust upward = negative screen-y delta)
    expected = mode._gravity() - mode.THRUST_FORCE
    assert abs(mode.vel_y - expected) < 1e-6, (
        f"vel_y should be {expected:.4f}, got {mode.vel_y:.4f}"
    )
    print(f"✓ Thrust at 90° correct: vel_y = {mode.vel_y:.4f}")


def test_physics_thrust_right_at_0_degrees():
    """Thrust at 0° (pointing right) should increase vel_x only."""
    mode = _make_mode()
    mode.angle = 0.0
    mode.vel_x = 0.0
    mode.vel_y = 0.0
    mode._update_physics(thrust_on=True)
    assert mode.vel_x > 0, "Thrust at 0° should increase vel_x"
    assert abs(mode.vel_y - mode._gravity()) < 1e-6, (
        "Thrust at 0° should not add vertical force beyond gravity"
    )
    print(f"✓ Thrust at 0°: vel_x = {mode.vel_x:.4f}")


def test_wall_bounce_left_slow():
    """Ship gently hitting the left wall should bounce without crashing."""
    mode = _make_mode()
    mode.ship_x = -0.5
    mode.vel_x = -0.2   # slow horizontal speed
    crashed = mode._check_wall_collision()
    assert not crashed, "Slow left-wall hit should not crash"
    assert mode.ship_x == 0.0, "Ship should be placed at x=0 after bounce"
    assert mode.vel_x > 0, "vel_x should be reversed after left-wall bounce"
    print(f"✓ Slow left-wall bounce: vel_x = {mode.vel_x:.4f}")


def test_wall_crash_left_fast():
    """Ship hitting the left wall above crash speed must crash."""
    mode = _make_mode()
    mode.ship_x = -0.5
    mode.vel_x = -(mode._crash_speed + 0.1)
    crashed = mode._check_wall_collision()
    assert crashed, "Fast left-wall hit should be a crash"
    print("✓ Fast left-wall crash detected")


def test_floor_crash_fast():
    """Ship hitting the floor above crash speed must crash."""
    mode = _make_mode()
    mode.ship_y = float(mode.MATRIX_HEIGHT)
    mode.vel_y = mode._crash_speed + 0.1
    crashed = mode._check_wall_collision()
    assert crashed, "High-speed floor impact should crash"
    print("✓ Floor crash detected correctly")


def test_floor_bounce_no_crash():
    """Ship gently touching the floor should bounce, not crash."""
    mode = _make_mode()
    mode.ship_y = float(mode.MATRIX_HEIGHT)
    mode.vel_y = mode._crash_speed * 0.5
    crashed = mode._check_wall_collision()
    assert not crashed, "Gentle floor touch should not crash"
    assert mode.ship_y == float(mode.MATRIX_HEIGHT - 1), (
        "Ship should sit at MATRIX_HEIGHT-1 after floor bounce"
    )
    print("✓ Gentle floor bounce: no crash")


def test_over_pad_detection_in_range():
    """_over_pad returns True when ship is directly above the pad."""
    mode = _make_mode()
    mode._pad_x = 5   # pad covers x=5, x=6

    mode.ship_x = 5.0
    mode.ship_y = float(mode.MATRIX_HEIGHT - 2)
    assert mode._over_pad(), "Should be over pad at x=5, near floor"

    mode.ship_x = 6.0
    assert mode._over_pad(), "Should be over pad at x=6 (second pad pixel)"
    print("✓ _over_pad: True when within range")


def test_over_pad_detection_out_of_range():
    """_over_pad returns False when ship is to the side or too high."""
    mode = _make_mode()
    mode._pad_x = 5

    # One pixel left of pad
    mode.ship_x = 4.0
    mode.ship_y = float(mode.MATRIX_HEIGHT - 2)
    assert not mode._over_pad(), "x=4 is left of pad (starts at 5)"

    # Too high
    mode.ship_x = 5.0
    mode.ship_y = 5.0
    assert not mode._over_pad(), "y=5 is too high for tractor range"
    print("✓ _over_pad: False when outside range")


def test_angle_full_rotation_wraps_to_zero():
    """32 encoder ticks (one full revolution) must wrap back to 0°."""
    mode = _make_mode()
    ticks_per_rev = round(360.0 / mode.DEGREES_PER_TICK)
    angle = (ticks_per_rev * mode.DEGREES_PER_TICK) % 360.0
    assert angle == 0.0, f"Full revolution should return 0°, got {angle}"
    print(f"✓ {ticks_per_rev} ticks wraps back to 0°")


def test_new_pad_within_safe_bounds():
    """Landing pad must always spawn within the safe inner region."""
    mode = _make_mode()
    for _ in range(50):
        mode._new_pad()
        assert mode._pad_x >= 2, "Pad left edge must not touch the left border"
        assert mode._pad_x + mode.PAD_WIDTH - 1 <= mode.MATRIX_WIDTH - 3, (
            "Pad right edge must not touch the right border"
        )
    print("✓ _new_pad always within safe bounds")


def test_difficulty_gravity_multipliers_are_distinct():
    """Each difficulty level must produce a distinct gravity value."""
    mode = _make_mode()
    gravities = {
        round(mode.GRAVITY_BASE * mode._DIFFICULTY[d]["gravity_mult"], 6)
        for d in ("EASY", "NORMAL", "HARD", "INSANE")
    }
    assert len(gravities) == 4, "Each difficulty should produce a unique gravity"
    print("✓ Four difficulty levels yield four distinct gravity values")


def test_render_draws_ship_body_pixel():
    """_render must place the ship body pixel at the ship's rounded position."""
    mode = _make_mode()
    mode.ship_x = 8.0
    mode.ship_y = 8.0
    mode.angle = 90.0
    mode._pad_x = 2

    # Replace matrix with a simple pixel recorder
    pixels = {}

    def _draw_pixel(x, y, color):
        pixels[(x, y)] = color

    mode.core.matrix.clear.side_effect = lambda: pixels.clear()
    mode.core.matrix.draw_pixel.side_effect = _draw_pixel

    mode._render(tractor_active=False, frame_count=0)

    assert (8, 8) in pixels, "Ship body pixel should be at (8, 8)"
    print("✓ Ship body pixel rendered at correct position")


def test_render_draws_pad_pixels():
    """_render must draw exactly PAD_WIDTH pixels for the landing pad."""
    mode = _make_mode()
    mode.ship_x = 0.0
    mode.ship_y = 0.0
    mode.angle = 90.0
    mode._pad_x = 6

    pixels = {}

    def _draw_pixel(x, y, color):
        pixels[(x, y)] = color

    mode.core.matrix.clear.side_effect = lambda: pixels.clear()
    mode.core.matrix.draw_pixel.side_effect = _draw_pixel

    mode._render(tractor_active=False, frame_count=0)

    pad_pixels = [(x, y) for (x, y) in pixels if y == mode.MATRIX_HEIGHT - 1]
    assert len(pad_pixels) == mode.PAD_WIDTH, (
        f"Expected {mode.PAD_WIDTH} pad pixels, got {len(pad_pixels)}"
    )
    print(f"✓ Pad drawn with exactly {mode.PAD_WIDTH} pixels")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
