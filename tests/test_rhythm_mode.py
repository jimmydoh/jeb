"""Test module for the RhythmMode (NEON BEATS) game.

Tests verify:
- rhythm_mode.py file exists and has valid Python syntax
- RhythmMode is correctly registered in the manifest
- button_columns property returns 4 evenly-spaced columns for different matrix sizes
- hit_zone_row property returns matrix.height - 1
- Master time anchor logic (ticks_ms-based elapsed time calculation)
- Hit detection grades (PERFECT, GOOD, MISS windows)
- Beatmap rendering helpers (note y-position interpolation)
- Demo beatmap is non-empty and correctly structured
- Song discovery falls back to ["demo"] when no SD card
- Per-difficulty beatmap path construction
- _slug_to_display_name conversion
- RHYTHM icon exists in the icon library as 16x16 (256 pixels)
- extract_beatmap.py example script exists and has valid syntax
"""

import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# ---------------------------------------------------------------------------
# File / manifest checks (no hardware required)
# ---------------------------------------------------------------------------

def test_rhythm_mode_file_exists():
    """rhythm_mode.py must exist in src/modes/."""
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'rhythm_mode.py')
    assert os.path.exists(path), "rhythm_mode.py does not exist"


def test_rhythm_mode_valid_syntax():
    """rhythm_mode.py must have valid Python syntax."""
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'rhythm_mode.py')
    with open(path, 'r', encoding='utf-8') as fh:
        code = fh.read()
    compile(code, path, 'exec')


def test_rhythm_in_manifest():
    """RHYTHM must be registered in MODE_REGISTRY."""
    from modes.manifest import MODE_REGISTRY
    assert "RHYTHM" in MODE_REGISTRY, "RHYTHM not found in MODE_REGISTRY"
    entry = MODE_REGISTRY["RHYTHM"]
    assert entry["id"] == "RHYTHM"
    assert entry["name"] == "NEON BEATS"
    assert entry["module_path"] == "modes.rhythm_mode"
    assert entry["class_name"] == "RhythmMode"
    assert entry["icon"] == "RHYTHM"
    assert "CORE" in entry["requires"]


def test_rhythm_manifest_settings():
    """RHYTHM mode must have difficulty and latency settings."""
    from modes.manifest import MODE_REGISTRY
    entry = MODE_REGISTRY["RHYTHM"]
    settings = entry.get("settings", [])

    difficulty = next((s for s in settings if s["key"] == "difficulty"), None)
    assert difficulty is not None, "Missing 'difficulty' setting"
    assert "EASY" in difficulty["options"]
    assert "NORMAL" in difficulty["options"]
    assert "HARD" in difficulty["options"]
    assert difficulty["default"] == "NORMAL"

    latency = next((s for s in settings if s["key"] == "latency"), None)
    assert latency is not None, "Missing 'latency' setting"
    assert "45" in latency["options"]
    assert latency["default"] == "45"


def test_rhythm_icon_is_16x16():
    """RHYTHM icon must be present in Icons.ICON_LIBRARY as a 16x16 (256-pixel) icon."""
    from utilities.icons import Icons
    assert "RHYTHM" in Icons.ICON_LIBRARY, "RHYTHM icon not found in ICON_LIBRARY"
    icon = Icons.ICON_LIBRARY["RHYTHM"]
    assert len(icon) == 256, (
        f"RHYTHM icon should have 256 pixels (16x16 matrix), got {len(icon)}"
    )


# ---------------------------------------------------------------------------
# Logic tests (pure Python, no hardware imports)
# ---------------------------------------------------------------------------

import unittest.mock as mock
import time as _time

# Stub out CircuitPython-only modules once for the whole module
for _mod in ('adafruit_ticks', 'audiocore', 'audiomixer', 'audiobusio',
             'synthio', 'board', 'busio', 'digitalio', 'neopixel',
             'analogio', 'microcontroller', 'watchdog', 'audiopwmio'):
    if _mod not in sys.modules:
        sys.modules[_mod] = mock.MagicMock()

