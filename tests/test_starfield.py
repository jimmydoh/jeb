"""Tests for the Parallax Starfield / Warp Core zero-player mode.

Verifies:
- StarfieldMode._depth_color() maps z correctly (dim far, bright close)
- StarfieldMode._step() advances stars toward the camera
- StarfieldMode._step() recycles stars that pass z_min
- StarfieldMode._step() renders projected star positions into the frame buffer
- StarfieldMode._reset_stars() creates the correct star count
- StarfieldMode._reset_stars() allocates the frame buffer
- manifest.py contains a valid STARFIELD entry in the ZERO_PLAYER submenu
- icons.py exposes a 256-byte STARFIELD icon
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

def _make_starfield(width=16, height=16):
    """Return a StarfieldMode instance ready for unit testing."""
    from modes.starfield import StarfieldMode
    from unittest.mock import MagicMock

    fake_core = MagicMock()
    mode = StarfieldMode(fake_core)
    mode.width  = width
    mode.height = height
    mode._frame = bytearray(width * height)
    return mode


def _constants():
    """Return tunable constants from the module under test."""
    from modes import starfield as sf
    return (
        sf._Z_MIN, sf._Z_MAX, sf._SCALE,
        sf._WARP_LEVELS, sf._STAR_COUNTS,
        sf._DEPTH_PALETTE, sf._DEFAULT_WARP_IDX, sf._DEFAULT_STAR_IDX,
    )


# ===========================================================================
# 1. Depth colour mapping
# ===========================================================================

def test_depth_color_far_star_is_dim():
    """A star at maximum z should map to the dimmest palette index."""
    from modes import starfield as sf
    mode = _make_starfield()
    color = mode._depth_color(sf._Z_MAX)
    assert color == sf._DEPTH_PALETTE[0], (
        f"Farthest star should have palette index {sf._DEPTH_PALETTE[0]}, "
        f"got {color}"
    )
    print(f"✓ depth_color: farthest z={sf._Z_MAX} → palette index {color}")


def test_depth_color_near_star_is_bright():
    """A star just above z_min should map to the brightest palette index."""
    from modes import starfield as sf
    mode = _make_starfield()
    color = mode._depth_color(sf._Z_MIN + 0.01)
    assert color == sf._DEPTH_PALETTE[-1], (
        f"Nearest star should have palette index {sf._DEPTH_PALETTE[-1]}, "
        f"got {color}"
    )
    print(f"✓ depth_color: nearest z≈{sf._Z_MIN} → palette index {color}")


def test_depth_color_near_brighter_than_far():
    """A star at mid-depth should be brighter than one at maximum depth."""
    from modes import starfield as sf
    mode = _make_starfield()
    far_color  = mode._depth_color(sf._Z_MAX)
    mid_color  = mode._depth_color((sf._Z_MAX + sf._Z_MIN) / 2.0)
    near_color = mode._depth_color(sf._Z_MIN + 0.01)
    assert near_color >= mid_color >= far_color, (
        "Color should increase (brighten) as z decreases. "
        f"far={far_color} mid={mid_color} near={near_color}"
    )
    print(f"✓ depth_color: brightness increases as z decreases "
          f"({far_color} → {mid_color} → {near_color})")


def test_depth_color_clamped():
    """_depth_color must not raise for z values outside [_Z_MIN, _Z_MAX]."""
    from modes import starfield as sf
    mode = _make_starfield()
    # Should not raise even for extreme values
    c_lo = mode._depth_color(-100.0)
    c_hi = mode._depth_color(sf._Z_MAX + 100.0)
    assert c_lo in sf._DEPTH_PALETTE
    assert c_hi in sf._DEPTH_PALETTE
    print("✓ depth_color: handles out-of-range z without error")


# ===========================================================================
# 2. _step – star movement
# ===========================================================================

def test_step_moves_stars_closer():
    """Each call to _step() decreases every star's z coordinate."""
    from modes import starfield as sf
    mode = _make_starfield()
    mode._reset_stars()
    # Place all stars safely in the middle of the depth range
    mid_z = (sf._Z_MAX + sf._Z_MIN) / 2.0
    for star in mode._stars:
        star[2] = mid_z

    mode._step()
    speed = sf._WARP_LEVELS[mode._warp_idx]
    for star in mode._stars:
        assert star[2] < mid_z or star[2] == sf._Z_MAX, (
            "Star should have moved closer (lower z) or been recycled"
        )
    print("✓ _step: all stars moved toward camera after one tick")


def test_step_recycles_stars_past_z_min():
    """Stars that reach z <= _Z_MIN are recycled to z = _Z_MAX."""
    from modes import starfield as sf
    mode = _make_starfield()
    mode._reset_stars()
    # Force all stars to the boundary so they are recycled on the next step.
    for star in mode._stars:
        star[2] = sf._Z_MIN

    mode._step()
    for star in mode._stars:
        assert star[2] == sf._Z_MAX, (
            f"Recycled star should have z={sf._Z_MAX}, got {star[2]}"
        )
    print("✓ _step: stars at z_min are recycled to z_max")


