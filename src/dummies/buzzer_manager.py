# File: src/dummies/buzzer_manager.py
"""Dummy BuzzerManager - no-op replacement for isolated hardware testing."""


class BuzzerManager:
    """Drop-in dummy for BuzzerManager. All methods are no-ops."""

    def __init__(self, *args, **kwargs):
        pass

    async def stop(self):
        pass

    def play_note(self, frequency, duration=None):
        pass

    def play_sequence(self, sequence_data, loop=None):
        pass
