"""Tests for Bouncing Sprite screensaver mode.

Verifies:
- BouncingSprite._reset() places sprite at a random valid position/velocity
- BouncingSprite._step() moves sprite by its velocity each tick
- BouncingSprite._step() reverses vx on left/right wall collision
- BouncingSprite._step() reverses vy on top/bottom wall collision
- BouncingSprite._step() cycles colour index on every wall hit
- BouncingSprite._step() handles corner collision (both axes bounce together)
- BouncingSprite._build_frame() renders the correct palette bytes
- BouncingSprite velocity values are always non-zero integers (sub-pixel fixed-point)
- manifest.py contains a valid BOUNCING_SPRITE entry under ZERO_PLAYER
- icons.py exposes a BOUNCING_SPRITE icon that is 256 bytes
"""

import sys
import os
import traceback

# ---------------------------------------------------------------------------
# Mock CircuitPython / Adafruit hardware modules BEFORE importing src code
# ---------------------------------------------------------------------------

class _MockModule:
    """Catch-all stub that satisfies attribute access and call syntax."""
    def __getattr__(self, name):
        return _MockModule()

    def __call__(self, *args, **kwargs):
        return _MockModule()

    def __iter__(self):
        return iter([])

    def __int__(self):
        return 0


_CP_MODULES = [
    'digitalio', 'board', 'busio', 'neopixel', 'microcontroller',
    'analogio', 'audiocore', 'audiobusio', 'audioio', 'audiomixer',
    'audiopwmio', 'synthio', 'ulab', 'watchdog',
    'adafruit_mcp230xx', 'adafruit_mcp230xx.mcp23017',
    'adafruit_ticks',
    'adafruit_displayio_ssd1306',
    'adafruit_display_text', 'adafruit_display_text.label',
    'adafruit_ht16k33', 'adafruit_ht16k33.segments',
    'adafruit_httpserver', 'adafruit_bus_device', 'adafruit_register',
    'sdcardio', 'storage', 'displayio', 'terminalio',
    'adafruit_framebuf', 'framebufferio', 'rgbmatrix', 'supervisor',
]

for _mod in _CP_MODULES:
    if _mod not in sys.modules:
        sys.modules[_mod] = _MockModule()

# Provide a realistic adafruit_ticks so ticks_ms / ticks_diff work
import types as _types
_ticks_mod = _types.ModuleType('adafruit_ticks')
_ticks_mod.ticks_ms = lambda: 0
_ticks_mod.ticks_diff = lambda a, b: a - b
sys.modules['adafruit_ticks'] = _ticks_mod

# ---------------------------------------------------------------------------
# Add src to path
# ---------------------------------------------------------------------------

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# ===========================================================================
# Helpers
# ===========================================================================

def _make_sprite(width=16, height=16):
    """Return a BouncingSprite instance with buffers initialised."""
    from modes.bouncing_sprite import BouncingSprite
    from unittest.mock import MagicMock

    fake_core = MagicMock()
    sprite = BouncingSprite(fake_core)
    sprite.width = width
    sprite.height = height
    sprite._frame = bytearray(width * height)
    sprite._reset()
    return sprite


# ===========================================================================
# 1. _reset() – initial state
# ===========================================================================

def test_reset_sets_starting_position():
    """_reset() places the sprite at a random position within valid fixed-point bounds."""
    from modes.bouncing_sprite import _SPRITE_W, _SPRITE_H
    s = _make_sprite()
    s._reset()
    max_x_fp = (s.width - _SPRITE_W) << 8
    max_y_fp = (s.height - _SPRITE_H) << 8
    assert 0 <= s._x <= max_x_fp, \
        f"Expected x in [0, {max_x_fp}] after reset, got {s._x}"
    assert 0 <= s._y <= max_y_fp, \
        f"Expected y in [0, {max_y_fp}] after reset, got {s._y}"
    print(f"✓ _reset: sprite placed at valid starting position ({s._x >> 8}, {s._y >> 8})")


def test_reset_sets_starting_velocity():
    """_reset() sets a random non-zero sub-pixel velocity for both axes."""
    s = _make_sprite()
    s._reset()
    assert isinstance(s._vx, int), f"vx should be an int after reset, got {type(s._vx)}"
    assert isinstance(s._vy, int), f"vy should be an int after reset, got {type(s._vy)}"
    assert s._vx != 0, f"vx should be non-zero after reset, got {s._vx}"
    assert s._vy != 0, f"vy should be non-zero after reset, got {s._vy}"
    assert 179 <= abs(s._vx) <= 331, f"vx magnitude should be in [179, 331] after reset, got {abs(s._vx)}"
    assert 179 <= abs(s._vy) <= 331, f"vy magnitude should be in [179, 331] after reset, got {abs(s._vy)}"
    print(f"✓ _reset: velocity set to valid sub-pixel values (vx={s._vx}, vy={s._vy})")