def test_step_recycled_stars_get_new_xy():
    """Recycled stars receive fresh (x, y) positions."""
    from modes import starfield as sf
    mode = _make_starfield()
    mode._reset_stars()
    # Pin a single star at the exact recycle boundary.
    mode._stars[0][0] = 0.0
    mode._stars[0][1] = 0.0
    mode._stars[0][2] = sf._Z_MIN

    mode._step()
    # After recycling, x and y may be anything in the spawn range.
    half = sf._Z_MAX * 0.5
    sx, sy, sz = mode._stars[0]
    assert sz == sf._Z_MAX
    assert -half <= sx <= half
    assert -half <= sy <= half
    print("✓ _step: recycled star gets valid new (x, y) position")


# ===========================================================================
# 3. _step – frame buffer rendering
# ===========================================================================

def test_step_renders_visible_star():
    """A star placed at the matrix centre should appear in the frame buffer."""
    from modes import starfield as sf
    mode = _make_starfield(16, 16)
    mode._reset_stars()
    w, h = mode.width, mode.height

    # Place a single star exactly at the projection origin so that it maps
    # to the pixel at approximately (half_x, half_y).
    mode._stars = [[0.0, 0.0, 1.0]]  # x=0, y=0 → projects to centre

    mode._step()
    # The centre pixel (7,7) or (8,8) should be non-zero after the step.
    lit = [mode._frame[y * w + x] for x in range(w) for y in range(h)
           if mode._frame[y * w + x] != 0]
    assert len(lit) >= 1, "At least one pixel should be lit after _step"
    print(f"✓ _step: centre star visible in frame ({len(lit)} lit pixel(s))")


def test_step_clears_frame_each_tick():
    """Frame buffer is fully cleared at the start of each _step call."""
    from modes import starfield as sf
    mode = _make_starfield(16, 16)
    mode._reset_stars()
    # Manually set all pixels to a non-zero value.
    for i in range(len(mode._frame)):
        mode._frame[i] = 4

    # Place stars outside the visible area so nothing new is plotted.
    mode._stars = []
    mode._step()
    assert all(b == 0 for b in mode._frame), (
        "Frame buffer should be all zeros when no visible stars exist"
    )
    print("✓ _step: frame buffer cleared at start of each tick")


def test_step_out_of_bounds_star_not_rendered():
    """Stars that project outside the matrix bounds are silently ignored."""
    from modes import starfield as sf
    mode = _make_starfield(16, 16)
    mode._reset_stars()
    # A star far off-axis at close range will project way outside the matrix.
    mode._stars = [[1000.0, 1000.0, 0.6]]

    mode._step()
    assert all(b == 0 for b in mode._frame), (
        "Out-of-bounds star should not set any pixel in the frame buffer"
    )
    print("✓ _step: out-of-bounds projection does not corrupt frame buffer")


def test_step_overlapping_stars_keep_brightest():
    """When two stars project to the same pixel the brightest color wins."""
    from modes import starfield as sf
    mode = _make_starfield(16, 16)
    mode._reset_stars()
    # Two stars at the same (x, y) but different depths.
    mode._stars = [
        [0.0, 0.0, sf._Z_MAX - 0.1],   # dim (far)
        [0.0, 0.0, sf._Z_MIN + 0.5],   # bright (close)
    ]
    mode._step()
    # Find the pixel where both stars project (centre).
    w, h = mode.width, mode.height
    half_x = (w - 1) / 2.0
    half_y = (h - 1) / 2.0
    # Both project to centre; the close star should win.
    bright_color = mode._depth_color(sf._Z_MIN + 0.5)
    centre_pixel = mode._frame[int(half_y + 0.5) * w + int(half_x + 0.5)]
    assert centre_pixel == bright_color, (
        f"Overlapping pixel should hold brightest color {bright_color}, "
        f"got {centre_pixel}"
    )
    print("✓ _step: overlapping stars keep the brightest colour")


# ===========================================================================
# 4. _reset_stars
# ===========================================================================

def test_reset_stars_correct_count():
    """_reset_stars() creates exactly _STAR_COUNTS[star_idx] stars."""
    from modes import starfield as sf
    mode = _make_starfield()
    for idx, count in enumerate(sf._STAR_COUNTS):
        mode._star_idx = idx
        mode._reset_stars()
        assert len(mode._stars) == count, (
            f"Expected {count} stars for star_idx={idx}, "
            f"got {len(mode._stars)}"
        )
    print("✓ reset_stars: creates correct number of stars for each density")


def test_reset_stars_allocates_frame():
    """_reset_stars() allocates a bytearray frame buffer of width*height."""
    mode = _make_starfield(16, 16)
    mode._frame = None   # Force re-allocation
    mode._reset_stars()
    assert isinstance(mode._frame, bytearray)
    assert len(mode._frame) == 16 * 16
    print("✓ reset_stars: allocates bytearray frame buffer of correct size")


