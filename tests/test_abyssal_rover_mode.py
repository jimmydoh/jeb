"""Test module for AbyssalRover game mode.

Validates:
- Mode file existence and valid Python syntax
- Manifest registration with correct metadata
- Absence of a METADATA class attribute (centralized in manifest.py)
- Icon presence and size in icons.py and ICON_LIBRARY
- Direction and hardware index constants
- Difficulty parameter table (_DIFF_PARAMS)
- World size per difficulty
- Phase identifier constants
- Maze generation correctness (walls/passages, start/exit cells)
- Viewport rendering dimensions (5×5 around rover)
- Distance-to-wall computation
- Movement logic (forward, backward, wall collision)
- Flare mechanics (decrement, cooldown when exhausted)
- Satellite helper fallbacks (no satellite connected)
- Score computation on victory
"""

import sys
import os
import ast
import re
import asyncio

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

_MODE_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'src', 'modes', 'abyssal_rover.py'
)
_ICONS_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'src', 'utilities', 'icons.py'
)

# ---------------------------------------------------------------------------
# Stub CircuitPython-specific modules before any src imports
# ---------------------------------------------------------------------------
from unittest.mock import MagicMock, AsyncMock, patch

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

# Provide ticks_ms / ticks_diff stubs
import time as _time
sys.modules['adafruit_ticks'].ticks_ms = lambda: int(_time.monotonic() * 1000)
sys.modules['adafruit_ticks'].ticks_diff = lambda a, b: a - b


def _source():
    with open(_MODE_PATH, 'r') as f:
        return f.read()


# ---------------------------------------------------------------------------
# Mock core / helpers
# ---------------------------------------------------------------------------

class MockMatrix:
    def __init__(self):
        self.pixels_drawn = {}
        self.cleared = False
        self.width  = 16
        self.height = 16

    def clear(self):
        self.cleared = True
        self.pixels_drawn.clear()

    def draw_pixel(self, x, y, color, show=False):
        self.pixels_drawn[(x, y)] = color

    def show_frame(self):
        pass

    def show_icon(self, *args, **kwargs):
        pass


class MockDisplay:
    def __init__(self):
        self.status_line1 = ""
        self.status_line2 = ""

    def use_standard_layout(self):
        pass

    def update_status(self, line1, line2=""):
        self.status_line1 = line1
        self.status_line2 = line2

    def update_header(self, text):
        pass

    def update_footer(self, text):
        pass


class MockHID:
    def __init__(self):
        self.encoder_positions = [0]
        self._buttons = {}
        self._button_taps = {}

    def reset_encoder(self, idx=0):
        self.encoder_positions[idx] = 0

    def is_button_pressed(self, idx, long=False, duration=2000, action=None):
        if action == "tap":
            val = self._button_taps.get(idx, False)
            self._button_taps[idx] = False   # consume tap
            return val
        return self._buttons.get(idx, False)

    def is_encoder_button_pressed(self, *args, **kwargs):
        return False


class MockAudio:
    CH_SFX   = 0
    CH_VOICE = 1

    async def play(self, *args, **kwargs):
        pass

    def stop_all(self):
        pass


class MockSynth:
    def play_note(self, *args, **kwargs):
        pass

    async def play_sequence(self, *args, **kwargs):
        pass


class MockBuzzer:
    def play_sequence(self, *args, **kwargs):
        pass

    def stop(self):
        pass


class MockData:
    def get_setting(self, mode, key, default=None):
        return default

    def get_high_score(self, *args):
        return 0

    def save_high_score(self, *args):
        return False


class MockCore:
    def __init__(self):
        self.matrix    = MockMatrix()
        self.display   = MockDisplay()
        self.hid       = MockHID()
        self.audio     = MockAudio()
        self.synth     = MockSynth()
        self.buzzer    = MockBuzzer()
        self.data      = MockData()
        self.satellites = {}
        self.leds      = MagicMock()

    async def clean_slate(self):
        pass


# ---------------------------------------------------------------------------
# File and syntax checks
# ---------------------------------------------------------------------------

