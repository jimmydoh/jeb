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
        self.k_map = ['1','2','3','4','5','6','7','8','9','*','0','#']
        self.k_pad = keypad.Keypad(row_pins=keypad_rows,
                                  col_pins=keypad_cols)

        # Encoder Pins & Button
        self.encoder = rotaryio.IncrementalEncoder(encoder_pins[0], encoder_pins[1])
        self.enc_btn = digitalio.DigitalInOut(button_pins[0])
        self.enc_btn.pull = digitalio.Pull.UP

    @property
    def encoder_position(self):
        """Returns the local hardware encoder position."""
        return self.encoder.position

    def flush_keypad(self):
        """Clears any pending key events in the buffer."""
        while self.k_pad.events.get():
            pass

    def set_encoder_position(self, value):
        """Sets the encoder position to a specific value."""
        self.encoder.position = value

    def get_status_string(self):
        """Read all inputs and format status packet."""
        # READ INPUTS
        # Expects Index 0 to be Buttons
        btn_val = "0" if not self.enc_btn.value else "1"

        # Latching Toggles, 4-bit String
        toggle_bits = "".join(["1" if not t.value else "0" for t in self.toggles])

        # Momentary Toggles "U", "D" or "C"
        momentary_1_val = "U" if not self.momentary_1_up.value else ("D" if not self.momentary_1_down.value else "C")
        momentary_vals = momentary_1_val + "C" # Placeholder for L2

        # Keypad
        k_event = self.k_pad.events.get()
        if k_event and k_event.pressed:
            k_val = self.k_map[k_event.key_number]
        else:
            k_val = "N"  # 'N' for No Key

        # Raw Encoder Pins for Master-side Quadrature Logic
        enc_pos = self.encoder_position

        # FORMAT: Buttons,Toggles,MomentaryToggles,Keypad,Encoder
        return f"{btn_val},{toggle_bits},{momentary_vals},{k_val},{enc_pos}\n"
