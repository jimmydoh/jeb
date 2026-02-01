"""Class to manage Master Box hardware inputs."""

import digitalio
import rotaryio

from adafruit_ticks import ticks_ms, ticks_diff

class HIDManager:
    """Class to manage Master Box hardware inputs.

    Attributes:
        _btns (list): List of buttons, including the 4 face buttons and rotary encoder 'Push'.
        _btns_press_start (list): List of ints to track time pressed for the buttons.
        _hw_encoder (rotaryio.IncrementalEncoder): Hardware rotary encoder object.
    """
    def __init__(self, button_pins, estop_pin, encoder_pins):
        # Master Face Buttons (A, B, C, D) and Main Dial Button
        self._btns = [digitalio.DigitalInOut(p) for p in [*button_pins]]
        for b in self._btns:
            b.pull = digitalio.Pull.UP
        self._btns_press_start = [0, 0, 0, 0, 0]  # Long-press detection

        self._estop = digitalio.DigitalInOut(estop_pin)
        self._estop.pull = digitalio.Pull.UP

        # Main Dial - Hardware Encoder
        self._hw_encoder = rotaryio.IncrementalEncoder(encoder_pins[0], encoder_pins[1])
    @property
    def encoder_pos(self):
        """Returns the raw hardware position."""
        return self._hw_encoder.position

    def get_scaled_pos(self, multiplier=1.0, wrap=None):
        """Consistent scaling method shared with Satellite classes."""
        scaled = int(self._hw_encoder.position * multiplier)
        if wrap:
            return scaled % wrap
        return scaled

    def reset_encoder(self, value=0):
        """Sets the hardware encoder to a specific starting position."""
        self._hw_encoder.position = value

    def is_pressed(self, index, long=False, duration=2000):
        """Check if a face button is pressed (indices 0-4)."""
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
    def dial_pressed(self):
        """Returns True if the rotary encoder button is pressed."""
        return not self._btns[4].value

    @property
    def estop(self):
        """Returns True estop is pressed."""
        return not self._estop.value
