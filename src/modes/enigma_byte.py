# File: src/modes/enigma_byte.py
"""Enigma Byte – Deductive Logic Puzzle Game Mode.

A Mastermind-style logic puzzle where the player must deduce three hidden
8-bit codes (one per layer) using trial, error, and binary feedback.

Hardware:
    Core:
        - 16x16 Matrix: Feedback board (green=exact match, yellow=right
          value/wrong position count), layer status and remaining guesses
        - OLED: Active layer, guess count, and keypad notepad

    Industrial Satellite (SAT-01):
        - 8x Latching Toggles (0-7): Set the 8-bit guess
        - Big Red Button (index 0): Submit current toggle state as a guess
        - 3-Position Rotary Switch (indices 10-11): Select active layer (0-2)
        - 9-Digit Keypad: Physical notepad – typed digits appear on the OLED
        - 14-Segment Display: Active layer and guess count

Gameplay:
    - Three independent hidden 8-bit codes must all be cracked to win.
    - Use the rotary switch to choose which layer to work on.
    - Set the 8 latching toggles to your guess and press the big red button.
    - The matrix shows feedback for the active layer's guess history:
        * Green pixels = bit is correct value AND in the correct position
        * Yellow pixels = correct value count but displaced (wrong positions)
    - The keypad acts as a physical notepad; digits appear on the OLED.
    - Solve all three layers within the per-layer guess budget to win.

Scoring:
    - 100 base points per layer solved.
    - 10 bonus points per remaining guess when a layer is solved.
    - High score tracked per difficulty variant.
"""

import asyncio
import random

from utilities.palette import Palette
from utilities import tones

from .game_mode import GameMode

# ---------------------------------------------------------------------------
# Hardware indices (mirror sat_01_driver layout)
# ---------------------------------------------------------------------------
_TOGGLE_COUNT   = 8    # Latching toggles 0-7: current 8-bit guess
_BTN_SUBMIT     = 0    # Big red button: submit guess
_SW_ROTARY_A    = 10   # 3-position rotary switch – position A (index 10)
_SW_ROTARY_B    = 11   # 3-position rotary switch – position B (index 11)

# ---------------------------------------------------------------------------
# Game constants
# ---------------------------------------------------------------------------
_LAYER_COUNT            = 3    # Independent bytes to crack simultaneously
_POINTS_PER_SOLVE       = 100  # Base points awarded per solved layer
_POINTS_PER_GUESS_LEFT  = 10   # Bonus per unused guess when a layer is solved

# Matrix layout rows
_ROW_HISTORY_START  = 0    # First row of guess-history display
_ROW_HISTORY_END    = 11   # Last row of guess-history display (12 rows visible)
_ROW_TOGGLE_PREVIEW = 13   # Live preview of current toggle states
_ROW_LAYER_STATUS   = 14   # Layer solve-status indicator row
_ROW_GUESS_BAR      = 15   # Remaining-guesses progress bar

# ---------------------------------------------------------------------------
# Difficulty tuning
# ---------------------------------------------------------------------------
_DIFF_PARAMS = {
    "NORMAL": {
        "max_guesses": 10,
        "points_multiplier": 1,
    },
    "HARD":   {
        "max_guesses": 8,
        "points_multiplier": 3
    },
    "INSANE": {
        "max_guesses": 6,
        "points_multiplier": 5
    },
}

# ---------------------------------------------------------------------------
# Phase identifiers
# ---------------------------------------------------------------------------
_PHASE_INPUT    = "INPUT"
_PHASE_FEEDBACK = "FEEDBACK"


