"""Tests for the JEB-808 Groovebox mode.

Validates:
- groovebox.py exists and has valid Python syntax
- GROOVEBOX is correctly registered in the mode manifest
- GrooveboxMode initialises with the correct defaults
- _step_interval_ms is correctly computed from BPM
- _process_keypad handles digits, '*' confirm, and '#' cancel correctly
- BPM clamping (min/max enforcement on confirm)
- _render does not raise and calls draw_pixel for active notes
- _fire_step plays notes for active, un-muted tracks
- _is_muted returns False when no satellite is present
- GROOVEBOX icon exists in the icon library as a 16×16 (256-pixel) icon
"""

import sys
import os
import ast
import unittest.mock as mock

# Make src/ importable.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

_MODE_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'src', 'modes', 'groovebox.py'
)

# ---------------------------------------------------------------------------
# Stub out CircuitPython-only modules once for the whole test module.
# ---------------------------------------------------------------------------
for _mod in ('adafruit_ticks', 'audiocore', 'audiomixer', 'audiobusio',
             'synthio', 'board', 'busio', 'digitalio', 'neopixel',
             'analogio', 'microcontroller', 'watchdog', 'audiopwmio',
             'keypad', 'rotaryio'):
    if _mod not in sys.modules:
        sys.modules[_mod] = mock.MagicMock()

# Provide a real ticks_ms / ticks_diff shim.
import time as _time
_t0 = _time.monotonic()
_ticks_mock = mock.MagicMock()
_ticks_mock.ticks_ms = lambda: int((_time.monotonic() - _t0) * 1000)
_ticks_mock.ticks_diff = lambda a, b: a - b
sys.modules['adafruit_ticks'] = _ticks_mock


# ---------------------------------------------------------------------------
# Minimal stubs
# ---------------------------------------------------------------------------

class _FakeMatrix:
    def __init__(self, width=16, height=16):
        self.width = width
        self.height = height
        self.pixels = {}

    def clear(self):
        self.pixels.clear()

    def draw_pixel(self, x, y, color):
        self.pixels[(x, y)] = color

    def show_frame(self):
        pass

    def show_icon(self, *a, **kw):
        pass


class _FakeSynth:
    def __init__(self):
        self.last_freq  = None
        self.last_patch = None
        self.play_count = 0

    def play_note(self, freq, patch=None, duration=None):
        self.last_freq  = freq
        self.last_patch = patch
        self.play_count += 1


class _FakeDisplay:
    def update_status(self, *a, **kw):
        pass

    def update_header(self, *a, **kw):
        pass

    def use_standard_layout(self):
        pass


class _FakeHid:
    def __init__(self):
        self._enc = 0
        self._enc_btn = False
        self._buttons = {}

    def flush(self):
        pass

    def reset_encoder(self, *a, **kw):
        pass

    def encoder_position(self, index=0):
        return self._enc

    def is_encoder_button_pressed(self, long=False, duration=2000, action=None, index=0):
        v = self._enc_btn
        if action == "tap":
            self._enc_btn = False
        return v

    def is_button_pressed(self, index, long=False, duration=2000, action=None):
        v = self._buttons.get(index, False)
        if action == "tap":
            self._buttons[index] = False
        return v

    def is_latching_toggled(self, index, *a, **kw):
        return False

    def is_momentary_toggled(self, index, direction="U", *a, **kw):
        return False

    def get_keypad_next_key(self, index=0):
        return None


class _FakeCore:
    def __init__(self, matrix_width=16, matrix_height=16):
        self.matrix      = _FakeMatrix(matrix_width, matrix_height)
        self.display     = _FakeDisplay()
        self.synth       = _FakeSynth()
        self.hid         = _FakeHid()
        self.satellites  = {}
        self.current_mode_step = 0

    async def clean_slate(self):
        pass


def _make_mode(matrix_width=16, matrix_height=16):
    """Construct a GrooveboxMode backed by a stub core (no real hardware)."""
    from modes.groovebox import GrooveboxMode
    return GrooveboxMode(_FakeCore(matrix_width, matrix_height))


# ---------------------------------------------------------------------------
# File / syntax checks
# ---------------------------------------------------------------------------

