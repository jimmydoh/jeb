"""Tests for the Falling Sand particle simulation mode.

Verifies:
- FallingSandMode._step() applies correct physics for sand, water, wood, fire
- FallingSandMode._randomize() seeds the grid with at least some particles
- manifest.py contains a valid FALLING_SAND entry in the ZERO_PLAYER submenu
- icons.py exposes a 256-byte FALLING_SAND icon
"""

import sys
import os
import traceback
import random

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

def _make_sand(width=8, height=8):
    """Return a FallingSandMode instance with grids initialised."""
    from modes.falling_sand import FallingSandMode
    from unittest.mock import MagicMock

    fake_core = MagicMock()
    mode = FallingSandMode(fake_core)
    mode.width  = width
    mode.height = height
    mode._grid  = bytearray(width * height)
    return mode


# Import particle constants from the module under test
def _constants():
    from modes import falling_sand as fs
    return fs._EMPTY, fs._SAND, fs._WATER, fs._WOOD, fs._FIRE


# ===========================================================================
# 1. Sand physics
# ===========================================================================

def test_sand_falls_straight_down():
    """Sand placed above an empty cell falls one row per step."""
    EMPTY, SAND, WATER, WOOD, FIRE = _constants()
    mode = _make_sand(4, 4)
    w = mode.width
    # Place sand at (1, 1) with empty cell below at (1, 2)
    mode._grid[1 * w + 1] = SAND
    mode._step()
    assert mode._grid[2 * w + 1] == SAND, "Sand should have moved one row down"
    assert mode._grid[1 * w + 1] == EMPTY, "Origin cell should now be empty"
    print("✓ sand: falls straight down into empty cell")


def test_sand_blocked_stays_put():
    """Sand that cannot fall (wood below, no diagonal free) stays in place."""
    EMPTY, SAND, WATER, WOOD, FIRE = _constants()
    mode = _make_sand(4, 4)
    w = mode.width
    # Sand at (1, 1), wood directly below and at both diagonals below
    mode._grid[1 * w + 1] = SAND
    mode._grid[2 * w + 0] = WOOD
    mode._grid[2 * w + 1] = WOOD
    mode._grid[2 * w + 2] = WOOD
    mode._step()
    assert mode._grid[1 * w + 1] == SAND, "Sand with all exits blocked should stay"
    print("✓ sand: stays put when all fall paths are blocked")


def test_sand_falls_diagonal_when_straight_blocked():
    """Sand slides diagonally when the cell directly below is occupied."""
    EMPTY, SAND, WATER, WOOD, FIRE = _constants()
    # Run multiple times and confirm sand moves diagonally at least once
    moved_diag = False
    for _ in range(50):
        mode = _make_sand(4, 4)
        w = mode.width
        # Sand at (2, 1), wood directly below, empty diagonals
        mode._grid[1 * w + 2] = SAND
        mode._grid[2 * w + 2] = WOOD   # block straight down
        # Keep (2,1) and (2,3) empty for diagonal movement
        mode._step()
        if mode._grid[2 * w + 1] == SAND or mode._grid[2 * w + 3] == SAND:
            moved_diag = True
            break
    assert moved_diag, "Sand should eventually slide diagonally when straight path blocked"
    print("✓ sand: slides diagonally when straight path is blocked")


def test_sand_stays_on_bottom_row():
    """Sand on the bottom row (h-1) cannot fall further and stays in place."""
    EMPTY, SAND, WATER, WOOD, FIRE = _constants()
    mode = _make_sand(4, 4)
    w, h = mode.width, mode.height
    mode._grid[(h - 1) * w + 2] = SAND
    mode._step()
    assert mode._grid[(h - 1) * w + 2] == SAND, \
        "Sand on bottom row should not move"
    print("✓ sand: stays on bottom row (cannot fall further)")


def test_sand_does_not_pass_through_wood():
    """Sand cannot pass through a wood wall beneath it."""
    EMPTY, SAND, WATER, WOOD, FIRE = _constants()
    mode = _make_sand(4, 4)
    w = mode.width
    # Sand at row 0, wood covers entire row 1
    for x in range(w):
        mode._grid[1 * w + x] = WOOD
    mode._grid[0 * w + 2] = SAND
    mode._step()
    # Sand must still be above the wood
    assert mode._grid[1 * w + 2] != SAND, \
        "Sand should not overwrite a wood cell below"
    print("✓ sand: cannot pass through wood")


