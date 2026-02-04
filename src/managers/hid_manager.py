"""Class to manage Master Box hardware inputs."""

import digitalio
import keypad
import rotaryio

from adafruit_ticks import ticks_ms, ticks_diff

class HIDManager:
    """
    Unified Input Manager.
    Handles: Buttons, Latching Toggles, Momentary Toggles, Encoders, Matrix Keypads.

    Buttons [board.GPx, board.GPy, ...]
        - Managed via keypad.Keys for debouncing and event handling.
    Latching Toggles [board.GPx, board.GPy, ...]
        - Simple digital inputs with pull-ups.
    Momentary Toggles [[up_pin, down_pin], ...]
        - Each momentary toggle has two pins (up and down) with pull-ups.
    Encoders [[pin_a, pin_b, push_btn], ...]
        - Managed via rotaryio.IncrementalEncoder.
        - Optional push button pin for each encoder.
    Matrix Keypads [[[key_map_0, ...],[row_pin_a, ...],[col_pin_a, ...]], ...]
        - Managed via keypad.Keypad for matrix scanning.

    """
    def __init__(self,
                 buttons=None,
                 latching_toggles=None,
                 momentary_toggles=None,
                 encoders=None,
                 matrix_keypads=None,
                 estop_pin=None,
                 monitor_only=False
                 ):
        """Initialize HID Manager with specified inputs."""

        self.monitor_only = monitor_only

        # --- Initialize State Storage ---
        # Buttons States
        self.buttons_values = [False] * (len(buttons) or 0)
        self.buttons_timestamps = [0] * (len(buttons) or 0)
        self.buttons_tapped = [False] * (len(buttons) or 0)
        # Latching Toggles States
        self.latching_values = [False] * (len(latching_toggles) or 0)
        self.latching_timestamps = [0] * (len(latching_toggles) or 0)
        self.latching_tapped = [False] * (len(latching_toggles) or 0)
        # Momentary Toggles States
        self.momentary_values = [[False, False] for _ in range(len(momentary_toggles) or 0)]
        self.momentary_timestamps = [[0, 0] for _ in range(len(momentary_toggles) or 0)]
        self.momentary_tapped = [[False, False] for _ in range(len(momentary_toggles) or 0)]
        # Encoder States
        self.encoder_positions = [0] * (len(encoders) or 0)
        self.encoder_timestamps = [0] * (len(encoders) or 0)
        self.encoder_buttons_values = [False] * (len(encoders) or 0)
        self.encoder_buttons_timestamps = [0] * (len(encoders) or 0)
        self.encoder_buttons_tapped = [False] * (len(encoders) or 0)
        # Matrix Keypads States
        self.matrix_keypads_queues = [[] for _ in (matrix_keypads or [])]
        self.matrix_keypads_maps = [mk[0] for mk in matrix_keypads] if matrix_keypads else []
        # E-Stop State
        self.estop_value = False

        # --- Initialize Always Available Properties ---
        # Matrix Keypad Keymaps
        if matrix_keypads:
            for mk in matrix_keypads:
                key_map, _, _ = mk
                self.matrix_keypads_maps.append(key_map)

        # --- Initialize Hardware Interfaces ---
        if not self.monitor_only:
            # Buttons Hardware
            self._buttons = keypad.Keys(
                buttons,
                value_when_pressed=False,
                pull=True
            ) if buttons else None

            # Latching Toggles Hardware
            self._latching_toggles = keypad.Keys(
                latching_toggles,
                value_when_pressed=False,
                pull=True
            ) if latching_toggles else None

            # Momentary Toggles
            # Flatten the list of pairs for keypad.Keys
            flat_momentary_pins = []
            for pair in momentary_toggles or []:
                flat_momentary_pins.extend(pair)
            self._momentary_toggles = keypad.Keys(
                flat_momentary_pins,
                value_when_pressed=False,
                pull=True
            ) if momentary_toggles else None

            # Encoders
            self._encoders = []
            encoder_button_pins = []
            for e in encoders:
                encoder = rotaryio.IncrementalEncoder(e[0], e[1])
                if len(e) > 2 and e[2] is not None:
                    encoder_button_pins.append(e[2])
                self._encoders.append(encoder)
            self._encoder_buttons = keypad.Keys(
                encoder_button_pins,
                value_when_pressed=False,
                pull=True
            ) if encoder_button_pins else None

            # Matrix Keypads
            self._matrix_keypads = []
            for mk in matrix_keypads:
                _, row_pins, col_pins = mk
                self._matrix_keypads.append(keypad.Keypad(
                    row_pins,
                    col_pins
                    ))

            # E-Stop
            self._estop = None
            if estop_pin is not None:
                self._estop = digitalio.DigitalInOut(estop_pin)
                self._estop.pull = digitalio.Pull.UP

    #region --- Button Handling ---
    def is_button_pressed(self, index, long=False, duration=2000, action=None):
        """Check if a button is pressed, tapped or held."""
        if action == "tap":
            tapped = self.buttons_tapped[index]
            if tapped:
                self.buttons_tapped[index] = False
            return tapped

        if not self.buttons_values[index]:
            return False

        if long or action == "hold":
            elapsed = ticks_diff(ticks_ms(), self.buttons_timestamps[index])
            return elapsed >= duration

        return True

    def _sw_set_buttons(self, buttons):
        """Set the state of buttons without hardware polling."""
        if not self.monitor_only:
            return
        now = ticks_ms()
        for i, char in enumerate(buttons):
            val = char == "1"
            if val != self.buttons_values[i]:
                self.buttons_values[i] = val
                self.buttons_timestamps[i] = now
                if val and ticks_diff(now, self.buttons_timestamps[i]) < 500:
                    self.buttons_tapped[i] = True

    def _hw_poll_buttons(self):
        """Poll hardware buttons and update states."""
        if self.monitor_only:
            return
        event = keypad.Event()
        while self._buttons.events.get_into(event):
            key_idx = event.key_number
            now = ticks_ms()
            if event.pressed: # Button pressed
                self.buttons_values[key_idx] = True
                self.buttons_timestamps[key_idx] = now
            elif event.released: # Button released
                start_time = self.buttons_timestamps[key_idx]
                if start_time > 0 and ticks_diff(now, start_time) < 500: # Handle 'tap' detection
                    self.buttons_tapped[key_idx] = True
                self.buttons_values[key_idx] = False

    def _buttons_string(self):
        """Returns a string representation of all buttons."""
        result = ""
        for state in self.buttons_values:
            result += "1" if state else "0"
        return result
    #endregion

    #region  --- Latching Toggles Handling ---
    def is_latching_toggled(self, index, long=False, duration=2000, action=None):
        """Check if a latching toggle is switched, 'tapped' or held."""
        if action == "tap":
            tapped = self.latching_tapped[index]
            if tapped:
                self.latching_tapped[index] = False
            return tapped

        if not self.latching_values[index]:
            return False

        if long or action == "hold":
            elapsed = ticks_diff(ticks_ms(), self.latching_timestamps[index])
            return elapsed >= duration

        return True

    def _sw_set_latching_toggles(self, latching_toggles):
        """Set the state of a latching toggle without hardware polling."""
        if not self.monitor_only:
            return
        now = ticks_ms()
        for i, char in enumerate(latching_toggles):
            val = char == "1"
            if val != self.latching_values[i]:
                self.latching_values[i] = val
                self.latching_timestamps[i] = now
                if val and ticks_diff(now, self.latching_timestamps[i]) < 500:
                    self.latching_tapped[i] = True

    def _hw_poll_latching_toggles(self):
        """Poll hardware latching toggles and update states."""
        if self.monitor_only:
            return
        event = keypad.Event()
        while self._latching_toggles.events.get_into(event):
            key_idx = event.key_number
            now = ticks_ms()
            if event.pressed: # Toggle turned on
                self.latching_values[key_idx] = True
                self.latching_timestamps[key_idx] = now
            elif event.released: # Toggle turned off
                self.latching_values[key_idx] = False
                start_time = self.latching_timestamps[key_idx]
                if start_time > 0 and ticks_diff(now, start_time) < 500: # Handle 'tap' detection
                    self.latching_tapped[key_idx] = True
                self.latching_timestamps[key_idx] = 0

    def _latching_toggles_string(self):
        """Returns a string representation of all latching toggles."""
        result = ""
        for state in self.latching_values:
            result += "1" if state else "0"
        return result
    #endregion

    #region --- Momentary Toggles Handling ---
    def is_momentary_toggled(self, index, direction="U", long=False, duration=2000, action=None):
        """Check if a momentary toggle is held in a specific direction."""
        dir_idx = 0 if direction == "U" else 1
        if action == "tap":
            tapped = self.momentary_tapped[index][dir_idx]
            if tapped:
                self.momentary_tapped[index][dir_idx] = False
            return tapped

        if not self.momentary_values[index][dir_idx]:
            return False

        if long or action == "hold":
            elapsed = ticks_diff(ticks_ms(), self.momentary_timestamps[index][dir_idx])
            return elapsed >= duration

        return True

    def _sw_set_momentary_toggles(self, momentary_toggles):
        """
        Set the state of momentary toggles without hardware polling.

        :param momentary_toggles:
            A string where each character represents the state of
            a momentary on-off-on toggle - 'U' for up, 'D' for down, 'C' for center.

        :example: "UD" means first toggle up, second toggle down.
        """
        if not self.monitor_only:
            return
        now = ticks_ms()
        for i, char in enumerate(momentary_toggles):
            up_val = char == "U"
            down_val = char == "D"
            # Up Direction
            if up_val != self.momentary_values[i][0]:
                self.momentary_values[i][0] = up_val
                self.momentary_timestamps[i][0] = now
                if up_val and ticks_diff(now, self.momentary_timestamps[i][0]) < 500:
                    self.momentary_tapped[i][0] = True
            # Down Direction
            if down_val != self.momentary_values[i][1]:
                self.momentary_values[i][1] = down_val
                self.momentary_timestamps[i][1] = now
                if down_val and ticks_diff(now, self.momentary_timestamps[i][1]) < 500:
                    self.momentary_tapped[i][1] = True

    def _hw_poll_momentary_toggles(self):
        """Poll hardware momentary toggles and update states."""
        if self.monitor_only:
            return
        event = keypad.Event()
        while self._momentary_toggles.events.get_into(event):
            key_idx = event.key_number // 2
            direction = 0 if event.key_number % 2 == 0 else 1
            now = ticks_ms()
            if event.pressed: # Button pressed
                self.momentary_values[key_idx][direction] = True
                self.momentary_timestamps[key_idx][direction] = now
            elif event.released: # Button released
                start_time = self.momentary_timestamps[key_idx][direction]
                if start_time > 0 and ticks_diff(now, start_time) < 500: # Handle 'tap' detection
                    self.momentary_tapped[key_idx][direction] = True
                self.momentary_values[key_idx][direction] = False

    def _momentary_toggles_string(self):
        """Returns a string representation of all momentary toggles, either U, D, or C."""
        result = ""
        for toggle in self.momentary_values:
            if toggle[0]:
                result += "U"
            elif toggle[1]:
                result += "D"
            else:
                result += "C"
        return result
    #endregion

    #region --- Encoder Handling ---
    @property
    def encoder_position(self, index=0):
        """Returns the encoder position state."""
        return self.encoder_positions[index]

    def encoder_position_scaled(self, multiplier=1.0, wrap=None, index=0):
        """Consistent scaling method for encoder position logic."""
        scaled = int(self.encoder_positions[index] * multiplier)
        if wrap:
            return scaled % wrap
        return scaled

    def reset_encoder(self, value=0, index=0):
        """Sets the hardware encoder to a specific starting position."""
        if 0 <= index < len(self.encoder_positions):
            self.encoder_positions[index] = value

        if not self.monitor_only and 0 <= index < len(self._encoders):
            self._encoders[index].position = value

    def _sw_set_encoders(self, positions):
        """
        Set the state of encoders without hardware polling.
        :param positions: A string representing the positions of each encoder.
        :example: "0:25:123" sets encoder 0 to 0, encoder 1 to 25, encoder 2 to 123.
        """
        if not self.monitor_only:
            return
        parts = positions.split(":")
        for i, pos in enumerate(parts):
            if i < len(self.encoder_positions):
                try:
                    self.encoder_positions[i] = int(pos)
                except (ValueError, IndexError):
                    continue

    def _hw_poll_encoders(self):
        """Poll hardware encoders and update states."""
        if self.monitor_only:
            return
        for i, enc in enumerate(self._encoders):
            self.encoder_positions[i] = enc.position

    def _encoders_string(self):
        """Returns a string representation of all encoder positions."""
        return ":".join([str(pos) for pos in self.encoder_positions])
    #endregion

    #region --- Encoder Button Handling ---
    def is_encoder_button_pressed(self, long=False, duration=2000, action=None, index=0):
        """Check if an encoder button is pressed."""
        if action == "tap":
            tapped = self.encoder_buttons_tapped[index]
            if tapped:
                self.encoder_buttons_tapped[index] = False
            return tapped

        if not self.encoder_buttons_values[index]:
            return False

        if long or action == "hold":
            elapsed = ticks_diff(ticks_ms(), self.encoder_buttons_timestamps[index])
            return elapsed >= duration

        return True

    def _sw_set_encoder_buttons(self, encoder_buttons):
        """Set the state of encoder buttons without hardware polling."""
        if not self.monitor_only:
            return
        now = ticks_ms()
        for i, val in enumerate(encoder_buttons):
            if val != self.encoder_buttons_values[i]:
                self.encoder_buttons_values[i] = val
                self.encoder_buttons_timestamps[i] = now
                if val and ticks_diff(now, self.encoder_buttons_timestamps[i]) < 500:
                    self.encoder_buttons_tapped[i] = True

    def _hw_poll_encoder_buttons(self):
        """Poll hardware encoder buttons and update states."""
        if self.monitor_only:
            return
        event = keypad.Event()
        while self._encoder_buttons.events.get_into(event):
            key_idx = event.key_number
            now = ticks_ms()
            if event.pressed: # Button pressed
                self.encoder_buttons_values[key_idx] = True
                self.encoder_buttons_timestamps[key_idx] = now
            elif event.released: # Button released
                start_time = self.encoder_buttons_timestamps[key_idx]
                if start_time > 0 and ticks_diff(now, start_time) < 500: # Handle 'tap' detection
                    self.encoder_buttons_tapped[key_idx] = True
                self.encoder_buttons_values[key_idx] = False

    def _encoder_buttons_string(self):
        """Returns a string representation of all encoder buttons."""
        result = ""
        for state in self.encoder_buttons_values:
            result += "1" if state else "0"
        return result
    #endregion

    #region --- Matrix Keypad Handling ---
    def get_keypad_next_key(self, index=0):
        """Get the latest key event from the matrix keypad."""
        if len(self.matrix_keypads_queues[index]) > 0:
            return self.matrix_keypads_queues[index].pop(0)
        return None

    def _sw_set_matrix_keypads(self, char_sequences):
        """
        Set the state of matrix keypads without hardware polling.
        :param char_sequences: A series of strings separated by ':', each representing
                              the sequence of characters pressed on each keypad.
        :example: "123A:456B" sets first keypad to "123A" and second to "456B".
        """
        if not self.monitor_only:
            return
        parts = char_sequences.split(":")
        for i, chars in enumerate(parts):
            if i < len(self.matrix_keypads_queues):
                for char in chars:
                    self.matrix_keypads_queues[i].append(char)

    def _hw_poll_matrix_keypads(self):
        """Poll hardware matrix keypads and update states."""
        if self.monitor_only:
            return
        for i, k_pad in enumerate(self._matrix_keypads):
            event = k_pad.events.get()
            while k_pad.events.get_into(event):
                if event.pressed:
                    raw_idx = event.key_number

                    # Safe check for key map existence
                    if i < len(self.matrix_keypads_maps):
                        key_map = self.matrix_keypads_maps[i]
                        if 0 < raw_idx < len(key_map):
                            self.matrix_keypads_queues[i].append(key_map[raw_idx])

    def _matrix_keypads_string(self):
        """
        Returns a string representation of all matrix keypads.
        Each keypad's queued characters are joined together,
        and different keypads are separated by ':'.

        :example: "123A:456B" for two keypads.
        """
        queue_values = []
        for queues in self.matrix_keypads_queues:
            queue_values.append("".join(queues))
        return ":".join(queue_values)
    #endregion

    # --- E-Stop Handling ---
    @property
    def estop(self):
        """Returns True estop is pressed."""
        return self.estop_value

    def _sw_set_estop(self, value):
        """Set the state of e-stop without hardware polling."""
        if not self.monitor_only:
            return
        self.estop_value = value

    def _hw_poll_estop(self):
        """Poll hardware e-stop and update state."""
        if self.monitor_only or self._estop is None:
            return
        self.estop_value = not self._estop.value  # Active low

    def _estop_string(self):
        """Returns '1' if estop is pressed, else '0'."""
        return "1" if self.estop_value else "0"
    #endregion

    # --- Global Functions ---
    def hw_update(self):
        """Poll hardware inputs to update states."""
        if self.monitor_only:
            return
        self._hw_poll_buttons()
        self._hw_poll_latching_toggles()
        self._hw_poll_momentary_toggles()
        self._hw_poll_encoders()
        self._hw_poll_encoder_buttons()
        self._hw_poll_matrix_keypads()
        self._hw_poll_estop()

    def set_remote_state(self,
                         buttons,           # [bool, bool, ...]
                         latching_toggles,  # [bool, bool, ...]
                         momentary_toggles, # [[bool_up, bool_down], ...]
                         encoders,          # [int_position, int_position, ...]
                         encoder_buttons,   # [bool, bool, ...]
                         matrix_keypads,    # [[char, char, ...], ...]
                         estop              # bool
                        ):
        """Set remote HID states (for monitor-only mode)."""
        if not self.monitor_only:
            return
        if buttons:
            self._sw_set_buttons(buttons)
        if latching_toggles:
            self._sw_set_latching_toggles(latching_toggles)
        if momentary_toggles:
            self._sw_set_momentary_toggles(momentary_toggles)
        if encoders:
            self._sw_set_encoders(encoders)
        if encoder_buttons:
            self._sw_set_encoder_buttons(encoder_buttons)
        if matrix_keypads:
            self._sw_set_matrix_keypads(matrix_keypads)
        if estop:
            self._sw_set_estop(estop)

    def get_status_string(self, order=None):
        """
        Read inputs and format status packet with custom ordering and selection.

        :param order: A list of strings identifying which data to include and in what order.
                    If None, defaults to all fields in standard order.
        """
        # 1. Map string keys to the actual class methods
        sources = {
            'buttons': self._buttons_string,
            'toggles': self._latching_toggles_string,
            'momentary': self._momentary_toggles_string,
            'keypads': self._matrix_keypads_string,
            'encoders': self._encoders_string,
            'encoder_btns': self._encoder_buttons_string,
            'estop': self._estop_string
        }

        # 2. Set default order if none is provided
        if order is None:
            order = [
                'buttons', 'toggles', 'momentary', 'keypads',
                'encoders', 'encoder_btns', 'estop'
            ]

        # 3. Iterate, execute, and filter
        result_parts = []
        for key in order:
            # Check if key exists to prevent errors
            if key in sources:
                # Execute the method
                val = sources[key]()
                result_parts.append(str(val) if val is not None else "")

        # 4. Join with commas (handles spacing automatically) and add newline
        return ",".join(result_parts) + "\n"
