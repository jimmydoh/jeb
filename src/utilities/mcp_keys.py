# File: src/utilities/mcp_keys.py
"""MCP23017 Keypad Wrapper Module"""

import digitalio
import keypad
from adafruit_ticks import ticks_ms

class MCPKeys:
    """
    A wrapper for MCP23017 pins that mimics keypad.Keys behavior.
    """
    def __init__(self, mcp, pins, value_when_pressed=False, pull=True):
        self._mcp = mcp
        self._pins = []
        self._last_state = []
        self.events = self  # Mimic the .events property
        self._queue = []

        # Initialize pins on the MCP object
        for pin_num in pins:
            pin = mcp.get_pin(pin_num)
            pin.direction = digitalio.Direction.INPUT
            pin.pull = digitalio.Pull.UP if pull else None # *** MCP only supports Pull.UP
            self._pins.append((pin_num, pin))
            # Store initial state (True = Released for Pull-Up)
            self._last_state.append(pin.value)

            # Enable Interrupts for this pin (if supported by the specific MCP library)
            if hasattr(mcp, 'interrupt_enable') and hasattr(mcp, 'interrupt_configuration'):
                mcp.interrupt_enable |= (1 << pin_num)
                mcp.interrupt_configuration &= ~(1 << pin_num)  # Change on any state

        self.value_when_pressed = value_when_pressed

    def get(self):
        """
        Pop the next event from the queue and return it.
        Returns None if the queue is empty.
        """
        if not self._queue:
            return None

        next_evt = self._queue.pop(0)
        
        try:
            import keypad
            # Create a native keypad.Event (key_number, pressed)
            return keypad.Event(next_evt["key_number"], next_evt["pressed"])
        except ImportError:
            # Fallback for pure CPython testing
            class MockEvent:
                def __init__(self, key_number, pressed):
                    self.key_number = key_number
                    self.pressed = pressed
                    self.released = not pressed
            return MockEvent(next_evt["key_number"], next_evt["pressed"])

    def update(self):
        """
        Manual poll function. Call this when the MCP INT pin goes LOW.
        """
        # Read the GPIO state (this clears the MCP interrupt)
        # We read all pins we are tracking
        now = ticks_ms()

        live_gpio_register = self._mcp.gpio  # Read the entire GPIO register once

        for i, (pin_num, pin) in enumerate(self._pins):

            val = bool((live_gpio_register >> pin_num) & 1)

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
