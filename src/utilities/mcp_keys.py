# File: src/utilities/mcp_keys.py
"""MCP23017 Keypad Wrapper Module"""

import digitalio
from adafruit_ticks import ticks_ms

class MCPKeys:
    """
    A wrapper for MCP23017 pins that mimics keypad.Keys behavior.
    """
    def __init__(self, mcp, pins, value_when_pressed=False, pull=True):
        self._pins = []
        self._last_state = []
        self.events = self  # Mimic the .events property
        self._queue = []

        # Initialize pins on the MCP object
        for pin_num in pins:
            pin = mcp.get_pin(pin_num)
            pin.direction = digitalio.Direction.INPUT
            pin.pull = digitalio.Pull.UP if pull else None # *** MCP only supports Pull.UP
            self._pins.append(pin)
            # Store initial state (True = Released for Pull-Up)
            self._last_state.append(pin.value)

            # Enable Interrupts for this pin (Library specific, or direct register write)
            mcp.interrupt_enable |= (1 << pin_num)
            mcp.interrupt_configuration &= ~(1 << pin_num)  # Change on any state

        self.value_when_pressed = value_when_pressed

    def get_into(self, event):
        """
        Pop the next event from the queue into the event object.
        Returns True if an event was popped, False otherwise.
        """
        if not self._queue:
            return False

        # Pop the oldest event
        next_evt = self._queue.pop(0)
        event.key_number = next_evt["key_number"]
        event.pressed = next_evt["pressed"]
        event.released = next_evt["released"]
        event.timestamp = next_evt["timestamp"]
        return True

    def update(self):
        """
        Manual poll function. Call this when the MCP INT pin goes LOW.
        """
        # Read the GPIO state (this clears the MCP interrupt)
        # We read all pins we are tracking
        now = ticks_ms()

        for i, pin in enumerate(self._pins):
            val = pin.value
            if val != self._last_state[i]:
                # State Changed!
                self._last_state[i] = val

                is_pressed = (val == self.value_when_pressed)

                # Add to queue
                self._queue.append({
                    "key_number": i,
                    "pressed": is_pressed,
                    "released": not is_pressed,
                    "timestamp": now
                })

    @property
    def num_pins(self):
        """Return the number of pins managed."""
        return len(self._pins)
