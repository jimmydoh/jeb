# File: src/modes/bunker_defuse.py
"""Bunker Defuse – Asymmetric Co-op Bomb Disposal Mode.

A "Keep Talking and Nobody Explodes"-style game that forces two players to
communicate under pressure.

Player 1 (The Expert) sits at the Core and reads the cryptic defusal manual
displayed on the OLED.  They must relay instructions verbally.

Player 2 (The Operator) sits at the Industrial Satellite and cannot see the
manual.  They must act on the Expert's instructions using only the physical
hardware.

Hardware Mapping:
    Core (Expert only):
        - 16x16 Matrix: Countdown timer ring, module wiring diagram, strike LEDs
        - OLED: Cryptic randomised defusal manual for the current module
        - Rotary Encoder (index 0): Scroll through multi-page manual entries

    Industrial Satellite (Operator only):
        - 8x Latching Toggles (0-7): WIRE module – match required ON/OFF pattern
        - Guarded Toggle (index 8): ARM module – must be raised before confirming
        - 3-Position Rotary Switch (indices 10-11): ROTARY module – set position
        - 9-Digit Keypad (index 0): CODE module – enter cipher key digits
        - Large Button (index 0): Confirm / submit action for all modules
        - 14-Segment Display: Live countdown timer and strike count

Gameplay:
    - The game generates N random modules from the module pool (difficulty-scaled).
    - The Expert reads OLED rules aloud; The Operator acts on the hardware.
    - Pressing the Big Button with the correct state solves a module.
    - Pressing the Big Button with the incorrect state costs a strike (-10 s).
    - 3 strikes = immediate game over.
    - Timer expires = game over.
    - All modules defused before time runs out = victory.
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
_TOGGLE_COUNT   = 8     # Latching toggles 0-7 (wire pattern)
_SW_ARM         = 8     # Guarded latching toggle / Master Arm
_SW_ROTARY_A    = 10    # 3-Position rotary switch: Position A
_SW_ROTARY_B    = 11    # 3-Position rotary switch: Position B
_BTN_FIRE       = 0     # Large momentary button (confirm / submit)
_ENC_CORE       = 0     # Core encoder index (manual page scroll)

# ---------------------------------------------------------------------------
# Module type identifiers
# ---------------------------------------------------------------------------
_MOD_WIRE       = "WIRE"       # Set 8 toggles to a required ON/OFF pattern
_MOD_ROTARY     = "ROTARY"     # Dial the 3-position rotary to a specific slot
_MOD_CODE       = "CODE"       # Type a numeric cipher on the keypad
_MOD_ARM        = "ARM"        # Raise the guarded toggle, then press the button
_MOD_SEQUENCE   = "SEQUENCE"   # Press the big button exactly N times

_ALL_MODULE_TYPES = [_MOD_WIRE, _MOD_ROTARY, _MOD_CODE, _MOD_ARM, _MOD_SEQUENCE]

# ---------------------------------------------------------------------------
# Game constants
# ---------------------------------------------------------------------------
_MAX_STRIKES            = 3      # Strikes before game over
_STRIKE_TIME_PENALTY    = 10.0   # Seconds deducted per strike
_POINTS_PER_MODULE      = 200    # Base points per defused module
_POINTS_PER_SECOND_LEFT = 5      # Bonus score per remaining second
_STRIKE_PENALTY_SCORE   = 100    # Score deducted per strike at end

# ---------------------------------------------------------------------------
# Difficulty tuning
# ---------------------------------------------------------------------------
_DIFF_PARAMS = {
    "NORMAL": {"global_time": 180.0, "num_modules": 4},
    "HARD":   {"global_time": 150.0, "num_modules": 5},
    "INSANE": {"global_time": 120.0, "num_modules": 6},
}

# ---------------------------------------------------------------------------
# Rotary position labels
# ---------------------------------------------------------------------------
_ROT_POS_A   = "A"
_ROT_POS_B   = "B"
_ROT_POS_CTR = "CENTER"

# ---------------------------------------------------------------------------
# Matrix layout constants
# ---------------------------------------------------------------------------
_MATRIX_SIZE     = 16
_TIMER_ROW_START = 13    # Rows 13-15 are the 3-row timer progress bar
_MODULE_ROW_END  = 12    # Rows 0-12 carry the module visual


class BunkerDefuse(GameMode):
    """Bunker Defuse – Asymmetric Co-op Bomb Disposal.

    Player 1 (Expert) reads the OLED manual; Player 2 (Operator) acts on
    the Industrial Satellite hardware.  Communication is the challenge.

    Hardware:
        Core:
            - 16x16 Matrix: Timer bar (rows 13-15), module diagram (rows 0-12)
            - OLED: Cryptic defusal manual for the current module
            - Rotary Encoder (index 0): Scroll through multi-page manuals

        Industrial Satellite (SAT-01):
            - 8x Latching Toggles (0-7): Wire configuration input
            - Guarded Toggle (index 8): Arm sequence gate
            - 3-Position Rotary Switch (indices 10-11): Rotary lock selection
            - 9-Digit Keypad (index 0): Cipher code entry
            - Large Button (index 0): Confirm / submit action
            - 14-Segment Display: Countdown timer and strike count
    """

    def __init__(self, core):
        super().__init__(core, "BUNKER DEFUSE", "Asymmetric Co-op Bomb Disposal")

        # Find the first Industrial satellite
        self.sat = None
        for sat in self.core.satellites.values():
            if sat.sat_type_name == "INDUSTRIAL":
                self.sat = sat
                break

        # Game state
        self._modules           = []
        self._current_mod_idx   = 0
        self._strikes           = 0
        self._time_remaining    = 180.0
        self._last_tick_ms      = 0

        # Button edge-detection
        self._last_btn_state    = False

        # Keypad accumulation
        self._kp_buf            = ""
        self._last_kp_snap      = ""

        # Encoder tracking (manual page scrolling on Core)
        self._last_enc_pos      = 0
        self._manual_page       = 0

        # Segment display dedup cache
        self._last_segment_text = ""

    # ------------------------------------------------------------------
    # Satellite I/O helpers
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
        """Return True if the large satellite button is currently pressed."""
        if not self.sat:
            return False
        try:
            return bool(self.sat.hid.buttons_values[idx])
        except (IndexError, AttributeError):
            return False

    def _send_segment(self, text):
        """Send up to 8 chars to the 14-segment display (cached to reduce UART)."""
        safe_text = text[:8]
        if self.sat and self._last_segment_text != safe_text:
            try:
                self.sat.send("DSP", safe_text)
                self._last_segment_text = safe_text
            except Exception:
                pass

    def _set_sat_led(self, idx, color):
        """Set a satellite NeoPixel LED colour."""
        if self.sat:
            try:
                self.sat.send("LED", f"{idx},{color.index},0.0,1.0,2")
            except Exception:
                pass

    def _get_rotary_position(self):
        """Decode the 3-position rotary switch into A / B / CENTER."""
        rot_a = self._sat_latching(_SW_ROTARY_A)
        rot_b = self._sat_latching(_SW_ROTARY_B)
        if rot_a and not rot_b:
            return _ROT_POS_A
        if not rot_a and rot_b:
            return _ROT_POS_B
        return _ROT_POS_CTR

    def _poll_keypad(self):
        """Accumulate keypad digits typed by the Operator into _kp_buf."""
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

        if len(current) > len(self._last_kp_snap):
            self._kp_buf += current[len(self._last_kp_snap):]
            self._last_kp_snap = current
        elif len(current) < len(self._last_kp_snap):
            # Key released – update snapshot only, do not clear buffer
            self._last_kp_snap = current

    # ------------------------------------------------------------------
    # Module generation
    # ------------------------------------------------------------------

    def _generate_modules(self, num_modules):
        """Return a shuffled list of ``num_modules`` randomised module dicts."""
        type_pool = (_ALL_MODULE_TYPES * ((num_modules // len(_ALL_MODULE_TYPES)) + 2))
        types = list(type_pool[:num_modules])
        random.shuffle(types)
        return [self._make_module(t) for t in types]

    def _make_module(self, mtype):
        """Create a randomised module dict for the given type identifier."""
        if mtype == _MOD_WIRE:
            return {
                "type": _MOD_WIRE,
                "required": [random.choice([True, False]) for _ in range(_TOGGLE_COUNT)],
                "solved": False,
            }
        if mtype == _MOD_ROTARY:
            position = random.choice([_ROT_POS_A, _ROT_POS_B, _ROT_POS_CTR])
            # Embed a cryptic conditional hint in the manual
            condition_vars = ["TIMER", "STRIKES", "MODULE", "TOGGLE", "CHANNEL"]
            return {
                "type": _MOD_ROTARY,
                "required_pos": position,
                "cvar": random.choice(condition_vars),
                "cval": random.randint(1, 5),
                "solved": False,
            }
        if mtype == _MOD_CODE:
            length = random.randint(3, 4)
            code = "".join(str(random.randint(1, 9)) for _ in range(length))
            return {
                "type": _MOD_CODE,
                "code": code,
                "solved": False,
            }
        if mtype == _MOD_ARM:
            confirm_count = random.randint(1, 3)
            return {
                "type": _MOD_ARM,
                "confirm_count": confirm_count,
                "press_count": 0,
                "solved": False,
            }
        if mtype == _MOD_SEQUENCE:
            target_presses = random.randint(2, 5)
            return {
                "type": _MOD_SEQUENCE,
                "target_presses": target_presses,
                "press_count": 0,
                "solved": False,
            }
        return {"type": mtype, "solved": False}

    # ------------------------------------------------------------------
    # Matrix rendering
    # ------------------------------------------------------------------

    def _render_matrix(self):
        """Render module visual (rows 0-12) and timer bar (rows 13-15)."""
        self.core.matrix.clear()
        self._render_module_visual()
        self._render_timer_bar()
        self.core.matrix.show_frame()

    def _render_module_visual(self):
        """Render a module-specific visual hint in rows 0-12."""
        if self._current_mod_idx >= len(self._modules):
            return

        mod   = self._modules[self._current_mod_idx]
        mtype = mod["type"]

        if mtype == _MOD_WIRE:
            self._render_wire_diagram(mod)
        elif mtype == _MOD_ROTARY:
            self._render_rotary_indicator(mod)
        elif mtype == _MOD_CODE:
            self._render_code_indicator()
        elif mtype == _MOD_ARM:
            self._render_arm_indicator(mod)
        elif mtype == _MOD_SEQUENCE:
            self._render_sequence_indicator(mod)

        # Strike indicator pixels: top-right corner (3 pixels)
        for i in range(_MAX_STRIKES):
            col    = _MATRIX_SIZE - 1 - i
            color  = Palette.RED if i < self._strikes else Palette.CHARCOAL
            bright = 0.9 if i < self._strikes else 0.2
            self.core.matrix.draw_pixel(col, 0, color, brightness=bright)

    def _render_wire_diagram(self, mod):
        """Draw 8 vertical wires coloured green (ON) or red (OFF)."""
        for i, req in enumerate(mod["required"]):
            col    = 3 + i
            color  = Palette.GREEN if req else Palette.RED
            # Top connector
            self.core.matrix.draw_pixel(col, 2, Palette.WHITE, brightness=0.4)
            # Wire body (rows 3-10)
            for row in range(3, 11):
                self.core.matrix.draw_pixel(col, row, color, brightness=0.7)
            # Bottom connector
            self.core.matrix.draw_pixel(col, 11, Palette.WHITE, brightness=0.4)

    def _render_rotary_indicator(self, mod):
        """Draw a simple rotary dial icon with the required position highlighted."""
        cx, cy = _MATRIX_SIZE // 2, 6
        # Dial ring
        for dx in range(-4, 5):
            for dy in range(-4, 5):
                dist = (dx * dx + dy * dy) ** 0.5
                if 3.2 <= dist <= 4.2:
                    self.core.matrix.draw_pixel(cx + dx, cy + dy,
                                                Palette.TEAL, brightness=0.4)
        # Required position marker (bright yellow dot)
        pos = mod["required_pos"]
        if pos == _ROT_POS_A:
            self.core.matrix.draw_pixel(cx - 4, cy, Palette.YELLOW, brightness=1.0)
        elif pos == _ROT_POS_B:
            self.core.matrix.draw_pixel(cx + 4, cy, Palette.YELLOW, brightness=1.0)
        else:
            self.core.matrix.draw_pixel(cx, cy - 4, Palette.YELLOW, brightness=1.0)

    def _render_code_indicator(self):
        """Draw a keypad icon indicating cipher entry is needed."""
        # Four glowing columns representing keypad digits
        for col in [3, 5, 8, 10]:
            for row in range(4, 10):
                self.core.matrix.draw_pixel(col, row, Palette.CYAN, brightness=0.5)

    def _render_arm_indicator(self, mod):
        """Draw a guard-toggle + button icon."""
        # Guard toggle pillar (left side)
        for row in range(3, 11):
            self.core.matrix.draw_pixel(5, row, Palette.ORANGE, brightness=0.7)
        # Big button (right side)
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                self.core.matrix.draw_pixel(11 + dx, 6 + dy, Palette.RED, brightness=0.9)

    def _render_sequence_indicator(self, mod):
        """Draw dots showing target presses (filled = already pressed)."""
        target  = mod["target_presses"]
        pressed = mod["press_count"]
        start_col = (_MATRIX_SIZE - target * 2) // 2
        for i in range(target):
            col   = start_col + i * 2
            color = Palette.GREEN if i < pressed else Palette.CHARCOAL
            for row in range(5, 9):
                self.core.matrix.draw_pixel(col, row, color, brightness=0.8)

    def _render_timer_bar(self):
        """Fill rows 13-15 proportionally to time remaining."""
        max_time     = _DIFF_PARAMS.get(self.difficulty, _DIFF_PARAMS["NORMAL"])["global_time"]
        total_pixels = _MATRIX_SIZE * 3   # 48 pixels across 3 rows
        filled       = int(total_pixels * max(0.0, self._time_remaining) / max_time)
        filled       = max(0, min(total_pixels, filled))

        ratio = self._time_remaining / max_time
        if ratio > 0.5:
            color = Palette.GREEN
        elif ratio > 0.25:
            color = Palette.YELLOW
        else:
            color = Palette.RED

        for i in range(filled):
            row = _TIMER_ROW_START + (i // _MATRIX_SIZE)
            col = i % _MATRIX_SIZE
            self.core.matrix.draw_pixel(col, row, color, brightness=0.6)

    # ------------------------------------------------------------------
    # OLED manual rendering
    # ------------------------------------------------------------------

    def _update_oled_manual(self):
        """Write the current module's defusal manual page to the Core OLED."""
        if self._current_mod_idx >= len(self._modules):
            return

        mod    = self._modules[self._current_mod_idx]
        total  = len(self._modules)
        mod_num = self._current_mod_idx + 1
        header  = f"MOD {mod_num}/{total} S:{self._strikes}/{_MAX_STRIKES}"

        mtype = mod["type"]
        if mtype == _MOD_WIRE:
            lines = self._wire_manual(mod)
        elif mtype == _MOD_ROTARY:
            lines = self._rotary_manual(mod)
        elif mtype == _MOD_CODE:
            lines = self._code_manual(mod)
        elif mtype == _MOD_ARM:
            lines = self._arm_manual(mod)
        elif mtype == _MOD_SEQUENCE:
            lines = self._sequence_manual(mod)
        else:
            lines = ["UNKNOWN", "MODULE TYPE"]

        # Page through lines (2 per screen), scroll via encoder
        total_pages = (len(lines) + 1) // 2
        page        = self._manual_page % max(1, total_pages)
        idx         = page * 2
        line1       = lines[idx]     if idx     < len(lines) else ""
        line2       = lines[idx + 1] if idx + 1 < len(lines) else ""

        self.core.display.update_header(header)
        self.core.display.update_status(line1, line2)

    def _wire_manual(self, mod):
        """Return OLED lines for a WIRE module."""
        on_idx  = ",".join(str(i) for i, v in enumerate(mod["required"]) if v)     or "NONE"
        off_idx = ",".join(str(i) for i, v in enumerate(mod["required"]) if not v) or "NONE"
        return [
            "WIRE CONFIG",
            f"ON : {on_idx}",
            f"OFF: {off_idx}",
            "THEN PRESS BTN",
        ]

    def _rotary_manual(self, mod):
        """Return OLED lines for a ROTARY module."""
        pos_label = {_ROT_POS_A: "POS-A", _ROT_POS_B: "POS-B", _ROT_POS_CTR: "CENTER"}
        label     = pos_label.get(mod["required_pos"], mod["required_pos"])
        return [
            "ROTARY LOCK",
            f"IF {mod['cvar']}>{mod['cval']}:",
            f"  SET {label}",
            "ELSE: CENTER",
            "THEN PRESS BTN",
        ]

    def _code_manual(self, mod):
        """Return OLED lines for a CODE module."""
        code      = mod["code"]
        scrambled = "".join(reversed(code))
        return [
            "CIPHER KEY",
            f"CODE: {code}",
            f"REV : {scrambled}",
            "ENTER + BTN",
        ]

    def _arm_manual(self, mod):
        """Return OLED lines for an ARM module."""
        count = mod["confirm_count"]
        return [
            "ARM SEQUENCE",
            "1. LIFT GUARD",
            f"2. BTN x{count}",
            "ORDER MATTERS",
        ]

    def _sequence_manual(self, mod):
        """Return OLED lines for a SEQUENCE module."""
        target = mod["target_presses"]
        return [
            "PRESS SEQUENCE",
            f"BTN x{target} TIMES",
            "COUNT CAREFULLY",
            "NO MORE NO LESS",
        ]

    # ------------------------------------------------------------------
    # Module validation helpers
    # ------------------------------------------------------------------

    def _check_wire_module(self, mod):
        """Return True if all 8 toggle states match the required pattern."""
        for i, req in enumerate(mod["required"]):
            if self._sat_latching(i) != req:
                return False
        return True

    def _check_rotary_module(self, mod):
        """Return True if the rotary switch is in the required position."""
        return self._get_rotary_position() == mod["required_pos"]

    # ------------------------------------------------------------------
    # Timer helpers
    # ------------------------------------------------------------------

    def _tick_timer(self):
        """Deduct elapsed time from _time_remaining."""
        now                  = ticks_ms()
        elapsed              = ticks_diff(now, self._last_tick_ms) / 1000.0
        self._last_tick_ms   = now
        self._time_remaining -= elapsed

    def _apply_strike(self):
        """Record a strike and apply the time penalty."""
        self._strikes        += 1
        self._time_remaining -= _STRIKE_TIME_PENALTY

    # ------------------------------------------------------------------
    # Tutorial
    # ------------------------------------------------------------------

    async def run_tutorial(self):
        """
        Guided walkthrough of Bunker Defuse mechanics (~30 seconds).

        The Voiceover Script (audio/tutes/bunker_tute.wav) would read:
            [0:00] "Welcome to Bunker Defuse. This is a two-player asymmetric game."
            [0:04] "Player one is the Expert. They read the instructions on this screen."
            [0:08] "Player two is the Operator. They can only touch the satellite."
            [0:13] "Wire modules: the Expert reads which toggles must be on or off."
            [0:17] "Rotary modules: dial to the correct position, then press the button."
            [0:21] "Code modules: enter the cipher on the keypad, then press confirm."
            [0:24] "Arm modules: lift the guard, then press the button the right number of times."
            [0:28] "Three strikes, and the bomb explodes. Communicate clearly!"
            [0:32] (End of file)
        """
        await self.core.clean_slate()

        if not self.sat or not self.sat.is_active:
            self.core.display.update_status("BUNKER DEFUSE", "SAT OFFLINE - ABORT")
            await asyncio.sleep(2)
            return "TUTORIAL_FAILED"

        self.game_state = "TUTORIAL"

        self.core.display.update_header("BUNKER DEFUSE")
        self.core.display.update_status("ASYMMETRIC CO-OP", "STAND BY...")
        self.core.matrix.show_icon("BUNKER_DEFUSE", clear=True)
        self.core.buzzer.play_sequence(tones.POWER_UP)
        await asyncio.sleep(3.0)

        # Roles
        self.core.display.update_status("PLAYER 1: EXPERT", "READ THIS SCREEN")
        await asyncio.sleep(3.0)
        self.core.display.update_status("PLAYER 2: OPERATOR", "USE THE SATELLITE")
        await asyncio.sleep(3.0)

        # Wire module demo
        self.core.display.update_header("MODULE: WIRES")
        demo_mod = self._make_module(_MOD_WIRE)
        demo_mod["required"] = [True, False, True, False, True, False, False, False]
        self._modules         = [demo_mod]
        self._current_mod_idx = 0
        self._time_remaining  = 180.0
        self._strikes         = 0
        self.difficulty       = "NORMAL"
        self._render_matrix()
        self.core.display.update_status("WIRE CONFIG", "ON:0,2,4 OFF:1,3,5,6,7")
        await asyncio.sleep(4.0)

        # Rotary module demo
        self.core.display.update_header("MODULE: ROTARY")
        self.core.display.update_status("ROTARY LOCK", "DIAL TO POS-A THEN BTN")
        await asyncio.sleep(3.0)

        # Code module demo
        self.core.display.update_header("MODULE: CIPHER")
        self.core.display.update_status("CIPHER KEY", "ENTER 4712 + BTN")
        await asyncio.sleep(3.0)

        # Arm module demo
        self.core.display.update_header("MODULE: ARM")
        self.core.display.update_status("LIFT GUARD FIRST", "THEN PRESS BTN x2")
        await asyncio.sleep(3.0)

        # Strikes & timer
        self.core.display.update_header("STRIKES & TIMER")
        self.core.display.update_status("3 STRIKES = BOOM", "WRONG=-10s PENALTY")
        self.core.buzzer.play_sequence(tones.ERROR)
        await asyncio.sleep(3.0)

        self.core.display.update_header("GOOD LUCK!")
        self.core.display.update_status("COMMUNICATE!", "OR GO BOOM!")
        self.core.synth.play_note(880.0, "SUCCESS", duration=0.3)
        await asyncio.sleep(3.0)

        await self.core.clean_slate()
        return "TUTORIAL_COMPLETE"

    # ------------------------------------------------------------------
    # Main game loop
    # ------------------------------------------------------------------

    async def run(self):
        """Main Bunker Defuse game loop."""
        self.difficulty = self.core.data.get_setting("BUNKER_DEFUSE", "difficulty", "NORMAL")
        self.variant    = self.difficulty

        params              = _DIFF_PARAMS.get(self.difficulty, _DIFF_PARAMS["NORMAL"])
        self._time_remaining = params["global_time"]
        num_modules          = params["num_modules"]

        if not self.sat or not self.sat.is_active:
            self.core.display.update_status("BUNKER DEFUSE", "SAT OFFLINE - ABORT")
            await asyncio.sleep(2)
            return "FAILURE"

        # Initialise game state
        self._modules           = self._generate_modules(num_modules)
        self._current_mod_idx   = 0
        self._strikes           = 0
        self._last_btn_state    = False
        self._kp_buf            = ""
        self._last_kp_snap      = ""
        self._last_enc_pos      = 0
        self._manual_page       = 0
        self._last_segment_text = ""
        self.score              = 0

        # Intro splash
        self.core.display.use_standard_layout()
        self.core.display.update_status("BUNKER DEFUSE", "DEFUSE THE BOMB!")
        self.core.matrix.show_icon("BUNKER_DEFUSE", clear=True)
        self.core.synth.play_note(440.0, "ALARM", duration=0.5)
        await asyncio.sleep(2.0)

        self._last_tick_ms = ticks_ms()

        # ---- Main loop ----
        while self._current_mod_idx < len(self._modules):

            # Timer
            self._tick_timer()

            # Lose conditions
            if self._time_remaining <= 0:
                return await self._explode()
            if self._strikes >= _MAX_STRIKES:
                return await self._explode()

            mod = self._modules[self._current_mod_idx]

            # Encoder: scroll manual pages (Core encoder)
            try:
                enc_now = self.core.hid.encoder_positions[_ENC_CORE]
            except (IndexError, AttributeError):
                enc_now = self._last_enc_pos
            if enc_now != self._last_enc_pos:
                delta = enc_now - self._last_enc_pos
                self._manual_page = max(0, self._manual_page + (1 if delta > 0 else -1))
                self._last_enc_pos = enc_now

            # Button edge detection
            btn_now    = self._sat_button(_BTN_FIRE)
            btn_rising = btn_now and not self._last_btn_state
            self._last_btn_state = btn_now

            # Keypad accumulation
            self._poll_keypad()

            # Module logic
            result = await self._process_module(mod, btn_rising)
            if result == "SOLVED":
                mod["solved"] = True
                await self._on_module_solved()
                self._current_mod_idx += 1
                self._manual_page  = 0
                self._kp_buf       = ""
                self._last_kp_snap = ""
                continue

            # Update OLED manual
            self._update_oled_manual()

            # Segment display: live timer + strikes
            mins     = int(max(0, self._time_remaining)) // 60
            secs     = int(max(0, self._time_remaining)) % 60
            seg_text = f"{mins}:{secs:02d} S{self._strikes}"
            self._send_segment(seg_text)

            # Matrix
            self._render_matrix()

            await asyncio.sleep(0.05)

        # ---- All modules solved ----
        time_bonus      = int(max(0.0, self._time_remaining) * _POINTS_PER_SECOND_LEFT)
        modules_score   = len(self._modules) * _POINTS_PER_MODULE
        strike_penalty  = self._strikes * _STRIKE_PENALTY_SCORE
        self.score      = max(0, modules_score + time_bonus - strike_penalty)

        return await self.victory()

    # ------------------------------------------------------------------
    # Module processing
    # ------------------------------------------------------------------

    async def _process_module(self, mod, btn_rising):
        """Process one loop tick for the active module.

        Returns ``'SOLVED'`` when the module is correctly completed, otherwise
        ``None``.  Incorrect submissions trigger a strike.
        """
        mtype = mod["type"]

        if mtype == _MOD_WIRE:
            # Operator sets toggles then presses the button to submit
            if btn_rising:
                if self._check_wire_module(mod):
                    return "SOLVED"
                await self._on_strike("WRONG WIRES!")
            return None

        if mtype == _MOD_ROTARY:
            # Operator dials rotary then presses button to submit
            if btn_rising:
                if self._check_rotary_module(mod):
                    return "SOLVED"
                await self._on_strike("WRONG POS!")
            return None

        if mtype == _MOD_CODE:
            # Operator types digits on keypad then presses button
            if btn_rising:
                entered = self._kp_buf
                if entered == mod["code"]:
                    return "SOLVED"
                await self._on_strike("WRONG CODE!")
                # Clear buffer so the Operator can try again
                self._kp_buf       = ""
                self._last_kp_snap = ""
            return None

        if mtype == _MOD_ARM:
            # Guarded toggle must be UP before button presses are counted
            arm_up = self._sat_latching(_SW_ARM)
            if btn_rising:
                if arm_up:
                    mod["press_count"] = mod.get("press_count", 0) + 1
                    if mod["press_count"] >= mod["confirm_count"]:
                        return "SOLVED"
                else:
                    await self._on_strike("ARM FIRST!")
            return None

        if mtype == _MOD_SEQUENCE:
            # Count exact button presses; over-pressing triggers a strike
            if btn_rising:
                mod["press_count"] = mod.get("press_count", 0) + 1
                if mod["press_count"] == mod["target_presses"]:
                    return "SOLVED"
                if mod["press_count"] > mod["target_presses"]:
                    await self._on_strike("TOO MANY!")
                    mod["press_count"] = 0
            return None

        return None

    # ------------------------------------------------------------------
    # Feedback helpers
    # ------------------------------------------------------------------

    async def _on_module_solved(self):
        """Flash green and show solved feedback."""
        self.core.synth.play_note(1400.0, "SUCCESS", duration=0.1)
        remaining = len(self._modules) - self._current_mod_idx - 1
        self.core.display.update_header("MODULE DEFUSED!")
        self.core.display.update_status(
            f"+{_POINTS_PER_MODULE} PTS",
            f"{remaining} REMAINING",
        )
        # Green flash on matrix
        self.core.matrix.fill(Palette.GREEN, show=True)
        await asyncio.sleep(0.3)
        self.core.matrix.clear()
        self.core.matrix.show_frame()
        await asyncio.sleep(1.0)

        # Light up a green LED on the satellite for each solved module
        try:
            solved_count = self._current_mod_idx + 1
            if solved_count <= _TOGGLE_COUNT:
                self._set_sat_led(solved_count - 1, Palette.GREEN)
        except Exception:
            pass

    async def _on_strike(self, reason=""):
        """Flash red, apply strike penalty, and update displays."""
        self._apply_strike()
        self.core.synth.play_note(220.0, "ALARM", duration=0.3)
        self.core.display.update_header(f"STRIKE! {self._strikes}/{_MAX_STRIKES}")
        self.core.display.update_status(reason, f"-{int(_STRIKE_TIME_PENALTY)}s PENALTY")
        # Red flash on matrix
        self.core.matrix.fill(Palette.RED, show=True)
        await asyncio.sleep(0.5)
        self.core.matrix.clear()
        self.core.matrix.show_frame()
        await asyncio.sleep(0.8)

    async def _explode(self):
        """Handle bomb explosion (timer expired or max strikes reached)."""
        self.core.audio.stop_all()
        self.core.buzzer.stop()

        defused = self._current_mod_idx
        total   = len(self._modules)

        self.core.display.update_header("BOOM! GAME OVER")
        self.core.display.update_status(
            f"DEFUSED {defused}/{total}",
            f"SCORE: {self.score}",
        )
        # Explosion animation: red → orange → red → dark
        self.core.matrix.fill(Palette.RED,    show=True)
        self.core.synth.play_sequence(tones.POWER_FAIL, patch="ALARM")
        await asyncio.sleep(0.3)
        self.core.matrix.fill(Palette.ORANGE, show=True)
        await asyncio.sleep(0.2)
        self.core.matrix.fill(Palette.RED,    show=True)
        await asyncio.sleep(0.2)
        self.core.matrix.clear()
        self.core.matrix.show_frame()
        await asyncio.sleep(2.0)

        return await self.game_over()
