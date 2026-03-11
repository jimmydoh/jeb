"""Numbers Station – Cold War Espionage Audio Cipher Game.

The player intercepts eerie shortwave radio broadcasts from a covert
numbers station and decrypts the digit sequences using the hardware as a
cryptograph.

Gameplay:
    Each round the player must:
    1. TUNE    – Rotate the 3-position switch to the correct radio band so
                 the broadcast comes in clear (wrong bands are jammed).
    2. LISTEN  – The audio engine plays a sequence of digits as distinct
                 synth tones.  Press the core encoder button to replay
                 (up to the allowed replay limit).
    3. DECODE  – The 14-segment display shows the active cipher
                 (e.g. "SHIFT +3").  Apply the shift to each heard digit
                 (mod 10) and type the result on the 9-key keypad.
    4. SUBMIT  – Press the Big Red Button to transmit the decrypted code.

Cipher:
    decoded_digit = (heard_digit + shift) % 10

Bands (3-position rotary switch):
    ALPHA  – A=ON,  B=OFF  (latching indices 10 / 11)
    BRAVO  – A=OFF, B=OFF  (centre / default)
    CHARLIE– A=OFF, B=ON

Hardware:
    Core:
        - OLED: Phase info, cipher, heard digits, player input
        - 16×16 Matrix: Animated static noise / signal strength / result
        - Rotary Encoder: Click to replay the digit sequence

    Industrial Satellite (SAT-01):
        - 14-Segment Display: Cipher instruction, band status, input echo
        - 3-Position Rotary Switch (indices 10-11): Band selection
        - 9-Digit Keypad (index 0): Decoded digit entry
        - Large Button (index 0): Submit / Transmit
"""

import asyncio
import random

from adafruit_ticks import ticks_ms, ticks_diff

from utilities.palette import Palette
from utilities import tones

from .game_mode import GameMode

# ---------------------------------------------------------------------------
# Hardware indices (mirror sat_01_driver layout)
# ---------------------------------------------------------------------------
_SW_ROTARY_A  = 10    # 3-position rotary: Position A (latching index 10)
_SW_ROTARY_B  = 11    # 3-position rotary: Position B (latching index 11)
_BTN_SUBMIT   = 0     # Big red button: submit decrypted sequence
_KP_INDEX     = 0     # Matrix keypad index
_ENC_REPLAY   = 0     # Core encoder button: replay broadcast

# ---------------------------------------------------------------------------
# Radio band identifiers
# ---------------------------------------------------------------------------
BAND_ALPHA   = "ALPHA"
BAND_BRAVO   = "BRAVO"
BAND_CHARLIE = "CHARLIE"

_ALL_BANDS = [BAND_ALPHA, BAND_BRAVO, BAND_CHARLIE]

# ---------------------------------------------------------------------------
# Digit → synth note mapping  (one octave of a pentatonic-ish scale)
# ---------------------------------------------------------------------------
_DIGIT_NOTE = {
    '0': 'A3',
    '1': 'C4',
    '2': 'D4',
    '3': 'E4',
    '4': 'G4',
    '5': 'A4',
    '6': 'C5',
    '7': 'D5',
    '8': 'E5',
    '9': 'G5',
}

_DIGIT_DURATION     = 0.35   # Seconds each digit tone plays
_DIGIT_GAP          = 0.25   # Silence between digits

# Listen phase – grace window after playback ends
_GRACE_WINDOW_TICKS  = 30    # 30 × _GRACE_TICK_INTERVAL = 3 s
_GRACE_TICK_INTERVAL = 0.1   # Poll interval during grace window (seconds)

# Scoring
_SPEED_BONUS_THRESHOLD   = 20.0  # Seconds: decode within this for a bonus
_SPEED_BONUS_MULTIPLIER  = 2     # Points per second under the threshold

# ---------------------------------------------------------------------------
# Phase identifiers
# ---------------------------------------------------------------------------
_PHASE_TUNE     = "TUNE"
_PHASE_LISTEN   = "LISTEN"
_PHASE_DECODE   = "DECODE"
_PHASE_SUBMIT   = "SUBMIT"