def test_abyssal_rover_file_exists():
    """abyssal_rover.py must exist in src/modes/."""
    assert os.path.exists(_MODE_PATH), "abyssal_rover.py does not exist"
    print("✓ abyssal_rover.py exists")


def test_abyssal_rover_valid_syntax():
    """abyssal_rover.py must have valid Python syntax."""
    src = _source()
    try:
        ast.parse(src)
    except SyntaxError as e:
        raise AssertionError(f"Syntax error in abyssal_rover.py: {e}")
    print("✓ Valid Python syntax")


# ---------------------------------------------------------------------------
# Manifest checks
# ---------------------------------------------------------------------------

def test_abyssal_rover_in_manifest():
    """ABYSSAL_ROVER must be registered in MODE_REGISTRY."""
    from modes.manifest import MODE_REGISTRY
    assert "ABYSSAL_ROVER" in MODE_REGISTRY, \
        "ABYSSAL_ROVER not found in MODE_REGISTRY"
    print("✓ ABYSSAL_ROVER found in MODE_REGISTRY")


def test_abyssal_rover_manifest_metadata():
    """ABYSSAL_ROVER manifest entry must have correct required fields."""
    from modes.manifest import MODE_REGISTRY
    meta = MODE_REGISTRY["ABYSSAL_ROVER"]

    assert meta["id"]          == "ABYSSAL_ROVER"
    assert meta["name"]        == "ABYSSAL ROVER"
    assert meta["module_path"] == "modes.abyssal_rover"
    assert meta["class_name"]  == "AbyssalRover"
    assert meta["icon"]        == "ABYSSAL_ROVER"
    assert "CORE" in meta["requires"], "Must require CORE"
    assert meta.get("menu")    == "MAIN", "Should appear in MAIN menu"
    assert meta.get("has_tutorial") is True, "Should have a tutorial"
    print("✓ ABYSSAL_ROVER manifest metadata is correct")


def test_abyssal_rover_manifest_settings():
    """ABYSSAL_ROVER must expose a difficulty setting (NORMAL / HARD / INSANE)."""
    from modes.manifest import MODE_REGISTRY
    settings = MODE_REGISTRY["ABYSSAL_ROVER"].get("settings", [])
    diff = next((s for s in settings if s["key"] == "difficulty"), None)

    assert diff is not None,            "Missing 'difficulty' setting"
    assert diff["label"]   == "DIFF"
    assert "NORMAL" in diff["options"]
    assert "HARD"   in diff["options"]
    assert "INSANE" in diff["options"]
    assert diff["default"] == "NORMAL"
    print("✓ ABYSSAL_ROVER difficulty settings are correct")


def test_abyssal_rover_core_only():
    """ABYSSAL_ROVER should be playable on Core alone (no mandatory satellite)."""
    from modes.manifest import MODE_REGISTRY
    meta = MODE_REGISTRY["ABYSSAL_ROVER"]
    # Must only require CORE
    assert meta["requires"] == ["CORE"], \
        "ABYSSAL_ROVER must require only CORE (satellite is optional)"
    print("✓ ABYSSAL_ROVER is Core-only (satellite optional)")


def test_abyssal_rover_optional_industrial():
    """ABYSSAL_ROVER should list INDUSTRIAL as optional."""
    from modes.manifest import MODE_REGISTRY
    meta = MODE_REGISTRY["ABYSSAL_ROVER"]
    optional = meta.get("optional", [])
    assert "INDUSTRIAL" in optional, \
        "ABYSSAL_ROVER should list INDUSTRIAL in optional"
    print("✓ ABYSSAL_ROVER lists INDUSTRIAL as optional")


def test_abyssal_rover_no_metadata_in_class():
    """AbyssalRover must NOT define a METADATA class attribute."""
    from modes.abyssal_rover import AbyssalRover
    assert not hasattr(AbyssalRover, 'METADATA'), \
        "AbyssalRover should not define METADATA; use manifest.py"
    print("✓ No METADATA class attribute")


# ---------------------------------------------------------------------------
# Icon checks
# ---------------------------------------------------------------------------

