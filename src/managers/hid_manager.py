"""Class to manage Master Box hardware inputs."""

from adafruit_ticks import ticks_ms, ticks_diff
import keypad

class HIDManager:
    """
    Unified Input Manager.
    Handles: Buttons, Latching Toggles, Momentary Toggles,
        Encoders, Matrix Keypads, E-Stop (gameplay), Expanded Inputs via MCP23017.

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
    E-Stop [board.GPx]
        - Single digital input with pull-up (for gameplay interaction).
    Expanded Inputs via MCP23017 (if provided)
        - Buttons, Latching Toggles, Momentary Toggles.
    """

    # Class constant for status buffer size
    # Buffer size calculation for default order (7 fields with 6 commas):
    # - Buttons: ~100 chars max
    # - Toggles: ~100 chars max
    # - Momentary: ~100 chars max
    # - Keypads: ~100 chars max
    # - Encoders: ~200 chars max (supports large position values like -99999:99999:...)
    # - Encoder buttons: ~100 chars max
    # - E-stop: 1 char
    # - Separators: 6 commas + 1 newline = 7 chars
    # Total estimate: ~808 bytes; using 1024 for safety margin
    _STATUS_BUFFER_SIZE = 1024

    def __init__(self,
                 buttons=None,
                 latching_toggles=None,
                 momentary_toggles=None,
                 encoders=None,
                 matrix_keypads=None,
                 estop_pin=None,
                 mcp_chip=None,
                 mcp_i2c=None,
                 mcp_i2c_address=None,
                 mcp_int_pin=None,
                 expanded_buttons=None,
                 expanded_latching_toggles=None,
                 expanded_momentary_toggles=None,
                 monitor_only=False
                 ):
        """Initialize HID Manager with specified inputs."""

        #region --- Initialize State Storage ---
        # Buttons States
        num_local_btns = len(buttons or [])
        num_exp_btns   = len(expanded_buttons or [])
        total_btns     = num_local_btns + num_exp_btns
        self.buttons_values = [False] * total_btns
        self.buttons_timestamps = [0] * total_btns
        self.buttons_tapped = [False] * total_btns
        self._local_button_count = num_local_btns

        # Latching Toggles States
        num_local_latch = len(latching_toggles or [])
        num_exp_latch   = len(expanded_latching_toggles or [])
        total_latch     = num_local_latch + num_exp_latch
        self.latching_values = [False] * total_latch
        self.latching_timestamps = [0] * total_latch
        self.latching_tapped = [False] * total_latch
        self._local_latching_count = num_local_latch

        # Momentary Toggles States
        num_local_mom = len(momentary_toggles or [])
        num_exp_mom   = len(expanded_momentary_toggles or [])
        total_mom     = num_local_mom + num_exp_mom
        self.momentary_values = [[False, False] for _ in range(total_mom)]
        self.momentary_timestamps = [[0, 0] for _ in range(total_mom)]
        self.momentary_tapped = [[False, False] for _ in range(total_mom)]
        self._local_momentary_count = num_local_mom

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

        # Pre-allocated buffer for get_status_string to reduce heap fragmentation
        self._status_buffer = bytearray(self._STATUS_BUFFER_SIZE)
        #endregion

        #region --- Initialize Always Available Properties ---
        self.monitor_only = monitor_only

        # Matrix Keypad Keymaps
        if matrix_keypads:
            for mk in matrix_keypads:
                key_map, _, _ = mk
                self.matrix_keypads_maps.append(key_map)
        #endregion

        #region --- Initialize Hardware Interfaces ---
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

            if encoders:
                try:
                    import rotaryio
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
                except ImportError:
                    print("❗Error: 'rotaryio' module not found. Encoders will not be initialized.❗")

            # Matrix Keypads
            self._matrix_keypads = []
            for mk in matrix_keypads or []:
                _, row_pins, col_pins = mk
                self._matrix_keypads.append(keypad.Keypad(
                    row_pins,
                    col_pins
                    ))

            # E-Stop
            self._estop = None
            if estop_pin is not None:
                try:
                    import digitalio
                    self._estop = digitalio.DigitalInOut(estop_pin)
                    self._estop.pull = digitalio.Pull.UP
                except ImportError:
                    print("❗Error: 'digitalio' module not found. E-Stop input will not be initialized.❗")

            # MCP230xx Expanded Inputs
            # Check for all required parameters
            if mcp_chip and mcp_i2c and mcp_i2c_address:
                self._mcp = None
                self._mcp_int = None
                MCP23017 = None
                MCP23008 = None

                if mcp_chip == "MCP23017":
                    try:
                        from adafruit_mcp230xx.mcp23017 import MCP23017
                        self._mcp = MCP23017(mcp_i2c, mcp_i2c_address)
                    except ImportError:
                        MCP23017 = None
                if mcp_chip == "MCP23008":
                    try:
                        from adafruit_mcp230xx.mcp23008 import MCP23008
                        self._mcp = MCP23008(mcp_i2c, mcp_i2c_address)
                    except ImportError:
                        MCP23008 = None
                if mcp_int_pin:
                    self._mcp_int = mcp_int_pin

                if MCP23017 or MCP23008:
                    print(f"✅ MCP Chip '{mcp_chip}' initialized at address {hex(mcp_i2c_address)}. Expanded inputs will be available. ✅")
                    try:
                        from utilities.mcp_keys import MCPKeys

                        if MCPKeys and self._mcp and expanded_buttons:
                            self._expanded_buttons_keys = MCPKeys(
                                self._mcp,
                                expanded_buttons,
                                value_when_pressed=False,
                                pull=True
                            )

                        if MCPKeys and self._mcp and expanded_latching_toggles:
                            self._expanded_latching_keys = MCPKeys(
                                self._mcp,
                                expanded_latching_toggles,
                                value_when_pressed=False,
                                pull=True
                            )

                        if MCPKeys and self._mcp and expanded_momentary_toggles:
                            flat_expanded_momentary_pins = []
                            for pair in expanded_momentary_toggles:
                                flat_expanded_momentary_pins.extend(pair)
                            self._expanded_momentary_keys = MCPKeys(
                                self._mcp,
                                flat_expanded_momentary_pins,
                                value_when_pressed=False,
                                pull=True
                            )
                    except ImportError:
                        print("❗Error: 'MCPKeys' class not found. Expanded inputs will not be initialized.❗")
        #endregion

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
        if self.monitor_only or not self._buttons:
            return False
        changed = False
        event = keypad.Event()
        while self._buttons.events.get_into(event):
            changed = True # State changed
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
        return changed

    def _buttons_string(self):
        """Returns a string representation of all buttons."""
        result = ""
        for state in self.buttons_values:
            result += "1" if state else "0"
        return result

    def _buttons_to_buffer(self, buf, offset):
        """Write button states to buffer at offset. Returns new offset."""
        for state in self.buttons_values:
            buf[offset] = ord('1') if state else ord('0')
            offset += 1
        return offset
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
        if self.monitor_only or not self._latching_toggles:
            return False
        changed = False
        event = keypad.Event()
        while self._latching_toggles.events.get_into(event):
            changed = True # State changed
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
        return changed

    def _latching_toggles_string(self):
        """Returns a string representation of all latching toggles."""
        result = ""
        for state in self.latching_values:
            result += "1" if state else "0"
        return result

    def _latching_to_buffer(self, buf, offset):
        """Write latching toggle states to buffer at offset. Returns new offset."""
        for state in self.latching_values:
            buf[offset] = ord('1') if state else ord('0')
            offset += 1
        return offset
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
        if self.monitor_only or not self._momentary_toggles:
            return False
        changed = False
        event = keypad.Event()
        while self._momentary_toggles.events.get_into(event):
            changed = True # State changed
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
        return changed

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

    def _momentary_to_buffer(self, buf, offset):
        """Write momentary toggle states to buffer at offset. Returns new offset."""
        for toggle in self.momentary_values:
            if toggle[0]:
                buf[offset] = ord('U')
            elif toggle[1]:
                buf[offset] = ord('D')
            else:
                buf[offset] = ord('C')
            offset += 1
        return offset
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
        if self.monitor_only or not self._encoders:
            return False
        changed = False
        for i, enc in enumerate(self._encoders):
            if self.encoder_positions[i] != enc.position:
                self.encoder_positions[i] = enc.position
                changed = True
        return changed

    def _encoders_string(self):
        """Returns a string representation of all encoder positions."""
        return ":".join([str(pos) for pos in self.encoder_positions])

    def _encoders_to_buffer(self, buf, offset):
        """Write encoder positions to buffer at offset. Returns new offset."""
        for i, pos in enumerate(self.encoder_positions):
            if i > 0:
                buf[offset] = ord(':')
                offset += 1
            # Convert integer to buffer without creating intermediate strings
            # Handle negative numbers
            if pos < 0:
                buf[offset] = ord('-')
                offset += 1
                pos = -pos
            # Special case for zero
            if pos == 0:
                buf[offset] = ord('0')
                offset += 1
            else:
                # Calculate digits and write them in reverse, then reverse in place
                start_offset = offset
                while pos > 0:
                    buf[offset] = ord('0') + (pos % 10)
                    pos //= 10
                    offset += 1
                # Reverse the digits to correct order
                end_offset = offset - 1
                while start_offset < end_offset:
                    buf[start_offset], buf[end_offset] = buf[end_offset], buf[start_offset]
                    start_offset += 1
                    end_offset -= 1
        return offset
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
        if self.monitor_only or not self._encoder_buttons:
            return False
        changed = False
        event = keypad.Event()
        while self._encoder_buttons.events.get_into(event):
            changed = True # State changed
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
        return changed

    def _encoder_buttons_string(self):
        """Returns a string representation of all encoder buttons."""
        result = ""
        for state in self.encoder_buttons_values:
            result += "1" if state else "0"
        return result

    def _encoder_buttons_to_buffer(self, buf, offset):
        """Write encoder button states to buffer at offset. Returns new offset."""
        for state in self.encoder_buttons_values:
            buf[offset] = ord('1') if state else ord('0')
            offset += 1
        return offset
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
        if self.monitor_only or not self._matrix_keypads:
            return False
        changed = False
        for i, k_pad in enumerate(self._matrix_keypads):
            event = k_pad.events.get()
            while k_pad.events.get_into(event):
                if event.pressed:
                    changed = True # State changed
                    raw_idx = event.key_number

                    # Safe check for key map existence
                    if i < len(self.matrix_keypads_maps):
                        key_map = self.matrix_keypads_maps[i]
                        if 0 < raw_idx < len(key_map):
                            self.matrix_keypads_queues[i].append(key_map[raw_idx])
        return changed

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

    def _keypads_to_buffer(self, buf, offset):
        """Write matrix keypad states to buffer at offset. Returns new offset."""
        for i, queues in enumerate(self.matrix_keypads_queues):
            if i > 0:
                buf[offset] = ord(':')
                offset += 1
            for ch in queues:
                buf[offset] = ord(ch)
                offset += 1
        return offset
    #endregion

    #region --- E-Stop Handling ---
    @property
    def estop(self):
        """Returns True if E-Stop button is pressed (gameplay interaction)."""
        return self.estop_value

    def _sw_set_estop(self, value):
        """Set the state of E-Stop button without hardware polling (for testing/gameplay)."""
        if not self.monitor_only:
            return
        self.estop_value = value

    def _hw_poll_estop(self):
        """Poll hardware E-Stop button and update state (gameplay interaction)."""
        if self.monitor_only or not self._estop:
            return False
        new_value = not self._estop.value  # Active low
        if new_value != self.estop_value:
            self.estop_value = new_value
            return True  # State changed
        return False  # No change

    def _estop_string(self):
        """Returns '1' if estop is pressed, else '0'."""
        return "1" if self.estop_value else "0"

    def _estop_to_buffer(self, buf, offset):
        """Write estop state to buffer at offset. Returns new offset."""
        buf[offset] = ord('1') if self.estop_value else ord('0')
        return offset + 1
    #endregion

    #region --- Expander MCP23017 Handling ---
    def _hw_expander_buttons(self):
        """Polls MCP23017 and processes events into the global state arrays."""
        if self.monitor_only or not self._expanded_buttons_keys:
            return False
        changed = False
        event = keypad.Event()
        while self._expanded_buttons_keys.events.get_into(event):
            key_idx = self._local_button_count + event.key_number
            now = ticks_ms()
            if event.pressed: # Button pressed
                self.buttons_values[key_idx] = True
                self.buttons_timestamps[key_idx] = now
            elif event.released: # Button released
                start_time = self.buttons_timestamps[key_idx]
                if start_time > 0 and ticks_diff(now, start_time) < 500: # Handle 'tap' detection
                    self.buttons_tapped[key_idx] = True
                self.buttons_values[key_idx] = False
        return changed

    def _hw_expander_latching_toggles(self):
        """Polls MCP23017 and processes events into the global state arrays."""
        if self.monitor_only or not self._expanded_latching_keys:
            return False
        changed = False
        event = keypad.Event()
        while self._expanded_latching_keys.events.get_into(event):
            changed = True # State changed
            key_idx = self._local_latching_count + event.key_number
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
        return changed

    def _hw_expander_momentary_toggles(self):
        """Polls MCP23017 and processes events into the global state arrays."""
        if self.monitor_only or not self._expanded_momentary_keys:
            return False
        changed = False
        event = keypad.Event()
        while self._expanded_momentary_keys.events.get_into(event):
            changed = True # State changed
            key_idx = self._local_momentary_count + (event.key_number // 2)
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
        return changed
    #endregion

    #region --- Global Functions ---
    def hw_update(self):
        """Poll hardware inputs to update states."""
        if self.monitor_only:
            return False

        dirty = False
        dirty |= self._hw_poll_buttons()
        dirty |= self._hw_poll_latching_toggles()
        dirty |= self._hw_poll_momentary_toggles()
        dirty |= self._hw_poll_encoders()
        dirty |= self._hw_poll_encoder_buttons()
        dirty |= self._hw_poll_matrix_keypads()
        dirty |= self._hw_poll_estop()
        if self._mcp: # Poll expander if available
            if (self._mcp_int and not self._mcp_int.value) or not self._mcp_int:
                # Interrupt Active LOW or no INT pin
                self._expanded_buttons_keys.update()
                self._expanded_latching_keys.update()
                self._expanded_momentary_keys.update()
                dirty |= self._hw_expander_buttons()
                dirty |= self._hw_expander_latching_toggles()
                dirty |= self._hw_expander_momentary_toggles()

        return dirty

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

    def get_status_bytes(self, order=None):
        """
        Read inputs and format status packet as bytes with custom ordering and selection.
        Uses pre-allocated buffer to minimize heap fragmentation.

        Returns bytes directly to avoid string allocation overhead.
        Optimized for high-frequency telemetry (10Hz-60Hz) to reduce GC pressure.

        :param order: A list of strings identifying which data to include and in what order.
                    Valid field identifiers: 'buttons', 'toggles', 'momentary', 'keypads',
                    'encoders', 'encoder_btns', 'estop'
                    If None, defaults to all fields in standard order.
        :return: bytes object containing the status data with newline terminator
        """
        # 1. Map string keys to the actual buffer-writing methods
        sources = {
            'buttons': self._buttons_to_buffer,
            'toggles': self._latching_to_buffer,
            'momentary': self._momentary_to_buffer,
            'keypads': self._keypads_to_buffer,
            'encoders': self._encoders_to_buffer,
            'encoder_btns': self._encoder_buttons_to_buffer,
            'estop': self._estop_to_buffer
        }

        # 2. Set default order if none is provided
        if order is None:
            order = [
                'buttons', 'toggles', 'momentary', 'keypads',
                'encoders', 'encoder_btns', 'estop'
            ]

        # 3. Write to pre-allocated buffer
        offset = 0
        for i, key in enumerate(order):
            # Check if key exists to prevent errors
            if key in sources:
                # Add comma separator (except for first element)
                if i > 0:
                    self._status_buffer[offset] = ord(',')
                    offset += 1
                # Execute the buffer-writing method
                offset = sources[key](self._status_buffer, offset)

        # 4. Add newline
        self._status_buffer[offset] = ord('\n')
        offset += 1

        # Return only the used portion of the buffer as bytes
        # This avoids the string allocation that occurs with decode()
        return bytes(self._status_buffer[:offset])

    def get_status_string(self, order=None):
        """
        Read inputs and format status packet with custom ordering and selection.
        Uses pre-allocated buffer to minimize heap fragmentation.

        For high-frequency telemetry, prefer get_status_bytes() to avoid string allocation.

        :param order: A list of strings identifying which data to include and in what order.
                    Valid field identifiers: 'buttons', 'toggles', 'momentary', 'keypads',
                    'encoders', 'encoder_btns', 'estop'
                    If None, defaults to all fields in standard order.
        :return: str containing the status data with newline terminator
        """
        # Use get_status_bytes() and decode to string
        # This ensures consistent behavior between both methods
        return self.get_status_bytes(order).decode('utf-8')
    #endregion
