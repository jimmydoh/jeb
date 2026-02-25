# File: src/dummies/buzzer_manager.py
"""Dummy BuzzerManager - no-op replacement for isolated hardware testing."""

from utilities.logger import JEBLogger

class BuzzerManager:
    """Drop-in dummy for BuzzerManager. All methods are no-ops."""

    def __init__(self, *args, **kwargs):
        JEBLogger.info("BUZZ", f"[INIT] DummyBuzzerManager")

    async def stop(self):
        JEBLogger.info("BUZZ", f"[STOP] DummyBuzzerManager")

    def play_note(self, frequency, duration=None):
        JEBLogger.info("BUZZ", f"[PLAY_NOTE] DummyBuzzerManager")

    def play_sequence(self, sequence_data, loop=None):
        JEBLogger.info("BUZZ", f"[PLAY_SEQUENCE] DummyBuzzerManager")