def test_groovebox_file_exists():
    """groovebox.py must exist in src/modes/."""
    assert os.path.exists(_MODE_PATH), "groovebox.py does not exist in src/modes/"


def test_groovebox_valid_syntax():
    """groovebox.py must have valid Python syntax."""
    with open(_MODE_PATH, 'r', encoding='utf-8') as fh:
        src = fh.read()
    try:
        ast.parse(src)
    except SyntaxError as exc:
        raise AssertionError(f"Syntax error in groovebox.py: {exc}") from exc


# ---------------------------------------------------------------------------
# Manifest checks
# ---------------------------------------------------------------------------

def test_groovebox_in_manifest():
    """GROOVEBOX must be present in MODE_REGISTRY."""
    from modes.manifest import MODE_REGISTRY
    assert "GROOVEBOX" in MODE_REGISTRY, "GROOVEBOX not found in MODE_REGISTRY"


def test_groovebox_manifest_metadata():
    """GROOVEBOX manifest entry must have all required fields."""
    from modes.manifest import MODE_REGISTRY
    meta = MODE_REGISTRY["GROOVEBOX"]

    assert meta["id"]          == "GROOVEBOX"
    assert meta["name"]        == "JEB-808"
    assert meta["module_path"] == "modes.groovebox"
    assert meta["class_name"]  == "GrooveboxMode"
    assert meta["icon"]        == "GROOVEBOX"
    assert "CORE" in meta["requires"], "GROOVEBOX must require CORE"
    assert meta.get("menu")    == "MAIN", "GROOVEBOX should appear in the MAIN menu"


def test_groovebox_manifest_settings():
    """GROOVEBOX must have a 'bpm' setting with sensible defaults."""
    from modes.manifest import MODE_REGISTRY
    settings = MODE_REGISTRY["GROOVEBOX"].get("settings", [])
    bpm_setting = next((s for s in settings if s["key"] == "bpm"), None)
    assert bpm_setting is not None, "Missing 'bpm' setting in GROOVEBOX manifest"
    assert "120" in bpm_setting["options"], "'120' must be a valid BPM option"
    assert bpm_setting["default"] == "120", "Default BPM should be '120'"


# ---------------------------------------------------------------------------
# Icon check
# ---------------------------------------------------------------------------

def test_groovebox_icon_in_library():
    """GROOVEBOX icon must be in Icons.ICON_LIBRARY as a 16×16 (256-pixel) icon."""
    from utilities.icons import Icons
    assert "GROOVEBOX" in Icons.ICON_LIBRARY, "GROOVEBOX icon not found in ICON_LIBRARY"
    icon = Icons.ICON_LIBRARY["GROOVEBOX"]
    assert len(icon) == 256, (
        f"GROOVEBOX icon should have 256 pixels (16×16), got {len(icon)}"
    )


# ---------------------------------------------------------------------------
# Default state
# ---------------------------------------------------------------------------

def test_default_state():
    """GrooveboxMode must initialise with correct defaults."""
    from modes.groovebox import NUM_TRACKS, NUM_STEPS, _DEFAULT_BPM
    mode = _make_mode()

    assert mode.bpm        == _DEFAULT_BPM, "Default BPM should be 120"
    assert mode.is_playing is True,         "Sequencer should start playing"
    assert mode.current_step == 0,          "Playback should start at step 0"
    assert mode.cursor_track == 0,          "Cursor should start at track 0"
    assert mode.cursor_step  == 0,          "Cursor should start at step 0"
    assert mode.sat is None,                "No satellite stub in this test"

    # All notes should be off.
    for track in range(NUM_TRACKS):
        for step in range(NUM_STEPS):
            assert not mode.notes[track][step], (
                f"notes[{track}][{step}] should be False at init"
            )


# ---------------------------------------------------------------------------
# Step-interval timing
# ---------------------------------------------------------------------------

def test_step_interval_120bpm():
    """At 120 BPM a 16th-note step should be 125 ms."""
    mode = _make_mode()
    mode.bpm = 120
    assert mode._step_interval_ms == 125, (
        f"Expected 125 ms at 120 BPM, got {mode._step_interval_ms}"
    )


