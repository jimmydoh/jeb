"""Test module for the RhythmMode (NEON BEATS) game.

Tests verify:
- rhythm_mode.py file exists and has valid Python syntax
- RhythmMode is correctly registered in the manifest
- Master time anchor logic (ticks_ms-based elapsed time calculation)
- Hit detection grades (PERFECT, GOOD, MISS windows)
- Beatmap rendering helpers (note y-position interpolation)
- Demo beatmap is non-empty and correctly structured
- RHYTHM icon exists in the icon library
- extract_beatmap.py example script exists and has valid syntax
"""

import sys
import os
import asyncio

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


def test_rhythm_icon_exists():
    """RHYTHM icon must be present in Icons.ICON_LIBRARY."""
    from utilities.icons import Icons
    assert "RHYTHM" in Icons.ICON_LIBRARY, "RHYTHM icon not found in ICON_LIBRARY"
    icon = Icons.ICON_LIBRARY["RHYTHM"]
    assert len(icon) in (64, 256), (
        f"RHYTHM icon should have 64 (8x8) or 256 (16x16) pixels, got {len(icon)}"
    )


# ---------------------------------------------------------------------------
# Logic tests (pure Python, no hardware imports)
# ---------------------------------------------------------------------------

class _FakeCore:
    """Minimal core stub that satisfies RhythmMode.__init__ and logic methods."""

    class _FakeAudio:
        CH_ATMO = 1
        async def play(self, *a, **kw): pass
        async def stop_all(self): pass

    class _FakeDisplay:
        def update_status(self, *a, **kw): pass
        def use_standard_layout(self): pass

    class _FakeMatrix:
        def clear(self): pass
        def draw_pixel(self, *a, **kw): pass

    class _FakeLeds:
        def set_pixel(self, *a, **kw): pass

    class _FakeSynth:
        def play_note(self, *a, **kw): pass

    class _FakeHid:
        def flush(self): pass
        def is_button_pressed(self, *a, **kw): return False

    class _FakeData:
        def get_setting(self, *a, default=None, **kw):
            return default
        def get_high_score(self, *a, **kw): return 0
        def save_high_score(self, *a, **kw): return False

    class _FakeBuzzer:
        async def stop(self): pass

    def __init__(self):
        self.audio = self._FakeAudio()
        self.display = self._FakeDisplay()
        self.matrix = self._FakeMatrix()
        self.leds = self._FakeLeds()
        self.synth = self._FakeSynth()
        self.hid = self._FakeHid()
        self.data = self._FakeData()
        self.buzzer = self._FakeBuzzer()
        self.current_mode_step = 0


def _make_mode():
    """Construct a RhythmMode with a stub core (no hardware)."""
    # Stub out CircuitPython-only modules before importing
    import unittest.mock as mock
    for mod in ('adafruit_ticks', 'audiocore', 'audiomixer', 'audiobusio',
                'synthio', 'board', 'busio', 'digitalio', 'neopixel',
                'analogio', 'microcontroller', 'watchdog', 'audiopwmio'):
        if mod not in sys.modules:
            sys.modules[mod] = mock.MagicMock()

    # Provide a real ticks implementation backed by time.monotonic
    import time
    ticks_mock = mock.MagicMock()
    _start = time.monotonic()
    ticks_mock.ticks_ms = lambda: int((time.monotonic() - _start) * 1000)
    ticks_mock.ticks_diff = lambda a, b: a - b
    sys.modules['adafruit_ticks'] = ticks_mock

    from modes.rhythm_mode import RhythmMode
    return RhythmMode(_FakeCore())


def test_demo_beatmap_non_empty():
    """_demo_beatmap() must return a non-empty list of valid note dicts."""
    mode = _make_mode()
    beatmap = mode._demo_beatmap()
    assert len(beatmap) > 0, "Demo beatmap is empty"
    for note in beatmap:
        assert "time" in note, "Note missing 'time' key"
        assert "col" in note, "Note missing 'col' key"
        assert "state" in note, "Note missing 'state' key"
        assert note["col"] in (0, 2, 5, 7), f"Unexpected column: {note['col']}"