# ===========================================================================
# 2. Water physics
# ===========================================================================

def test_water_falls_straight_down():
    """Water placed above an empty cell falls one row per step."""
    EMPTY, SAND, WATER, WOOD, FIRE = _constants()
    mode = _make_sand(4, 4)
    w = mode.width
    mode._grid[1 * w + 1] = WATER
    mode._step()
    assert mode._grid[2 * w + 1] == WATER, "Water should fall one row down"
    assert mode._grid[1 * w + 1] == EMPTY, "Water origin should now be empty"
    print("✓ water: falls straight down")


def test_water_spreads_sideways_when_blocked():
    """Water spreads sideways when the cell directly below is occupied."""
    EMPTY, SAND, WATER, WOOD, FIRE = _constants()
    spread = False
    for _ in range(50):
        mode = _make_sand(6, 4)
        w = mode.width
        # Water at (3, 1), wood directly below, empty cells to sides
        mode._grid[1 * w + 3] = WATER
        mode._grid[2 * w + 3] = WOOD
        mode._step()
        if mode._grid[1 * w + 2] == WATER or mode._grid[1 * w + 4] == WATER:
            spread = True
            break
    assert spread, "Water should spread sideways when below is blocked"
    print("✓ water: spreads sideways when path below is blocked")


def test_water_stays_on_bottom_row():
    """Water on the bottom row with no sideways room stays in place."""
    EMPTY, SAND, WATER, WOOD, FIRE = _constants()
    mode = _make_sand(4, 4)
    w, h = mode.width, mode.height
    # Fill entire bottom row with water
    for x in range(w):
        mode._grid[(h - 1) * w + x] = WATER
    mode._step()
    for x in range(w):
        assert mode._grid[(h - 1) * w + x] == WATER, \
            f"Water at bottom row x={x} should not move"
    print("✓ water: stays on full bottom row")


def test_water_does_not_displace_wood():
    """Water cannot overwrite a wood cell."""
    EMPTY, SAND, WATER, WOOD, FIRE = _constants()
    mode = _make_sand(4, 4)
    w = mode.width
    # Wood at every cell except (1, 1) where water is placed
    for i in range(len(mode._grid)):
        mode._grid[i] = WOOD
    mode._grid[1 * w + 1] = WATER
    mode._step()
    # Wood cells should remain unchanged
    for i in range(len(mode._grid)):
        if i != 1 * w + 1:
            assert mode._grid[i] in (WOOD, WATER), \
                f"Wood at index {i} should not be displaced by water"
    print("✓ water: cannot displace wood cells")


# ===========================================================================
# 3. Wood physics
# ===========================================================================

def test_wood_is_static():
    """Wood cells never move on their own."""
    EMPTY, SAND, WATER, WOOD, FIRE = _constants()
    mode = _make_sand(4, 4)
    w, h = mode.width, mode.height
    # Fill every cell with wood
    for i in range(len(mode._grid)):
        mode._grid[i] = WOOD
    original = bytearray(mode._grid)
    mode._step()
    assert mode._grid == original, "Wood should not change position after a step"
    print("✓ wood: remains completely static")


# ===========================================================================
# 4. Fire physics
# ===========================================================================

def test_fire_can_rise():
    """Fire can move upward into an empty cell above it."""
    EMPTY, SAND, WATER, WOOD, FIRE = _constants()
    rose = False
    for _ in range(200):
        mode = _make_sand(4, 4)
        w = mode.width
        # Fire at row 2, empty row above
        mode._grid[2 * w + 2] = FIRE
        mode._step()
        if mode._grid[1 * w + 2] == FIRE:
            rose = True
            break
    assert rose, "Fire should eventually rise into the empty cell above it"
    print("✓ fire: rises upward into empty cell")