# ===========================================================================
# 2. _step() – normal movement (no wall hit)
# ===========================================================================

def test_step_moves_sprite_by_velocity():
    """_step() advances the sprite position by (vx, vy) when no wall is hit."""
    s = _make_sprite(16, 16)
    s._x = 5
    s._y = 5
    s._vx = 1
    s._vy = 1
    s._step()
    assert s._x == 6, f"Expected x=6 after step, got {s._x}"
    assert s._y == 6, f"Expected y=6 after step, got {s._y}"
    print("✓ _step: sprite moves by velocity when no wall is hit")


def test_step_no_color_change_without_wall_hit():
    """_step() does not change colour when no wall is hit."""
    s = _make_sprite(16, 16)
    s._x = 5
    s._y = 5
    s._vx = 1
    s._vy = 1
    original_idx = s._color_idx
    s._step()
    assert s._color_idx == original_idx, \
        "Colour index should not change when sprite does not hit a wall"
    print("✓ _step: colour unchanged when no wall is hit")


# ===========================================================================
# 3. _step() – horizontal wall collisions
# ===========================================================================

def test_step_bounces_off_right_wall():
    """Sprite moving right reverses vx when it reaches the right boundary."""
    from modes.bouncing_sprite import _SPRITE_W
    s = _make_sprite(16, 16)
    max_x_fp = (16 - _SPRITE_W) << 8   # = 3328 (fixed-point)
    step = 256                           # 1 pixel per step in fixed-point
    s._x = max_x_fp - step + 1          # overshoots wall on next step; clamped to max_x_fp
    s._y = 5 << 8
    s._vx = step
    s._vy = 0
    s._step()
    assert s._x == max_x_fp, f"Expected x={max_x_fp} at right wall, got {s._x}"
    assert s._vx < 0, f"Expected vx<0 after right-wall bounce, got {s._vx}"
    print("✓ _step: vx reversed on right-wall collision")


def test_step_bounces_off_left_wall():
    """Sprite moving left reverses vx when it reaches x=0."""
    s = _make_sprite(16, 16)
    step = 256                  # 1 pixel per step in fixed-point
    s._x = step                 # 1 pixel from the left wall
    s._y = 5 << 8
    s._vx = -step
    s._vy = 0
    s._step()
    assert s._x == 0, f"Expected x=0 at left wall, got {s._x}"
    assert s._vx > 0, f"Expected vx>0 after left-wall bounce, got {s._vx}"
    print("✓ _step: vx reversed on left-wall collision")


def test_step_left_wall_clamps_position():
    """Sprite that would go negative is clamped to x=0."""
    s = _make_sprite(16, 16)
    step = 256                  # 1 pixel per step in fixed-point
    s._x = 0
    s._y = 5 << 8
    s._vx = -step
    s._vy = 0
    s._step()
    assert s._x == 0, f"Expected x clamped to 0, got {s._x}"
    assert s._vx > 0, "Expected vx reversed to positive"
    print("✓ _step: position clamped to 0 on left-wall hit")


# ===========================================================================
# 4. _step() – vertical wall collisions
# ===========================================================================

def test_step_bounces_off_bottom_wall():
    """Sprite moving down reverses vy when it reaches the bottom boundary."""
    from modes.bouncing_sprite import _SPRITE_H
    s = _make_sprite(16, 16)
    max_y_fp = (16 - _SPRITE_H) << 8   # = 3328 (fixed-point)
    step = 256                           # 1 pixel per step in fixed-point
    s._x = 5 << 8
    s._y = max_y_fp - step + 1          # overshoots wall on next step; clamped to max_y_fp
    s._vx = 0
    s._vy = step
    s._step()
    assert s._y == max_y_fp, f"Expected y={max_y_fp} at bottom wall, got {s._y}"
    assert s._vy < 0, f"Expected vy<0 after bottom-wall bounce, got {s._vy}"
    print("✓ _step: vy reversed on bottom-wall collision")


def test_step_bounces_off_top_wall():
    """Sprite moving up reverses vy when it reaches y=0."""
    s = _make_sprite(16, 16)
    step = 256                  # 1 pixel per step in fixed-point
    s._x = 5 << 8
    s._y = step                 # 1 pixel from the top wall
    s._vx = 0
    s._vy = -step
    s._step()
    assert s._y == 0, f"Expected y=0 at top wall, got {s._y}"
    assert s._vy > 0, f"Expected vy>0 after top-wall bounce, got {s._vy}"
    print("✓ _step: vy reversed on top-wall collision")


