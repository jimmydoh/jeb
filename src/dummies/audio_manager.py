# File: src/dummies/audio_manager.py
"""Dummy AudioManager - no-op replacement for isolated hardware testing."""

import asyncio

from utilities.audio_channels import AudioChannels


class AudioManager:
    """Drop-in dummy for AudioManager. All methods are no-ops."""

    def __init__(self, *args, **kwargs):
        self.CH_ATMO = AudioChannels.CH_ATMO
        self.CH_SFX = AudioChannels.CH_SFX
        self.CH_VOICE = AudioChannels.CH_VOICE
        self.CH_SYNTH = AudioChannels.CH_SYNTH

    def attach_synth(self, synth_source):
        pass

    def preload(self, files):
        pass

    async def play(self, file, channel=1, loop=False, level=1.0, wait=False, interrupt=True):
        pass

    def stop(self, channel):
        pass

    def stop_all(self):
        pass

    def set_level(self, channel, level):
        pass

    async def start_polling(self, heartbeat_callback=None):
        """Dummy implementation - does nothing."""
        while True:
            heartbeat_callback() if heartbeat_callback else None
            await asyncio.sleep(0.1)
