"""Class to manage Master Box hardware inputs."""

from adafruit_ticks import ticks_ms, ticks_diff
import keypad
from utilities.logger import JEBLogger

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
                 expander_configs=None,
                 monitor_only=False
                 ):
        """Initialize HID Manager with specified inputs."""
        JEBLogger.info("HIDM", "[INIT] HIDManager")

        #region --- Initialize State Storage ---
        # Buttons States
        num_local_btns = len(buttons or [])
        num_exp_btns   = sum(len(cfg.get('buttons', [])) for cfg in (expander_configs or []))
        total_btns     = num_local_btns + num_exp_btns
        self.buttons_values = [False] * total_btns
        self.buttons_timestamps = [0] * total_btns
        self.buttons_tapped = [False] * total_btns
        self._local_button_count = num_local_btns

        # Latching Toggles States
        num_local_latch = len(latching_toggles or [])
        num_exp_latch   = sum(len(cfg.get('latching', [])) for cfg in (expander_configs or []))
        total_latch     = num_local_latch + num_exp_latch
        self.latching_values = [False] * total_latch
        self.latching_timestamps = [0] * total_latch
        self.latching_tapped = [False] * total_latch
        self._local_latching_count = num_local_latch

        # Momentary Toggles States
        num_local_mom = len(momentary_toggles or [])
        num_exp_mom   = sum(len(cfg.get('momentary', [])) for cfg in (expander_configs or []))
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

        # Idle tracking: timestamp (ms) of last detected hardware interaction
        self.last_interaction_time = ticks_ms()
        #endregion

        #region --- Initialize Always Available Properties ---
        self.monitor_only = monitor_only
        self.has_expander = False  # True only if an I/O expander is successfully detected

        # Matrix Keypad Keymaps
        if matrix_keypads:
            for mk in matrix_keypads:
                key_map, _, _ = mk
                self.matrix_keypads_maps.append(key_map)
        #endregion

        #region --- Initialize Hardware Interfaces ---
        if not self.monitor_only:

            self._shared_event = keypad.Event()  # Reusable event object for polling to minimize allocations

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
                    JEBLogger.error("HIDM", "rotaryio module not found, encoders will not be initialized")

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
                    JEBLogger.error("HIDM", "digitalio module not found, E-Stop input will not be initialized")

            # MCP230xx Expanded Inputs
            # Check for all required parameters
            self._active_expanders = []

            if not self.monitor_only and expander_configs:
                btn_offset = 0
                latch_offset = 0
                mom_offset = 0

                for cfg in expander_configs:
                    JEBLogger.info("HIDM", f"Configuring MCP Expander at {hex(cfg['address'])}")
                    chip_type = cfg.get("chip")
                    try:
                        int_io = None
                        if chip_type == "MCP23008":
                            from adafruit_mcp230xx.mcp23008 import MCP23008
                            mcp = MCP23008(cfg.get("i2c"), cfg["address"])
                        elif chip_type == "MCP23017":
                            from adafruit_mcp230xx.mcp23017 import MCP23017
                            mcp = MCP23017(cfg.get("i2c"), cfg["address"])
                            # Interrupt only supported on MCP23017 currently
                            if cfg.get("int_pin"):
                                import digitalio
                                int_io = digitalio.DigitalInOut(cfg["int_pin"])
                                int_io.direction = digitalio.Direction.INPUT
                                int_io.pull = digitalio.Pull.UP
                        else:
                            continue

                        self.has_expander = True 

                        # Initialize MCPKeys
                        from utilities.mcp_keys import MCPKeys

                        exp_data = {
                            "mcp": mcp,
                            "int_io": int_io,
                            "btn_keys": MCPKeys(mcp, cfg["buttons"], value_when_pressed=False, pull=True) if cfg.get("buttons") else None,
                            "btn_offset": btn_offset,
                            "latch_keys": MCPKeys(mcp, cfg["latching"], value_when_pressed=False, pull=True) if cfg.get("latching") else None,
                            "latch_offset": latch_offset,
                            "mom_keys": None,
                            "mom_offset": mom_offset,
                            "abs_btn_base": self._local_button_count + btn_offset,
                            "abs_latch_base": self._local_latching_count + latch_offset,
                            "abs_mom_base": self._local_momentary_count + mom_offset,
                        }

                        if cfg.get("momentary"):
                            flat_mom = [pin for pair in cfg["momentary"] for pin in pair]
                            exp_data["mom_keys"] = MCPKeys(mcp, flat_mom, value_when_pressed=False, pull=True)

                        self._active_expanders.append(exp_data)

                        # Increment global offsets for the next chip
                        btn_offset += len(cfg.get("buttons", []))
                        latch_offset += len(cfg.get("latching", []))
                        mom_offset += len(cfg.get("momentary", []))

                    except (ImportError, OSError, ValueError) as e:
                        JEBLogger.warning("HIDM", f"Expander {chip_type} at {cfg['address']} failed")
                        JEBLogger.error("HIDM", f"Expander Error: {e}")
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
            return False
        dirty = False
        now = ticks_ms()
        for i, char in enumerate(buttons):
            val = char == "1"
            if val != self.buttons_values[i]:
                self.buttons_values[i] = val
                if val:  # Button pressed - record timestamp
                    self.buttons_timestamps[i] = now
                else:  # Button released - detect tap
                    start_time = self.buttons_timestamps[i]
                    if start_time > 0 and ticks_diff(now, start_time) < 500:
                        self.buttons_tapped[i] = True
                dirty = True
        return dirty

    def _hw_poll_buttons(self):
        """Poll hardware buttons and update states."""
        if self.monitor_only or not self._buttons:
            return False
        changed = False

        while self._buttons.events.get_into(self._shared_event):
            changed = True # State changed
            key_idx = self._shared_event.key_number
            now = ticks_ms()
            if self._shared_event.pressed: # Button pressed
                self.buttons_values[key_idx] = True
                self.buttons_timestamps[key_idx] = now
            elif self._shared_event.released: # Button released
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
            return False
        dirty = False
        now = ticks_ms()
        for i, char in enumerate(latching_toggles):
            val = char == "1"
            if val != self.latching_values[i]:
                self.latching_values[i] = val
                if val:  # Toggle turned on - record timestamp
                    self.latching_timestamps[i] = now
                else:  # Toggle turned off - detect tap
                    start_time = self.latching_timestamps[i]
                    if start_time > 0 and ticks_diff(now, start_time) < 500:
                        self.latching_tapped[i] = True
                dirty = True
        return dirty

    def _hw_poll_latching_toggles(self):
        """Poll hardware latching toggles and update states."""
        if self.monitor_only or not self._latching_toggles:
            return False
        changed = False

        while self._latching_toggles.events.get_into(self._shared_event):
            changed = True # State changed
            key_idx = self._shared_event.key_number
            now = ticks_ms()
            if self._shared_event.pressed: # Toggle turned on
                self.latching_values[key_idx] = True
                self.latching_timestamps[key_idx] = now
            elif self._shared_event.released: # Toggle turned off
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
            return False
        dirty = False
        now = ticks_ms()
        for i, char in enumerate(momentary_toggles):
            up_val = char == "U"
            down_val = char == "D"

            # Check if the momentary toggle state has changed in either direction
            if (up_val != self.momentary_values[i][0]) or (down_val != self.momentary_values[i][1]):
                dirty = True

                # Up Direction
                if up_val != self.momentary_values[i][0]:
                    self.momentary_values[i][0] = up_val
                    if up_val:  # Pressed up - record timestamp
                        self.momentary_timestamps[i][0] = now
                    else:  # Released up - detect tap
                        start_time = self.momentary_timestamps[i][0]
                        if start_time > 0 and ticks_diff(now, start_time) < 500:
                            self.momentary_tapped[i][0] = True
                # Down Direction
                if down_val != self.momentary_values[i][1]:
                    self.momentary_values[i][1] = down_val
                    if down_val:  # Pressed down - record timestamp
                        self.momentary_timestamps[i][1] = now
                    else:  # Released down - detect tap
                        start_time = self.momentary_timestamps[i][1]
                        if start_time > 0 and ticks_diff(now, start_time) < 500:
                            self.momentary_tapped[i][1] = True
        return dirty

    def _hw_poll_momentary_toggles(self):
        """Poll hardware momentary toggles and update states."""
        if self.monitor_only or not self._momentary_toggles:
            return False
        changed = False

        while self._momentary_toggles.events.get_into(self._shared_event):
            changed = True # State changed
            key_idx = self._shared_event.key_number // 2
            direction = 0 if self._shared_event.key_number % 2 == 0 else 1
            now = ticks_ms()
            if self._shared_event.pressed: # Button pressed
                self.momentary_values[key_idx][direction] = True
                self.momentary_timestamps[key_idx][direction] = now
            elif self._shared_event.released: # Button released
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
            return False
        dirty = False
        parts = positions.split(":")
        for i, pos in enumerate(parts):
            if i < len(self.encoder_positions):
                try:
                    if self.encoder_positions[i] != int(pos):
                        self.encoder_positions[i] = int(pos)
                        dirty = True
                except (ValueError, IndexError):
                    continue
        return dirty

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
            return False
        dirty = False
        now = ticks_ms()
        for i, val in enumerate(encoder_buttons):
            if val != self.encoder_buttons_values[i]:
                self.encoder_buttons_values[i] = val
                if val:  # Button pressed - record timestamp
                    self.encoder_buttons_timestamps[i] = now
                else:  # Button released - detect tap
                    start_time = self.encoder_buttons_timestamps[i]
                    if start_time > 0 and ticks_diff(now, start_time) < 500:
                        self.encoder_buttons_tapped[i] = True
                dirty = True
        return dirty



    def _hw_poll_encoder_buttons(self):
        """Poll hardware encoder buttons and update states."""
        if self.monitor_only or not self._encoder_buttons:
            return False
        changed = False

        while self._encoder_buttons.events.get_into(self._shared_event):
            changed = True # State changed
            key_idx = self._shared_event.key_number
            now = ticks_ms()
            if self._shared_event.pressed: # Button pressed
                self.encoder_buttons_values[key_idx] = True
                self.encoder_buttons_timestamps[key_idx] = now
            elif self._shared_event.released: # Button released
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

    def flush_keypad_queue(self, index=0):
        """Clear all pending key events from the matrix keypad queue."""
        self.matrix_keypads_queues[index].clear()

    def _sw_set_matrix_keypads(self, char_sequences):
        """
        Set the state of matrix keypads without hardware polling.
        :param char_sequences: A series of strings separated by ':', each representing
                              the sequence of characters pressed on each keypad.
        :example: "123A:456B" sets first keypad to "123A" and second to "456B".
        """
        if not self.monitor_only:
            return False
        dirty = False
        parts = char_sequences.split(":")
        for i, chars in enumerate(parts):
            if i < len(self.matrix_keypads_queues):
                for char in chars:
                    if len(self.matrix_keypads_queues[i]) > 16:
                        self.matrix_keypads_queues[i].pop(0)  # Prevent unbounded growth
                    self.matrix_keypads_queues[i].append(char)
                    dirty = True
        return dirty

    def _hw_poll_matrix_keypads(self):
        """Poll hardware matrix keypads and update states."""
        if self.monitor_only or not self._matrix_keypads:
            return False
        changed = False

        for i, k_pad in enumerate(self._matrix_keypads):
            # Loop until the queue is completely empty
            while True:
                event = k_pad.events.get()
                if not event:
                    break # Break the while loop when queue is empty

                if event.pressed:
                    changed = True # State changed
                    raw_idx = event.key_number

                    # Safe check for key map existence
                    if i < len(self.matrix_keypads_maps):
                        key_map = self.matrix_keypads_maps[i]
                        if 0 <= raw_idx < len(key_map):
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
            return False
        dirty = False
        if value != self.estop_value:
            self.estop_value = value
            dirty = True
        return dirty


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
        #JEBLogger.info("HIDM", "Polling MCP Expander Buttons...")
        if self.monitor_only or not self.has_expander:
            return False
        changed = False
        for exp in self._active_expanders:
            keys = exp.get("btn_keys")
            if not keys:
                continue

            while True:
                event = keys.events.get()
                if not event:
                    break # Break the while loop when queue is empty
                changed = True # State changed
                key_idx = exp["abs_btn_base"] + event.key_number
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
        #JEBLogger.info("HIDM", "Polling MCP Expander Latching Toggles...")
        if self.monitor_only or not self.has_expander:
            return False
        changed = False

        for exp in self._active_expanders:
            keys = exp.get("latch_keys")
            if not keys:
                continue
            
            while True:
                event = keys.events.get()
                if not event:
                    break # Break the while loop when queue is empty
                changed = True # State changed
                key_idx = exp["abs_latch_base"] + event.key_number
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
                JEBLogger.info("HIDM", f"Expander Latching Toggle Event: {event.key_number}, Pressed: {event.pressed}, Released: {event.released}")
        return changed

    def _hw_expander_momentary_toggles(self):
        """Polls MCP23017 and processes events into the global state arrays."""
        #JEBLogger.info("HIDM", "Polling MCP Expander Momentary Toggles...")
        if self.monitor_only or not self.has_expander:
            return False
        changed = False

        for exp in self._active_expanders:
            keys = exp.get("mom_keys")
            if not keys:
                continue
            
            while True:
                event = keys.events.get()
                if not event:
                    break # Break the while loop when queue is empty
                changed = True # State changed
                key_idx = exp["abs_mom_base"] + (event.key_number // 2)
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
                JEBLogger.info("HIDM", f"Momentary Toggle Event: {event.key_number}, Pressed: {event.pressed}, Released: {event.released}")
        return changed
    #endregion

    #region --- Global Functions ---
    def hw_update(self, sid=None):
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
        if self.has_expander: # Poll expander if available
            # 1. Update the underlying key states based on interrupt triggers
            for exp in self._active_expanders:
                int_io = exp.get("int_io")

                # If interrupt triggered (Active LOW) or no INT pin assigned
                if not int_io or not int_io.value:
                    # Dynamically find and update any attached MCPKeys instances
                    # regardless of what dictionary key they were stored under!
                    for key, component in exp.items():
                        if hasattr(component, "update") and key not in ["mcp", "int_io"]:
                            component.update()

                # Process the generated events into the state
                dirty |= self._hw_expander_buttons()
                dirty |= self._hw_expander_latching_toggles()
                dirty |= self._hw_expander_momentary_toggles()

        if dirty:
            self.last_interaction_time = ticks_ms()
            JEBLogger.debug("HIDM", "HID HW `I want to clean your dusty cups`")

        return dirty

    def get_idle_time_ms(self):
        """Return milliseconds elapsed since the last hardware interaction."""
        return ticks_diff(ticks_ms(), self.last_interaction_time)

    def set_remote_state(self,
                         buttons,           # [bool, bool, ...]
                         latching_toggles,  # [bool, bool, ...]
                         momentary_toggles, # [[bool_up, bool_down], ...]
                         encoders,          # [int_position, int_position, ...]
                         encoder_buttons,   # [bool, bool, ...]
                         matrix_keypads,    # [[char, char, ...], ...]
                         estop,             # bool
                         sid
                        ):
        """Set remote HID states (for monitor-only mode)."""
        if not self.monitor_only:
            return False
        dirty = False
        if buttons:
            if self._sw_set_buttons(buttons):
                dirty = True
                JEBLogger.debug("HIDM", f"Driver - Buttons: {buttons}", src=sid)
        if latching_toggles:
            if self._sw_set_latching_toggles(latching_toggles):
                dirty = True
                JEBLogger.debug("HIDM", f"Driver - Latching Toggles: {latching_toggles}", src=sid)
        if momentary_toggles:
            if self._sw_set_momentary_toggles(momentary_toggles):
                dirty = True
                JEBLogger.debug("HIDM", f"Driver - Momentary Toggles: {momentary_toggles}", src=sid)
        if encoders:
            if self._sw_set_encoders(encoders):
                dirty = True
                JEBLogger.debug("HIDM", f"Driver - Encoders: {encoders}", src=sid)
        if encoder_buttons:
            if self._sw_set_encoder_buttons(encoder_buttons):
                dirty = True
                JEBLogger.debug("HIDM", f"Driver - Encoder Buttons: {encoder_buttons}", src=sid)
        if matrix_keypads:
            if self._sw_set_matrix_keypads(matrix_keypads):
                dirty = True
                JEBLogger.debug("HIDM", f"Driver - Matrix Keypads: {matrix_keypads}", src=sid)
        if estop:
            if self._sw_set_estop(estop):
                dirty = True
                JEBLogger.debug("HIDM", f"Driver - E-Stop: {estop}", src=sid)
        return dirty

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

    def flush(self):
        """Clear all input states and queues."""
        if not self.monitor_only:
            # Flush hardware event queues (non-monitor-only only)
            if self._buttons:
                while self._buttons.events.get_into(self._shared_event):
                    pass

            if self._latching_toggles:
                while self._latching_toggles.events.get_into(self._shared_event):
                    pass

            if self._momentary_toggles:
                while self._momentary_toggles.events.get_into(self._shared_event):
                    pass

            # TODO: Encoders - no events to flush, but reset positions if needed

            if self._encoder_buttons:
                while self._encoder_buttons.events.get_into(self._shared_event):
                    pass

            for exp in self._active_expanders:
                for key in ["btn_keys", "latch_keys", "mom_keys"]:
                    if exp.get(key):
                        exp[key]._queue.clear()

            if self._matrix_keypads:
                for k_pad in self._matrix_keypads:
                    while k_pad.events.get_into(self._shared_event):
                        pass

        for q in self.matrix_keypads_queues:
            q.clear()

        # Clear all pending tap flags to prevent ghost inputs from previous modes
        for i in range(len(self.buttons_tapped)):
            self.buttons_tapped[i] = False
        for i in range(len(self.latching_tapped)):
            self.latching_tapped[i] = False
        for i in range(len(self.momentary_tapped)):
            self.momentary_tapped[i] = [False, False]
        for i in range(len(self.encoder_buttons_tapped)):
            self.encoder_buttons_tapped[i] = False

    #endregion