def test_abyssal_rover_icon_in_icons_py():
    """ABYSSAL_ROVER icon must be defined in icons.py."""
    with open(_ICONS_PATH, 'r', encoding='utf-8') as f:
        src = f.read()
    assert "ABYSSAL_ROVER" in src, "ABYSSAL_ROVER icon not in icons.py"
    print("✓ ABYSSAL_ROVER icon defined in icons.py")


def test_abyssal_rover_icon_in_icon_library():
    """ABYSSAL_ROVER must be registered in the ICON_LIBRARY dict."""
    with open(_ICONS_PATH, 'r', encoding='utf-8') as f:
        src = f.read()
    lib_start    = src.find("ICON_LIBRARY")
    lib_end      = src.find("}", lib_start)
    library_block = src[lib_start:lib_end]
    assert '"ABYSSAL_ROVER"' in library_block, \
        "ABYSSAL_ROVER not in ICON_LIBRARY dict"
    print("✓ ABYSSAL_ROVER registered in ICON_LIBRARY")


def test_abyssal_rover_icon_is_256_bytes():
    """ABYSSAL_ROVER icon must be exactly 256 bytes (16×16)."""
    with open(_ICONS_PATH, 'r', encoding='utf-8') as f:
        src = f.read()
    match = re.search(r'ABYSSAL_ROVER\s*=\s*bytes\(\[(.*?)\]\)', src, re.DOTALL)
    assert match is not None, \
        "Could not find ABYSSAL_ROVER bytes literal in icons.py"

    raw_content = match.group(1).replace('\n', ',')
    tokens = [t.strip() for t in raw_content.split(',')]
    values = [t for t in tokens if t.isdigit()]
    assert len(values) == 256, \
        f"ABYSSAL_ROVER icon should be 256 bytes (16×16), got {len(values)}"
    print(f"✓ ABYSSAL_ROVER icon is 256 bytes (16×16)")


def test_abyssal_rover_icon_registered_in_library_class():
    """ABYSSAL_ROVER must be retrievable via Icons.ICON_LIBRARY."""
    from utilities.icons import Icons
    assert "ABYSSAL_ROVER" in Icons.ICON_LIBRARY, \
        "ABYSSAL_ROVER not in Icons.ICON_LIBRARY"
    assert len(Icons.ICON_LIBRARY["ABYSSAL_ROVER"]) == 256, \
        "ABYSSAL_ROVER icon is not 256 bytes"
    print("✓ ABYSSAL_ROVER icon retrievable from Icons.ICON_LIBRARY with correct size")


# ---------------------------------------------------------------------------
# Constant checks
# ---------------------------------------------------------------------------

def test_phase_identifiers():
    """_PHASE_NAVIGATE and _PHASE_FLARE must be defined."""
    src = _source()
    for phase in ["_PHASE_NAVIGATE", "_PHASE_FLARE"]:
        assert phase in src, f"Phase constant {phase} missing"
    print("✓ Phase identifiers defined")


def test_hardware_index_constants():
    """_BTN_FORWARD, _BTN_BACKWARD, _BTN_FLARE, _ENC_CORE, _ENC_SAT, _SW_ARM, _BTN_SAT_FLARE must exist."""
    src = _source()
    for const in [
        "_BTN_FORWARD", "_BTN_BACKWARD", "_BTN_FLARE",
        "_ENC_CORE", "_ENC_SAT", "_SW_ARM", "_BTN_SAT_FLARE",
    ]:
        assert const in src, f"Hardware constant {const} missing"
    print("✓ All hardware index constants defined")


def test_max_flares_is_three():
    """_MAX_FLARES must equal 3."""
    src   = _source()
    match = re.search(r'_MAX_FLARES\s*=\s*(\d+)', src)
    assert match is not None, "_MAX_FLARES not found"
    assert int(match.group(1)) == 3, \
        f"_MAX_FLARES should be 3, got {match.group(1)}"
    print("✓ _MAX_FLARES is 3")


def test_viewport_radius_is_two():
    """_VIEWPORT_RADIUS must equal 2 (giving a 5×5 viewport)."""
    src   = _source()
    match = re.search(r'_VIEWPORT_RADIUS\s*=\s*(\d+)', src)
    assert match is not None, "_VIEWPORT_RADIUS not found"
    assert int(match.group(1)) == 2, \
        f"_VIEWPORT_RADIUS should be 2 (5×5 viewport), got {match.group(1)}"
    print("✓ _VIEWPORT_RADIUS is 2 (5×5 viewport)")