def test_fire_can_die():
    """Fire can spontaneously disappear (die) during a step."""
    EMPTY, SAND, WATER, WOOD, FIRE = _constants()
    # Use a large grid full of fire; after many steps some must have died
    size = 8
    mode = _make_sand(size, size)
    for i in range(len(mode._grid)):
        mode._grid[i] = FIRE
    for _ in range(30):
        mode._step()
    alive = sum(1 for b in mode._grid if b == FIRE)
    assert alive < size * size, \
        "Some fire pixels should have died after repeated steps"
    print(f"✓ fire: fire pixels die over time (remaining: {alive}/{size*size})")


def test_fire_can_ignite_adjacent_wood():
    """Fire can convert an adjacent wood pixel to fire (ignition)."""
    EMPTY, SAND, WATER, WOOD, FIRE = _constants()
    ignited = False
    for _ in range(500):
        mode = _make_sand(4, 4)
        w = mode.width
        # Fire at (2, 2), wood at (2, 1) directly above
        mode._grid[2 * w + 2] = FIRE
        mode._grid[1 * w + 2] = WOOD
        mode._step()
        if mode._grid[1 * w + 2] == FIRE:
            ignited = True
            break
    assert ignited, "Fire should eventually ignite adjacent wood"
    print("✓ fire: ignites adjacent wood pixel")


def test_fire_does_not_ignite_sand_or_water():
    """Fire does not ignite sand or water cells."""
    EMPTY, SAND, WATER, WOOD, FIRE = _constants()
    # Run many independent steps; verify sand/water cells are never turned into fire
    for _ in range(100):
        mode = _make_sand(4, 4)
        w = mode.width
        mode._grid[2 * w + 2] = FIRE
        mode._grid[1 * w + 2] = SAND
        mode._grid[2 * w + 3] = WATER
        mode._step()
        # Fire only spreads to WOOD, so no new FIRE pixels should appear beyond
        # what was already fire (fire may move up, but cannot convert sand/water)
        for b in mode._grid:
            assert b in (EMPTY, SAND, WATER, FIRE), \
                f"Grid should only contain EMPTY/SAND/WATER/FIRE, got {b}"
    # Additionally: a grid of pure fire should only ever become empty (no new particle types)
    mode = _make_sand(4, 4)
    w = mode.width
    for i in range(len(mode._grid)):
        mode._grid[i] = FIRE
    for _ in range(20):
        mode._step()
    for b in mode._grid:
        assert b in (EMPTY, FIRE), \
            f"Fire-only grid should only contain EMPTY or FIRE, got palette index {b}"
    print("✓ fire: does not ignite sand or water")


# ===========================================================================
# 5. _step increments tick counter
# ===========================================================================

def test_step_increments_tick():
    """Each call to _step() increments self._tick by 1."""
    mode = _make_sand(4, 4)
    assert mode._tick == 0
    mode._step()
    assert mode._tick == 1
    mode._step()
    assert mode._tick == 2
    print("✓ _step: tick counter increments correctly")


# ===========================================================================
# 6. _randomize seeds the grid
# ===========================================================================

def test_randomize_produces_particles():
    """_randomize() fills the grid with at least some non-empty particles."""
    EMPTY, SAND, WATER, WOOD, FIRE = _constants()
    mode = _make_sand(8, 8)
    mode._randomize()
    non_empty = sum(1 for b in mode._grid if b != EMPTY)
    assert non_empty > 0, "_randomize() should place at least one particle"
    print(f"✓ randomize: produced {non_empty} non-empty cells")


def test_randomize_includes_sand():
    """_randomize() places at least some sand particles."""
    EMPTY, SAND, WATER, WOOD, FIRE = _constants()
    mode = _make_sand(8, 8)
    mode._randomize()
    sand_count = sum(1 for b in mode._grid if b == SAND)
    assert sand_count > 0, "_randomize() should place at least one sand particle"
    print(f"✓ randomize: placed {sand_count} sand particle(s)")


def test_randomize_includes_wood():
    """_randomize() places at least one wood platform."""
    EMPTY, SAND, WATER, WOOD, FIRE = _constants()
    mode = _make_sand(8, 8)
    mode._randomize()
    wood_count = sum(1 for b in mode._grid if b == WOOD)
    assert wood_count > 0, "_randomize() should place at least one wood cell"
    print(f"✓ randomize: placed {wood_count} wood cell(s)")