# ===========================================================================
# 5. _step() – colour cycling on wall hit
# ===========================================================================

def test_step_color_cycles_on_right_wall():
    """Colour index increments by 1 when sprite hits the right wall."""
    from modes.bouncing_sprite import _SPRITE_W, _COLOR_INDICES
    s = _make_sprite(16, 16)
    max_x_fp = (16 - _SPRITE_W) << 8   # = 3328 (fixed-point)
    step = 256                           # 1 pixel per step in fixed-point
    s._x = max_x_fp - step + 1          # overshoots right wall; clamped to max_x_fp
    s._y = 5 << 8
    s._vx = step
    s._vy = 0
    s._color_idx = 0
    s._step()
    assert s._color_idx == 1, \
        f"Colour index should advance to 1 on wall hit, got {s._color_idx}"
    print("✓ _step: colour index cycles on right-wall collision")


def test_step_color_cycles_on_top_wall():
    """Colour index increments by 1 when sprite hits the top wall."""
    s = _make_sprite(16, 16)
    step = 256                  # 1 pixel per step in fixed-point
    s._x = 5 << 8
    s._y = step                 # 1 pixel from the top wall
    s._vx = 0
    s._vy = -step
    s._color_idx = 2
    s._step()
    assert s._color_idx == 3, \
        f"Colour index should advance to 3 on top-wall hit, got {s._color_idx}"
    print("✓ _step: colour index cycles on top-wall collision")


def test_step_color_wraps_around():
    """Colour index wraps from last to first entry."""
    from modes.bouncing_sprite import _COLOR_INDICES
    s = _make_sprite(16, 16)
    step = 256                  # 1 pixel per step in fixed-point
    s._x = 5 << 8
    s._y = step                 # 1 pixel from the top wall
    s._vx = 0
    s._vy = -step
    last_idx = len(_COLOR_INDICES) - 1
    s._color_idx = last_idx
    s._step()
    assert s._color_idx == 0, \
        f"Colour index should wrap to 0 after last entry, got {s._color_idx}"
    print("✓ _step: colour index wraps around correctly")


def test_step_corner_collision_cycles_color_once():
    """Corner collision (both axes hit simultaneously) cycles colour exactly once."""
    from modes.bouncing_sprite import _SPRITE_W, _SPRITE_H
    s = _make_sprite(16, 16)
    step = 256                          # 1 pixel per step in fixed-point
    max_x_fp = (16 - _SPRITE_W) << 8   # = 3328
    max_y_fp = (16 - _SPRITE_H) << 8   # = 3328
    s._x = max_x_fp - step + 1         # overshoots right wall; clamped to max_x_fp
    s._y = max_y_fp - step + 1         # overshoots bottom wall; clamped to max_y_fp
    s._vx = step
    s._vy = step
    s._color_idx = 0
    s._step()
    assert s._color_idx == 1, \
        f"Corner collision should cycle colour once, got index {s._color_idx}"
    print("✓ _step: corner collision cycles colour exactly once")


# ===========================================================================
# 6. _step() – integer-only velocities
# ===========================================================================

def test_step_velocity_always_integer():
    """Velocity values are always non-zero integers after multiple steps."""
    s = _make_sprite(16, 16)
    for _ in range(200):
        s._step()
        assert isinstance(s._vx, int), f"vx is not an int: {type(s._vx)}"
        assert isinstance(s._vy, int), f"vy is not an int: {type(s._vy)}"
        assert s._vx != 0, f"vx must be non-zero, got {s._vx}"
        assert s._vy != 0, f"vy must be non-zero, got {s._vy}"
    print("✓ _step: velocity remains a non-zero integer throughout simulation")


def test_step_position_always_integer():
    """Position values are always integers after multiple steps."""
    s = _make_sprite(16, 16)
    for _ in range(200):
        s._step()
        assert isinstance(s._x, int), f"x is not an int: {type(s._x)}"
        assert isinstance(s._y, int), f"y is not an int: {type(s._y)}"
    print("✓ _step: position remains integer throughout simulation")


# ===========================================================================
# 7. _step() – sprite stays within bounds
# ===========================================================================