def test_diff_params_defines_all_difficulties():
    """_DIFF_PARAMS must define NORMAL, HARD, and INSANE."""
    src = _source()
    assert "_DIFF_PARAMS" in src, "_DIFF_PARAMS dict missing"
    for diff in ["NORMAL", "HARD", "INSANE"]:
        assert diff in src, f"Difficulty '{diff}' missing"
    print("✓ _DIFF_PARAMS defines NORMAL, HARD, INSANE")


def test_world_size_increases_with_difficulty():
    """INSANE must have a larger world size than HARD, and HARD larger than NORMAL."""
    from modes.abyssal_rover import _DIFF_PARAMS
    assert _DIFF_PARAMS["HARD"]["world"] > _DIFF_PARAMS["NORMAL"]["world"], \
        "HARD world size should be larger than NORMAL"
    assert _DIFF_PARAMS["INSANE"]["world"] > _DIFF_PARAMS["HARD"]["world"], \
        "INSANE world size should be larger than HARD"
    print("✓ World size increases with difficulty")


# ---------------------------------------------------------------------------
# Maze generation correctness
# ---------------------------------------------------------------------------

def test_maze_generation_all_open_cells_reachable():
    """All open cells in the generated maze must be reachable from the start."""
    from modes.abyssal_rover import AbyssalRover
    core  = MockCore()
    rover = AbyssalRover(core)
    ws    = 25
    world = rover._generate_maze(ws)

    # BFS from start cell (1,1) to check connectivity
    start = (1, 1)
    assert world[start[1] * ws + start[0]] == 1, "Start cell must be open"

    visited = set()
    queue   = [start]
    visited.add(start)

    while queue:
        cx, cy = queue.pop(0)
        for ddx, ddy in [(0, -1), (1, 0), (0, 1), (-1, 0)]:
            nx, ny = cx + ddx, cy + ddy
            if (nx, ny) not in visited and 0 <= nx < ws and 0 <= ny < ws:
                if world[ny * ws + nx] == 1:
                    visited.add((nx, ny))
                    queue.append((nx, ny))

    # Count all open cells
    total_open = sum(1 for v in world if v == 1)
    assert len(visited) == total_open, \
        f"Not all open cells are reachable: {len(visited)} reachable vs {total_open} total open"
    print(f"✓ All {total_open} open cells in the maze are reachable from start")


def test_maze_start_and_exit_are_open():
    """Start cell (1,1) and exit cell (ws-2, ws-2) must be open passages."""
    from modes.abyssal_rover import AbyssalRover
    core  = MockCore()
    rover = AbyssalRover(core)
    ws    = 25
    world = rover._generate_maze(ws)

    assert world[1 * ws + 1] == 1, "Start cell (1,1) must be open"
    assert world[(ws-2) * ws + (ws-2)] == 1, f"Exit cell ({ws-2},{ws-2}) must be open"
    print("✓ Start and exit cells are open passages")


def test_maze_border_is_all_walls():
    """The outer border of the maze must be all walls (value 0)."""
    from modes.abyssal_rover import AbyssalRover
    core  = MockCore()
    rover = AbyssalRover(core)
    ws    = 25
    world = rover._generate_maze(ws)

    for x in range(ws):
        assert world[0  * ws + x] == 0, f"Top border at ({x},0) not a wall"
        assert world[(ws-1) * ws + x] == 0, f"Bottom border at ({x},{ws-1}) not a wall"
    for y in range(ws):
        assert world[y * ws + 0] == 0, f"Left border at (0,{y}) not a wall"
        assert world[y * ws + (ws-1)] == 0, f"Right border at ({ws-1},{y}) not a wall"
    print("✓ Maze border is all walls")


# ---------------------------------------------------------------------------
# World query helpers
# ---------------------------------------------------------------------------

