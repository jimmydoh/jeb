# File: src/dummies/synth_manager.py
"""Dummy SynthManager - no-op replacement for isolated hardware testing."""

import asyncio


class SynthManager:
    """Drop-in dummy for SynthManager. All methods are no-ops."""

    def __init__(self, *args, **kwargs):
        pass

    @property
    def source(self):
        return None

    def play_note(self, frequency, patch=None, duration=None):
        return None

    def stop_note(self, note_obj):
        pass

    def release_all(self):
        pass

    async def play_sequence(self, sequence_data, patch=None):
        pass

    async def start_generative_drone(self):
        pass