def test_step_sprite_stays_within_bounds():
    """After many steps the sprite's bounding box never exceeds the grid."""
    from modes.bouncing_sprite import _SPRITE_W, _SPRITE_H
    s = _make_sprite(16, 16)
    max_x_fp = (16 - _SPRITE_W) << 8
    max_y_fp = (16 - _SPRITE_H) << 8
    for _ in range(500):
        s._step()
        assert 0 <= s._x <= max_x_fp, \
            f"x={s._x} out of fixed-point bounds [0, {max_x_fp}]"
        assert 0 <= s._y <= max_y_fp, \
            f"y={s._y} out of fixed-point bounds [0, {max_y_fp}]"
    print("✓ _step: sprite stays within grid bounds over 500 steps")


# ===========================================================================
# 8. _build_frame() – rendering
# ===========================================================================

def test_build_frame_clears_previous_content():
    """_build_frame() clears the buffer before drawing."""
    s = _make_sprite(16, 16)
    # Pre-fill with garbage
    for i in range(len(s._frame)):
        s._frame[i] = 99
    s._x = 5
    s._y = 5
    s._build_frame()
    # Pixel at (0, 0) is outside the sprite at (5, 5) and must be cleared.
    assert s._frame[0] == 0, "Frame buffer should be cleared for off-sprite pixels"
    print("✓ _build_frame: buffer is cleared before drawing the sprite")


def test_build_frame_primary_pixels_use_current_color():
    """Primary-type sprite pixels use the current colour index."""
    from modes.bouncing_sprite import _COLOR_INDICES, _SPRITE_PIXELS
    s = _make_sprite(16, 16)
    s._x = 0
    s._y = 0
    s._color_idx = 0
    s._build_frame()
    expected_primary = _COLOR_INDICES[0]
    for dx, dy, ptype in _SPRITE_PIXELS:
        if ptype == 1:
            val = s._frame[dy * 16 + dx]
            assert val == expected_primary, \
                f"Primary pixel at ({dx},{dy}) should be {expected_primary}, got {val}"
    print("✓ _build_frame: primary pixels use the current palette colour")


def test_build_frame_accent_pixel_is_fixed():
    """Accent-type pixel always uses the fixed accent palette index."""
    from modes.bouncing_sprite import _ACCENT_INDEX, _SPRITE_PIXELS, _COLOR_INDICES
    s = _make_sprite(16, 16)
    s._x = 0
    s._y = 0
    # Try every colour index; accent must always be _ACCENT_INDEX.
    for cidx in range(len(_COLOR_INDICES)):
        s._color_idx = cidx
        s._build_frame()
        for dx, dy, ptype in _SPRITE_PIXELS:
            if ptype == 2:
                val = s._frame[dy * 16 + dx]
                assert val == _ACCENT_INDEX, \
                    f"Accent pixel at ({dx},{dy}) should always be {_ACCENT_INDEX}, got {val}"
    print(f"✓ _build_frame: accent pixel is always palette index {_ACCENT_INDEX}")


def test_build_frame_off_pixels_are_zero():
    """Grid positions not covered by the sprite are set to 0 (off)."""
    from modes.bouncing_sprite import _SPRITE_PIXELS
    s = _make_sprite(16, 16)
    s._x = 4 << 8               # fixed-point for pixel position 4
    s._y = 4 << 8
    s._build_frame()

    # Collect sprite pixel positions (using actual pixel coordinates)
    sprite_positions = {(4 + dx, 4 + dy) for dx, dy, _ in _SPRITE_PIXELS}

    for y in range(16):
        for x in range(16):
            if (x, y) not in sprite_positions:
                assert s._frame[y * 16 + x] == 0, \
                    f"Off-sprite pixel ({x},{y}) should be 0, got {s._frame[y * 16 + x]}"
    print("✓ _build_frame: all off-sprite pixels are 0")


def test_build_frame_color_change_updates_pixels():
    """After a colour change, _build_frame() renders the new colour."""
    from modes.bouncing_sprite import _COLOR_INDICES, _SPRITE_PIXELS
    s = _make_sprite(16, 16)
    s._x = 0
    s._y = 0

    # Cycle through all colour indices and verify each is reflected in the frame.
    for cidx in range(len(_COLOR_INDICES)):
        s._color_idx = cidx
        s._build_frame()
        expected = _COLOR_INDICES[cidx]
        for dx, dy, ptype in _SPRITE_PIXELS:
            if ptype == 1:
                val = s._frame[dy * 16 + dx]
                assert val == expected, \
                    f"colour_idx={cidx}: primary pixel at ({dx},{dy}) should be {expected}, got {val}"
    print("✓ _build_frame: new colour reflected after _color_idx change")