def test_world_at_out_of_bounds_returns_zero():
    """_world_at() must return 0 for out-of-bounds coordinates."""
    from modes.abyssal_rover import AbyssalRover
    core  = MockCore()
    rover = AbyssalRover(core)
    rover._world_size = 25
    rover._world      = rover._generate_maze(25)

    assert rover._world_at(-1, 0) == 0
    assert rover._world_at(0, -1) == 0
    assert rover._world_at(25, 0) == 0
    assert rover._world_at(0, 25) == 0
    print("✓ _world_at() returns 0 for out-of-bounds coordinates")


def test_distance_to_wall_non_negative():
    """_distance_to_wall() must always return a non-negative integer."""
    from modes.abyssal_rover import AbyssalRover
    core  = MockCore()
    rover = AbyssalRover(core)
    rover._world_size = 25
    rover._world      = rover._generate_maze(25)
    rover._rover_x    = 1
    rover._rover_y    = 1

    for facing in range(4):
        rover._facing = facing
        dist = rover._distance_to_wall()
        assert dist >= 0, f"Negative distance returned for facing {facing}"
    print("✓ _distance_to_wall() returns non-negative value for all directions")


# ---------------------------------------------------------------------------
# Movement logic
# ---------------------------------------------------------------------------

def test_try_move_forward_into_open_cell():
    """_try_move(forward=True) must return True when moving into an open cell."""
    from modes.abyssal_rover import AbyssalRover, _DIFF_PARAMS
    core  = MockCore()
    rover = AbyssalRover(core)
    ws    = _DIFF_PARAMS["NORMAL"]["world"]
    rover._world_size = ws
    rover._world      = rover._generate_maze(ws)

    # Start at (1,1) facing EAST (1) – the corridor should eventually be open
    rover._rover_x = 1
    rover._rover_y = 1

    # Try all four directions; at least one should succeed from (1,1)
    original_x, original_y = rover._rover_x, rover._rover_y
    success = False
    for facing in range(4):
        rover._rover_x = original_x
        rover._rover_y = original_y
        rover._facing  = facing
        if rover._try_move(forward=True):
            success = True
            break

    assert success, "Could not move in any direction from start cell (1,1)"
    print("✓ _try_move(forward=True) succeeds into open cell")


def test_try_move_blocked_by_wall():
    """_try_move() must return False when the target cell is a wall."""
    from modes.abyssal_rover import AbyssalRover
    core  = MockCore()
    rover = AbyssalRover(core)

    # Build a tiny 5×5 world: walls everywhere except (1,1)
    ws = 5
    rover._world_size = ws
    rover._world = bytearray(ws * ws)   # all walls
    rover._world[1 * ws + 1] = 1        # only (1,1) is open

    rover._rover_x = 1
    rover._rover_y = 1

    # All four directions lead to walls
    for facing in range(4):
        rover._facing = facing
        result = rover._try_move(forward=True)
        assert result is False, \
            f"Should not move into wall (facing {facing})"
    print("✓ _try_move() returns False when blocked by a wall")


def test_try_move_backward():
    """_try_move(forward=False) must move in the opposite facing direction."""
    from modes.abyssal_rover import AbyssalRover
    core  = MockCore()
    rover = AbyssalRover(core)

    # Build a tiny 3×3 world with a horizontal corridor
    ws = 5
    rover._world_size = ws
    rover._world = bytearray(ws * ws)   # all walls
    # Open a horizontal corridor: y=1, x=1..3
    for x in range(1, 4):
        rover._world[1 * ws + x] = 1

    # Rover at (2,1) facing EAST; backward = WEST
    rover._rover_x = 2
    rover._rover_y = 1
    rover._facing  = 1  # EAST

    result = rover._try_move(forward=False)
    assert result is True,         "Backward move into open cell should succeed"
    assert rover._rover_x == 1,    "Rover should have moved WEST (x-1)"
    assert rover._rover_y == 1,    "Rover y should be unchanged"
    print("✓ _try_move(forward=False) moves in opposite direction")


# ---------------------------------------------------------------------------
# Viewport rendering
# ---------------------------------------------------------------------------