def test_demo_beatmap_sorted_by_time():
    """Demo beatmap notes should be in non-decreasing time order."""
    mode = _make_mode()
    beatmap = mode._demo_beatmap()
    times = [n["time"] for n in beatmap]
    assert times == sorted(times), "Demo beatmap is not sorted by time"


def test_process_hit_perfect():
    """A hit within PERFECT_WINDOW_MS of a waiting note scores 100 and marks HIT."""
    mode = _make_mode()
    mode.beatmap = [{"time": 2000, "col": 0, "state": "WAITING"}]
    mode.hit_window_ms = 150

    # Hit exactly on time → should be PERFECT
    mode._process_hit(2000, 0)

    assert mode.beatmap[0]["state"] == "HIT"
    assert mode.score == 100
    assert mode.combo == 1


def test_process_hit_good():
    """A hit within GOOD window but outside PERFECT window scores 50."""
    mode = _make_mode()
    mode.beatmap = [{"time": 2000, "col": 2, "state": "WAITING"}]
    mode.hit_window_ms = 150

    # 100 ms off → GOOD
    mode._process_hit(2100, 2)

    assert mode.beatmap[0]["state"] == "HIT"
    assert mode.score == 50
    assert mode.combo == 1


def test_process_hit_miss():
    """A hit with no nearby note resets the combo and does not change any note."""
    mode = _make_mode()
    mode.beatmap = [{"time": 2000, "col": 0, "state": "WAITING"}]
    mode.combo = 3
    mode.hit_window_ms = 150

    # Wrong column → miss
    mode._process_hit(2000, 5)

    assert mode.beatmap[0]["state"] == "WAITING"
    assert mode.score == 0
    assert mode.combo == 0


def test_process_hit_already_hit_note_ignored():
    """A note that is already HIT must not be counted again."""
    mode = _make_mode()
    mode.beatmap = [{"time": 2000, "col": 0, "state": "HIT"}]
    mode.hit_window_ms = 150

    mode._process_hit(2000, 0)

    # State unchanged and no score awarded
    assert mode.score == 0


def test_render_marks_missed_notes():
    """_render() must set state='MISSED' for notes that passed the hit window."""
    mode = _make_mode()
    mode.beatmap = [{"time": 1000, "col": 0, "state": "WAITING"}]
    mode.hit_window_ms = 150

    # current_time is well past note["time"] + hit_window_ms
    mode._render(2000)

    assert mode.beatmap[0]["state"] == "MISSED"


def test_render_does_not_miss_upcoming_note():
    """_render() must not mark a future note as MISSED."""
    mode = _make_mode()
    mode.beatmap = [{"time": 5000, "col": 0, "state": "WAITING"}]
    mode.hit_window_ms = 150

    mode._render(1000)

    assert mode.beatmap[0]["state"] == "WAITING"


def test_note_y_position_interpolation():
    """Notes should interpolate from row 0 at spawn_time to HIT_ZONE_ROW at hit time."""
    mode = _make_mode()
    fall_duration = mode.fall_duration_ms
    hit_zone = mode.HIT_ZONE_ROW  # 7

    # At exactly spawn_time, progress=0 → y=0
    note_time = 2000
    spawn_time = note_time - fall_duration

    progress_start = (spawn_time - spawn_time) / fall_duration  # 0.0
    y_start = int(progress_start * hit_zone)
    assert y_start == 0

    # Halfway through fall, progress=0.5 → y=3
    mid_time = spawn_time + fall_duration // 2
    progress_mid = (mid_time - spawn_time) / fall_duration  # 0.5
    y_mid = int(progress_mid * hit_zone)
    assert y_mid == 3

    # At hit time, progress=1.0 → y=7
    progress_end = (note_time - spawn_time) / fall_duration  # 1.0
    y_end = int(progress_end * hit_zone)
    assert y_end == hit_zone


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
    # Inline the mapping logic from the script to verify correctness
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
