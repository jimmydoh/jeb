"""
Docstring for core.managers.audio_manager
"""

import asyncio
import audiobusio
import audiocore
import audiomixer

class AudioManager:
    """Manages audio playback and mixing."""
    def __init__(self, sck, ws, sd):
        self.audio = audiobusio.I2SOut(sck, ws, sd)
        self.mixer = audiomixer.Mixer(
            voice_count=3,
            sample_rate=22050,
            channel_count=1,
            bits_per_sample=16,
            samples_signed=True
        )
        self.audio.play(self.mixer)

    async def play_sound(self, sound_file, voice=0, volume=0.5):
        """Play a sound file on the specified voice with given volume."""
        self.mixer.voice[voice].level = volume
        wave_file = audiocore.WaveFile(open(sound_file, "rb"), bytearray(1024))
        self.mixer.voice[voice].play(wave_file)

    async def play_sfx(self,file, voice=1, loop=False, vol=1.0, wait=False, skip=False):
        """Play sounds on specific channels without stopping others."""
        try:
            if loop:    # TODO Implement looping behaviour
                print("Looping not yet implemented.")
            if skip and self.mixer.playing(voice):
                return
            if voice > 0 and wait and self.mixer.playing(voice):
                while self.mixer.playing(voice):
                    await asyncio.sleep(0.1)
                await asyncio.sleep(0.5)
            await self.play_sound(file, voice=voice, volume=vol)
        except Exception as e:
            print(f"Audio Error: {e}")

    async def set_volume(self, voice, level):
        """Set volume level for a specific voice."""
        self.mixer.voice[voice].level = level