# ===========================================================================
# 9. Manifest entry
# ===========================================================================

def test_bouncing_sprite_in_manifest():
    """BOUNCING_SPRITE entry exists in MODE_REGISTRY with all required fields."""
    from modes.manifest import MODE_REGISTRY

    assert "BOUNCING_SPRITE" in MODE_REGISTRY, \
        "BOUNCING_SPRITE not found in MODE_REGISTRY"
    meta = MODE_REGISTRY["BOUNCING_SPRITE"]

    required_fields = ["id", "name", "module_path", "class_name", "icon", "menu", "requires", "settings"]
    for field in required_fields:
        assert field in meta, \
            f"BOUNCING_SPRITE missing required field '{field}'"

    assert meta["id"] == "BOUNCING_SPRITE"
    assert meta["module_path"] == "modes.bouncing_sprite", \
        "BOUNCING_SPRITE module_path should be 'modes.bouncing_sprite'"
    assert meta["class_name"] == "BouncingSprite", \
        "BOUNCING_SPRITE class_name should be 'BouncingSprite'"
    assert meta["menu"] == "ZERO_PLAYER", \
        "BOUNCING_SPRITE should belong to the ZERO_PLAYER submenu"
    assert meta["icon"] == "BOUNCING_SPRITE", \
        "BOUNCING_SPRITE should reference the BOUNCING_SPRITE icon"
    assert "CORE" in meta["requires"], \
        "BOUNCING_SPRITE should require CORE"
    print("✓ manifest: BOUNCING_SPRITE entry is complete and correct")


# ===========================================================================
# 10. Icon entry
# ===========================================================================

def test_bouncing_sprite_icon_in_icons():
    """icons.py exposes a BOUNCING_SPRITE icon that is a non-empty bytes object."""
    from utilities.icons import Icons

    icon = Icons.get("BOUNCING_SPRITE")
    assert icon is not None, "Icons library should contain a BOUNCING_SPRITE icon"
    assert isinstance(icon, (bytes, bytearray)), \
        "BOUNCING_SPRITE icon should be bytes or bytearray"
    assert len(icon) > 0, "BOUNCING_SPRITE icon should not be empty"
    print(f"✓ icons: BOUNCING_SPRITE icon present ({len(icon)} bytes)")


def test_bouncing_sprite_icon_correct_size():
    """BOUNCING_SPRITE icon has the expected 16×16 = 256-byte size."""
    from utilities.icons import Icons

    icon = Icons.get("BOUNCING_SPRITE")
    assert len(icon) == 256, \
        f"BOUNCING_SPRITE icon should be 256 bytes (16×16), got {len(icon)}"
    print("✓ icons: BOUNCING_SPRITE icon is 256 bytes (16×16)")


# ===========================================================================
# Standalone runner
# ===========================================================================

if __name__ == "__main__":
    print("Running Bouncing Sprite feature tests...\n")

    tests = [
        # _reset
        test_reset_sets_starting_position,
        test_reset_sets_starting_velocity,
        # _step – normal movement
        test_step_moves_sprite_by_velocity,
        test_step_no_color_change_without_wall_hit,
        # _step – horizontal bouncing
        test_step_bounces_off_right_wall,
        test_step_bounces_off_left_wall,
        test_step_left_wall_clamps_position,
        # _step – vertical bouncing
        test_step_bounces_off_bottom_wall,
        test_step_bounces_off_top_wall,
        # _step – colour cycling
        test_step_color_cycles_on_right_wall,
        test_step_color_cycles_on_top_wall,
        test_step_color_wraps_around,
        test_step_corner_collision_cycles_color_once,
        # _step – integer invariants
        test_step_velocity_always_integer,
        test_step_position_always_integer,
        # _step – bounds
        test_step_sprite_stays_within_bounds,
        # _build_frame
        test_build_frame_clears_previous_content,
        test_build_frame_primary_pixels_use_current_color,
        test_build_frame_accent_pixel_is_fixed,
        test_build_frame_off_pixels_are_zero,
        test_build_frame_color_change_updates_pixels,
        # manifest
        test_bouncing_sprite_in_manifest,
        # icons
        test_bouncing_sprite_icon_in_icons,
        test_bouncing_sprite_icon_correct_size,
    ]

    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except AssertionError as exc:
            print(f"❌ {test_fn.__name__}: {exc}")
            failed += 1
        except Exception as exc:
            print(f"❌ {test_fn.__name__} (unexpected error): {exc}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'✅' if failed == 0 else '❌'} {passed}/{passed + failed} tests passed")
    sys.exit(min(failed, 1))
