"""Tests for the Wolfram 1D Cellular Automata feature.

Verifies:
- WolframAutomata._apply_rule() correctly implements Rule 90 (Sierpiński XOR)
  and Rule 30 (chaotic) on a known seed row.
- WolframAutomata._step() fills the grid from the top before scrolling.
- WolframAutomata._step() scrolls the grid upward once the buffer is full.
- WolframAutomata._reset() clears the grid and places a center-pixel seed.
- WolframAutomata._recolor() updates all alive cells to the active colour.
- manifest.py contains a valid WOLFRAM_AUTOMATA entry with all required fields.
- icons.py exposes a WOLFRAM_AUTOMATA icon that is 256 bytes (16×16).
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

def _make_automata(width=8, height=8):
    """Return a WolframAutomata instance with buffers initialised."""
    from modes.wolfram_automata import WolframAutomata
    from unittest.mock import MagicMock

    fake_core = MagicMock()
    wf = WolframAutomata(fake_core)
    wf.width  = width
    wf.height = height
    size = width * height
    wf._grid        = bytearray(size)
    wf._current_row = bytearray(width)
    wf._fill_row    = 1
    wf._step_count  = 0
    return wf


# ===========================================================================
# 1. _apply_rule – Rule 90 (Sierpiński XOR)
# ===========================================================================

def test_apply_rule90_single_center_pixel():
    """Rule 90 on a width-8 row with one center pixel produces the correct next row.

    Rule 90: new[x] = left XOR right (toroidal wrap).
    Seed: [0,0,0,0,1,0,0,0]  (center at index 4 of 0-7, i.e. width//2=4)
    Expected next row: positions 3 and 5 alive.
    """
    from modes.wolfram_automata import _RULE_NUMBERS
    wf = _make_automata(width=8, height=8)
    wf._rule_idx = _RULE_NUMBERS.index(90)

    seed = bytearray(8)
    seed[4] = 51  # center alive (CYAN)

    result = wf._apply_rule(seed)

    # Only positions 3 and 5 should be alive
    assert result[3] != 0, "Rule 90: position 3 should be alive after one step"
    assert result[5] != 0, "Rule 90: position 5 should be alive after one step"
    # All other positions should be dead
    for i in (0, 1, 2, 4, 6, 7):
        assert result[i] == 0, f"Rule 90: position {i} should be dead after one step"
    print("✓ _apply_rule: Rule 90 single center pixel → positions 3 and 5 alive")


def test_apply_rule90_produces_sierpinski_second_step():
    """Two consecutive Rule 90 steps from a center pixel grow the triangle correctly.

    Step 0: [0,0,0,0,1,0,0,0]
    Step 1: [0,0,0,1,0,1,0,0]
    Step 2: [0,0,1,0,0,0,1,0]  (positions 2 and 6)
    """
    from modes.wolfram_automata import _RULE_NUMBERS
    wf = _make_automata(width=8, height=8)
    wf._rule_idx = _RULE_NUMBERS.index(90)
    color_val = wf._color()

    seed = bytearray(8)
    seed[4] = color_val

    step1 = wf._apply_rule(seed)
    step2 = wf._apply_rule(step1)

    assert step2[2] != 0, "Rule 90 step 2: position 2 should be alive"
    assert step2[6] != 0, "Rule 90 step 2: position 6 should be alive"
    for i in (0, 1, 3, 4, 5, 7):
        assert step2[i] == 0, f"Rule 90 step 2: position {i} should be dead"
    print("✓ _apply_rule: Rule 90 two steps from center → positions 2 and 6 alive")


def test_apply_rule90_toroidal_wrap():
    """Rule 90 wraps around the edges (toroidal topology).

    Row with only the leftmost cell alive: [1,0,0,...,0]
    new[0] = row[-1 % w] XOR row[1] = row[w-1] XOR row[1] = 0 XOR 0 = 0
    new[1] = row[0] XOR row[2] = 1 XOR 0 = 1
    new[w-1] = row[w-2] XOR row[0] = 0 XOR 1 = 1  (wrap-around)
    """
    from modes.wolfram_automata import _RULE_NUMBERS
    wf = _make_automata(width=8, height=8)
    wf._rule_idx = _RULE_NUMBERS.index(90)
    color_val = wf._color()

    seed = bytearray(8)
    seed[0] = color_val  # only leftmost cell alive

    result = wf._apply_rule(seed)

    assert result[1]   != 0, "Rule 90 wrap: position 1 should be alive"
    assert result[7]   != 0, "Rule 90 wrap: position 7 (wrapped right) should be alive"
    assert result[0]   == 0, "Rule 90 wrap: position 0 should be dead"
    print("✓ _apply_rule: Rule 90 toroidal wrap works correctly")


# ===========================================================================
# 2. _apply_rule – Rule 30 (chaotic)
# ===========================================================================

def test_apply_rule30_single_center_pixel():
    """Rule 30 on a width-8 row with one center pixel produces the correct next row.

    Rule 30 table (30 = 0b00011110):
      pattern 0 (000) → 0
      pattern 1 (001) → 1
      pattern 2 (010) → 1
      pattern 3 (011) → 1
      pattern 4 (100) → 1
      pattern 5 (101) → 0
      pattern 6 (110) → 0
      pattern 7 (111) → 0

    Seed: [0,0,0,0,1,0,0,0]  (center at index 4)
    pos 3: left=0 center=0 right=1 → pattern=1 → 1  (alive)
    pos 4: left=0 center=1 right=0 → pattern=2 → 1  (alive)
    pos 5: left=1 center=0 right=0 → pattern=4 → 1  (alive)
    All others: 000 → 0
    """
    from modes.wolfram_automata import _RULE_NUMBERS
    wf = _make_automata(width=8, height=8)
    wf._rule_idx = _RULE_NUMBERS.index(30)
    color_val = wf._color()

    seed = bytearray(8)
    seed[4] = color_val

    result = wf._apply_rule(seed)

    assert result[3] != 0, "Rule 30: position 3 should be alive"
    assert result[4] != 0, "Rule 30: position 4 should be alive"
    assert result[5] != 0, "Rule 30: position 5 should be alive"
    for i in (0, 1, 2, 6, 7):
        assert result[i] == 0, f"Rule 30: position {i} should be dead"
    print("✓ _apply_rule: Rule 30 single center pixel → positions 3, 4, 5 alive")


# ===========================================================================
# 3. _step – initial fill (top-down)
# ===========================================================================

def test_step_fills_grid_from_top():
    """_step() places new rows starting from the top of the grid (row 0 = seed)."""
    from modes.wolfram_automata import _RULE_NUMBERS
    wf = _make_automata(width=4, height=4)
    wf._rule_idx = _RULE_NUMBERS.index(90)
    color_val = wf._color()

    # Seed at top: center pixel of width-4 → index 2
    seed = bytearray(4)
    seed[2] = color_val
    wf._current_row = seed
    wf._grid[0:4] = seed   # seed already placed in row 0
    wf._fill_row = 1        # next empty slot is row 1

    wf._step()

    # Row 0 must still contain the seed
    assert wf._grid[2] != 0, "Row 0 center should still hold the seed"
    # Row 1 must contain the computed next row (fill_row was 1)
    row1 = wf._grid[4:8]
    alive_in_row1 = [x for x in range(4) if row1[x] != 0]
    assert len(alive_in_row1) > 0, "Row 1 should contain at least one alive cell"
    assert wf._fill_row == 2, "_fill_row should advance to 2 after the first step"
    print("✓ _step: new rows fill from top during initial population")


def test_step_fill_row_increments_to_height():
    """_fill_row increments with each step until it reaches height."""
    from modes.wolfram_automata import _RULE_NUMBERS
    wf = _make_automata(width=4, height=4)
    wf._rule_idx = _RULE_NUMBERS.index(90)
    color_val = wf._color()

    seed = bytearray(4)
    seed[2] = color_val
    wf._current_row = seed
    wf._grid[0:4] = seed
    wf._fill_row = 1

    # Step 3 more times to fill rows 1, 2, 3
    for expected_fill in range(2, 5):
        wf._step()
        assert wf._fill_row == min(expected_fill, wf.height), \
            f"_fill_row should be {min(expected_fill, wf.height)}, got {wf._fill_row}"
    print("✓ _step: _fill_row increments correctly up to height")


# ===========================================================================
# 4. _step – scrolling once full
# ===========================================================================

def test_step_scrolls_when_full():
    """When the grid is full (_fill_row == height), _step scrolls up by one row."""
    from modes.wolfram_automata import _RULE_NUMBERS
    wf = _make_automata(width=4, height=4)
    wf._rule_idx = _RULE_NUMBERS.index(90)
    color_val = wf._color()

    # Pre-fill the grid with distinct sentinel values per row
    for r in range(4):
        for x in range(4):
            wf._grid[r * 4 + x] = r + 1   # rows have values 1, 2, 3, 4

    # Simulate a current row (all alive, will produce a non-trivial next row)
    seed = bytearray([color_val, 0, color_val, 0])
    wf._current_row = seed
    wf._fill_row = 4  # buffer is full

    wf._step()

    # Row 0 should now hold what was row 1 (value 2)
    assert wf._grid[0] == 2, \
        f"After scroll, row 0 col 0 should be old row-1 value (2), got {wf._grid[0]}"
    # Row 1 should hold what was row 2 (value 3)
    assert wf._grid[4] == 3, \
        f"After scroll, row 1 col 0 should be old row-2 value (3), got {wf._grid[4]}"
    # Row 2 should hold what was row 3 (value 4)
    assert wf._grid[8] == 4, \
        f"After scroll, row 2 col 0 should be old row-3 value (4), got {wf._grid[8]}"
    # _fill_row must stay at height (buffer remains full)
    assert wf._fill_row == 4, "_fill_row should remain at height after scrolling"
    print("✓ _step: grid scrolls up correctly when the buffer is full")


def test_step_increments_step_count():
    """Each call to _step() increments _step_count by 1."""
    from modes.wolfram_automata import _RULE_NUMBERS
    wf = _make_automata(width=4, height=4)
    wf._rule_idx = _RULE_NUMBERS.index(90)
    wf._current_row = bytearray([0, 51, 0, 0])
    wf._grid[0:4] = wf._current_row
    wf._fill_row = 1

    assert wf._step_count == 0
    wf._step()
    assert wf._step_count == 1
    wf._step()
    assert wf._step_count == 2
    print("✓ _step: _step_count increments correctly")


# ===========================================================================
# 5. _reset
# ===========================================================================

def test_reset_clears_grid():
    """_reset() sets every byte in _grid to 0."""
    wf = _make_automata(width=8, height=8)
    # Pre-fill with non-zero values
    for i in range(len(wf._grid)):
        wf._grid[i] = 41
    wf._reset()
    # Rows 1..7 must be all zeros
    for i in range(8, 64):
        assert wf._grid[i] == 0, f"_reset: grid[{i}] should be 0 after reset"
    print("✓ _reset: grid bytes outside row 0 are cleared to zero")


def test_reset_places_center_seed_at_top():
    """_reset() places a single center pixel in row 0 of the grid."""
    wf = _make_automata(width=8, height=8)
    wf._reset()
    center = wf.width // 2  # index 4
    # The center column of row 0 must be alive
    assert wf._grid[center] != 0, \
        f"_reset: center pixel at index {center} of row 0 should be alive"
    # All other columns in row 0 must be dead
    for x in range(wf.width):
        if x != center:
            assert wf._grid[x] == 0, \
                f"_reset: non-center pixel at row-0 index {x} should be dead"
    print("✓ _reset: single center pixel placed in row 0 after reset")


def test_reset_sets_fill_row_to_one():
    """_reset() initialises _fill_row to 1 (row 0 already holds the seed)."""
    wf = _make_automata(width=8, height=8)
    wf._fill_row = 99   # arbitrary pre-existing value
    wf._reset()
    assert wf._fill_row == 1, \
        f"_reset: _fill_row should be 1 after reset, got {wf._fill_row}"
    print("✓ _reset: _fill_row is 1 after reset")


def test_reset_initialises_step_count():
    """_reset() sets _step_count back to 0."""
    wf = _make_automata(width=8, height=8)
    wf._step_count = 500
    wf._reset()
    assert wf._step_count == 0, \
        f"_reset: _step_count should be 0 after reset, got {wf._step_count}"
    print("✓ _reset: _step_count is 0 after reset")


# ===========================================================================
# 6. _recolor
# ===========================================================================

def test_recolor_updates_alive_cells_in_grid():
    """_recolor() updates every non-zero cell in _grid to the active colour."""
    from modes.wolfram_automata import _RULE_COLORS
    wf = _make_automata(width=4, height=4)
    wf._rule_idx = 0   # Rule 30, colour = _RULE_COLORS[0]

    # Populate some alive cells with an old colour
    old_color = 99
    wf._grid[0] = old_color
    wf._grid[5] = old_color
    wf._grid[10] = old_color
    # Leave the rest dead (0)

    wf._recolor()

    expected = _RULE_COLORS[0]
    for pos in (0, 5, 10):
        assert wf._grid[pos] == expected, \
            f"_recolor: grid[{pos}] should be {expected}, got {wf._grid[pos]}"
    # Dead cells must remain dead
    for pos in (1, 2, 3, 4, 6, 7, 8, 9, 11, 12, 13, 14, 15):
        assert wf._grid[pos] == 0, \
            f"_recolor: dead grid[{pos}] should remain 0"
    print("✓ _recolor: alive cells updated to current colour, dead cells untouched")


def test_recolor_updates_current_row():
    """_recolor() also updates alive cells in _current_row."""
    from modes.wolfram_automata import _RULE_COLORS
    wf = _make_automata(width=4, height=4)
    wf._rule_idx = 1   # Rule 90

    old_color = 99
    wf._current_row = bytearray([old_color, 0, old_color, 0])

    wf._recolor()

    expected = _RULE_COLORS[1]
    assert wf._current_row[0] == expected, \
        f"_recolor: current_row[0] should be {expected}"
    assert wf._current_row[1] == 0, \
        "_recolor: dead current_row[1] should remain 0"
    assert wf._current_row[2] == expected, \
        f"_recolor: current_row[2] should be {expected}"
    print("✓ _recolor: _current_row alive cells also updated")


# ===========================================================================
# 7. Manifest entry
# ===========================================================================

def test_wolfram_automata_in_manifest():
    """WOLFRAM_AUTOMATA entry exists in MODE_REGISTRY with all required fields."""
    from modes.manifest import MODE_REGISTRY

    assert "WOLFRAM_AUTOMATA" in MODE_REGISTRY, \
        "WOLFRAM_AUTOMATA not found in MODE_REGISTRY"
    meta = MODE_REGISTRY["WOLFRAM_AUTOMATA"]

    required_fields = ["id", "name", "module_path", "class_name",
                       "icon", "menu", "requires", "settings"]
    for field in required_fields:
        assert field in meta, \
            f"WOLFRAM_AUTOMATA missing required field '{field}'"

    assert meta["id"] == "WOLFRAM_AUTOMATA"
    assert meta["module_path"] == "modes.wolfram_automata", \
        "WOLFRAM_AUTOMATA module_path should be 'modes.wolfram_automata'"
    assert meta["class_name"] == "WolframAutomata", \
        "WOLFRAM_AUTOMATA class_name should be 'WolframAutomata'"
    assert meta["menu"] == "ZERO_PLAYER", \
        "WOLFRAM_AUTOMATA should belong to the ZERO_PLAYER submenu"
    assert meta["icon"] == "WOLFRAM_AUTOMATA", \
        "WOLFRAM_AUTOMATA should reference the WOLFRAM_AUTOMATA icon"
    assert "CORE" in meta["requires"], \
        "WOLFRAM_AUTOMATA should require CORE"
    print("✓ manifest: WOLFRAM_AUTOMATA entry is complete and correct")


def test_wolfram_automata_has_rule_setting():
    """WOLFRAM_AUTOMATA manifest entry has a 'rule' setting with valid options."""
    from modes.manifest import MODE_REGISTRY

    meta = MODE_REGISTRY["WOLFRAM_AUTOMATA"]
    settings = meta["settings"]
    rule_setting = next((s for s in settings if s["key"] == "rule"), None)

    assert rule_setting is not None, \
        "WOLFRAM_AUTOMATA should have a 'rule' setting"
    assert "30" in rule_setting["options"], \
        "Rule 30 should be a selectable option"
    assert "90" in rule_setting["options"], \
        "Rule 90 should be a selectable option"
    assert rule_setting["default"] == "90", \
        "Default rule should be '90'"
    print("✓ manifest: WOLFRAM_AUTOMATA has 'rule' setting with Rule 30 and 90 options")


def test_wolfram_automata_is_zero_player_mode():
    """WOLFRAM_AUTOMATA appears in the ZERO_PLAYER submenu alongside other zero-player modes."""
    from modes.manifest import MODE_REGISTRY

    zero_player_modes = {k: v for k, v in MODE_REGISTRY.items()
                         if v.get("menu") == "ZERO_PLAYER"}

    assert "WOLFRAM_AUTOMATA" in zero_player_modes, \
        "WOLFRAM_AUTOMATA should be in the ZERO_PLAYER submenu"
    assert "CONWAYS_LIFE" in zero_player_modes, \
        "CONWAYS_LIFE should also be in the ZERO_PLAYER submenu"
    assert "LANGTONS_ANT" in zero_player_modes, \
        "LANGTONS_ANT should also be in the ZERO_PLAYER submenu"
    print(f"✓ manifest: WOLFRAM_AUTOMATA is in ZERO_PLAYER alongside "
          f"{len(zero_player_modes) - 1} other mode(s)")


# ===========================================================================
# 8. Icon library
# ===========================================================================

def test_wolfram_automata_icon_in_icons():
    """icons.py exposes a WOLFRAM_AUTOMATA icon that is a non-empty bytes object."""
    from utilities.icons import Icons

    icon = Icons.get("WOLFRAM_AUTOMATA")
    assert icon is not None, "Icons library should contain a WOLFRAM_AUTOMATA icon"
    assert isinstance(icon, (bytes, bytearray)), \
        "WOLFRAM_AUTOMATA icon should be bytes or bytearray"
    assert len(icon) > 0, "WOLFRAM_AUTOMATA icon should not be empty"
    print(f"✓ icons: WOLFRAM_AUTOMATA icon present ({len(icon)} bytes)")


def test_wolfram_automata_icon_correct_size():
    """WOLFRAM_AUTOMATA icon has the expected 16×16 = 256-byte size."""
    from utilities.icons import Icons

    icon = Icons.get("WOLFRAM_AUTOMATA")
    assert len(icon) == 256, \
        f"WOLFRAM_AUTOMATA icon should be 256 bytes (16×16), got {len(icon)}"
    print("✓ icons: WOLFRAM_AUTOMATA icon is 256 bytes (16×16)")


def test_wolfram_automata_icon_has_alive_cells():
    """WOLFRAM_AUTOMATA icon contains at least one non-zero (alive/border) cell."""
    from utilities.icons import Icons

    icon = Icons.get("WOLFRAM_AUTOMATA")
    non_zero = sum(1 for b in icon if b != 0)
    assert non_zero > 0, \
        "WOLFRAM_AUTOMATA icon should have at least one non-zero byte"
    print(f"✓ icons: WOLFRAM_AUTOMATA icon has {non_zero} non-zero bytes")


# ===========================================================================
# Standalone runner
# ===========================================================================

if __name__ == "__main__":
    print("Running Wolfram 1D Cellular Automata feature tests...\n")

    tests = [
        # _apply_rule – Rule 90
        test_apply_rule90_single_center_pixel,
        test_apply_rule90_produces_sierpinski_second_step,
        test_apply_rule90_toroidal_wrap,
        # _apply_rule – Rule 30
        test_apply_rule30_single_center_pixel,
        # _step – fill
        test_step_fills_grid_from_top,
        test_step_fill_row_increments_to_height,
        # _step – scroll
        test_step_scrolls_when_full,
        test_step_increments_step_count,
        # _reset
        test_reset_clears_grid,
        test_reset_places_center_seed_at_top,
        test_reset_sets_fill_row_to_one,
        test_reset_initialises_step_count,
        # _recolor
        test_recolor_updates_alive_cells_in_grid,
        test_recolor_updates_current_row,
        # manifest
        test_wolfram_automata_in_manifest,
        test_wolfram_automata_has_rule_setting,
        test_wolfram_automata_is_zero_player_mode,
        # icons
        test_wolfram_automata_icon_in_icons,
        test_wolfram_automata_icon_correct_size,
        test_wolfram_automata_icon_has_alive_cells,
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
