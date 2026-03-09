# File: src/modes/groovebox.py
"""JEB-808 Groovebox – 16-step musical sequencer creative sandbox.

A pure "toy" mode with no win/loss state, no timer, and no score.  The
player arranges notes on an 8-track × 16-step grid and the sequencer loops
indefinitely, making it a live-mixing instrument.

Hardware mapping
----------------
Core:
    16×16 Matrix    8-track × 16-step sequencer grid.
                    Each track spans 2 matrix rows; columns = time steps.
                    Rows 0–1  = Track 0 (KICK)
                    Rows 2–3  = Track 1 (SNARE)
                    Rows 4–5  = Track 2 (HIHAT)
                    Rows 6–7  = Track 3 (TOM)
                    Rows 8–9  = Track 4 (BASS)
                    Rows 10–11 = Track 5 (LEAD)
                    Rows 12–13 = Track 6 (PAD)
                    Rows 14–15 = Track 7 (FX)

    OLED            Shows BPM and the currently selected track name.
    Rotary Encoder  Scroll the edit cursor left/right through the 16 steps.
    Encoder Button  Place or remove a note at the cursor position.
    Button 0        Move the edit cursor UP one track.
    Button 1        Move the edit cursor DOWN one track.
    Button 2        Toggle playback start / stop.

Industrial Satellite (SAT-01, optional – mode degrades gracefully without it):
    14-Seg Display  Shows current BPM (or the BPM entry buffer).
    Latching [0-7]  Track mutes: toggle ON = that track is silenced.
    9-Digit Keypad  Punch in a new BPM.  Accumulate up to 3 digits;
                    press '*' to confirm, '#' to cancel.
    Momentary [0]   Audio pitch-shift effect while held:
                    UP held   → all notes pitched up   (×1.5)
                    DOWN held → all notes pitched down (×0.67)
"""

import asyncio

from adafruit_ticks import ticks_ms, ticks_diff

from utilities.palette import Palette
from utilities.synth_registry import Patches
from .base import BaseMode

# ---------------------------------------------------------------------------
# Sequencer constants
# ---------------------------------------------------------------------------

NUM_TRACKS = 8
NUM_STEPS  = 16

# Each of the 8 tracks occupies 2 matrix rows (8 × 2 = 16 rows total).
_ROWS_PER_TRACK = 2

# BPM range and start value.
_DEFAULT_BPM = 120
_MIN_BPM     = 40
_MAX_BPM     = 300

# Pitch-shift factors applied while the satellite momentary toggle is held.
_PITCH_UP_FACTOR   = 1.5
_PITCH_DOWN_FACTOR = 0.667

# Keypad confirmation / cancellation keys on the 3×3 keypad.
_KEY_CONFIRM = "*"
_KEY_CANCEL  = "#"

# ---------------------------------------------------------------------------
# Track definitions
# (display_name, base_frequency_hz, patch_key_string, matrix_color)
#
# Noise-based patches (RETRO_NOISE) are referenced by name because they are
# lazily generated; _get_patch() resolves the actual dict at call time.
# ---------------------------------------------------------------------------

_TRACK_INFO = (
    ("KICK",   60.0,    "PUNCH",       Palette.RED),
    ("SNARE",  200.0,   "RETRO_NOISE", Palette.ORANGE),
    ("HIHAT",  1200.0,  "CLICK",       Palette.YELLOW),
    ("TOM",    150.0,   "PUNCH",       Palette.GREEN),
    ("BASS",   80.0,    "RETRO_BASS",  Palette.CYAN),
    ("LEAD",   440.0,   "RETRO_LEAD",  Palette.MAGENTA),
    ("PAD",    330.0,   "PAD",         Palette.BLUE),
    ("FX",     600.0,   "BEEP_SQUARE", Palette.WHITE),
)

# Visual: cursor cell (editing position) shown in silver.
_CURSOR_COLOR   = Palette.SILVER
# Visual: the advancing playhead column shown in charcoal when no note is active.
_PLAYHEAD_COLOR = Palette.CHARCOAL


