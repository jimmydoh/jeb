"""Tests for the Wireworld cellular automaton feature.

Verifies:
- Wireworld._step() applies the four-state rules correctly
  (EMPTY→EMPTY, HEAD→TAIL, TAIL→COPPER, COPPER→HEAD iff 1–2 HEAD neighbours)
- _count_head_neighbors() uses toroidal (wrap-around) Moore neighbourhood
- _build_frame() maps state codes to the expected palette indices
- _load_pattern() resets the grid and generation counter from a pattern bytes object
- All three hardcoded patterns are 256 bytes, contain copper and electron cells
- manifest.py contains a valid WIREWORLD entry in the ZERO_PLAYER submenu
- icons.py exposes a WIREWORLD icon that is exactly 256 bytes
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

def _make_ww(width=8, height=8):
    """Return a Wireworld instance with grid/next/frame buffers initialised."""
    from modes.wireworld import Wireworld
    from unittest.mock import MagicMock

    fake_core = MagicMock()
    ww = Wireworld(fake_core)
    ww.width  = width
    ww.height = height
    size = width * height
    ww._grid  = bytearray(size)
    ww._next  = bytearray(size)
    ww._frame = bytearray(size)
    return ww


# ===========================================================================
# 1. State-transition rules via _step()
# ===========================================================================

def test_step_empty_stays_empty():
    """EMPTY cells always remain EMPTY."""
    from modes.wireworld import _EMPTY
    ww = _make_ww(4, 4)
    # Grid is all zeros (EMPTY) by default
    ww._step()
    assert all(b == _EMPTY for b in ww._grid), \
        "All EMPTY cells should remain EMPTY after one step"
    print("✓ step: EMPTY → EMPTY")


def test_step_head_becomes_tail():
    """An electron HEAD cell always becomes TAIL on the next step."""
    from modes.wireworld import _HEAD, _TAIL
    ww = _make_ww(4, 4)
    ww._grid[1 * 4 + 1] = _HEAD    # isolated HEAD
    ww._step()
    assert ww._grid[1 * 4 + 1] == _TAIL, \
        "HEAD should become TAIL on the next step"
    print("✓ step: HEAD → TAIL")


def test_step_tail_becomes_copper():
    """An electron TAIL cell always becomes COPPER on the next step."""
    from modes.wireworld import _TAIL, _COPPER
    ww = _make_ww(4, 4)
    ww._grid[2 * 4 + 2] = _TAIL    # isolated TAIL
    ww._step()
    assert ww._grid[2 * 4 + 2] == _COPPER, \
        "TAIL should become COPPER on the next step"
    print("✓ step: TAIL → COPPER")


def test_step_copper_with_one_head_becomes_head():
    """COPPER with exactly 1 HEAD neighbour becomes HEAD."""
    from modes.wireworld import _COPPER, _HEAD
    ww = _make_ww(4, 4)
    ww._grid[1 * 4 + 1] = _COPPER   # the cell under test
    ww._grid[0 * 4 + 0] = _HEAD     # one diagonal HEAD neighbour
    ww._step()
    assert ww._grid[1 * 4 + 1] == _HEAD, \
        "COPPER with 1 HEAD neighbour should become HEAD"
    print("✓ step: COPPER + 1 HEAD neighbour → HEAD")


def test_step_copper_with_two_heads_becomes_head():
    """COPPER with exactly 2 HEAD neighbours becomes HEAD."""
    from modes.wireworld import _COPPER, _HEAD
    ww = _make_ww(4, 4)
    ww._grid[2 * 4 + 2] = _COPPER   # cell under test
    ww._grid[1 * 4 + 1] = _HEAD     # neighbour 1
    ww._grid[1 * 4 + 2] = _HEAD     # neighbour 2
    ww._step()
    assert ww._grid[2 * 4 + 2] == _HEAD, \
        "COPPER with 2 HEAD neighbours should become HEAD"
    print("✓ step: COPPER + 2 HEAD neighbours → HEAD")


def test_step_copper_with_zero_heads_stays_copper():
    """COPPER with no HEAD neighbours remains COPPER."""
    from modes.wireworld import _COPPER
    ww = _make_ww(4, 4)
    ww._grid[2 * 4 + 2] = _COPPER
    ww._step()
    assert ww._grid[2 * 4 + 2] == _COPPER, \
        "COPPER with 0 HEAD neighbours should stay COPPER"
    print("✓ step: COPPER + 0 HEAD neighbours → COPPER")


def test_step_copper_with_three_heads_stays_copper():
    """COPPER with 3 HEAD neighbours stays COPPER (not 1 or 2)."""
    from modes.wireworld import _COPPER, _HEAD
    ww = _make_ww(4, 4)
    ww._grid[2 * 4 + 2] = _COPPER
    ww._grid[1 * 4 + 1] = _HEAD
    ww._grid[1 * 4 + 2] = _HEAD
    ww._grid[1 * 4 + 3] = _HEAD
    ww._step()
    assert ww._grid[2 * 4 + 2] == _COPPER, \
        "COPPER with 3 HEAD neighbours should stay COPPER"
    print("✓ step: COPPER + 3 HEAD neighbours → COPPER (inhibited)")


def test_step_increments_generation():
    """Each call to _step() increments _generation by exactly 1."""
    ww = _make_ww(4, 4)
    assert ww._generation == 0
    ww._step()
    assert ww._generation == 1
    ww._step()
    assert ww._generation == 2
    print("✓ step: _generation increments correctly")


def test_step_swaps_buffers():
    """After _step(), _grid and _next reference the swapped buffers."""
    ww = _make_ww(4, 4)
    orig_grid_id = id(ww._grid)
    orig_next_id = id(ww._next)
    ww._step()
    assert id(ww._grid) == orig_next_id, \
        "_grid should point to the old _next buffer after swap"
    assert id(ww._next) == orig_grid_id, \
        "_next should point to the old _grid buffer after swap"
    print("✓ step: grid/next buffers swapped after each generation")


# ===========================================================================
# 2. Electron propagation on a copper track
# ===========================================================================

def test_electron_propagates_along_copper():
    """HEAD advances one cell along a copper line, leaving TAIL and COPPER behind."""
    from modes.wireworld import _HEAD, _TAIL, _COPPER
    ww = _make_ww(8, 8)
    # Horizontal copper track on row 3: cols 1-6
    for x in range(1, 7):
        ww._grid[3 * 8 + x] = _COPPER
    # Place electron: TAIL at col 1, HEAD at col 2
    ww._grid[3 * 8 + 1] = _TAIL
    ww._grid[3 * 8 + 2] = _HEAD
    ww._step()
    # HEAD should advance to col 3; col 2 becomes TAIL; col 1 becomes COPPER
    assert ww._grid[3 * 8 + 3] == _HEAD,   "HEAD should advance to col 3"
    assert ww._grid[3 * 8 + 2] == _TAIL,   "Previous HEAD (col 2) should be TAIL"
    assert ww._grid[3 * 8 + 1] == _COPPER, "Previous TAIL (col 1) should be COPPER"
    print("✓ propagation: electron moves one cell along copper each step")


# ===========================================================================
# 3. _count_head_neighbors – toroidal wrap-around
# ===========================================================================

def test_count_head_neighbors_no_heads():
    """A cell surrounded only by EMPTY/COPPER cells has 0 HEAD neighbours."""
    from modes.wireworld import _COPPER
    ww = _make_ww(8, 8)
    ww._grid[4 * 8 + 4] = _COPPER   # cell under test
    assert ww._count_head_neighbors(4, 4) == 0, \
        "No HEAD neighbours should return 0"
    print("✓ count_head_neighbors: 0 neighbours correctly counted")


def test_count_head_neighbors_toroidal_corner():
    """HEAD at the opposite corner is counted as a neighbour (toroidal wrap)."""
    from modes.wireworld import _HEAD, _COPPER
    ww = _make_ww(8, 8)
    ww._grid[0 * 8 + 0] = _COPPER   # cell at top-left corner
    ww._grid[7 * 8 + 7] = _HEAD     # HEAD at bottom-right (diagonal wrap)
    count = ww._count_head_neighbors(0, 0)
    assert count == 1, \
        f"Corner (0,0) should see 1 toroidally-wrapped HEAD neighbour, got {count}"
    print("✓ count_head_neighbors: toroidal corner wrap counted correctly")


def test_count_head_neighbors_does_not_count_self():
    """A HEAD cell is NOT counted as its own neighbour."""
    from modes.wireworld import _HEAD
    ww = _make_ww(8, 8)
    ww._grid[3 * 8 + 3] = _HEAD
    count = ww._count_head_neighbors(3, 3)
    assert count == 0, "A HEAD cell must not count itself as a neighbour"
    print("✓ count_head_neighbors: self not counted")


# ===========================================================================
# 4. _build_frame – palette mapping
# ===========================================================================

def test_build_frame_palette_mapping():
    """_build_frame maps each state code to the correct palette index."""
    from modes.wireworld import _EMPTY, _HEAD, _TAIL, _COPPER, _STATE_COLORS
    ww = _make_ww(2, 2)
    ww._grid[0] = _EMPTY
    ww._grid[1] = _HEAD
    ww._grid[2] = _TAIL
    ww._grid[3] = _COPPER
    ww._build_frame()
    assert ww._frame[0] == _STATE_COLORS[_EMPTY],  "EMPTY should map to palette 0"
    assert ww._frame[1] == _STATE_COLORS[_HEAD],   "HEAD should map to BLUE palette idx"
    assert ww._frame[2] == _STATE_COLORS[_TAIL],   "TAIL should map to CYAN palette idx"
    assert ww._frame[3] == _STATE_COLORS[_COPPER], "COPPER should map to ORANGE palette idx"
    print("✓ _build_frame: correct palette index for each state")


def test_build_frame_does_not_modify_grid():
    """_build_frame only writes to _frame; _grid is unchanged."""
    from modes.wireworld import _HEAD
    ww = _make_ww(4, 4)
    ww._grid[0] = _HEAD
    ww._build_frame()
    assert ww._grid[0] == _HEAD, "_build_frame must not modify _grid"
    print("✓ _build_frame: _grid is not mutated")


# ===========================================================================
# 5. _load_pattern
# ===========================================================================

def test_load_pattern_resets_generation():
    """_load_pattern resets the generation counter to 0."""
    ww = _make_ww(16, 16)
    ww._generation = 999
    ww._pattern_idx = 0
    ww._load_pattern()
    assert ww._generation == 0, "_load_pattern should reset _generation to 0"
    print("✓ _load_pattern: _generation reset to 0")


def test_load_pattern_copies_state_bytes():
    """_load_pattern fills _grid with the bytes from the selected pattern."""
    from modes.wireworld import _PATTERNS, _COPPER
    ww = _make_ww(16, 16)
    ww._pattern_idx = 0
    ww._load_pattern()
    pattern_bytes = _PATTERNS[0][0]
    for i in range(256):
        assert ww._grid[i] == pattern_bytes[i], \
            f"Grid cell {i} should match pattern byte, got {ww._grid[i]} != {pattern_bytes[i]}"
    print("✓ _load_pattern: grid matches pattern bytes exactly")


# ===========================================================================
# 6. Pattern data integrity
# ===========================================================================

def test_all_patterns_are_256_bytes():
    """Every hardcoded pattern is exactly 256 bytes (16×16 grid)."""
    from modes.wireworld import _PATTERNS
    for pat_bytes, name in _PATTERNS:
        assert len(pat_bytes) == 256, \
            f"Pattern '{name}' should be 256 bytes, got {len(pat_bytes)}"
    print(f"✓ patterns: all {len(_PATTERNS)} patterns are 256 bytes")


def test_patterns_contain_copper():
    """Each pattern contains at least one COPPER cell."""
    from modes.wireworld import _PATTERNS, _COPPER
    for pat_bytes, name in _PATTERNS:
        has_copper = any(b == _COPPER for b in pat_bytes)
        assert has_copper, f"Pattern '{name}' should contain at least one COPPER cell"
    print("✓ patterns: all patterns contain COPPER cells")


def test_patterns_contain_electron():
    """Each pattern contains at least one HEAD and one TAIL cell."""
    from modes.wireworld import _PATTERNS, _HEAD, _TAIL
    for pat_bytes, name in _PATTERNS:
        has_head = any(b == _HEAD for b in pat_bytes)
        has_tail = any(b == _TAIL for b in pat_bytes)
        assert has_head, f"Pattern '{name}' should contain at least one HEAD cell"
        assert has_tail, f"Pattern '{name}' should contain at least one TAIL cell"
    print("✓ patterns: all patterns contain both HEAD and TAIL cells")


def test_at_least_three_patterns():
    """There are at least three distinct circuit patterns."""
    from modes.wireworld import _PATTERNS
    assert len(_PATTERNS) >= 3, \
        f"Expected at least 3 patterns, found {len(_PATTERNS)}"
    print(f"✓ patterns: {len(_PATTERNS)} patterns present (≥ 3 required)")


def test_patterns_only_valid_states():
    """All bytes in every pattern are valid state codes (0–3)."""
    from modes.wireworld import _PATTERNS
    for pat_bytes, name in _PATTERNS:
        for i, b in enumerate(pat_bytes):
            assert b in (0, 1, 2, 3), \
                f"Pattern '{name}' cell {i} has invalid state {b}"
    print("✓ patterns: all cells contain valid state codes (0–3)")


def test_pattern_preserves_cell_count():
    """Running pattern 1 for many steps keeps the total non-empty cell count stable.

    In Wireworld with Moore neighbourhood, rectangular loops may generate
    additional electrons at corners (COPPER → HEAD when 1–2 HEAD neighbours
    are present in the 8-cell neighbourhood).  Regardless of how many
    electrons circulate, the invariant that holds is: the sum of all non-EMPTY
    cells (HEAD + TAIL + COPPER) equals the initial copper-track size, because
    each state transition is a cyclic permutation that preserves cell count.
    """
    from modes.wireworld import _EMPTY
    ww = _make_ww(16, 16)
    ww._pattern_idx = 0
    ww._load_pattern()

    # Count initial non-empty cells (the invariant)
    initial_count = sum(1 for b in ww._grid if b != _EMPTY)
    assert initial_count > 0, "Pattern 1 must have non-empty cells"

    # Run 100 steps; the total non-empty count must be preserved at every step
    for step in range(100):
        ww._step()
        current_count = sum(1 for b in ww._grid if b != _EMPTY)
        assert current_count == initial_count, \
            f"Step {step+1}: non-empty cell count changed from {initial_count} to {current_count}"

    assert ww._generation == 100, "Step count should be 100 after 100 steps"
    print(f"✓ simulation: pattern 1 stable after 100 steps ({initial_count} non-empty cells preserved)")


def test_pattern2_twin_pulses_has_two_electrons():
    """The Twin Pulses pattern starts with exactly 2 HEADs and 2 TAILs."""
    from modes.wireworld import _PATTERN_TWIN_PULSES, _HEAD, _TAIL
    heads = sum(1 for b in _PATTERN_TWIN_PULSES if b == _HEAD)
    tails = sum(1 for b in _PATTERN_TWIN_PULSES if b == _TAIL)
    assert heads == 2, f"Twin Pulses should start with 2 HEADs, got {heads}"
    assert tails == 2, f"Twin Pulses should start with 2 TAILs, got {tails}"
    print(f"✓ pattern2: Twin Pulses has {heads} HEADs and {tails} TAILs at start")


def test_pattern3_three_loops_has_three_electrons():
    """The Three Loops pattern starts with exactly 3 HEADs and 3 TAILs."""
    from modes.wireworld import _PATTERN_THREE_LOOPS, _HEAD, _TAIL
    heads = sum(1 for b in _PATTERN_THREE_LOOPS if b == _HEAD)
    tails = sum(1 for b in _PATTERN_THREE_LOOPS if b == _TAIL)
    assert heads == 3, f"Three Loops should start with 3 HEADs, got {heads}"
    assert tails == 3, f"Three Loops should start with 3 TAILs, got {tails}"
    print(f"✓ pattern3: Three Loops has {heads} HEADs and {tails} TAILs at start")


# ===========================================================================
# 7. Manifest entry
# ===========================================================================

def test_wireworld_in_manifest():
    """WIREWORLD entry exists in MODE_REGISTRY with all required fields."""
    from modes.manifest import MODE_REGISTRY

    assert "WIREWORLD" in MODE_REGISTRY, \
        "WIREWORLD not found in MODE_REGISTRY"
    meta = MODE_REGISTRY["WIREWORLD"]

    required_fields = ["id", "name", "module_path", "class_name",
                       "icon", "menu", "requires", "settings"]
    for field in required_fields:
        assert field in meta, f"WIREWORLD missing required field '{field}'"

    assert meta["id"]          == "WIREWORLD"
    assert meta["module_path"] == "modes.wireworld",  \
        "WIREWORLD module_path should be 'modes.wireworld'"
    assert meta["class_name"]  == "Wireworld", \
        "WIREWORLD class_name should be 'Wireworld'"
    assert meta["menu"]        == "ZERO_PLAYER", \
        "WIREWORLD should belong to the ZERO_PLAYER submenu"
    assert meta["icon"]        == "WIREWORLD", \
        "WIREWORLD should reference the WIREWORLD icon"
    assert "CORE" in meta["requires"], "WIREWORLD should require CORE"
    print("✓ manifest: WIREWORLD entry is complete and correct")


def test_existing_zero_player_entries_undisturbed():
    """Adding WIREWORLD has not disturbed existing ZERO_PLAYER entries."""
    from modes.manifest import MODE_REGISTRY

    for key in ("ZERO_PLAYER_MENU", "CONWAYS_LIFE", "LANGTONS_ANT",
                "WOLFRAM_AUTOMATA", "FALLING_SAND"):
        assert key in MODE_REGISTRY, \
            f"Existing entry '{key}' should still be present in MODE_REGISTRY"
    print("✓ manifest: existing ZERO_PLAYER entries are intact")


# ===========================================================================
# 8. Icon
# ===========================================================================

def test_wireworld_icon_in_icons():
    """icons.py exposes a WIREWORLD icon that is a non-empty bytes object."""
    from utilities.icons import Icons

    icon = Icons.get("WIREWORLD")
    assert icon is not None, "Icons library should contain a WIREWORLD icon"
    assert isinstance(icon, (bytes, bytearray)), \
        "WIREWORLD icon should be bytes or bytearray"
    assert len(icon) > 0, "WIREWORLD icon should not be empty"
    print(f"✓ icons: WIREWORLD icon present ({len(icon)} bytes)")


def test_wireworld_icon_correct_size():
    """WIREWORLD icon has the expected 16×16 = 256-byte size."""
    from utilities.icons import Icons

    icon = Icons.get("WIREWORLD")
    assert len(icon) == 256, \
        f"WIREWORLD icon should be 256 bytes (16×16), got {len(icon)}"
    print("✓ icons: WIREWORLD icon is 256 bytes (16×16)")


# ===========================================================================
# Standalone runner
# ===========================================================================

if __name__ == "__main__":
    print("Running Wireworld feature tests...\n")

    tests = [
        # State-transition rules
        test_step_empty_stays_empty,
        test_step_head_becomes_tail,
        test_step_tail_becomes_copper,
        test_step_copper_with_one_head_becomes_head,
        test_step_copper_with_two_heads_becomes_head,
        test_step_copper_with_zero_heads_stays_copper,
        test_step_copper_with_three_heads_stays_copper,
        test_step_increments_generation,
        test_step_swaps_buffers,
        # Propagation
        test_electron_propagates_along_copper,
        # Neighbourhood counting
        test_count_head_neighbors_no_heads,
        test_count_head_neighbors_toroidal_corner,
        test_count_head_neighbors_does_not_count_self,
        # Frame building
        test_build_frame_palette_mapping,
        test_build_frame_does_not_modify_grid,
        # Pattern loading
        test_load_pattern_resets_generation,
        test_load_pattern_copies_state_bytes,
        # Pattern integrity
        test_all_patterns_are_256_bytes,
        test_patterns_contain_copper,
        test_patterns_contain_electron,
        test_at_least_three_patterns,
        test_patterns_only_valid_states,
        test_pattern_preserves_cell_count,
        test_pattern2_twin_pulses_has_two_electrons,
        test_pattern3_three_loops_has_three_electrons,
        # Manifest
        test_wireworld_in_manifest,
        test_existing_zero_player_entries_undisturbed,
        # Icon
        test_wireworld_icon_in_icons,
        test_wireworld_icon_correct_size,
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
