"""Tests for Conway's Game of Life feature.

Verifies:
- ConwaysLife._count_neighbors() implements toroidal wrap-around neighbour counting
- ConwaysLife._step() applies the standard Conway survival/birth rules
- MatrixManager.show_frame() renders alive/dead cells with the correct colours
- manifest.py contains valid ZERO_PLAYER_MENU and CONWAYS_LIFE entries
- main_menu.py tracks last_rendered_zero_player and calls _build_menu_items("ZERO_PLAYER")
- icons.py exposes ZERO_PLAYER and CONWAYS_LIFE icon data
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
# Helpers – lightweight mocks used by multiple tests
# ===========================================================================

class _MockNeoPixel:
    """Minimal neopixel.NeoPixel stand-in."""
    def __init__(self, n):
        self._buf = [(0, 0, 0)] * n
        self.brightness = 0.3
        self.n = n

    def __setitem__(self, idx, color):
        self._buf[idx] = color

    def __getitem__(self, idx):
        return self._buf[idx]

    def fill(self, color):
        self._buf = [color] * self.n

    def show(self):
        pass


class _MockJEBPixel:
    """Minimal JEBPixel stand-in that wraps _MockNeoPixel."""
    def __init__(self, n=64):
        self._pixels = _MockNeoPixel(n)
        self.n = n
        self.brightness = 0.3

    def __setitem__(self, idx, color):
        self._pixels[idx] = color

    def __getitem__(self, idx):
        return self._pixels[idx]

    def fill(self, color):
        self._pixels.fill(color)

    def show(self):
        pass


def _make_life(width=8, height=8):
    """Return a ConwaysLife instance with _grid and _next initialised."""
    from modes.conways_life import ConwaysLife
    from unittest.mock import MagicMock

    # Use MagicMock so any unexpected core attribute access doesn't raise
    fake_core = MagicMock()
    life = ConwaysLife(fake_core)
    life.width = width
    life.height = height
    size = width * height
    life._grid = bytearray(size)
    life._next = bytearray(size)
    return life


def _make_matrix(width=8, height=8):
    """Return a MatrixManager backed by a mock pixel strip."""
    from managers.matrix_manager import MatrixManager
    pixel = _MockJEBPixel(width * height)
    return MatrixManager(pixel, width=width, height=height)


# ===========================================================================
# 1. ConwaysLife – _count_neighbors
# ===========================================================================

def test_count_neighbors_isolated_cell():
    """An isolated alive cell has 0 neighbours."""
    life = _make_life(8, 8)
    life._grid[3 * 8 + 3] = 1          # cell (3, 3) alive, rest dead
    assert life._count_neighbors(3, 3) == 0, \
        "Isolated cell should have 0 alive neighbours"
    print("✓ count_neighbors: isolated cell → 0 neighbours")


def test_count_neighbors_surrounded_cell():
    """A cell whose 8 surrounding cells are all alive reports 8 neighbours."""
    life = _make_life(8, 8)
    cx, cy = 4, 4
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if not (dx == 0 and dy == 0):
                nx, ny = (cx + dx) % 8, (cy + dy) % 8
                life._grid[ny * 8 + nx] = 1
    assert life._count_neighbors(cx, cy) == 8, \
        "Cell surrounded by 8 alive neighbours should return 8"
    print("✓ count_neighbors: fully surrounded cell → 8 neighbours")


def test_count_neighbors_partial_neighbours():
    """A cell with exactly 3 neighbours reports 3."""
    life = _make_life(8, 8)
    cx, cy = 2, 2
    # Place exactly 3 alive neighbours
    life._grid[(cy - 1) * 8 + (cx - 1)] = 1
    life._grid[(cy - 1) * 8 + cx] = 1
    life._grid[(cy - 1) * 8 + (cx + 1)] = 1
    assert life._count_neighbors(cx, cy) == 3, \
        "Cell with 3 alive neighbours should return 3"
    print("✓ count_neighbors: 3 neighbours correctly counted")


def test_count_neighbors_toroidal_wrap_corner():
    """Neighbours wrap around the grid edges (toroidal topology)."""
    life = _make_life(8, 8)
    # Make the top-right corner alive – it should be a neighbour of top-left (0,0)
    life._grid[0 * 8 + 7] = 1          # (7, 0)  right of (0, 0) wrapping
    life._grid[7 * 8 + 0] = 1          # (0, 7)  below (0, 0) wrapping
    life._grid[7 * 8 + 7] = 1          # (7, 7)  diagonal from (0, 0) wrapping
    count = life._count_neighbors(0, 0)
    assert count == 3, \
        f"Corner cell (0,0) should see 3 wrapped neighbours, got {count}"
    print("✓ count_neighbors: toroidal corner wrap → 3 neighbours")


def test_count_neighbors_does_not_count_self():
    """The cell at (x, y) is not counted as its own neighbour."""
    life = _make_life(8, 8)
    # Mark (3, 3) alive – make sure it is not counted as its own neighbour
    life._grid[3 * 8 + 3] = 1
    # Also mark two real neighbours
    life._grid[2 * 8 + 2] = 1
    life._grid[2 * 8 + 3] = 1
    count = life._count_neighbors(3, 3)
    assert count == 2, \
        f"Self should not be counted as a neighbour; expected 2, got {count}"
    print("✓ count_neighbors: self not counted as own neighbour")


# ===========================================================================
# 2. ConwaysLife – _step (survival / birth / death rules)
# ===========================================================================

def test_step_underpopulation_death():
    """A live cell with fewer than 2 neighbours dies (underpopulation)."""
    life = _make_life(8, 8)
    cx, cy = 4, 4
    life._grid[cy * 8 + cx] = 1        # alive with 0 neighbours → must die
    life._step()
    assert life._grid[cy * 8 + cx] == 0, \
        "Cell with 0 neighbours should die from underpopulation"
    print("✓ step: cell with 0 neighbours dies (underpopulation)")


def test_step_survival_two_neighbours():
    """A live cell with exactly 2 neighbours survives."""
    life = _make_life(8, 8)
    cx, cy = 4, 4
    life._grid[cy * 8 + cx] = 1
    # Place exactly 2 alive neighbours
    life._grid[(cy - 1) * 8 + (cx - 1)] = 1
    life._grid[(cy - 1) * 8 + cx] = 1
    life._step()
    assert life._grid[cy * 8 + cx] == 1, \
        "Cell with 2 neighbours should survive"
    print("✓ step: cell with 2 neighbours survives")


def test_step_survival_three_neighbours():
    """A live cell with exactly 3 neighbours survives."""
    life = _make_life(8, 8)
    cx, cy = 4, 4
    life._grid[cy * 8 + cx] = 1
    life._grid[(cy - 1) * 8 + (cx - 1)] = 1
    life._grid[(cy - 1) * 8 + cx] = 1
    life._grid[(cy - 1) * 8 + (cx + 1)] = 1
    life._step()
    assert life._grid[cy * 8 + cx] == 1, \
        "Cell with 3 neighbours should survive"
    print("✓ step: cell with 3 neighbours survives")


def test_step_overpopulation_death():
    """A live cell with more than 3 neighbours dies (overpopulation)."""
    life = _make_life(8, 8)
    cx, cy = 4, 4
    life._grid[cy * 8 + cx] = 1
    # Place 4 alive neighbours
    life._grid[(cy - 1) * 8 + cx] = 1
    life._grid[(cy + 1) * 8 + cx] = 1
    life._grid[cy * 8 + (cx - 1)] = 1
    life._grid[cy * 8 + (cx + 1)] = 1
    life._step()
    assert life._grid[cy * 8 + cx] == 0, \
        "Cell with 4 neighbours should die from overpopulation"
    print("✓ step: cell with 4 neighbours dies (overpopulation)")


def test_step_birth_with_three_neighbours():
    """A dead cell with exactly 3 alive neighbours becomes alive (birth)."""
    life = _make_life(8, 8)
    cx, cy = 4, 4
    # (cx, cy) is dead; 3 alive neighbours
    life._grid[(cy - 1) * 8 + (cx - 1)] = 1
    life._grid[(cy - 1) * 8 + cx] = 1
    life._grid[(cy - 1) * 8 + (cx + 1)] = 1
    life._step()
    assert life._grid[cy * 8 + cx] == 1, \
        "Dead cell with 3 alive neighbours should be born"
    print("✓ step: dead cell with 3 neighbours is born")


def test_step_no_birth_two_neighbours():
    """A dead cell with only 2 alive neighbours stays dead."""
    life = _make_life(8, 8)
    cx, cy = 4, 4
    life._grid[(cy - 1) * 8 + (cx - 1)] = 1
    life._grid[(cy - 1) * 8 + cx] = 1
    life._step()
    assert life._grid[cy * 8 + cx] == 0, \
        "Dead cell with 2 alive neighbours should stay dead"
    print("✓ step: dead cell with 2 neighbours stays dead")


def test_step_increments_generation():
    """Each call to _step() increments the generation counter by 1."""
    life = _make_life(8, 8)
    assert life._generation == 0
    life._step()
    assert life._generation == 1
    life._step()
    assert life._generation == 2
    print("✓ step: generation counter increments correctly")


def test_step_swaps_buffers():
    """After _step(), _grid and _next reference the new and old buffers."""
    life = _make_life(8, 8)
    original_grid_id = id(life._grid)
    original_next_id = id(life._next)
    life._step()
    # After swap: the old _next is now _grid, and vice-versa
    assert id(life._grid) == original_next_id, \
        "After _step(), _grid should point to the old _next buffer"
    assert id(life._next) == original_grid_id, \
        "After _step(), _next should point to the old _grid buffer"
    print("✓ step: grid/next buffers are swapped after each generation")


def test_step_blinker_oscillator():
    """A horizontal blinker becomes vertical after one step (classic oscillator)."""
    life = _make_life(8, 8)
    # Horizontal blinker at row 4: cells (3,4), (4,4), (5,4)
    life._grid[4 * 8 + 3] = 1
    life._grid[4 * 8 + 4] = 1
    life._grid[4 * 8 + 5] = 1
    life._step()
    # After one step the blinker rotates 90°: cells (4,3), (4,4), (4,5)
    assert life._grid[3 * 8 + 4] == 1, "Blinker top cell should be alive after step"
    assert life._grid[4 * 8 + 4] == 1, "Blinker centre cell should survive"
    assert life._grid[5 * 8 + 4] == 1, "Blinker bottom cell should be alive after step"
    # Original left and right wings should now be dead
    assert life._grid[4 * 8 + 3] == 0, "Blinker left wing should die"
    assert life._grid[4 * 8 + 5] == 0, "Blinker right wing should die"
    print("✓ step: horizontal blinker rotates to vertical after one generation")


def test_step_still_life_block():
    """A 2×2 block (still life) is unchanged after one step."""
    life = _make_life(8, 8)
    # Place a 2×2 block at (3,3)–(4,4)
    for y in (3, 4):
        for x in (3, 4):
            life._grid[y * 8 + x] = 1
    life._step()
    for y in (3, 4):
        for x in (3, 4):
            assert life._grid[y * 8 + x] == 1, \
                f"Block cell ({x},{y}) should still be alive"
    print("✓ step: 2×2 block still-life is unchanged after one generation")


# ===========================================================================
# 3. MatrixManager.show_frame
# ===========================================================================

def _slot_color(matrix, x, y):
    """Return the color stored in the animation slot for (x, y), or None if inactive."""
    idx = matrix._get_idx(x, y)
    slot = matrix.active_animations[idx]
    return slot.color if slot.active else None


def test_show_frame_alive_cells_use_alive_color():
    """show_frame registers alive cells (value=1) with the alive_color animation slot."""
    matrix = _make_matrix(4, 4)
    alive_color = (0, 255, 0)
    frame = bytearray(16)
    frame[0] = 1    # pixel (0, 0)
    frame[5] = 1    # pixel (1, 1)
    matrix.show_frame(frame, alive_color)
    assert _slot_color(matrix, 0, 0) == alive_color, \
        "Alive cell (0,0) animation slot should hold alive_color"
    assert _slot_color(matrix, 1, 1) == alive_color, \
        "Alive cell (1,1) animation slot should hold alive_color"
    print("✓ show_frame: alive cells registered with alive_color")


def test_show_frame_dead_cells_off_by_default():
    """Dead cells leave animation slots inactive when dead_color is None (default)."""
    matrix = _make_matrix(4, 4)
    alive_color = (255, 0, 0)
    # All cells dead
    frame = bytearray(16)
    matrix.show_frame(frame, alive_color, clear=True, dead_color=None)
    # After a clear + all-dead frame (no dead_color), every slot should be inactive
    for y in range(4):
        for x in range(4):
            idx = matrix._get_idx(x, y)
            assert not matrix.active_animations[idx].active, \
                f"Dead cell ({x},{y}) slot should be inactive when dead_color is None"
    print("✓ show_frame: dead cells leave slots inactive when dead_color is None")


def test_show_frame_dead_cells_painted_with_dead_color():
    """Dead cells have their animation slot set to dead_color when it is provided."""
    matrix = _make_matrix(4, 4)
    alive_color = (0, 255, 0)
    dead_color = (10, 0, 0)
    frame = bytearray(16)   # all dead
    matrix.show_frame(frame, alive_color, dead_color=dead_color)
    for y in range(4):
        for x in range(4):
            assert _slot_color(matrix, x, y) == dead_color, \
                f"Dead cell ({x},{y}) slot should hold dead_color"
    print("✓ show_frame: dead cells registered with dead_color when supplied")


def test_show_frame_clear_true_removes_previous_content():
    """clear=True (default) clears all animation slots before rendering the frame."""
    matrix = _make_matrix(4, 4)
    stale_color = (99, 99, 99)
    alive_color = (0, 0, 255)
    # Pre-activate every slot with a stale colour
    for i in range(matrix.num_pixels):
        matrix.set_animation(i, "SOLID", stale_color)
    # Render an all-dead frame with clear=True (no dead_color)
    frame = bytearray(16)
    matrix.show_frame(frame, alive_color, clear=True)
    # All slots should now be inactive (stale colour cleared, nothing alive drawn)
    for i in range(matrix.num_pixels):
        assert not matrix.active_animations[i].active, \
            f"Slot {i} should be inactive after clear=True with all-dead frame"
    print("✓ show_frame: clear=True wipes stale animation slots before rendering")


def test_show_frame_mixed_frame():
    """show_frame correctly registers alive and dead cells for a mixed frame."""
    matrix = _make_matrix(4, 4)
    alive_color = (0, 200, 0)
    dead_color = (5, 5, 5)
    frame = bytearray(16)
    alive_positions = {0, 3, 5, 10, 15}
    for p in alive_positions:
        frame[p] = 1
    matrix.show_frame(frame, alive_color, dead_color=dead_color)
    for pos in range(16):
        x = pos % 4
        y = pos // 4
        expected = alive_color if pos in alive_positions else dead_color
        assert _slot_color(matrix, x, y) == expected, \
            f"Frame position {pos} ({x},{y}): expected slot color {expected}, " \
            f"got {_slot_color(matrix, x, y)}"
    print("✓ show_frame: mixed alive/dead frame registered correctly")


def test_show_frame_frame_length_larger_than_grid():
    """show_frame handles a frame buffer larger than the grid without error."""
    matrix = _make_matrix(4, 4)
    alive_color = (255, 255, 0)
    # Frame is twice the grid size – extra bytes must be ignored
    frame = bytearray(32)
    for i in range(16):
        frame[i] = 1    # all alive within the actual 4×4 grid
    matrix.show_frame(frame, alive_color)
    for y in range(4):
        for x in range(4):
            assert _slot_color(matrix, x, y) == alive_color, \
                f"Pixel ({x},{y}) should have alive_color even with oversized frame"
    print("✓ show_frame: oversized frame buffer handled without error")


# ===========================================================================
# 4. Manifest entries
# ===========================================================================

def test_zero_player_menu_in_manifest():
    """ZERO_PLAYER_MENU entry exists in MODE_REGISTRY with all required fields."""
    from modes.manifest import MODE_REGISTRY

    assert "ZERO_PLAYER_MENU" in MODE_REGISTRY, \
        "ZERO_PLAYER_MENU not found in MODE_REGISTRY"
    meta = MODE_REGISTRY["ZERO_PLAYER_MENU"]

    required_fields = ["id", "name", "module_path", "class_name", "icon", "menu", "requires", "settings"]
    for field in required_fields:
        assert field in meta, \
            f"ZERO_PLAYER_MENU missing required field '{field}'"

    assert meta["id"] == "ZERO_PLAYER_MENU"
    assert meta["menu"] == "MAIN", \
        "ZERO_PLAYER_MENU should appear in the MAIN menu"
    assert meta["icon"] == "ZERO_PLAYER", \
        "ZERO_PLAYER_MENU should reference the ZERO_PLAYER icon"
    assert meta.get("submenu") == "ZERO_PLAYER", \
        "ZERO_PLAYER_MENU should declare submenu='ZERO_PLAYER'"
    print("✓ manifest: ZERO_PLAYER_MENU entry is complete and correct")


def test_conways_life_in_manifest():
    """CONWAYS_LIFE entry exists in MODE_REGISTRY with all required fields."""
    from modes.manifest import MODE_REGISTRY

    assert "CONWAYS_LIFE" in MODE_REGISTRY, \
        "CONWAYS_LIFE not found in MODE_REGISTRY"
    meta = MODE_REGISTRY["CONWAYS_LIFE"]

    required_fields = ["id", "name", "module_path", "class_name", "icon", "menu", "requires", "settings"]
    for field in required_fields:
        assert field in meta, \
            f"CONWAYS_LIFE missing required field '{field}'"

    assert meta["id"] == "CONWAYS_LIFE"
    assert meta["module_path"] == "modes.conways_life", \
        "CONWAYS_LIFE module_path should be 'modes.conways_life'"
    assert meta["class_name"] == "ConwaysLife", \
        "CONWAYS_LIFE class_name should be 'ConwaysLife'"
    assert meta["menu"] == "ZERO_PLAYER", \
        "CONWAYS_LIFE should belong to the ZERO_PLAYER submenu"
    assert meta["icon"] == "CONWAYS_LIFE", \
        "CONWAYS_LIFE should reference the CONWAYS_LIFE icon"
    assert "CORE" in meta["requires"], \
        "CONWAYS_LIFE should require CORE"
    print("✓ manifest: CONWAYS_LIFE entry is complete and correct")


def test_zero_player_modes_have_required_fields():
    """All ZERO_PLAYER-menu modes carry the minimum required metadata fields."""
    from modes.manifest import MODE_REGISTRY

    zero_player_modes = {k: v for k, v in MODE_REGISTRY.items()
                         if v.get("menu") == "ZERO_PLAYER"}
    assert len(zero_player_modes) >= 1, \
        "Expected at least one ZERO_PLAYER menu mode"

    required_fields = ["id", "name", "module_path", "class_name", "icon", "menu", "requires", "settings"]
    for mode_id, meta in zero_player_modes.items():
        for field in required_fields:
            assert field in meta, \
                f"ZERO_PLAYER mode '{mode_id}' is missing required field '{field}'"
    print(f"✓ manifest: all {len(zero_player_modes)} ZERO_PLAYER mode(s) have required fields")


# ===========================================================================
# 5. main_menu.py structural checks
# ===========================================================================

def test_main_menu_last_rendered_zero_player_tracking():
    """main_menu.py declares a last_rendered_zero_player tracking variable."""
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'main_menu.py')
    with open(path, 'r') as fh:
        content = fh.read()
    assert "last_rendered_zero_player" in content, \
        "main_menu.py should contain a last_rendered_zero_player tracking variable"
    print("✓ main_menu.py has last_rendered_zero_player tracking variable")


def test_main_menu_uses_build_menu_items_zero_player():
    """main_menu.py calls _build_menu_items('ZERO_PLAYER') for the zero-player carousel."""
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'main_menu.py')
    with open(path, 'r') as fh:
        content = fh.read()
    # Accept either single or double quotes around the argument
    has_call = (
        '_build_menu_items("ZERO_PLAYER")' in content
        or "_build_menu_items('ZERO_PLAYER')" in content
    )
    assert has_call, \
        "main_menu.py should call _build_menu_items('ZERO_PLAYER') for the zero-player mode list"
    print('✓ main_menu.py uses _build_menu_items("ZERO_PLAYER")')


def test_main_menu_handles_zero_player_state():
    """main_menu.py contains a ZERO_PLAYER state handler."""
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'main_menu.py')
    with open(path, 'r') as fh:
        content = fh.read()
    assert '"ZERO_PLAYER"' in content or "'ZERO_PLAYER'" in content, \
        "main_menu.py should reference the ZERO_PLAYER state"
    print("✓ main_menu.py contains ZERO_PLAYER state handling")


# ===========================================================================
# 6. Icon library entries
# ===========================================================================

def test_zero_player_icon_in_icons():
    """icons.py exposes a ZERO_PLAYER icon that is a non-empty bytes object."""
    from utilities.icons import Icons

    icon = Icons.get("ZERO_PLAYER")
    assert icon is not None, "Icons library should contain a ZERO_PLAYER icon"
    assert isinstance(icon, (bytes, bytearray)), \
        "ZERO_PLAYER icon should be bytes or bytearray"
    assert len(icon) > 0, "ZERO_PLAYER icon should not be empty"
    print(f"✓ icons: ZERO_PLAYER icon present ({len(icon)} bytes)")


def test_conways_life_icon_in_icons():
    """icons.py exposes a CONWAYS_LIFE icon that is a non-empty bytes object."""
    from utilities.icons import Icons

    icon = Icons.get("CONWAYS_LIFE")
    assert icon is not None, "Icons library should contain a CONWAYS_LIFE icon"
    assert isinstance(icon, (bytes, bytearray)), \
        "CONWAYS_LIFE icon should be bytes or bytearray"
    assert len(icon) > 0, "CONWAYS_LIFE icon should not be empty"
    print(f"✓ icons: CONWAYS_LIFE icon present ({len(icon)} bytes)")


def test_zero_player_icon_correct_size():
    """ZERO_PLAYER icon has the expected 16×16 = 256-byte size."""
    from utilities.icons import Icons

    icon = Icons.get("ZERO_PLAYER")
    assert len(icon) == 256, \
        f"ZERO_PLAYER icon should be 256 bytes (16×16), got {len(icon)}"
    print("✓ icons: ZERO_PLAYER icon is 256 bytes (16×16)")


def test_conways_life_icon_correct_size():
    """CONWAYS_LIFE icon has the expected 16×16 = 256-byte size."""
    from utilities.icons import Icons

    icon = Icons.get("CONWAYS_LIFE")
    assert len(icon) == 256, \
        f"CONWAYS_LIFE icon should be 256 bytes (16×16), got {len(icon)}"
    print("✓ icons: CONWAYS_LIFE icon is 256 bytes (16×16)")


# ===========================================================================
# Standalone runner
# ===========================================================================

if __name__ == "__main__":
    print("Running Conway's Game of Life feature tests...\n")

    tests = [
        # _count_neighbors
        test_count_neighbors_isolated_cell,
        test_count_neighbors_surrounded_cell,
        test_count_neighbors_partial_neighbours,
        test_count_neighbors_toroidal_wrap_corner,
        test_count_neighbors_does_not_count_self,
        # _step
        test_step_underpopulation_death,
        test_step_survival_two_neighbours,
        test_step_survival_three_neighbours,
        test_step_overpopulation_death,
        test_step_birth_with_three_neighbours,
        test_step_no_birth_two_neighbours,
        test_step_increments_generation,
        test_step_swaps_buffers,
        test_step_blinker_oscillator,
        test_step_still_life_block,
        # show_frame
        test_show_frame_alive_cells_use_alive_color,
        test_show_frame_dead_cells_off_by_default,
        test_show_frame_dead_cells_painted_with_dead_color,
        test_show_frame_clear_true_removes_previous_content,
        test_show_frame_mixed_frame,
        test_show_frame_frame_length_larger_than_grid,
        # manifest
        test_zero_player_menu_in_manifest,
        test_conways_life_in_manifest,
        test_zero_player_modes_have_required_fields,
        # main_menu
        test_main_menu_last_rendered_zero_player_tracking,
        test_main_menu_uses_build_menu_items_zero_player,
        test_main_menu_handles_zero_player_state,
        # icons
        test_zero_player_icon_in_icons,
        test_conways_life_icon_in_icons,
        test_zero_player_icon_correct_size,
        test_conways_life_icon_correct_size,
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
    sys.exit(0 if failed == 0 else 1)