class GrooveboxMode(BaseMode):
    """JEB-808 Groovebox – 16-step musical sequencer creative sandbox.

    No win/loss state.  Runs indefinitely until the player exits with a
    3-second long-press of Button 3 (handled automatically by BaseMode).

    See module docstring for the full hardware mapping.
    """

    def __init__(self, core):
        super().__init__(core, "JEB-808", "Groovebox Sequencer")

        # Locate the Industrial Satellite (optional).
        self.sat = None
        for sat in self.core.satellites.values():
            if sat.sat_type_name == "INDUSTRIAL":
                self.sat = sat
                break

        # Sequencer grid: notes[track_idx][step_idx] → bool
        self.notes = [[False] * NUM_STEPS for _ in range(NUM_TRACKS)]

        # Playback state.
        self.bpm        = _DEFAULT_BPM
        self.is_playing = True
        self.current_step = 0
        self._last_step_ms = 0

        # Edit cursor state.
        self.cursor_track = 0
        self.cursor_step  = 0

        # BPM keypad entry buffer (accumulates digits before confirmation).
        self._bpm_buf = ""

        # Pitch multiplier set by the momentary toggle; 1.0 = no shift.
        self._pitch_mult = 1.0

    # ------------------------------------------------------------------
    # Timing
    # ------------------------------------------------------------------

    @property
    def _step_interval_ms(self):
        """Duration of one 16th-note step at the current BPM (milliseconds).

        1 bar = 4 beats; 16 steps per bar → 1 step = ¼ beat.
        step_ms = 60 000 / (bpm × 4)
        """
        return int(60000 / (self.bpm * 4))

    # ------------------------------------------------------------------
    # Patch resolution (handles lazily-initialised noise patches)
    # ------------------------------------------------------------------

    def _get_patch(self, track):
        """Return the synthio patch dict for the given track index."""
        patch_key = _TRACK_INFO[track][2]
        if patch_key == "RETRO_NOISE":
            return Patches.get_retro_noise_patch()
        if patch_key == "NOISE":
            return Patches.get_noise_patch()
        return getattr(Patches, patch_key)

    # ------------------------------------------------------------------
    # Satellite helpers – all guarded with try/except for graceful fallback
    # ------------------------------------------------------------------

    def _is_muted(self, track):
        """Return True if the satellite latching toggle for this track is ON."""
        if not self.sat:
            return False
        try:
            return self.sat.hid.is_latching_toggled(track)
        except (IndexError, AttributeError):
            return False

    def _poll_keypad_key(self):
        """Return the next pending keypad character from the satellite, or None."""
        if not self.sat:
            return None
        try:
            return self.sat.hid.get_keypad_next_key(0)
        except (IndexError, AttributeError):
            return None

    def _read_pitch_toggle(self):
        """Update _pitch_mult from the satellite momentary toggle state."""
        if not self.sat:
            self._pitch_mult = 1.0
            return
        try:
            if self.sat.hid.is_momentary_toggled(0, direction="U"):
                self._pitch_mult = _PITCH_UP_FACTOR
            elif self.sat.hid.is_momentary_toggled(0, direction="D"):
                self._pitch_mult = _PITCH_DOWN_FACTOR
            else:
                self._pitch_mult = 1.0
        except (IndexError, AttributeError):
            self._pitch_mult = 1.0

    def _send_segment_display(self):
        """Push the current BPM (or entry buffer) to the satellite 14-seg display."""
        if not self.sat:
            return
        try:
            if self._bpm_buf:
                self.sat.send("DSP", f"BPM {self._bpm_buf:>3s}?")
            else:
                self.sat.send("DSP", f"BPM {self.bpm:>4d}")
        except (AttributeError, OSError, RuntimeError):
            # Satellite may be temporarily unreachable; display update is
            # best-effort and safe to skip.
            pass

    # ------------------------------------------------------------------
    # Sequencer playback
    # ------------------------------------------------------------------

    def _fire_step(self):
        """Trigger all active, un-muted notes at the current playback step."""
        for track in range(NUM_TRACKS):
            if not self.notes[track][self.current_step]:
                continue
            if self._is_muted(track):
                continue
            base_freq = _TRACK_INFO[track][1]
            freq  = base_freq * self._pitch_mult
            patch = self._get_patch(track)
            self.core.synth.play_note(freq, patch=patch, duration=0.08)

    # ------------------------------------------------------------------
    # BPM keypad entry
    # ------------------------------------------------------------------

    def _process_keypad(self):
        """Drain the keypad queue and handle BPM entry one key at a time."""
        while True:
            key = self._poll_keypad_key()
            if key is None:
                break
            key_str = str(key)
            if key_str.isdigit():
                if len(self._bpm_buf) < 3:
                    self._bpm_buf += key_str
                    self.core.display.update_status("JEB-808", f"BPM>{self._bpm_buf}")
            elif key_str == _KEY_CONFIRM:
                if self._bpm_buf:
                    new_bpm = int(self._bpm_buf)
                    self.bpm = max(_MIN_BPM, min(_MAX_BPM, new_bpm))
                self._bpm_buf = ""
                self.core.display.update_status("JEB-808", f"BPM:{self.bpm}")
            elif key_str == _KEY_CANCEL:
                self._bpm_buf = ""
                self.core.display.update_status("JEB-808", f"BPM:{self.bpm}")

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render(self):
        """Draw the 8-track × 16-step grid on the LED matrix."""
        self.core.matrix.clear()

        for track in range(NUM_TRACKS):
            track_color = _TRACK_INFO[track][3]
            muted = self._is_muted(track)

            row_a = track * _ROWS_PER_TRACK
            row_b = row_a + 1

            for step in range(NUM_STEPS):
                has_note   = self.notes[track][step]
                is_cursor  = (track == self.cursor_track and step == self.cursor_step)
                is_playhead = (self.is_playing and step == self.current_step)

                if is_cursor:
                    # Silver cursor marks the current edit position.
                    color = _CURSOR_COLOR
                elif has_note and is_playhead:
                    # White flash when the playhead hits an active note.
                    color = Palette.WHITE
                elif has_note:
                    # Active note: track colour; charcoal when muted.
                    color = Palette.CHARCOAL if muted else track_color
                elif is_playhead:
                    # Playhead column with no note: subtle charcoal tick.
                    color = _PLAYHEAD_COLOR
                else:
                    color = Palette.OFF

                self.core.matrix.draw_pixel(step, row_a, color)
                self.core.matrix.draw_pixel(step, row_b, color)

    # ------------------------------------------------------------------
    # Main async run loop
    # ------------------------------------------------------------------

    async def run(self):
        """Groovebox main loop – runs until Button 3 long-press exits."""
        self.core.display.update_status("JEB-808", f"BPM:{self.bpm}")
        self.core.hid.flush()
        self.core.hid.reset_encoder(0)

        self._last_step_ms = ticks_ms()
        last_enc = self.core.hid.encoder_position()

        while True:
            now = ticks_ms()

            # --- Sequencer clock ---
            if self.is_playing and ticks_diff(now, self._last_step_ms) >= self._step_interval_ms:
                self._last_step_ms = now
                self._fire_step()
                self.current_step = (self.current_step + 1) % NUM_STEPS

            # --- Core encoder: move cursor step left / right ---
            curr_enc = self.core.hid.encoder_position()
            enc_diff = curr_enc - last_enc
            if enc_diff != 0:
                self.cursor_step = (self.cursor_step + enc_diff) % NUM_STEPS
                last_enc = curr_enc

            # --- Encoder button: place or remove a note ---
            if self.core.hid.is_encoder_button_pressed(action="tap"):
                self.notes[self.cursor_track][self.cursor_step] = \
                    not self.notes[self.cursor_track][self.cursor_step]
                # Audition the note for immediate tactile feedback.
                self.core.synth.play_note(
                    _TRACK_INFO[self.cursor_track][1] * self._pitch_mult,
                    patch=self._get_patch(self.cursor_track),
                    duration=0.08,
                )

            # --- Button 0: cursor track UP ---
            if self.core.hid.is_button_pressed(0, action="tap"):
                self.cursor_track = (self.cursor_track - 1) % NUM_TRACKS
                self.core.display.update_status(
                    "JEB-808", _TRACK_INFO[self.cursor_track][0]
                )

            # --- Button 1: cursor track DOWN ---
            if self.core.hid.is_button_pressed(1, action="tap"):
                self.cursor_track = (self.cursor_track + 1) % NUM_TRACKS
                self.core.display.update_status(
                    "JEB-808", _TRACK_INFO[self.cursor_track][0]
                )

            # --- Button 2: toggle playback start / stop ---
            if self.core.hid.is_button_pressed(2, action="tap"):
                self.is_playing = not self.is_playing
                if self.is_playing:
                    self._last_step_ms = ticks_ms()
                    self.current_step = 0
                self.core.display.update_status(
                    "JEB-808", "PLAYING" if self.is_playing else "STOPPED"
                )

            # --- Satellite inputs ---
            self._read_pitch_toggle()
            self._process_keypad()
            self._send_segment_display()

            # --- Render the matrix ---
            self._render()
            self.core.matrix.show_frame()

            await asyncio.sleep(0.016)  # ~60 fps