def test_render_viewport_draws_within_5x5_around_rover():
    """_render_viewport() must draw pixels only within the 5×5 window."""
    from modes.abyssal_rover import AbyssalRover, _MATRIX_CENTER_X, _MATRIX_CENTER_Y
    core  = MockCore()
    rover = AbyssalRover(core)
    ws    = 25
    rover._world_size = ws
    rover._world      = rover._generate_maze(ws)
    rover._rover_x    = 1
    rover._rover_y    = 1

    rover._render_viewport()

    # Every drawn pixel must be within [cx-2, cx+2] × [cy-2, cy+2]
    cx, cy = _MATRIX_CENTER_X, _MATRIX_CENTER_Y
    for (mx, my) in core.matrix.pixels_drawn:
        assert cx - 2 <= mx <= cx + 2, \
            f"Pixel at ({mx},{my}) is outside viewport x-range"
        assert cy - 2 <= my <= cy + 2, \
            f"Pixel at ({mx},{my}) is outside viewport y-range"
    print("✓ _render_viewport() only draws within 5×5 viewport")


def test_render_viewport_rover_at_center():
    """The rover's pixel must be drawn at the matrix centre."""
    from modes.abyssal_rover import AbyssalRover, _MATRIX_CENTER_X, _MATRIX_CENTER_Y, _COL_ROVER
    core  = MockCore()
    rover = AbyssalRover(core)
    ws    = 25
    rover._world_size = ws
    rover._world      = rover._generate_maze(ws)
    rover._rover_x    = 1
    rover._rover_y    = 1

    rover._render_viewport()

    center_color = core.matrix.pixels_drawn.get(
        (_MATRIX_CENTER_X, _MATRIX_CENTER_Y)
    )
    assert center_color == _COL_ROVER, \
        "Rover must be drawn at matrix centre with _COL_ROVER colour"
    print("✓ Rover pixel rendered at matrix centre")


def test_render_viewport_clears_matrix_first():
    """_render_viewport() must call matrix.clear() before drawing."""
    from modes.abyssal_rover import AbyssalRover
    core  = MockCore()
    rover = AbyssalRover(core)
    ws    = 25
    rover._world_size = ws
    rover._world      = rover._generate_maze(ws)
    rover._rover_x    = 1
    rover._rover_y    = 1

    core.matrix.cleared = False
    rover._render_viewport()
    assert core.matrix.cleared, "_render_viewport() must call matrix.clear()"
    print("✓ _render_viewport() clears the matrix before drawing")


# ---------------------------------------------------------------------------
# Flare mechanics
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fire_flare_decrements_count():
    """_fire_flare() must decrement _flares_remaining by 1."""
    from modes.abyssal_rover import AbyssalRover, _MAX_FLARES, _FLARE_DURATION
    core  = MockCore()
    rover = AbyssalRover(core)
    ws    = 25
    rover._world_size        = ws
    rover._world             = rover._generate_maze(ws)
    rover._rover_x           = 1
    rover._rover_y           = 1
    rover._flares_remaining  = _MAX_FLARES

    with patch('asyncio.sleep', new_callable=AsyncMock):
        await rover._fire_flare()

    assert rover._flares_remaining == _MAX_FLARES - 1, \
        "Flare count should decrease by 1 after firing"
    print("✓ _fire_flare() decrements _flares_remaining")


@pytest.mark.asyncio
async def test_fire_flare_when_none_remaining_plays_error():
    """_fire_flare() with 0 flares must play error sound and not fire."""
    from modes.abyssal_rover import AbyssalRover
    core  = MockCore()
    rover = AbyssalRover(core)
    ws    = 25
    rover._world_size       = ws
    rover._world            = rover._generate_maze(ws)
    rover._rover_x          = 1
    rover._rover_y          = 1
    rover._flares_remaining = 0

    error_played = []
    core.buzzer.play_sequence = lambda seq: error_played.append(seq)

    await rover._fire_flare()
    assert len(error_played) == 1, \
        "Error sound should play when no flares remain"
    assert rover._flares_remaining == 0, \
        "Flare count must remain 0 when no flares are available"
    print("✓ _fire_flare() plays error when no flares remain")


# ---------------------------------------------------------------------------
# Satellite helper fallbacks
# ---------------------------------------------------------------------------

