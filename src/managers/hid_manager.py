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
    Matrix Keypads [[[key_map_0, key_map_1, ...],
                     [row_pin_a, row_pin_b, ...],
                     [col_pin_a, col_pin_b, ...]], ...]
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
        self.momentary_values = [False][False] * (len(momentary_toggles) or 0)
        self.momentary_timestamps = [0][0] * (len(momentary_toggles) or 0)
        self.momentary_tapped = [False][False] * (len(momentary_toggles) or 0)
        # Encoder States
        self.encoder_positions = [0] * (len(encoders) or 0)
        self.encoder_timestamps = [0] * (len(encoders) or 0)
        self.encoder_buttons_values = [False] * (len(encoders) or 0)
        self.encoder_buttons_timestamps = [0] * (len(encoders) or 0)
        self.encoder_buttons_tapped = [False] * (len(encoders) or 0)
        # Matrix Keypads States
        self.matrix_keypads_values = ["N"] * (len(matrix_keypads) or 0)
        # E-Stop State
        self.estop_value = False

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
                btn = None
                if len(e) > 2 and e[2] is not None:
                    encoder_button_pins.append(e[2])
                self.encoders.append(encoder)
            self._encoder_buttons = keypad.Keys(
                encoder_button_pins,
                value_when_pressed=False,
                pull=True
            ) if encoder_button_pins else None

            # Matrix Keypads
            self._matrix_keypads = []
            for mk in matrix_keypads:
                key_map, row_pins, col_pins = mk
                k_pad = keypad.Keypad(row_pins=row_pins, col_pins=col_pins)
                self._matrix_keypads.append((k_pad, key_map))

            # E-Stop
            self._estop = None
            if estop_pin is not None:
                self._estop = digitalio.DigitalInOut(estop_pin)
                self._estop.pull = digitalio.Pull.UP

    #region --- Button Handling ---
    def is_button_pressed(self, index, long=False, duration=2000, action=None): # action: "hold" | "tap"
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
        for i, val in enumerate(buttons):
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
        self._process_button_events()
        result = ""
        for state in self._key_states:
            result += "1" if state > 0 else "0"
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

    def _sw_set_latching_toggle(self, latching_toggles):
        """Set the state of a latching toggle without hardware polling."""
        if not self.monitor_only:
            return
        now = ticks_ms()
        for i, val in enumerate(latching_toggles):
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
        return "".join(["1" if not t.value else "0" for t in self.latching_toggles])
    #endregion

    #region --- Momentary Toggles Handling ---
    def is_momentary_toggled(self, index, direction="U", long=False, duration=2000, action=None):
        """Check if a momentary toggle is held in a specific direction."""
        self._process_momentary_toggle_events()
        state_time = self.momentary_toggles_states[index][direction]

        if state_time == 0:
            return False

        if long or action == "hold":
            elapsed = ticks_diff(ticks_ms(), state_time)
            return elapsed >= duration

        if action == "tap":
            tapped = self.momentary_toggles_tapped[index][direction]
            if tapped:
                self.momentary_toggles_tapped[index][direction] = False
            return tapped

        return True

    def _sw_set_momentary_toggle(self, momentary_toggles):
        """Set the state of momentary toggles without hardware polling."""
        if not self.monitor_only:
            return
        now = ticks_ms()
        for i, (up_val, down_val) in enumerate(momentary_toggles):
            # Up Direction
            if up_val != self.momentary_toggles_values[i]["U"]:
                self.momentary_toggles_values[i]["U"] = up_val
                self.momentary_toggles_timestamps[i]["U"] = now
                if up_val and ticks_diff(now, self.momentary_toggles_timestamps[i]["U"]) < 500:
                    self.momentary_toggles_tapped[i]["U"] = True
            # Down Direction
            if down_val != self.momentary_toggles_values[i]["D"]:
                self.momentary_toggles_values[i]["D"] = down_val
                self.momentary_toggles_timestamps[i]["D"] = now
                if down_val and ticks_diff(now, self.momentary_toggles_timestamps[i]["D"]) < 500:
                    self.momentary_toggles_tapped[i]["D"] = True

    def _hw_poll_momentary_toggles(self):
        """Poll hardware momentary toggles and update states."""
        if self.monitor_only:
            return
        event = keypad.Event()
        while self._momentary_toggles.events.get_into(event):
            key_idx = event.key_number // 2
            direction = "U" if event.key_number % 2 == 0 else "D"
            now = ticks_ms()
            if event.pressed: # Button pressed
                self.momentary_toggles_values[key_idx][direction] = True
                self.momentary_toggles_timestamps[key_idx][direction] = now
            elif event.released: # Button released
                start_time = self.momentary_toggles_timestamps[key_idx][direction]
                if start_time > 0 and ticks_diff(now, start_time) < 500: # Handle 'tap' detection
                    self.momentary_toggles_tapped[key_idx][direction] = True
                self.momentary_toggles_values[key_idx][direction] = False
    
    def _momentary_toggles_string(self):
        """Returns a string representation of all momentary toggles, either U, D, or C."""
        result = ""
        for toggle in self.momentary_toggles:
            if toggle[0].value == False:
                result += "U"
            elif toggle[1].value == False:
                result += "D"
            else:
                result += "C"
        return result        
    #endregion

    # --- Encoder Handling ---
    @property
    def encoder_position(self, index=0):
        """Returns the raw hardware position."""
        return self.encoders[index].position

    def encoder_position_scaled(self, multiplier=1.0, wrap=None, index=0):
        """Consistent scaling method for encoder position logic."""
        scaled = int(self.encoders[index].position * multiplier)
        if wrap:
            return scaled % wrap
        return scaled

    def reset_encoder(self, value=0, index=0):
        """Sets the hardware encoder to a specific starting position."""
        self.encoders[index].position = value

    def _encoders_string(self):
        """Returns a string representation of all encoder positions."""
        return ",".join([str(enc.position) for enc in self.encoders])

    @property
    def encoder_pressed(self, long=False, duration=2000, index=0):
        """Returns True if the rotary encoder button is pressed."""
        if self.encoders_button[index] is None:
            return False
        return self.is_pressed(self.encoders_button[index], long=long, duration=duration)

    def is_encorder_button_pressed(self, long=False, duration=2000, action=None, index=0):
        """Check if an encoder button is pressed."""
        self._process_encoder_button_events()
        press_start_time = self.encoder_button_states[index]

        if press_start_time == 0:
            return False

        if long or action == "hold":
            elapsed = ticks_diff(ticks_ms(), press_start_time)
            return elapsed >= duration

        if action == "tap":
            tapped = self.encoder_button_tapped[index]
            if tapped:
                self.encoder_button_tapped[index] = False
            return tapped

        return True

    def _process_encoder_button_events(self):
        """Internal helper to process encoder button events."""
        for i, btn in enumerate(self.encoders_button):
            if btn is None:
                continue
            pressed = not btn.value
            prev_state = self.encoder_button_states[i] > 0

            if pressed and not prev_state:
                # Just pressed
                self.encoder_button_states[i] = ticks_ms()

            elif not pressed and prev_state:
                # Just released
                start_time = self.encoder_button_states[i]
                if start_time > 0:
                    elapsed = ticks_diff(ticks_ms(), start_time)
                    if elapsed < 500:
                        self.encoder_button_tapped[i] = True

                self.encoder_button_states[i] = 0

    def _encoder_buttons_string(self):
        """Returns a string representation of all encoder buttons."""
        result = ""
        for btn in self.encoders_button:
            if btn is None:
                result += "0"
            else:
                result += "1" if not btn.value else "0"
        return result

    # --- Matrix Keypad Handling ---

    def matrix_keypad_flush(self, index=0):
        """Flush any pending keypad events."""
        event = keypad.Event()
        while self.matrix_keypads[index].events.get_into(event):
            pass

    def matrix_keypad_get_key(self, index=0):
        """Get the latest key event from the matrix keypad."""
        k_pad, k_map = self.matrix_keypads[index]
        event = k_pad.events.get()
        if event and event.pressed:
            return k_map[event.key_number]
        return None

    def _matrix_keypads_string(self):
        """Returns a string representation of all matrix keypads."""
        result = ""
        for k_pad, k_map in self.matrix_keypads:
            event = k_pad.events.get()
            if event and event.pressed:
                result += k_map[event.key_number]
            else:
                result += "N"  # 'N' for No Key
        return result

    # TODO: Improve matrix keypad handling, as per button process events.

    # --- E-Stop Handling ---
    @property
    def estop(self):
        """Returns True estop is pressed."""
        return not self.estop.value

    def _estop_string(self):
        """Returns '1' if estop is pressed, else '0'."""
        return "1" if not self.estop.value else "0"

    # --- Global Functions ---
    def hw_update(self):
        """Poll hardware inputs to update states."""
        if self.monitor_only:
            return
        self._hw_poll_buttons()
        self._hw_poll_latching_toggles()

    def set_remote_state(self, latching_toggles):
        """Set remote HID states (for monitor-only mode)."""
        self._sw_set_latching_toggle(latching_toggles)

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

                # Only append if val is not None and not an empty string
                if val:
                    result_parts.append(str(val))

        # 4. Join with commas (handles spacing automatically) and add newline
        return ",".join(result_parts) + "\n"