def test_reset_stars_all_in_valid_depth_range():
    """All stars spawned by _reset_stars() have z in (_Z_MIN, _Z_MAX]."""
    from modes import starfield as sf
    mode = _make_starfield()
    mode._reset_stars()
    for i, star in enumerate(mode._stars):
        assert sf._Z_MIN < star[2] <= sf._Z_MAX, (
            f"Star {i} has invalid z={star[2]} (expected in "
            f"({sf._Z_MIN}, {sf._Z_MAX}])"
        )
    print("✓ reset_stars: all star z-values are within valid range")


def test_reset_stars_reinitialises_existing_list():
    """Calling _reset_stars() twice replaces the star list (no leftover stars)."""
    from modes import starfield as sf
    mode = _make_starfield()
    mode._star_idx = 0
    mode._reset_stars()
    count_before = len(mode._stars)

    mode._star_idx = 2   # switch to DENSE
    mode._reset_stars()
    count_after = len(mode._stars)

    assert count_after == sf._STAR_COUNTS[2], (
        f"Expected {sf._STAR_COUNTS[2]} stars after density change, "
        f"got {count_after}"
    )
    assert count_before != count_after, "Star count should differ between SPARSE and DENSE"
    print("✓ reset_stars: correctly reinitialises star list on second call")


# ===========================================================================
# 5. Manifest entry
# ===========================================================================

def test_starfield_in_manifest():
    """STARFIELD entry exists in MODE_REGISTRY with all required fields."""
    from modes.manifest import MODE_REGISTRY

    assert "STARFIELD" in MODE_REGISTRY, \
        "STARFIELD not found in MODE_REGISTRY"
    meta = MODE_REGISTRY["STARFIELD"]

    required_fields = ["id", "name", "module_path", "class_name",
                       "icon", "menu", "requires", "settings"]
    for field in required_fields:
        assert field in meta, \
            f"STARFIELD missing required field '{field}'"

    assert meta["id"]          == "STARFIELD"
    assert meta["module_path"] == "modes.starfield", \
        "module_path should be 'modes.starfield'"
    assert meta["class_name"]  == "StarfieldMode", \
        "class_name should be 'StarfieldMode'"
    assert meta["menu"]        == "ZERO_PLAYER", \
        "STARFIELD should belong to the ZERO_PLAYER submenu"
    assert meta["icon"]        == "STARFIELD", \
        "STARFIELD should reference the STARFIELD icon"
    assert "CORE" in meta["requires"], \
        "STARFIELD should require CORE"
    print("✓ manifest: STARFIELD entry is complete and correct")


# ===========================================================================
# 6. Icon
# ===========================================================================

def test_starfield_icon_exists():
    """icons.py exposes a STARFIELD icon that is a non-empty bytes object."""
    from utilities.icons import Icons

    icon = Icons.get("STARFIELD")
    assert icon is not None, "Icons library should contain a STARFIELD icon"
    assert isinstance(icon, (bytes, bytearray)), \
        "STARFIELD icon should be bytes or bytearray"
    assert len(icon) > 0, "STARFIELD icon should not be empty"
    print(f"✓ icons: STARFIELD icon present ({len(icon)} bytes)")


def test_starfield_icon_correct_size():
    """STARFIELD icon has the expected 16×16 = 256-byte size."""
    from utilities.icons import Icons

    icon = Icons.get("STARFIELD")
    assert len(icon) == 256, \
        f"STARFIELD icon should be 256 bytes (16×16), got {len(icon)}"
    print("✓ icons: STARFIELD icon is 256 bytes (16×16)")


def test_starfield_icon_valid_palette_indices():
    """Every byte in the STARFIELD icon is a valid palette index."""
    from utilities.icons import Icons
    from utilities.palette import Palette

    icon = Icons.get("STARFIELD")
    valid_indices = set(Palette.LIBRARY.keys())
    for i, byte in enumerate(icon):
        assert byte in valid_indices, \
            f"STARFIELD icon byte {i} has invalid palette index {byte}"
    print("✓ icons: all STARFIELD icon bytes are valid palette indices")


# ===========================================================================
# Standalone runner
# ===========================================================================

if __name__ == "__main__":
    print("Running Parallax Starfield / Warp Core mode tests...\n")

    tests = [
        # Depth colour mapping
        test_depth_color_far_star_is_dim,
        test_depth_color_near_star_is_bright,
        test_depth_color_near_brighter_than_far,
        test_depth_color_clamped,
        # Star movement
        test_step_moves_stars_closer,
        test_step_recycles_stars_past_z_min,
        test_step_recycled_stars_get_new_xy,
        # Frame buffer rendering
        test_step_renders_visible_star,
        test_step_clears_frame_each_tick,
        test_step_out_of_bounds_star_not_rendered,
        test_step_overlapping_stars_keep_brightest,
        # _reset_stars
        test_reset_stars_correct_count,
        test_reset_stars_allocates_frame,
        test_reset_stars_all_in_valid_depth_range,
        test_reset_stars_reinitialises_existing_list,
        # Manifest
        test_starfield_in_manifest,
        # Icon
        test_starfield_icon_exists,
        test_starfield_icon_correct_size,
        test_starfield_icon_valid_palette_indices,
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
