#File: src/core/modes/utility_mode.py
"""Utility Mode Base Class with Timeout Handling."""

from adafruit_ticks import ticks_ms, ticks_diff
from .base import BaseMode

class UtilityMode(BaseMode):
    """Base class for utility modes with timeout handling."""
    def __init__(self, jeb, name, description="", timeout=10):
        super().__init__(jeb, name, description=description)
        self.timeout_ms = timeout * 1000 if timeout else None
        self.last_interaction = ticks_ms()

    def touch(self):
        """Call this whenever the user presses a button/turns dial."""
        self.last_interaction = ticks_ms()

    def set_timeout(self, timeout):
        """Set a new timeout value in seconds."""
        self.timeout_ms = timeout * 1000 if timeout else None
        self.touch()

    @property
    def is_timed_out(self):
        """Check if the mode has timed out."""
        if self.timeout_ms is None:
            return False

        elapsed = ticks_diff(ticks_ms(), self.last_interaction)
        return elapsed > self.timeout_ms