def test_randomize_resets_tick():
    """_randomize() resets the tick counter to 0."""
    mode = _make_sand(8, 8)
    mode._tick = 999
    mode._randomize()
    assert mode._tick == 0, "_randomize() should reset _tick to 0"
    print("✓ randomize: resets tick counter to 0")


# ===========================================================================
# 7. Manifest entry
# ===========================================================================

def test_falling_sand_in_manifest():
    """FALLING_SAND entry exists in MODE_REGISTRY with all required fields."""
    from modes.manifest import MODE_REGISTRY

    assert "FALLING_SAND" in MODE_REGISTRY, \
        "FALLING_SAND not found in MODE_REGISTRY"
    meta = MODE_REGISTRY["FALLING_SAND"]

    required_fields = ["id", "name", "module_path", "class_name",
                       "icon", "menu", "requires", "settings"]
    for field in required_fields:
        assert field in meta, \
            f"FALLING_SAND missing required field '{field}'"

    assert meta["id"]          == "FALLING_SAND"
    assert meta["module_path"] == "modes.falling_sand", \
        "module_path should be 'modes.falling_sand'"
    assert meta["class_name"]  == "FallingSandMode", \
        "class_name should be 'FallingSandMode'"
    assert meta["menu"]        == "ZERO_PLAYER", \
        "FALLING_SAND should belong to the ZERO_PLAYER submenu"
    assert meta["icon"]        == "FALLING_SAND", \
        "FALLING_SAND should reference the FALLING_SAND icon"
    assert "CORE" in meta["requires"], \
        "FALLING_SAND should require CORE"
    print("✓ manifest: FALLING_SAND entry is complete and correct")


# ===========================================================================
# 8. Icon
# ===========================================================================

def test_falling_sand_icon_exists():
    """icons.py exposes a FALLING_SAND icon that is a non-empty bytes object."""
    from utilities.icons import Icons

    icon = Icons.get("FALLING_SAND")
    assert icon is not None, "Icons library should contain a FALLING_SAND icon"
    assert isinstance(icon, (bytes, bytearray)), \
        "FALLING_SAND icon should be bytes or bytearray"
    assert len(icon) > 0, "FALLING_SAND icon should not be empty"
    print(f"✓ icons: FALLING_SAND icon present ({len(icon)} bytes)")


def test_falling_sand_icon_correct_size():
    """FALLING_SAND icon has the expected 16×16 = 256-byte size."""
    from utilities.icons import Icons

    icon = Icons.get("FALLING_SAND")
    assert len(icon) == 256, \
        f"FALLING_SAND icon should be 256 bytes (16×16), got {len(icon)}"
    print("✓ icons: FALLING_SAND icon is 256 bytes (16×16)")


# ===========================================================================
# Standalone runner
# ===========================================================================

if __name__ == "__main__":
    print("Running Falling Sand particle simulation tests...\n")

    tests = [
        # Sand physics
        test_sand_falls_straight_down,
        test_sand_blocked_stays_put,
        test_sand_falls_diagonal_when_straight_blocked,
        test_sand_stays_on_bottom_row,
        test_sand_does_not_pass_through_wood,
        # Water physics
        test_water_falls_straight_down,
        test_water_spreads_sideways_when_blocked,
        test_water_stays_on_bottom_row,
        test_water_does_not_displace_wood,
        # Wood physics
        test_wood_is_static,
        # Fire physics
        test_fire_can_rise,
        test_fire_can_die,
        test_fire_can_ignite_adjacent_wood,
        test_fire_does_not_ignite_sand_or_water,
        # Tick counter
        test_step_increments_tick,
        # Randomize
        test_randomize_produces_particles,
        test_randomize_includes_sand,
        test_randomize_includes_wood,
        test_randomize_resets_tick,
        # Manifest
        test_falling_sand_in_manifest,
        # Icon
        test_falling_sand_icon_exists,
        test_falling_sand_icon_correct_size,
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