def test_step_interval_60bpm():
    """At 60 BPM a 16th-note step should be 250 ms."""
    mode = _make_mode()
    mode.bpm = 60
    assert mode._step_interval_ms == 250, (
        f"Expected 250 ms at 60 BPM, got {mode._step_interval_ms}"
    )


def test_step_interval_240bpm():
    """At 240 BPM a 16th-note step should be 62 ms."""
    mode = _make_mode()
    mode.bpm = 240
    assert mode._step_interval_ms == 62, (
        f"Expected 62 ms at 240 BPM, got {mode._step_interval_ms}"
    )


# ---------------------------------------------------------------------------
# BPM keypad entry – process_keypad
# ---------------------------------------------------------------------------

class _SatWithKeypad:
    """Minimal satellite stub that pre-loads a keypad queue."""

    class _FakeSatHid:
        def __init__(self, keys):
            self._keys = list(keys)

        def get_keypad_next_key(self, index=0):
            return self._keys.pop(0) if self._keys else None

        def is_latching_toggled(self, index, *a, **kw):
            return False

        def is_momentary_toggled(self, index, direction="U", *a, **kw):
            return False

    def __init__(self, keys):
        self.hid = self._FakeSatHid(keys)
        self.sat_type_name = "INDUSTRIAL"
        self.is_active = True

    def send(self, cmd, val):
        pass


def _make_mode_with_keypad(keys):
    """Return a GrooveboxMode whose satellite keypad will return *keys* in sequence."""
    from modes.groovebox import GrooveboxMode
    core = _FakeCore()
    mode = GrooveboxMode(core)
    mode.sat = _SatWithKeypad(keys)
    return mode


def test_keypad_digits_accumulate():
    """Typing '1', '2', '0' should fill the BPM buffer."""
    mode = _make_mode_with_keypad(['1', '2', '0'])
    mode._process_keypad()
    assert mode._bpm_buf == "120", f"Expected '120', got '{mode._bpm_buf}'"


def test_keypad_confirm_sets_bpm():
    """Typing '1', '4', '0', '*' should set BPM to 140 and clear the buffer."""
    mode = _make_mode_with_keypad(['1', '4', '0', '*'])
    display_calls = []
    mode.core.display.update_status = lambda *a: display_calls.append(a)

    mode._process_keypad()

    assert mode.bpm      == 140, f"Expected BPM 140, got {mode.bpm}"
    assert mode._bpm_buf == "",  "Buffer should be cleared after confirmation"
    # Check that the display was updated to reflect the confirmed BPM.
    assert any("140" in str(args) for args in display_calls), (
        "Display should have been updated with confirmed BPM '140'"
    )


def test_keypad_cancel_clears_buffer():
    """Typing '9', '9', '#' should discard the entry and leave BPM unchanged."""
    mode = _make_mode_with_keypad(['9', '9', '#'])
    original_bpm = mode.bpm
    mode._process_keypad()
    assert mode.bpm     == original_bpm, "BPM should not change after '#' cancel"
    assert mode._bpm_buf == "",          "Buffer should be cleared after '#'"


def test_keypad_bpm_clamped_to_min():
    """Entering a BPM below the minimum should clamp to _MIN_BPM."""
    from modes.groovebox import _MIN_BPM
    mode = _make_mode_with_keypad(['1', '*'])
    mode._process_keypad()
    assert mode.bpm == _MIN_BPM, f"Expected clamped min {_MIN_BPM}, got {mode.bpm}"


def test_keypad_bpm_clamped_to_max():
    """Entering a BPM above the maximum should clamp to _MAX_BPM."""
    from modes.groovebox import _MAX_BPM
    mode = _make_mode_with_keypad(['9', '9', '9', '*'])
    mode._process_keypad()
    assert mode.bpm == _MAX_BPM, f"Expected clamped max {_MAX_BPM}, got {mode.bpm}"


def test_keypad_max_3_digits():
    """The BPM buffer must not exceed 3 characters; first 3 digits are kept."""
    mode = _make_mode_with_keypad(['1', '2', '3', '4', '5'])
    mode._process_keypad()
    assert len(mode._bpm_buf) <= 3, (
        f"Buffer should not exceed 3 digits, got '{mode._bpm_buf}'"
    )
    assert mode._bpm_buf == "123", (
        f"Buffer should contain the first 3 digits '123', got '{mode._bpm_buf}'"
    )


