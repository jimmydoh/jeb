"""Manages Toggles, Keypad, and Rotary Encoder for Industrial Satellite. """

import digitalio
import keypad
import rotaryio

class HIDManager:
    """Manages Toggles, Keypad, and Rotary Encoder for Industrial Satellite."""
    def __init__(self, button_pins, toggle_pins, momentary_toggle_pins, keypad_rows, keypad_cols, encoder_pins):
        # Latching Toggles
        self.toggles = [digitalio.DigitalInOut(p) for p in toggle_pins]
        for t in self.toggles:
            t.pull = digitalio.Pull.UP

        # Momentary Toggle
        self.momentary_1_up = digitalio.DigitalInOut(momentary_toggle_pins[0])
        self.momentary_1_down = digitalio.DigitalInOut(momentary_toggle_pins[1])
        for m in [self.momentary_1_up, self.momentary_1_down]:
            m.pull = digitalio.Pull.UP

        # Keypad
        self.k_pad = keypad.Keypad(row_pins=keypad_rows,
                                  col_pins=keypad_cols)

        # Encoder Pins & Button
        self.enc_a = digitalio.DigitalInOut(encoder_pins[0])
        self.enc_b = digitalio.DigitalInOut(encoder_pins[1])
        self.enc_btn = digitalio.DigitalInOut(button_pins[0])
        for e in [self.enc_a, self.enc_b, self.enc_btn]:
            e.pull = digitalio.Pull.UP

    def get_status_string(self):
        """Reads all hardware and returns the formatted status string for heartbeat."""
        btn = "0" if not self.enc_btn.value else "1"
        toggles = "".join(["1" if not t.value else "0" for t in self.toggles])
        l1 = "U" if not self.momentary_1_up.value else ("D" if not self.momentary_1_down.value else "C")

        # Matrix Keypad event handling
        k_event = self.k_pad.events.get()
        key = str(k_event.key_number) if k_event and k_event.pressed else "N"

        # Return Raw Encoder Pins for Master-side quadrature logic
        return f"{btn},{toggles},{l1}C,{key},{1 if self.enc_a.value else 0},{1 if self.enc_b.value else 0}"