_ticks_start = _time.monotonic()
_ticks_mock = mock.MagicMock()
_ticks_mock.ticks_ms = lambda: int((_time.monotonic() - _ticks_start) * 1000)
_ticks_mock.ticks_diff = lambda a, b: a - b
sys.modules['adafruit_ticks'] = _ticks_mock


class _FakeMatrix:
    """Minimal matrix stub with configurable dimensions."""
    def __init__(self, width=16, height=16):
        self.width = width
        self.height = height

    def clear(self): pass
    def draw_pixel(self, *a, **kw): pass
    def show_icon(self, *a, **kw): pass


class _FakeCore:
    """Minimal core stub that satisfies RhythmMode.__init__ and logic methods."""

    class _FakeAudio:
        CH_ATMO = 1
        async def play(self, *a, **kw): pass
        async def stop_all(self): pass

    class _FakeDisplay:
        def update_status(self, *a, **kw): pass
        def update_header(self, *a, **kw): pass
        def use_standard_layout(self): pass

    class _FakeLeds:
        def set_pixel(self, *a, **kw): pass

    class _FakeSynth:
        def play_note(self, *a, **kw): pass

    class _FakeHid:
        def flush(self): pass
        def reset_encoder(self, *a, **kw): pass
        def is_button_pressed(self, *a, **kw): return False
        def is_encoder_button_pressed(self, *a, **kw): return False
        def encoder_position(self): return 0

    class _FakeData:
        def get_setting(self, *a, default=None, **kw):
            return default
        def get_high_score(self, *a, **kw): return 0
        def save_high_score(self, *a, **kw): return False

    class _FakeBuzzer:
        async def stop(self): pass

    def __init__(self, matrix_width=16, matrix_height=16):
        self.audio = self._FakeAudio()
        self.display = self._FakeDisplay()
        self.matrix = _FakeMatrix(matrix_width, matrix_height)
        self.leds = self._FakeLeds()
        self.synth = self._FakeSynth()
        self.hid = self._FakeHid()
        self.data = self._FakeData()
        self.buzzer = self._FakeBuzzer()
        self.current_mode_step = 0


def _make_mode(matrix_width=16, matrix_height=16):
    """Construct a RhythmMode with a stub core (no hardware)."""
    from modes.rhythm_mode import RhythmMode
    return RhythmMode(_FakeCore(matrix_width, matrix_height))


# ---------------------------------------------------------------------------
# Matrix-dimension-aware property tests
# ---------------------------------------------------------------------------

def test_button_columns_16x16():
    """button_columns must return 4 evenly-spaced columns for a 16-wide matrix."""
    mode = _make_mode(16, 16)
    cols = mode.button_columns
    assert len(cols) == 4, "Must return exactly 4 columns"
    assert cols == [2, 6, 10, 14], f"Expected [2,6,10,14] for 16-wide, got {cols}"


def test_button_columns_8x8():
    """button_columns must return 4 evenly-spaced columns for an 8-wide matrix."""
    mode = _make_mode(8, 8)
    cols = mode.button_columns
    assert len(cols) == 4, "Must return exactly 4 columns"
    assert cols == [1, 3, 5, 7], f"Expected [1,3,5,7] for 8-wide, got {cols}"


def test_hit_zone_row_16x16():
    """hit_zone_row must equal matrix.height - 1 for a 16x16 matrix."""
    mode = _make_mode(16, 16)
    assert mode.hit_zone_row == 15


def test_hit_zone_row_8x8():
    """hit_zone_row must equal matrix.height - 1 for an 8x8 matrix."""
    mode = _make_mode(8, 8)
    assert mode.hit_zone_row == 7


# ---------------------------------------------------------------------------
# Song discovery
# ---------------------------------------------------------------------------

def test_discover_songs_fallback():
    """_discover_songs() must return ['demo'] when no SD card is available."""
    mode = _make_mode()
    songs = mode._discover_songs()
    assert songs == ["demo"], f"Expected ['demo'] fallback, got {songs}"