# ---------------------------------------------------------------------------
# _is_muted without satellite
# ---------------------------------------------------------------------------

def test_is_muted_no_satellite():
    """_is_muted must return False for every track when no satellite is present."""
    from modes.groovebox import NUM_TRACKS
    mode = _make_mode()
    assert mode.sat is None
    for track in range(NUM_TRACKS):
        assert not mode._is_muted(track), (
            f"Track {track} should not be muted without a satellite"
        )


# ---------------------------------------------------------------------------
# _fire_step
# ---------------------------------------------------------------------------

def test_fire_step_plays_active_notes():
    """_fire_step must call synth.play_note for each active, un-muted note."""
    from modes.groovebox import NUM_TRACKS
    mode = _make_mode()

    # Activate notes at step 0 for every track.
    for t in range(NUM_TRACKS):
        mode.notes[t][0] = True

    mode.current_step = 0
    mode._fire_step()

    assert mode.core.synth.play_count == NUM_TRACKS, (
        f"Expected {NUM_TRACKS} notes, synth was called {mode.core.synth.play_count} times"
    )


def test_fire_step_skips_empty_cells():
    """_fire_step must not call synth.play_note when no notes are set."""
    mode = _make_mode()
    mode.current_step = 0
    mode._fire_step()
    assert mode.core.synth.play_count == 0, "No notes should be played on an empty step"


def test_fire_step_applies_pitch_multiplier():
    """_fire_step must multiply the base frequency by _pitch_mult."""
    from modes.groovebox import _TRACK_INFO, _PITCH_UP_FACTOR
    mode = _make_mode()
    mode.notes[0][0] = True          # KICK note at step 0
    mode.current_step = 0
    mode._pitch_mult = _PITCH_UP_FACTOR

    mode._fire_step()

    expected_freq = _TRACK_INFO[0][1] * _PITCH_UP_FACTOR
    assert mode.core.synth.last_freq == expected_freq, (
        f"Expected freq {expected_freq}, got {mode.core.synth.last_freq}"
    )


# ---------------------------------------------------------------------------
# _render
# ---------------------------------------------------------------------------

def test_render_active_note_uses_track_color():
    """An active note cell must be drawn in the track's colour."""
    from modes.groovebox import _TRACK_INFO
    mode = _make_mode()
    mode.notes[0][5] = True          # KICK at step 5
    mode.is_playing  = False         # Keep playhead out of the way
    mode.cursor_step = 15            # Move cursor away from the tested cell

    mode._render()

    # Track 0 occupies rows 0 and 1.
    track_color = _TRACK_INFO[0][3]
    assert mode.core.matrix.pixels.get((5, 0)) == track_color, (
        "Active note top-row should use the track colour"
    )
    assert mode.core.matrix.pixels.get((5, 1)) == track_color, (
        "Active note bottom-row should use the track colour"
    )


def test_render_cursor_uses_cursor_color():
    """The cursor cell must be drawn in _CURSOR_COLOR."""
    from modes.groovebox import _CURSOR_COLOR
    mode = _make_mode()
    mode.cursor_track = 2
    mode.cursor_step  = 7
    mode.is_playing   = False

    mode._render()

    # Track 2 occupies rows 4 and 5.
    assert mode.core.matrix.pixels.get((7, 4)) == _CURSOR_COLOR, (
        "Cursor cell top-row should use _CURSOR_COLOR"
    )
    assert mode.core.matrix.pixels.get((7, 5)) == _CURSOR_COLOR, (
        "Cursor cell bottom-row should use _CURSOR_COLOR"
    )


def test_render_empty_cell_is_off():
    """An empty, non-cursor, non-playhead cell must be drawn as OFF."""
    from modes.groovebox import _TRACK_INFO
    from utilities.palette import Palette
    mode = _make_mode()
    mode.is_playing  = False
    mode.cursor_step = 15            # Cursor is far from the tested cell

    mode._render()

    # Check cell (0, 0) for track 0 – no note, no cursor, no playhead.
    assert mode.core.matrix.pixels.get((0, 0)) == Palette.OFF, (
        "Empty cell should be drawn as Palette.OFF"
    )