class EnigmaByte(GameMode):
    """Enigma Byte – Deductive Logic game mode.

    The player cracks three hidden 8-bit codes using Mastermind-style
    binary feedback on the LED matrix.

    Hardware:
        Core:
            - 16x16 Matrix: Guess-history feedback board + layer status
            - OLED: Layer/guess info and keypad notepad

        Industrial Satellite (SAT-01):
            - 8x Latching Toggles (0-7): 8-bit guess input
            - Big Red Button (index 0): Submit guess
            - 3-Position Rotary Switch (indices 10-11): Layer selection
            - 9-Digit Keypad: Numeric notepad (shown on OLED)
            - 14-Segment Display: Active layer and guess count
    """
    def __init__(self, core):
        super().__init__(core, "ENIGMA BYTE", "Deductive Logic Puzzle")
        self.sat = None
        for sat in self.core.satellites.values():
            if sat.sat_type_name == "INDUSTRIAL":
                self.sat = sat
                break

        # Per-layer game state
        self._secrets  = [[] for _ in range(_LAYER_COUNT)]   # hidden bits
        self._guesses  = [[] for _ in range(_LAYER_COUNT)]   # [(bits, G, Y)]
        self._solved   = [False] * _LAYER_COUNT
        self._failed   = [False] * _LAYER_COUNT

        self._active_layer    = 1   # Default: rotary centered → layer 1
        self._max_guesses     = 10
        self._notes           = ""
        self._last_keypad_snap = ""
        self._last_btn_state   = False
        self._phase            = _PHASE_INPUT
        self._last_segment_text = ""

    # ------------------------------------------------------------------
    # Satellite helpers
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
        """Return True if the satellite large button is pressed."""
        if not self.sat:
            return False
        try:
            return bool(self.sat.hid.buttons_values[idx])
        except (IndexError, AttributeError):
            return False

    def _send_segment(self, text):
        """Send text to the satellite 14-segment display."""
        safe_text = text[:8]
        if self.sat and self._last_segment_text != safe_text:
            try:
                self.sat.send("DSP", safe_text)
                self._last_segment_text = safe_text
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Layer / guess helpers
    # ------------------------------------------------------------------

    def _get_layer(self):
        """Decode the 3-position rotary switch to a layer index (0, 1, or 2)."""
        rot_a = self._sat_latching(_SW_ROTARY_A)
        rot_b = self._sat_latching(_SW_ROTARY_B)
        if rot_a and not rot_b:
            return 0
        if not rot_a and rot_b:
            return 2
        return 1  # center (both off) or undefined → middle layer

    def _get_current_guess(self):
        """Read the 8 latching toggles as a list of booleans (the current guess)."""
        return [self._sat_latching(i) for i in range(_TOGGLE_COUNT)]

    def _compute_feedback(self, guess, secret):
        """Compute Mastermind feedback for a binary guess.

        Returns:
            (greens, yellows): count of exact-match bits and count of
            correct-value-but-wrong-position bits using standard rules.
        """
        n = len(secret)
        greens = sum(1 for i in range(n) if guess[i] == secret[i])

        # Total value-matches across all positions (greens + eligible yellows)
        secret_ones = sum(1 for b in secret if b)
        guess_ones  = sum(1 for b in guess  if b)
        value_matches = (min(guess_ones, secret_ones) +
                         min(n - guess_ones, n - secret_ones))
        yellows = value_matches - greens
        return greens, yellows

    # ------------------------------------------------------------------
    # Matrix rendering
    # ------------------------------------------------------------------

    def _render_matrix(self):
        """Render the full feedback board for the active layer."""
        self.core.matrix.clear()
        w = self.core.matrix.width
        layer = self._active_layer
        guesses = self._guesses[layer]

        # --- Guess history (rows 0-11, newest guess at the bottom) ---
        max_visible = _ROW_HISTORY_END - _ROW_HISTORY_START + 1
        start_idx = max(0, len(guesses) - max_visible)
        for row_offset, (_, greens, yellows) in enumerate(guesses[start_idx:]):
            row = _ROW_HISTORY_START + row_offset
            col = 0
            for _ in range(greens):
                self.core.matrix.draw_pixel(col, row, Palette.GREEN, brightness=0.9)
                col += 1
            for _ in range(yellows):
                self.core.matrix.draw_pixel(col, row, Palette.YELLOW, brightness=0.9)
                col += 1

        # --- Row 13: Live toggle-state preview (dim cyan/charcoal) ---
        current = self._get_current_guess()
        for i, bit in enumerate(current):
            if bit:
                self.core.matrix.draw_pixel(i, _ROW_TOGGLE_PREVIEW,
                                            Palette.CYAN, brightness=0.3)

        # --- Row 14: Layer solve-status dots (3 evenly spaced) ---
        spacing = w // _LAYER_COUNT
        for i in range(_LAYER_COUNT):
            if self._solved[i]:
                color = Palette.GREEN
            elif self._failed[i]:
                color = Palette.RED
            elif i == self._active_layer:
                color = Palette.YELLOW
            else:
                color = Palette.CYAN
            col = i * spacing + spacing // 2
            self.core.matrix.draw_pixel(col, _ROW_LAYER_STATUS, color, brightness=0.8)

        # --- Row 15: Remaining-guesses bar (8 pixels) ---
        used = len(guesses)
        for i in range(_TOGGLE_COUNT):
            if i < self._max_guesses - used:
                self.core.matrix.draw_pixel(i, _ROW_GUESS_BAR,
                                            Palette.CYAN, brightness=0.4)
            elif i < self._max_guesses:
                self.core.matrix.draw_pixel(i, _ROW_GUESS_BAR,
                                            Palette.RED, brightness=0.3)



    # ------------------------------------------------------------------
    # Notepad (keypad → OLED)
    # ------------------------------------------------------------------

    def _poll_notes(self):
        """Poll the satellite keypad and accumulate typed characters as notes."""
        if not self.sat:
            return
        try:
            keypads = self.sat.hid.keypad_values
            if keypads:
                current = "".join(
                    str(k) for k in keypads[0] if k is not None and str(k).isdigit()
                )
            else:
                current = ""
        except (IndexError, AttributeError):
            return

        if len(current) > len(self._last_keypad_snap):
            new_chars = current[len(self._last_keypad_snap):]
            self._notes += new_chars
            if len(self._notes) > 20:
                self._notes = self._notes[-20:]
            self._last_keypad_snap = current
        elif len(current) < len(self._last_keypad_snap):
            # Key released – update snapshot but do not clear notes
            self._last_keypad_snap = current

    # ------------------------------------------------------------------
    # Tutorial
    # ------------------------------------------------------------------

    async def run_tutorial(self):
        """
        Guided demonstration of an Enigma Byte session.

        The Voiceover Script (audio/tutes/enigma_tute.wav) ~ 21 seconds:
            [0:00] "Welcome to Enigma Byte. A test of deductive logic."
            [0:03] "You must crack three separate eight-bit codes. Use the rotary switch to change layers."
            [0:06] "Set your guess using the eight physical toggles."
            [0:09] "Then, press the big red button to submit your sequence."
            [0:11] "The matrix provides feedback. Green means right value, right place. Yellow means right value, wrong place."
            [0:14] "Use the numeric keypad to type physical notes onto your screen."
            [0:17] "Solve all three layers before you run out of guesses to win. Good luck."
            [0:21] (End of file)
        """
        await self.core.clean_slate()

        if not self.sat or not self.sat.is_active:
            self.core.display.update_status("ENIGMA BYTE", "SAT OFFLINE - ABORT")
            await asyncio.sleep(2)
            return "TUTORIAL_FAILED"

        self.game_state = "TUTORIAL"

        # Show intro splash
        self.core.display.update_header("ENIGMA BYTE")
        self.core.display.update_status("DEDUCTIVE LOGIC", "STAND BY")
        self.core.matrix.show_icon("ENIGMA_BYTE", clear=True)
        self.core.buzzer.play_sequence(tones.POWER_UP)
        await asyncio.sleep(3.0)

        # Explain layers and rotary switch
        self.core.display.update_status("3 LAYERS TO CRACK", "USE ROTARY SWITCH")
        self._send_segment("LAYER 1 ")
        await asyncio.sleep(3.0)

        # Explain toggle input
        self.core.display.update_status("SET 8-BIT GUESS", "FLIP TOGGLES 0-7")
        self._send_segment("GUESS   ")
        # Simulate a guess of alternating bits
        demo_guess = [True, False, True, False, True, False, True, False]
        try:
            for i, bit in enumerate(demo_guess):
                color = Palette.CYAN.index if bit else Palette.RED.index
                self.sat.send("LED", f"{i},{color},0.0,0.6,2")
        except Exception:
            pass
        await asyncio.sleep(3.0)

        # Explain button submit
        self.core.display.update_status("PRESS BIG BUTTON", "TO SUBMIT GUESS")
        self._send_segment("SUBMIT  ")
        self.core.buzzer.play_sequence(tones.BEEP)
        await asyncio.sleep(2.0)

        # Demonstrate matrix feedback
        self.core.display.update_status("GREEN=RIGHT POS", "YELLOW=WRONG POS")
        self.core.matrix.clear()
        # Simulate 4 greens and 2 yellows for a demo guess
        for c in range(4):
            self.core.matrix.draw_pixel(c, 0, Palette.GREEN, brightness=0.9)
        for c in range(4, 6):
            self.core.matrix.draw_pixel(c, 0, Palette.YELLOW, brightness=0.9)

        await asyncio.sleep(3.0)

        # Explain notepad
        self.core.display.update_status("USE KEYPAD AS", "NOTEPAD ON OLED")
        self._send_segment("NOTES   ")
        await asyncio.sleep(3.0)

        # Explain win condition
        self.core.display.update_status("SOLVE ALL 3 LAYERS", "TO DEFUSE SYSTEM")
        self.core.matrix.show_icon("ENIGMA_BYTE", clear=True)
        self.core.buzzer.play_sequence(tones.SUCCESS)
        await asyncio.sleep(3.0)

        # Clear LEDs
        try:
            for i in range(_TOGGLE_COUNT):
                self.sat.send("LED", f"{i},{Palette.OFF.index},0.0,0.0,2")
        except Exception:
            pass

        await self.core.audio.wait_for_bus(self.core.audio.CH_VOICE)

        await self.core.clean_slate()
        return "TUTORIAL_COMPLETE"

    # ------------------------------------------------------------------
    # Main game loop
    # ------------------------------------------------------------------

    async def run(self):
        """Main Enigma Byte game loop."""
        self.difficulty = self.core.data.get_setting("ENIGMA_BYTE", "difficulty", "NORMAL")
        self.variant = self.difficulty

        params = _DIFF_PARAMS.get(self.difficulty, _DIFF_PARAMS["NORMAL"])
        self._max_guesses = params["max_guesses"]

        # Satellite check
        if not self.sat or not self.sat.is_active:
            self.core.display.update_status("ENIGMA BYTE", "SAT OFFLINE - ABORT")
            await asyncio.sleep(2)
            return "FAILURE"

        # Generate secrets
        for i in range(_LAYER_COUNT):
            self._secrets[i] = [random.choice([True, False])
                                 for _ in range(_TOGGLE_COUNT)]
        self._guesses  = [[] for _ in range(_LAYER_COUNT)]
        self._solved   = [False] * _LAYER_COUNT
        self._failed   = [False] * _LAYER_COUNT
        self._notes           = ""
        self._last_keypad_snap = ""
        self._last_btn_state   = False
        self.score = 0

        # Intro
        self.core.display.use_standard_layout()
        self.core.display.update_status("ENIGMA BYTE", "CRACK THE CODES...")
        self.core.matrix.show_icon("ENIGMA_BYTE", clear=True)
        self.core.synth.play_note(440.0, "SCANNER", duration=0.3)
        await asyncio.sleep(2.0)

        self._active_layer = self._get_layer()
        self._render_matrix()

        # Main loop
        while True:
            # --- Layer selection via rotary ---
            new_layer = self._get_layer()
            if new_layer != self._active_layer:
                self._active_layer = new_layer
                self._render_matrix()

            # --- Keypad notepad ---
            self._poll_notes()

            # --- Determine current layer state ---
            layer = self._active_layer
            guesses_used = len(self._guesses[layer])

            # --- OLED status ---
            notes_str = self._notes[-16:] if self._notes else "--------"
            if self._solved[layer]:
                layer_info = f"L{layer} SOLVED!"
            elif self._failed[layer]:
                layer_info = f"L{layer} FAILED"
            else:
                layer_info = f"L{layer} G:{guesses_used}/{self._max_guesses}"
            self.core.display.update_status(layer_info, f"PAD:{notes_str}")

            # --- Segment display ---
            self._send_segment(f"L{layer} {guesses_used:02d}/{self._max_guesses:02d}")

            # --- Button edge detection (submit guess) ---
            btn_now = self._sat_button(_BTN_SUBMIT)
            rising_edge = btn_now and not self._last_btn_state
            self._last_btn_state = btn_now

            if rising_edge and not self._solved[layer] and not self._failed[layer]:
                await self._submit_guess(layer)

            # --- Win / lose checks ---
            if all(self._solved):
                # All layers cracked – victory
                break

            if any(self._failed):
                # A layer has been exhausted – defeat
                return await self.game_over()

            await asyncio.sleep(0.05)

        # Victory – compute score and celebrate
        points_multiplier = _DIFF_PARAMS.get(self.difficulty, _DIFF_PARAMS["NORMAL"])["points_multiplier"]
        for i in range(_LAYER_COUNT):
            if self._solved[i]:
                remaining = self._max_guesses - len(self._guesses[i])
                self.score += _POINTS_PER_SOLVE + remaining * (_POINTS_PER_GUESS_LEFT * points_multiplier)

        return await self.victory()

    async def _submit_guess(self, layer):
        """Process the current toggle state as a guess for the given layer."""
        guess  = self._get_current_guess()
        secret = self._secrets[layer]
        greens, yellows = self._compute_feedback(guess, secret)

        self._guesses[layer].append((guess, greens, yellows))

        if greens == _TOGGLE_COUNT:
            # Layer solved!
            self._solved[layer] = True
            self.core.synth.play_note(1200.0, "SUCCESS", duration=0.15)
            self._send_segment(f"L{layer} OK!  ")
            self.core.display.update_status(f"LAYER {layer} SOLVED!", "CODE CRACKED!")
            # Flash the matrix green
            self.core.matrix.fill(Palette.GREEN, show=True)
            await asyncio.sleep(0.3)
            self._render_matrix()
        else:
            # Show feedback
            asyncio.create_task(
                self.core.synth.play_sequence(tones.UI_TICK, patch="CLICK")
            )
            self._render_matrix()

            # Check if this layer is now exhausted
            if len(self._guesses[layer]) >= self._max_guesses:
                self._failed[layer] = True
                self._send_segment(f"L{layer} FAIL ")
                self.core.display.update_status(
                    f"LAYER {layer} FAILED!",
                    f"CODE: {''.join('1' if b else '0' for b in secret)}"
                )
                self.core.matrix.fill(Palette.RED, show=True)
                await asyncio.sleep(1.5)
                self._render_matrix()