# ---------------------------------------------------------------------------
# Difficulty tuning
# ---------------------------------------------------------------------------
_DIFF_PARAMS = {
    "NORMAL": {
        "seq_length":    3,
        "shift_range":   (1, 5),
        "lives":         5,
        "max_replays":   2,
        "bonus_time":    15.0,
    },
    "HARD": {
        "seq_length":    4,
        "shift_range":   (1, 9),
        "lives":         3,
        "max_replays":   1,
        "bonus_time":    10.0,
    },
    "INSANE": {
        "seq_length":    5,
        "shift_range":   (1, 9),
        "lives":         2,
        "max_replays":   0,
        "bonus_time":    8.0,
    },
}

_GLOBAL_TIME   = 120.0    # 2-minute total game timer (seconds)

# ---------------------------------------------------------------------------
# Matrix dimensions
# ---------------------------------------------------------------------------
_MATRIX_SIZE = 16


class NumbersStation(GameMode):
    """Cold War Espionage Audio Cipher.

    The player intercepts shortwave number broadcasts, tunes to the clear
    band, listens to synthesized digit tones, applies the displayed Caesar
    cipher, and types the decoded sequence on the keypad before submitting.

    Hardware:
        Core:
            - 16×16 Matrix: Static noise, signal strength, result animations
            - OLED: Phase info, cipher, heard digits, player input
            - Encoder Button (index 0): Replay the digit broadcast

        Industrial Satellite (SAT-01):
            - 9-Digit Keypad (index 0): Decoded digit entry
            - 3-Position Rotary Switch (indices 10-11): Band selection
            - Large Button (index 0): Transmit / submit
            - 14-Segment Display: Cipher, band, input echo
    """

    def __init__(self, core):
        super().__init__(core, "NMBRS STN", "Cold War Cipher Intercept")

        # Find the Industrial Satellite
        self.sat = None
        for sat in self.core.satellites.values():
            if sat.sat_type_name == "INDUSTRIAL":
                self.sat = sat
                break

        # Current round state
        self._sequence:      list   = []     # Heard digits (strings)
        self._answer:        list   = []     # Decoded digits (strings)
        self._cipher_shift:  int    = 1      # Active shift value
        self._clear_band:    str    = BAND_BRAVO  # Band with clean signal
        self._round:         int    = 0
        self._lives:         int    = 5
        self._replays_left:  int    = 2

        # Input tracking
        self._player_input:       str  = ""
        self._last_kp_snapshot:   str  = ""
        self._last_btn_state:     bool = False
        self._last_enc_btn:       bool = False

        # Timer
        self._time_remaining: float = _GLOBAL_TIME
        self._last_tick_ms:   int   = 0

        # Difficulty params (populated in run())
        self._seq_length:    int   = 3
        self._shift_range:   tuple = (1, 5)
        self._max_replays:   int   = 2
        self._bonus_time:    float = 15.0

        # Segment display cache
        self._last_segment_text: str = ""

    # ------------------------------------------------------------------
    # Satellite HID helpers
    # ------------------------------------------------------------------

    def _sat_latching(self, idx):
        """Return the state of a satellite latching toggle (safe)."""
        if not self.sat:
            return False
        try:
            return bool(self.sat.hid.latching_values[idx])
        except (IndexError, AttributeError):
            return False

    def _sat_button(self, idx=0):
        """Return True on a fresh press of the satellite big button."""
        if not self.sat:
            return False
        try:
            current = bool(self.sat.hid.buttons_values[idx])
        except (IndexError, AttributeError):
            return False
        pressed = current and not self._last_btn_state
        self._last_btn_state = current
        return pressed

    def _sat_button_peek(self, idx=0):
        """Return raw (non-edge) state of the satellite big button."""
        if not self.sat:
            return False
        try:
            return bool(self.sat.hid.buttons_values[idx])
        except (IndexError, AttributeError):
            return False

    def _send_segment(self, text):
        """Send text to the satellite 14-segment display (max 8 chars)."""
        safe = text[:8]
        if self.sat and self._last_segment_text != safe:
            try:
                self.sat.send("DSP", safe)
                self._last_segment_text = safe
            except Exception:
                pass

    def _set_sat_led(self, idx, color):
        """Set a satellite NeoPixel LED colour."""
        if self.sat:
            try:
                self.sat.send("LED", f"{idx},{color.index},0.0,1.0,2")
            except Exception:
                pass

    def _enc_button_pressed(self):
        """Return True on a fresh press of the core encoder button."""
        try:
            current = bool(self.core.hid.buttons_values[_ENC_REPLAY])
        except (IndexError, AttributeError):
            return False
        pressed = current and not self._last_enc_btn
        self._last_enc_btn = current
        return pressed

    # ------------------------------------------------------------------
    # Band helper
    # ------------------------------------------------------------------

    def _get_band(self):
        """Read the 3-position rotary and return the active BAND_ constant."""
        rot_a = self._sat_latching(_SW_ROTARY_A)
        rot_b = self._sat_latching(_SW_ROTARY_B)
        if rot_a and not rot_b:
            return BAND_ALPHA
        if not rot_a and rot_b:
            return BAND_CHARLIE
        return BAND_BRAVO    # centre (both OFF or both ON treated as BRAVO)

    # ------------------------------------------------------------------
    # Keypad helper
    # ------------------------------------------------------------------

    def _read_keypad_new_digits(self):
        """Return any new digit characters typed on the keypad since last call."""
        current = ""
        if self.sat:
            try:
                keypads = self.sat.hid.keypad_values
                if keypads:
                    current = "".join(
                        str(k) for k in keypads[0]
                        if k is not None and str(k).isdigit()
                    )
            except (IndexError, AttributeError):
                pass

        if len(current) > len(self._last_kp_snapshot):
            new = current[len(self._last_kp_snapshot):]
            self._last_kp_snapshot = current
            return new

        self._last_kp_snapshot = current
        return ""

    # ------------------------------------------------------------------
    # Audio helpers
    # ------------------------------------------------------------------

    async def _play_digit_sequence(self, sequence):
        """Play one digit tone per element in sequence via the synth engine."""
        for digit_char in sequence:
            note_name = _DIGIT_NOTE.get(digit_char, 'A4')
            self.core.synth.play_note(
                tones.note(note_name),
                "BEEP",
                duration=_DIGIT_DURATION
            )
            await asyncio.sleep(_DIGIT_DURATION + _DIGIT_GAP)

    async def _play_jam_noise(self):
        """Play a harsh tritone jammer squeal (one burst)."""
        asyncio.create_task(
            self.core.synth.play_sequence(tones.RADIATION_WARNING, patch="ALARM")
        )

    # ------------------------------------------------------------------
    # Matrix visualisations
    # ------------------------------------------------------------------

    def _render_static(self):
        """Fill the matrix with dim random 'radio static' pixels."""
        self.core.matrix.clear()
        for y in range(_MATRIX_SIZE):
            for x in range(_MATRIX_SIZE):
                if random.random() < 0.15:
                    self.core.matrix.draw_pixel(
                        x, y, Palette.TEAL, brightness=0.3
                    )

    def _render_signal_bars(self, level=3):
        """Draw equaliser-style signal strength bars (level 0-4)."""
        self.core.matrix.clear()
        bar_heights = [
            max(1, level * 1),
            max(1, level * 2),
            max(1, level * 3),
            max(1, level * 4),
            max(1, level * 3),
            max(1, level * 2),
            max(1, level * 1),
        ]
        colors = [Palette.TEAL, Palette.CYAN, Palette.GREEN,
                  Palette.LIME, Palette.GREEN, Palette.CYAN, Palette.TEAL]

        cx = _MATRIX_SIZE // 2
        for i, (h, col) in enumerate(zip(bar_heights, colors)):
            x = cx - 3 + i
            h = min(h, _MATRIX_SIZE)
            for y in range(_MATRIX_SIZE - 1, _MATRIX_SIZE - 1 - h, -1):
                self.core.matrix.draw_pixel(x, y, col, brightness=0.8)

    def _render_input_progress(self, entered, total):
        """Show the entered / remaining slots as dots on the bottom row."""
        self.core.matrix.clear()
        # Top row shows cipher shift as a bar
        for i in range(min(self._cipher_shift, _MATRIX_SIZE)):
            self.core.matrix.draw_pixel(i, 0, Palette.GOLD, brightness=0.6)

        # Bottom 2 rows show input progress
        for i in range(total):
            x = ((_MATRIX_SIZE - total) // 2) + i
            if i < len(entered):
                color = Palette.GREEN
            else:
                color = Palette.CHARCOAL
            self.core.matrix.draw_pixel(
                x, _MATRIX_SIZE - 2, color, brightness=0.8
            )
            self.core.matrix.draw_pixel(
                x, _MATRIX_SIZE - 1, color, brightness=0.6
            )

    # ------------------------------------------------------------------
    # Round generation
    # ------------------------------------------------------------------

    def _new_round(self):
        """Generate a new transmission sequence, cipher, and clear band."""
        self._sequence = [
            str(random.randint(0, 9)) for _ in range(self._seq_length)
        ]
        self._cipher_shift = random.randint(*self._shift_range)
        self._answer = [
            str((int(d) + self._cipher_shift) % 10)
            for d in self._sequence
        ]
        self._clear_band = random.choice(_ALL_BANDS)

        # Reset input state
        self._player_input     = ""
        self._last_kp_snapshot = ""
        self._last_btn_state   = self._sat_button_peek()
        self._replays_left     = self._max_replays

    # ------------------------------------------------------------------
    # Phase: TUNE (find the clear band)
    # ------------------------------------------------------------------

    async def _run_phase_tune(self):
        """Phase 1 – Player must rotate the band switch to the clear band.

        The 14-segment shows the target band name.  Wrong bands trigger a
        jammer squeal on the matrix + audio.
        """
        band_abbr = {
            BAND_ALPHA:   "ALPHA",
            BAND_BRAVO:   "BRAVO",
            BAND_CHARLIE: "CHRL ",
        }

        target_abbr = band_abbr[self._clear_band]
        self.core.display.update_header("-NMBRS STN-")
        self.core.display.update_status(
            f"ROUND {self._round + 1}  TUNE RADIO",
            "FIND CLEAR SIGNAL"
        )
        self._send_segment("SCANNING")

        jammed = False
        while True:
            current_band = self._get_band()
            on_target = (current_band == self._clear_band)

            if on_target:
                if jammed:
                    # Signal cleared – brief confirmation
                    self.core.synth.play_note(
                        tones.note('G5'), "SUCCESS", duration=0.1
                    )
                self._render_signal_bars(level=4)
                self._send_segment(f"TUNED   ")
                self.core.display.update_status(
                    f"TUNED: {target_abbr}",
                    "STANDBY..."
                )
                await asyncio.sleep(0.4)
                return True
            else:
                jammed = True
                self.core.synth.play_note(150.0, "NOISE", duration=0.15)
                self._render_static()
                cur_abbr = band_abbr.get(current_band, "????")
                self._send_segment(f"JAMMED  ")
                self.core.display.update_status(
                    "SIGNAL JAMMED",
                    "SWITCH BANDS!"
                )

            await asyncio.sleep(0.1)

    # ------------------------------------------------------------------
    # Phase: LISTEN (play the digit broadcast)
    # ------------------------------------------------------------------

    async def _run_phase_listen(self):
        """Phase 2 – Play the digit sequence; allow replays via encoder button.

        The 14-segment shows "SHFT+X" (the cipher).  The OLED shows the
        number of replays remaining.  Press the core encoder button to
        replay.  Continues to the decode phase automatically after the
        sequence ends (or when replays are exhausted and the button is
        pressed to advance).
        """
        seq_str = " ".join(self._sequence)
        cipher_str = f"SHFT+{self._cipher_shift}"
        self._send_segment(cipher_str[:8])
        self._render_signal_bars(level=4)

        self.core.display.update_status(
            f"INTERCEPTED  RPL:{self._replays_left}",
            "PLAYING..."
        )
        asyncio.create_task(
            self.core.synth.play_sequence(tones.NOTIFY_INBOX, patch="BEEP")
        )
        await asyncio.sleep(0.6)

        # First play
        await self._play_digit_sequence(self._sequence)

        while True:
            self.core.display.update_status(
                f"INTERCEPTED  RPL:{self._replays_left}",
                "PRESS ENC=REPLAY"
            )
            self._render_signal_bars(level=2)

            # Give a short window for encoder-button replay or auto-advance
            waited = 0
            while waited < _GRACE_WINDOW_TICKS:
                if self._enc_button_pressed():
                    if self._replays_left > 0:
                        self._replays_left -= 1

                        self._time_remaining -= 2.0
                        self.core.synth.play_note(300.0, "ALARM", duration=0.2)

                        self.core.display.update_status(
                            f"REPLAY (-2s)  RPL:{self._replays_left}",
                            "LISTENING..."
                        )
                        await self._play_digit_sequence(self._sequence)
                        waited = 0    # reset grace window after replay
                    else:
                        # No replays left – advance immediately
                        return True
                await asyncio.sleep(_GRACE_TICK_INTERVAL)
                waited += 1

            # Grace window expired – advance to decode phase
            return True

    # ------------------------------------------------------------------
    # Phase: DECODE (player types the decoded digits)
    # ------------------------------------------------------------------

    async def _run_phase_decode(self):
        """Phase 3 – Player types the shift-decoded sequence on the keypad.

        The 14-segment echoes typed digits.  The OLED shows the cipher and
        what has been entered so far.  Backspace/clear is not supported
        (the buffer auto-resets to the last ``seq_length`` digits on overflow).
        """
        cipher_str = f"SHFT+{self._cipher_shift}"
        self._send_segment(cipher_str[:8])
        self._player_input = ""
        self._last_kp_snapshot = ""
        target_len = len(self._answer)

        self.core.display.update_status(
            f"CIPHER: {cipher_str}",
            f"ENTER {target_len} DIGITS"
        )
        self._render_input_progress(self._player_input, target_len)

        while True:
            new_chars = self._read_keypad_new_digits()
            if new_chars:
                for ch in new_chars:
                    self._player_input += ch
                    # Keep only the last `target_len` characters
                    if len(self._player_input) > target_len:
                        self._player_input = self._player_input[-target_len:]
                    self.core.synth.play_note(
                        tones.note('C5'), "CLICK", duration=0.03
                    )

                self._send_segment(self._player_input.ljust(target_len)[:8])
                self.core.display.update_status(
                    f"CIPHER: {cipher_str}",
                    f"TYPED: {self._player_input}"
                )
                self._render_input_progress(self._player_input, target_len)

            await asyncio.sleep(0.05)

            # Auto-advance once full length is entered
            if len(self._player_input) >= target_len:
                return True

    # ------------------------------------------------------------------
    # Phase: SUBMIT (big red button)
    # ------------------------------------------------------------------

    async def _run_phase_submit(self):
        """Phase 4 – Player presses the Big Red Button to transmit."""
        self._send_segment("SEND?   ")
        self.core.display.update_status(
            "READY TO TRANSMIT",
            "PRESS BIG RED BTN"
        )
        asyncio.create_task(
            self.core.synth.play_sequence(tones.ALARM, patch="ALARM")
        )

        while True:
            if self._sat_button(_BTN_SUBMIT):
                return True
            await asyncio.sleep(0.05)

    # ------------------------------------------------------------------
    # Result helpers
    # ------------------------------------------------------------------

    def _check_answer(self):
        """Return True if the player's input matches the decoded answer."""
        entered = self._player_input[-len(self._answer):]
        return list(entered) == self._answer

    async def _show_correct(self, speed_bonus):
        """Animate and score a correct decryption."""
        self.core.synth.play_note(
            tones.note('G5'), "SUCCESS", duration=0.2
        )
        asyncio.create_task(
            self.core.synth.play_sequence(tones.SUCCESS, patch="SUCCESS")
        )
        pts = 50 + speed_bonus
        self.score += pts
        self._send_segment("CORRECT!")
        self.core.display.update_status(
            f"DECRYPTED! +{pts}",
            f"SCORE: {self.score}"
        )
        self.core.matrix.show_icon("SUCCESS", anim_mode="PULSE", speed=3.0)
        await asyncio.sleep(1.5)

    async def _show_wrong(self):
        """Animate and deduct a life on a wrong submission."""
        asyncio.create_task(
            self.core.synth.play_sequence(tones.ERROR, patch="ERROR")
        )
        self._lives -= 1
        expected_str = "".join(self._answer)
        self._send_segment(f"ERR {expected_str[:4]}")
        self.core.display.update_status(
            f"WRONG!  LIVES: {self._lives}",
            f"ANSWER: {''.join(self._answer)}"
        )
        self.core.matrix.show_icon("FAILURE", anim_mode="PULSE", speed=3.0)
        await asyncio.sleep(2.0)

    # ------------------------------------------------------------------
    # Timed phase wrapper
    # ------------------------------------------------------------------

    async def _timed_phase(self, phase_coro):
        """Run a phase coroutine; returns False if global time runs out first."""
        task = asyncio.create_task(phase_coro())
        try:
            while not task.done():
                now = ticks_ms()
                elapsed_ms = ticks_diff(now, self._last_tick_ms)
                if elapsed_ms >= 100:
                    self._time_remaining -= elapsed_ms / 1000.0
                    self._last_tick_ms = now

                if self._time_remaining <= 0:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    return False

                await asyncio.sleep(0.05)

            return await task

        except asyncio.CancelledError:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            raise

    # ------------------------------------------------------------------
    # Tutorial
    # ------------------------------------------------------------------

    async def run_tutorial(self):
        """
        Walk the player through a single guided round with commentary.

        The Voiceover Script (audio/tutes/numbers_tute.wav) ~38 seconds
            [0:00] "Welcome to Numbers Station. Your mission is to intercept and decode covert transmissions."
            [0:06] "Step one: Tune the radio. Turn the rotary switch to find the clear channel."
            [0:11] "Step two: Listen. The station will broadcast a sequence of digits. Press the dial to replay the audio if needed."
            [0:19] "Step three: Decode. Check the satellite display for the active cipher, and apply the shift to your numbers."
            [0:26] "Type the decrypted sequence into the keypad."
            [0:30] "Step four: Submit. Press the big red button to transmit your answer."
            [0:35] "Good luck, agent."
            [0:38] (End of file)
        """
        await self.core.clean_slate()

        if not self.sat or not self.sat.is_active:
            self.core.display.update_status("NMBRS STN", "SAT OFFLINE")
            await asyncio.sleep(2)
            return "TUTORIAL_FAILED"

        self.game_state = "TUTORIAL"

        # Start the voiceover track
        self.core.audio.play("audio/tutes/numbers_tute.wav", bus_id=self.core.audio.CH_VOICE)

        self.core.display.update_header("-NMBRS STN-")
        self.core.matrix.show_icon("NUMBERS_STATION", clear=True)
        asyncio.create_task(
            self.core.synth.play_sequence(tones.WARP_CORE_IDLE, patch="PAD")
        )

        # --- [0:00 - 0:06] Overview ---
        self.core.display.update_status("NUMBERS STATION", "COLD WAR CIPHER")
        self._send_segment("STNDBY  ")
        await asyncio.sleep(6.0)

        # --- [0:06 - 0:11] Tune the band ---
        self.core.display.update_status("STEP 1: TUNE BAND", "ROTATE SWITCH")
        self._send_segment("SCANNING")

        # Simulate static/jamming (Using the new continuous noise fix)
        self.core.synth.play_note(150.0, "NOISE", duration=1.5)
        self._render_static()
        await asyncio.sleep(1.5)

        # Clear signal found
        self._render_signal_bars(level=4)
        self.core.display.update_status("TUNED: ALPHA", "SIGNAL CLEAR")
        self._send_segment("TUNED   ")
        self.core.synth.play_note(tones.note('G5'), "SUCCESS", duration=0.1)
        await asyncio.sleep(3.5)

        # --- [0:11 - 0:19] Listen to digits ---
        demo_seq = ['4', '9', '2']
        self.core.display.update_status("STEP 2: LISTEN", "DIGIT TONES PLAY")
        self._send_segment("SHFT+3  ")
        await asyncio.sleep(1.0)

        # The audio playback takes exactly 1.8s ((0.35 + 0.25) * 3)
        await self._play_digit_sequence(demo_seq)

        self.core.display.update_status("REPLAY?", "PRESS CORE DIAL")
        await asyncio.sleep(5.2)

        # --- [0:19 - 0:26] Decode ---
        demo_cipher  = 3
        demo_answer  = [str((int(d) + demo_cipher) % 10) for d in demo_seq]
        self.core.display.update_status(
            "STEP 3: DECODE",
            ", ".join(f"{d}+{demo_cipher}={(int(d)+demo_cipher)%10}" for d in demo_seq)
        )
        self._send_segment("SHFT+3  ")
        await asyncio.sleep(7.0)

        # --- [0:26 - 0:30] Type ---
        self.core.display.update_status("TYPE ON KEYPAD", "")
        typed = ""
        for ch in demo_answer:
            typed += ch
            self._send_segment(typed.ljust(len(demo_seq))[:8])
            self.core.display.update_status(
                f"CIPHER: SHIFT+{demo_cipher}",
                f"TYPED: {typed}"
            )
            self.core.synth.play_note(tones.note('C5'), "CLICK", duration=0.03)
            self._render_input_progress(typed, len(demo_seq))
            await asyncio.sleep(1.0)

        await asyncio.sleep(1.0)

        # --- [0:30 - 0:35] Submit ---
        self.core.display.update_status("STEP 4: SUBMIT", "PRESS BIG RED BTN")
        self._send_segment("SEND?   ")
        await asyncio.sleep(2.0)

        asyncio.create_task(
            self.core.synth.play_sequence(tones.SUCCESS, patch="SUCCESS")
        )
        self.core.display.update_status("DECRYPTED! +50", "TRANSMISSION SENT")
        self._send_segment("CORRECT!")
        self.core.matrix.show_icon("SUCCESS", anim_mode="PULSE", speed=3.0)
        await asyncio.sleep(3.0)

        # --- [0:35 - 0:38] Outro ---
        self.core.display.update_status("GOOD LUCK", "AGENT")

        # Wait for the voice track to finish naturally
        if hasattr(self.core.audio, 'wait_for_bus'):
            await self.core.audio.wait_for_bus(self.core.audio.CH_VOICE)
        else:
            await asyncio.sleep(3.0)

        await self.core.clean_slate()
        return "TUTORIAL_COMPLETE"

    # ------------------------------------------------------------------
    # Main game loop
    # ------------------------------------------------------------------

    async def run(self):
        """Main Numbers Station game loop."""
        self.difficulty = self.core.data.get_setting(
            "NUMBERS_STATION", "difficulty", "NORMAL"
        )
        self.variant = self.difficulty

        params = _DIFF_PARAMS.get(self.difficulty, _DIFF_PARAMS["NORMAL"])
        self._seq_length    = params["seq_length"]
        self._shift_range   = params["shift_range"]
        self._lives         = params["lives"]
        self._max_replays   = params["max_replays"]
        self._bonus_time    = params["bonus_time"]

        # Require the Industrial Satellite
        if not self.sat or not self.sat.is_active:
            self.core.display.update_status(
                "NMBRS STN", "SAT OFFLINE - ABORT"
            )
            await asyncio.sleep(2)
            return "FAILURE"

        # Intro
        self.core.display.use_standard_layout()
        self.core.display.update_status(
            "NUMBERS STATION",
            "STANDBY..."
        )
        self.core.matrix.show_icon("NUMBERS_STATION", clear=True)
        asyncio.create_task(
            self.core.synth.play_sequence(tones.WARP_CORE_IDLE, patch="PAD")
        )
        self._send_segment("STNDBY  ")
        await asyncio.sleep(2.0)

        # Initialise timer
        self._time_remaining = _GLOBAL_TIME
        self._last_tick_ms   = ticks_ms()
        self.score           = 0
        self._round          = 0

        while True:
            # Global timer check
            now = ticks_ms()
            elapsed_ms = ticks_diff(now, self._last_tick_ms)
            if elapsed_ms >= 100:
                self._time_remaining -= elapsed_ms / 1000.0
                self._last_tick_ms = now

            if self._time_remaining <= 0 or self._lives <= 0:
                break

            # Generate new round
            self._new_round()

            # Header update
            self.core.display.update_header(
                f"T:{self._time_remaining:03.0f}s LIVES:{self._lives}"
            )

            # ---- Phase 1: Tune ----
            done = await self._timed_phase(self._run_phase_tune)
            if not done:
                break
            self._tick_timer()

            # ---- Phase 2: Listen ----
            done = await self._timed_phase(self._run_phase_listen)
            if not done:
                break
            self._tick_timer()

            # ---- Phase 3: Decode ----
            round_start_time = self._time_remaining
            done = await self._timed_phase(self._run_phase_decode)
            if not done:
                break
            self._tick_timer()

            # ---- Phase 4: Submit ----
            done = await self._timed_phase(self._run_phase_submit)
            if not done:
                break
            self._tick_timer()

            # ---- Score the round ----
            if self._check_answer():
                decode_time = round_start_time - self._time_remaining
                speed_bonus = max(
                    0,
                    int(_SPEED_BONUS_THRESHOLD - decode_time) * _SPEED_BONUS_MULTIPLIER
                )
                await self._show_correct(speed_bonus)
                self._time_remaining = min(
                    _GLOBAL_TIME, self._time_remaining + self._bonus_time
                )
            else:
                await self._show_wrong()
                if self._lives <= 0:
                    break

            self._round += 1

            # Update header
            self.core.display.update_header(
                f"T:{self._time_remaining:03.0f}s LIVES:{self._lives}"
            )

        # Game over
        self._send_segment("GAMEOVER")
        return await self.game_over()

    def _tick_timer(self):
        """Snap the global timer to the latest elapsed time."""
        now = ticks_ms()
        elapsed_ms = ticks_diff(now, self._last_tick_ms)
        self._time_remaining -= elapsed_ms / 1000.0
        self._last_tick_ms = now
