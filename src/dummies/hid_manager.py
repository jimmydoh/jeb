# File: src/dummies/hid_manager.py
"""Dummy HIDManager - no-op replacement for isolated hardware testing."""


class HIDManager:
    """Drop-in dummy for HIDManager. All inputs report idle/unpressed state."""

    def __init__(self, *args, **kwargs):
        self._estop = False

    def is_button_pressed(self, index, long=False, duration=2000, action=None):
        return False

    def is_latching_toggled(self, index, long=False, duration=2000, action=None):
        return False

    def is_momentary_toggled(self, index, direction="U", long=False, duration=2000, action=None):
        return False

    def encoder_position(self, index=0):
        return 0

    def encoder_position_scaled(self, multiplier=1.0, wrap=None, index=0):
        return 0

    def reset_encoder(self, value=0, index=0):
        pass

    def is_encoder_button_pressed(self, long=False, duration=2000, action=None, index=0):
        return False

    def get_keypad_next_key(self, index=0):
        return None

    def flush_keypad_queue(self, index=0):
        pass

    @property
    def estop(self):
        return self._estop

    def hw_update(self, sid=None):
        return False

    def get_idle_time_ms(self):
        return 0

    def set_remote_state(self, buttons, latching_toggles, momentary_toggles, encoders, encoder_buttons, matrix_keypads, estop, sid):
        return False

    def get_status_bytes(self, order=None):
        return b''

    def get_status_string(self, order=None):
        return ''

    def flush(self):
        pass
