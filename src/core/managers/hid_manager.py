"""Class to manage Master Box hardware inputs."""

import digitalio
import keypad
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
        self._keys = keypad.Keys(button_pins, value_when_pressed=False, pull=True)
        self._key_states = [0] * len(button_pins)
        self._key_tapped = [False] * len(button_pins)

        self._estop = digitalio.DigitalInOut(estop_pin)
        self._estop.pull = digitalio.Pull.UP

        # Main Dial - Hardware Encoder
        self._hw_encoder = rotaryio.IncrementalEncoder(encoder_pins[0], encoder_pins[1])
    @property
    def encoder_pos(self):
        """Returns the raw hardware position."""
        return self._hw_encoder.position

    def get_scaled_encoder_pos(self, multiplier=1.0, wrap=None):
        """Consistent scaling method shared with Satellite classes."""
        scaled = int(self._hw_encoder.position * multiplier)
        if wrap:
            return scaled % wrap
        return scaled

    def reset_encoder(self, value=0):
        """Sets the hardware encoder to a specific starting position."""
        self._hw_encoder.position = value

    def _process_events(self):
        """Internal helper to process keypad events."""
        event = keypad.Event()
        while self._keys.events.get_into(event):
            key_idx = event.key_number
            now = ticks_ms()

            if event.pressed:
                self._key_states[key_idx] = now

            elif event.released:
                start_time = self._key_states[key_idx]
                if start_time > 0:
                    elapsed = ticks_diff(now, start_time)
                    if elapsed < 500:
                        self._key_tapped[key_idx] = True

                self._key_states[key_idx] = 0

    def is_pressed(self, index, long=False, duration=2000, action=None): # action: "hold" | "tap"
        """Check if a face button is pressed (indices 0-4)."""
        self._process_events()
        press_start_time = self._key_states[index]

        if press_start_time == 0:
            return False

        if long or action == "hold":
            elapsed = ticks_diff(ticks_ms(), press_start_time)
            return elapsed >= duration

        if action == "tap":
            tapped = self._key_tapped[index]
            if tapped:
                self._key_tapped[index] = False
            return tapped

        return True

    @property
    def dial_pressed(self, long=False, duration=2000):
        """Returns True if the rotary encoder button is pressed."""
        return self.is_pressed(4, long=long, duration=duration)

    @property
    def estop(self):
        """Returns True estop is pressed."""
        return not self._estop.value