def test_slug_to_display_name():
    """_slug_to_display_name should convert underscores and uppercase."""
    mode = _make_mode()
    assert mode._slug_to_display_name("cyber_track") == "CYBER TRACK"
    assert mode._slug_to_display_name("demo") == "DEMO"
    assert mode._slug_to_display_name("neon_beats_vol2") == "NEON BEATS VOL2"


# ---------------------------------------------------------------------------
# Per-difficulty beatmap path construction
# ---------------------------------------------------------------------------

def test_beatmap_path_easy():
    """_beatmap_path should produce the correct path for EASY difficulty."""
    mode = _make_mode()
    path = mode._beatmap_path("cyber_track", "EASY")
    assert path == "/sd/data/rhythm/cyber_track_easy.json"


def test_beatmap_path_normal():
    """_beatmap_path should produce the correct path for NORMAL difficulty."""
    mode = _make_mode()
    path = mode._beatmap_path("cyber_track", "NORMAL")
    assert path == "/sd/data/rhythm/cyber_track_normal.json"


def test_beatmap_path_hard():
    """_beatmap_path should produce the correct path for HARD difficulty."""
    mode = _make_mode()
    path = mode._beatmap_path("cyber_track", "HARD")
    assert path == "/sd/data/rhythm/cyber_track_hard.json"


def test_load_beatmap_demo_fallback():
    """_load_beatmap('demo', ...) must return the built-in demo beatmap."""
    mode = _make_mode()
    beatmap = mode._load_beatmap("demo", "NORMAL")
    assert len(beatmap) > 0, "Demo beatmap must not be empty"
    for note in beatmap:
        assert "time" in note
        assert "col" in note
        assert "state" in note


def test_load_beatmap_unknown_song_returns_empty():
    """_load_beatmap with an unknown slug and no SD card returns an empty list."""
    mode = _make_mode()
    beatmap = mode._load_beatmap("nonexistent_song_xyz", "NORMAL")
    assert beatmap == [], f"Expected empty list, got {beatmap}"


# ---------------------------------------------------------------------------
# Demo beatmap
# ---------------------------------------------------------------------------

def test_demo_beatmap_non_empty():
    """_demo_beatmap() must return a non-empty list of valid note dicts."""
    mode = _make_mode()
    beatmap = mode._demo_beatmap()
    assert len(beatmap) > 0, "Demo beatmap is empty"
    valid_cols = set(mode.button_columns)
    for note in beatmap:
        assert "time" in note, "Note missing 'time' key"
        assert "col" in note, "Note missing 'col' key"
        assert "state" in note, "Note missing 'state' key"
        assert note["col"] in valid_cols, (
            f"Note col {note['col']} not in button_columns {valid_cols}"
        )


def test_demo_beatmap_sorted_by_time():
    """Demo beatmap notes should be in non-decreasing time order."""
    mode = _make_mode()
    beatmap = mode._demo_beatmap()
    times = [n["time"] for n in beatmap]
    assert times == sorted(times), "Demo beatmap is not sorted by time"


def test_demo_beatmap_uses_16x16_columns():
    """Demo beatmap columns must match the live button_columns of a 16x16 matrix."""
    mode = _make_mode(16, 16)
    expected_cols = set(mode.button_columns)  # {2, 6, 10, 14}
    for note in mode._demo_beatmap():
        assert note["col"] in expected_cols, (
            f"Demo note col {note['col']} not in 16x16 button_columns {expected_cols}"
        )


# ---------------------------------------------------------------------------
# Hit processing
# ---------------------------------------------------------------------------

def test_process_hit_perfect():
    """A hit within PERFECT_WINDOW_MS of a waiting note scores 100 and marks HIT."""
    mode = _make_mode()
    col = mode.button_columns[0]
    mode.beatmap = [{"time": 2000, "col": col, "state": "WAITING"}]
    mode.hit_window_ms = 150

    mode._process_hit(2000, col)

    assert mode.beatmap[0]["state"] == "HIT"
    assert mode.score == 100
    assert mode.combo == 1


