""""""

from adafruit_ticks import ticks_ms, ticks_diff
from .base import Satellite

class IndustrialSatellite(Satellite):
    """Class representing an Industrial Satellite box.

    Specific physical satellite style that includes
    toggles, keypad, rotary encoder, momentary toggles
    and 14-segment displays.

    Attributes:
        _btns (list): List of buttons, in this case a single rotary encoder 'Push'.
        _toggles (list): List of toggle switch states.
        _toggles_on_start (list): List of timers for long press detection.
        _mtoggles (list): List of momentary toggle switch states.
        _mtoggles_on_start (list): List of timers for long press detection of momentary toggle states.
        _keypad (str): Current keypad input.
        _encoder_pos (int): Rotary encoder position.
        _last_enc_a (int): Last state of encoder A pin.
        _last_enc_b (int): Last state of encoder B pin.
    """
    def __init__(self, sid):
        """Initialize an IndustrialSatellite object.

        Parameters:
            sid (str): Satellite ID.
        """
        super().__init__(sid, "INDUSTRIAL")

        # Rotary Encoder Button
        self._btns = [0]
        self._btns_press_start = [0]  # Long-press detection

        # Latching Toggles (1, 2, 3, 4)
        self._toggles = [0, 0, 0, 0]
        self._toggles_on_start = [0, 0, 0, 0]  # Long hold detection for latching toggles

        # Momentary Toggles (M1, M2)
        self._mtoggles = ["C","C"]
        self._mtoggles_on_start = [{"U":0,"D":0,"C":0}, {"U":0,"D":0,"C":0}]  # Long hold detection for momentary toggles

        # Previous value register
        self._last_latch = self._toggles[:]
        self._last_moment = self._mtoggles[:]

        # Numerical Keypad
        self._keypad = "N"

        # Rotary Encoder
        self._encoder_pos = 0
        self._last_enc_a = 1
        self._last_enc_b = 1

    def update_from_packet(self, data_str):
        """Updates the attribute states based on the received data string.

        Parameters:
            data_str (str): Comma-separated status string from satellite.

        Example:
            0,0000,CC,N,0,0
            1,1111,UU,*,1,1
        """
        try:
            self.update_heartbeat()
            data = data_str.split(",")
            self._btns = [int(x) for x in data[0]]
            self._toggles = [int(x) for x in data[1]]
            self._mtoggles = [str(x) for x in data[2]]
            self._last_latch = self._toggles[:]
            self._last_moment = self._mtoggles[:]
            new_key = data[3]
            new_enc_a = int(data[4])
            new_enc_b = int(data[5])

            # Keypad logic: Only update if a new key is pressed
            if new_key != "N":
                self._keypad = new_key

            # --- UPDATED: QUADRATURE ENCODER LOGIC ---
            # We look for a state change on Pin A
            if new_enc_a != self._last_enc_a:
                # If A matches B, it's rotating one way; otherwise, it's the other
                if new_enc_a == new_enc_b:
                    self._encoder_pos -= 1
                else:
                    self._encoder_pos += 1

            # Update last states
            self._last_enc_a = new_enc_a
            self._last_enc_b = new_enc_b

        except (IndexError, ValueError):
            print(f"Malformed packet from Sat {self.id}")

    def is_pressed(self, index, long=False, duration=2000):
        """Check if a button is pressed (indices 0)."""
        if long:
            if not self._btns[index].value:
                if self._btns_press_start[index] == 0:
                    self._btns_press_start[index] = ticks_ms()
                if ticks_diff(ticks_ms(), self._btns_press_start[index]) >= duration:
                    self._btns_press_start[index] = 0
                    return True
            else:
                self._btns_press_start[index] = 0
            return False
        return not self._btns[index].value

    @property
    def keypad(self):
        """Returns the raw hardware position."""
        return self._keypad

    def clear_key(self):
        """Consumes the current keypress so it isn't read twice."""
        self._keypad = "N"

    @property
    def encoder_pos(self):
        """Returns the raw hardware position."""
        return self._encoder_pos

    def get_scaled_encoder_pos(self, multiplier, wrap=None):
        """Get the encoder position scaled by a multiplier.

        Parameters:
            multiplier (int): Scaling factor.
            wrap (int, optional): If provided, wraps the value within this range.

        Returns:
            int: Scaled (and possibly wrapped) encoder position.
        """
        val = self._encoder_pos * multiplier
        if wrap:
            val = val % wrap
        return val

    def rest_encoder(self, value=0):
        """Resets the software-tracked encoder position."""
        self._encoder_pos = value

    def is_latching_toggled(self, index, long=False, duration=2000):
        """Check if a latching toggle is toggled 'on'.

        Parameters:
            index (int): Index of the latching toggle (0, 1, 2 or 3).
            long (bool): If True, checks for long-press.
            duration (int): Duration in ms for long-press detection.

        Returns:
            bool: True if toggled.
        """
        if self._toggles[index] != 1:
            self._toggles_on_start[index] = 0
            return False
        if long:
            if self._toggles_on_start[index] == 0:
                self._toggles_on_start[index] = ticks_ms()
            if ticks_diff(ticks_ms(), self._toggles_on_start[index]) >= duration:
                self._toggles_on_start[index] = 0
                return True
            return False
        return True

    def is_momentary_toggled(self, index, direction="U", long=False, duration=2000):
        """Check if a momentary toggle is held in a specific direction.

        Parameters:
            index (int): Index of the momentary toggle (0 or 1).
            direction (str): "U" for up, "D" for down.
            long (bool): If True, checks for long-press.
            duration (int): Duration in ms for long-press detection.

        Returns:
            bool: True if held in the specified direction.
        """
        if self._mtoggles[index] != direction:
            self._mtoggles_on_start[index][direction] = 0
            return False
        if long:
            if self._mtoggles_on_start[index][direction] == 0:
                self._mtoggles_on_start[index][direction] = ticks_ms()
            if ticks_diff(ticks_ms(), self._mtoggles_on_start[index][direction]) >= duration:
                self._mtoggles_on_start[index][direction] = 0
                return True
            return False
        return True

    def snapshot_state(self):
        """Saves current state of all toggles to compare against later."""
        self._last_latch = self._toggles[:]
        self._last_moment = self._mtoggles[:]

    def any_other_input_detected(self, index):
        """Returns True if any input OTHER than the target has changed."""
        # Check latching (excluding target)
        for i in range(4):
            if i != index and self._toggles[i] != self._last_latch[i]:
                return True
        # Check momentary
        for i in range(2):
            if (i + 4) != index and self._mtoggles[i] != "C":
                return True
        return False
