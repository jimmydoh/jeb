# File: src/core/managers/audio_manager.py
"""Audio Manager Module"""

import asyncio
import audiobusio
import audiocore
import audiomixer

class AudioManager:
    """Manages audio playback and mixing."""
    def __init__(self, sck, ws, sd, voice_count=3):
        self.audio = audiobusio.I2SOut(sck, ws, sd)
        self.mixer = audiomixer.Mixer(
            voice_count=voice_count,
            sample_rate=22050,
            channel_count=1,
            bits_per_sample=16,
            samples_signed=True
        )
        self.audio.play(self.mixer)

        # Channel Aliases for code readability
        self.CH_ATMO = 0
        self.CH_SFX  = 1
        self.CH_VOICE = 2

        # Cache for frequently used small sound files
        # Format: {"filename": WaveFileObject}
        self._cache = {}

    def preload(self, files):
        """
        Loads small WAV files into memory permanently.
        Call this during boot for UI sounds (ticks, clicks, beeps).
        """
        for filename in files:
            try:
                # We intentionally keep the file handle open for cached sounds
                f = open(filename, "rb")
                wav = audiocore.WaveFile(f, bytearray(256))
                self._cache[filename] = wav
            except OSError:
                print(f"Audio Error: Could not preload {filename}")

    async def play(self, file, channel=1, loop=False, level=1.0, wait=False, interrupt=True):
        """
        Plays a sound file.
        - file: Filename string.
        - channel: 0=Atmo, 1=SFX, 2=Voice.
        - interrupt: If False, will not play if channel is busy.
        """
        voice = self.mixer.voice[channel]

        # 1. Manage Channel State
        if voice.playing:
            if not interrupt and not wait:
                return
            elif interrupt:
                voice.stop()
            elif wait:
                while voice.playing:
                    await asyncio.sleep(0.1)

            # Small delay to let the buffer clear avoids 'pops'
            await asyncio.sleep(0.01)

        voice.level = level

        # 2. Source Selection (Cache vs Stream)
        if file in self._cache:
            # Use pre-loaded object (Fast, no allocation)
            voice.play(self._cache[file], loop=loop)
        else:
            # Stream from disk (For long narration/music)
            try:
                f = open(file, "rb")
                wav = audiocore.WaveFile(f, bytearray(1024))
                voice.play(wav, loop=loop)
            except OSError:
                print(f"Audio Error: File {file} not found")

    def stop(self, channel):
        """Stops playback on a specific channel."""
        self.mixer.voice[channel].stop()

    def stop_all(self):
        """Stops playback on all channels."""
        for voice in self.mixer.voice:
            voice.stop()

    def set_level(self, channel, level):
        """Set volume level for a specific channel."""
        self.mixer.voice[channel].level = level

    # --- COMPATIBILITY WRAPPERS ---
    async def play_sfx(self, file, voice=1, loop=False, vol=1.0, wait=False, skip=False):
        """Compatibility wrapper for older play_sfx method."""
        await self.play(file, channel=voice, loop=loop, level=vol, wait=wait, interrupt=not skip)

    async def set_volume(self, voice, level):
        """Compatibility wrapper for older set_volume method."""
        self.set_level(voice, level)