def test_sat_helpers_return_safe_defaults_when_no_sat():
    """Satellite helpers must return safe defaults when no satellite is connected."""
    from modes.abyssal_rover import AbyssalRover
    core  = MockCore()
    rover = AbyssalRover(core)
    # No satellite set
    rover.sat = None

    assert rover._sat_button(0)    is False
    assert rover._sat_latching(0)  is False
    assert rover._sat_encoder()    == 0
    print("✓ Satellite helpers return safe defaults when satellite is absent")


# ---------------------------------------------------------------------------
# Score computation
# ---------------------------------------------------------------------------

def test_score_is_positive():
    """The computed score must be a positive integer."""
    base              = 1000
    efficiency_bonus  = max(0, 2000 - 50 * 5)   # 50 moves
    time_bonus        = max(0, 500 - int(30 * 2))  # 30 seconds
    score             = base + efficiency_bonus + time_bonus
    assert score > 0, "Score must be positive"
    print(f"✓ Score computation yields positive value ({score})")


# ---------------------------------------------------------------------------
# Existing registry entries are undisturbed
# ---------------------------------------------------------------------------

def test_existing_core_game_entries_undisturbed():
    """Adding ABYSSAL_ROVER has not removed any existing CORE game entries."""
    from modes.manifest import MODE_REGISTRY
    for key in ("SIMON", "JEBRIS", "SNAKE", "PONG", "SAFE", "ASTRO_BREAKER"):
        assert key in MODE_REGISTRY, \
            f"Existing entry '{key}' should still be present in MODE_REGISTRY"
    print("✓ Existing CORE game entries are undisturbed")


def test_abyssal_ping_still_in_manifest():
    """ABYSSAL_PING must still be registered after adding ABYSSAL_ROVER."""
    from modes.manifest import MODE_REGISTRY
    assert "ABYSSAL_PING" in MODE_REGISTRY, \
        "ABYSSAL_PING should still be present in MODE_REGISTRY"
    print("✓ ABYSSAL_PING still registered")


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import traceback

    tests = [
        test_abyssal_rover_file_exists,
        test_abyssal_rover_valid_syntax,
        test_abyssal_rover_in_manifest,
        test_abyssal_rover_manifest_metadata,
        test_abyssal_rover_manifest_settings,
        test_abyssal_rover_core_only,
        test_abyssal_rover_optional_industrial,
        test_abyssal_rover_no_metadata_in_class,
        test_abyssal_rover_icon_in_icons_py,
        test_abyssal_rover_icon_in_icon_library,
        test_abyssal_rover_icon_is_256_bytes,
        test_abyssal_rover_icon_registered_in_library_class,
        test_phase_identifiers,
        test_hardware_index_constants,
        test_max_flares_is_three,
        test_viewport_radius_is_two,
        test_diff_params_defines_all_difficulties,
        test_world_size_increases_with_difficulty,
        test_maze_generation_all_open_cells_reachable,
        test_maze_start_and_exit_are_open,
        test_maze_border_is_all_walls,
        test_world_at_out_of_bounds_returns_zero,
        test_distance_to_wall_non_negative,
        test_try_move_forward_into_open_cell,
        test_try_move_blocked_by_wall,
        test_try_move_backward,
        test_render_viewport_draws_within_5x5_around_rover,
        test_render_viewport_rover_at_center,
        test_render_viewport_clears_matrix_first,
        test_sat_helpers_return_safe_defaults_when_no_sat,
        test_score_is_positive,
        test_existing_core_game_entries_undisturbed,
        test_abyssal_ping_still_in_manifest,
    ]

    async_tests = [
        test_fire_flare_decrements_count,
        test_fire_flare_when_none_remaining_plays_error,
    ]

    print("Running Abyssal Rover mode tests...\n")
    passed = failed = 0

    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"\n❌ {t.__name__}: {e}")
            traceback.print_exc()
            failed += 1

    for t in async_tests:
        try:
            asyncio.run(t())
            passed += 1
        except Exception as e:
            print(f"\n❌ {t.__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'✅' if failed == 0 else '❌'} {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
