# File: src/core/managers/audio_manager.py
"""Audio Manager Module"""

import asyncio
import io
import os
import audiobusio
import audiocore
import audiomixer
from utilities.audio_channels import AudioChannels
from utilities.logger import JEBLogger

# Maximum file size (in bytes) for preloading into RAM
# Files larger than this will be streamed from disk to prevent MemoryError
MAX_PRELOAD_SIZE_BYTES = 20 * 1024  # 20KB

class AudioManager:
    """Manages audio playback and mixing."""
    def __init__(self, sck, ws, sd, voice_count=None, root_data_dir="/"):
        self.root_data_dir = root_data_dir

        # Determine required voice count from channel definitions
        # Ignore the voice_count parameter now
        voice_count = AudioChannels.voice_count()

        JEBLogger.info("AUDI", f"[INIT] AudioManager - voice_count: {voice_count} root_data_dir: '{self.root_data_dir}'")

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
        self.CH_ATMO = AudioChannels.CH_ATMO
        self.CH_SFX = AudioChannels.CH_SFX
        self.CH_VOICE = AudioChannels.CH_VOICE
        self.CH_SYNTH = AudioChannels.CH_SYNTH

        self.SFX_POOL = AudioChannels.SFX_POOL
        self._sfx_index = 0  # For round-robin SFX channel assignment

        # Cache for frequently used small sound files
        # Format: {"filename": RawSampleObject}
        self._cache = {}

        # Stream buffer for files played from SD
        self._stream_buffer = bytearray(1024)

        # Track open file handles for streaming audio (by channel)
        # Format: {channel_number: file_handle}
        self._stream_files = {}

    def attach_synth(self, synth_source):
        """Attach a synth source (e.g., SynthManager) to the mixer."""
        self.mixer.voice[self.CH_SYNTH].play(synth_source)

    def preload(self, files):
        """
        Loads small WAV files into memory permanently.
        Call this during boot for UI sounds (ticks, clicks, beeps).
        """
        for filename in files:
            filepath = self.root_data_dir + filename

            try:
                file_size = os.stat(filepath).st_size
            except OSError as e:
                JEBLogger.error("AUDI", f"Could not stat {filename}: {e}")
                continue

            if file_size > MAX_PRELOAD_SIZE_BYTES:
                JEBLogger.warning("AUDI", f"Preload oversize {filename} ({file_size} bytes)")
                continue

            try:
                # 1. Open the file, read EVERYTHING into RAM, then let the context manager close it
                with open(filepath, "rb") as f:
                    wav_data = f.read()

                # 2. Wrap the RAM data in an in-memory stream that acts like a file
                wav_stream = io.BytesIO(wav_data)

                # 3. Pass the in-memory stream to WaveFile (which correctly parses the WAV header)
                self._cache[filepath] = audiocore.WaveFile(wav_stream)
                JEBLogger.info("AUDI", f"Preloaded {filename} ({file_size} bytes)")

            except Exception as e:
                JEBLogger.error("AUDI", f"Could not preload {filename}: {e}")

    async def play(self, file, channel=1, loop=False, level=1.0, wait=False, interrupt=True):
        """
        Plays a sound file.
        - file: Filename string.
        - channel: 0=Atmo, 1=SFX, 2=Voice.
        - interrupt: If False, will not play if channel is busy.
        """

        if channel == self.CH_SFX:
            # Round-robin through SFX pool channels
            routed_channel = None
            for sfx_chan in self.SFX_POOL:
                if not self.mixer.voice[sfx_chan].playing:
                    routed_channel = sfx_chan
                    break

            if routed_channel is None:
                routed_channel = self.SFX_POOL[self._sfx_index]
                # Advance the index, looping back to 0 if at the end
                self._sfx_index = (self._sfx_index + 1) % len(self.SFX_POOL)

            channel = routed_channel

        voice = self.mixer.voice[channel]

        # 1. Manage Channel State
        if voice.playing:
            if not interrupt and not wait:
                JEBLogger.info("AUDI", f"Channel {channel} busy, skipping '{file}'")
                return
            elif wait:
                JEBLogger.info("AUDI", f"Waiting for channel {channel} to finish before playing '{file}'")
                while voice.playing:
                    await asyncio.sleep(0.05)
            elif interrupt:
                JEBLogger.info("AUDI", f"Interrupting channel {channel} for '{file}'")

        voice.level = level

        # 2. Source Selection (Cache vs Stream)
        file = self.root_data_dir + file

        if file in self._cache:
            # Use pre-loaded object (Fast, no allocation)
            # Close any existing stream for this channel before playing cached audio
            if channel in self._stream_files:
                try:
                    self._stream_files[channel].close()
                except Exception:
                    pass
                del self._stream_files[channel]
            JEBLogger.info("AUDI", f"Playing cached '{file}' on channel {channel}")
            voice.play(self._cache[file], loop=loop)
        else:
            # Stream from disk (For long narration/music)
            # Close any existing stream for this channel before opening a new one
            if channel in self._stream_files:
                try:
                    self._stream_files[channel].close()
                except Exception:
                    pass
                del self._stream_files[channel]

            try:
                f = open(file, "rb")
            except OSError as e:
                JEBLogger.error("AUDI",f"File not found {file}")
                JEBLogger.error("AUDI",f"Error details: {e}")
            else:
                try:
                    wav = audiocore.WaveFile(f, self._stream_buffer)
                    JEBLogger.info("AUDI", f"Streaming '{file}' on channel {channel}")
                    voice.play(wav, loop=loop)
                except Exception:
                    # Ensure the file handle is not leaked on failure
                    try:
                        f.close()
                    except Exception:
                        pass
                    raise
                else:
                    # Track the file handle so we can close it later
                    self._stream_files[channel] = f

    def stop(self, channel):
        """Stops playback on a specific channel."""

        if channel == self.CH_SFX:
            JEBLogger.info("AUDI", "Stopping all SFX pool channels")
            for sfx_chan in self.SFX_POOL:
                self.mixer.voice[sfx_chan].stop()

                # Safely close any open stream handles for this specific voice
                if sfx_chan in self._stream_files:
                    try:
                        self._stream_files[sfx_chan].close()
                    except Exception:
                        pass
                    del self._stream_files[sfx_chan]
            return

        JEBLogger.info("AUDI", f"Stopping channel {channel}")
        self.mixer.voice[channel].stop()
        # Close any open file handle for this channel
        if channel in self._stream_files:
            try:
                self._stream_files[channel].close()
            except Exception:
                pass
            del self._stream_files[channel]

    def stop_all(self):
        """Stops playback on all channels."""
        JEBLogger.info("AUDI", "Stopping all channels")
        for voice in self.mixer.voice:
            voice.stop()
        # Close all open file handles
        for channel in list(self._stream_files.keys()):
            try:
                self._stream_files[channel].close()
            except Exception:
                pass
        self._stream_files.clear()

    def set_level(self, channel, level):
        """Set volume level for a specific channel."""
        level = max(0.0, min(1.0, level))

        if channel == self.CH_SFX:
            JEBLogger.info("AUDI", f"Setting all SFX pool channels level to {level}")
            for sfx_chan in self.SFX_POOL:
                self.mixer.voice[sfx_chan].level = level
            return

        JEBLogger.info("AUDI", f"Setting channel {channel} level to {level}")
        self.mixer.voice[channel].level = level