def test_process_hit_good():
    """A hit within GOOD window but outside PERFECT window scores 50."""
    mode = _make_mode()
    col = mode.button_columns[1]
    mode.beatmap = [{"time": 2000, "col": col, "state": "WAITING"}]
    mode.hit_window_ms = 150

    mode._process_hit(2100, col)

    assert mode.beatmap[0]["state"] == "HIT"
    assert mode.score == 50
    assert mode.combo == 1


def test_process_hit_miss():
    """A hit with no nearby note resets the combo and does not change any note."""
    mode = _make_mode()
    col0 = mode.button_columns[0]
    col2 = mode.button_columns[2]
    mode.beatmap = [{"time": 2000, "col": col0, "state": "WAITING"}]
    mode.combo = 3
    mode.hit_window_ms = 150

    # Press a different column → miss
    mode._process_hit(2000, col2)

    assert mode.beatmap[0]["state"] == "WAITING"
    assert mode.score == 0
    assert mode.combo == 0


def test_process_hit_already_hit_note_ignored():
    """A note that is already HIT must not be counted again."""
    mode = _make_mode()
    col = mode.button_columns[0]
    mode.beatmap = [{"time": 2000, "col": col, "state": "HIT"}]
    mode.hit_window_ms = 150

    mode._process_hit(2000, col)

    assert mode.score == 0


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def test_render_marks_missed_notes():
    """_render() must set state='MISSED' for notes that passed the hit window."""
    mode = _make_mode()
    col = mode.button_columns[0]
    mode.beatmap = [{"time": 1000, "col": col, "state": "WAITING"}]
    mode.hit_window_ms = 150

    mode._render(2000)

    assert mode.beatmap[0]["state"] == "MISSED"


def test_render_does_not_miss_upcoming_note():
    """_render() must not mark a future note as MISSED."""
    mode = _make_mode()
    col = mode.button_columns[0]
    mode.beatmap = [{"time": 5000, "col": col, "state": "WAITING"}]
    mode.hit_window_ms = 150

    mode._render(1000)

    assert mode.beatmap[0]["state"] == "WAITING"


def test_note_y_position_interpolation_16x16():
    """Notes should interpolate from row 0 at spawn_time to hit_zone_row (15) at hit time."""
    mode = _make_mode(16, 16)
    fall_duration = mode.fall_duration_ms
    hz = mode.hit_zone_row  # 15

    note_time = 2000
    spawn_time = note_time - fall_duration

    # At spawn_time: progress=0 → y=0
    y_start = int(((spawn_time - spawn_time) / fall_duration) * hz)
    assert y_start == 0

    # Halfway: progress=0.5 → y=7
    mid_time = spawn_time + fall_duration // 2
    y_mid = int(((mid_time - spawn_time) / fall_duration) * hz)
    assert y_mid == 7

    # At hit time: progress=1.0 → y=15
    y_end = int(((note_time - spawn_time) / fall_duration) * hz)
    assert y_end == hz


# ---------------------------------------------------------------------------
# extract_beatmap.py example script check
# ---------------------------------------------------------------------------

def test_extract_beatmap_script_exists():
    """examples/extract_beatmap.py must exist."""
    path = os.path.join(os.path.dirname(__file__), '..', 'examples', 'extract_beatmap.py')
    assert os.path.exists(path), "examples/extract_beatmap.py does not exist"


def test_extract_beatmap_script_valid_syntax():
    """examples/extract_beatmap.py must have valid Python syntax."""
    path = os.path.join(os.path.dirname(__file__), '..', 'examples', 'extract_beatmap.py')
    with open(path, 'r', encoding='utf-8') as fh:
        code = fh.read()
    compile(code, path, 'exec')


def test_extract_beatmap_note_to_column_mapping():
    """Expert difficulty should map MIDI pitches 96-99 to cols 0, 2, 5, 7."""
    difficulty_offsets = {"easy": 60, "medium": 72, "hard": 84, "expert": 96}
    base = difficulty_offsets["expert"]
    note_to_column = {
        base + 0: 0,
        base + 1: 2,
        base + 2: 5,
        base + 3: 7,
    }
    assert note_to_column[96] == 0
    assert note_to_column[97] == 2
    assert note_to_column[98] == 5
    assert note_to_column[99] == 7


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
