# File: src/core/managers/audio_manager.py
"""Audio Manager Module"""

import asyncio
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

        JEBLogger.info("AUDI", f"[INIT] AudioManager - voice_count: {voice_count} root_data_dir: '{self.root_data_dir}'")

        # Determine required voice count from channel definitions
        required_voices = AudioChannels.get_required_voice_count()

        # Use provided voice_count if specified, otherwise use required minimum
        # This maintains backward compatibility while ensuring sufficient voices
        if voice_count is None:
            voice_count = required_voices
        elif voice_count < required_voices:
            raise ValueError(
                f"voice_count ({voice_count}) must be at least {required_voices} "
                f"to support all defined audio channels"
            )

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
        self.CH_SFX  = AudioChannels.CH_SFX
        self.CH_VOICE = AudioChannels.CH_VOICE
        self.CH_SYNTH = AudioChannels.CH_SYNTH

        # Cache for frequently used small sound files
        # Format: {"filename": RawSampleObject}
        self._cache = {}

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
        Decodes the audio into RAM and closes file handles immediately.

        Files larger than 20KB are skipped and will be streamed from disk instead.
        This prevents MemoryError on RP2350 with limited RAM (520KB).
        """
        import os

        for filename in files:
            try:
                filepath = self.root_data_dir + filename

                # Check file size before attempting to load
                try:
                    file_size = os.stat(filepath).st_size
                except OSError as e:
                    JEBLogger.error("AUDI",f"Could not stat {filename}")
                    JEBLogger.error("AUDI",f"Error details: {e}")
                    continue

                # Only preload files smaller than 20KB
                if file_size > MAX_PRELOAD_SIZE_BYTES:
                    JEBLogger.warning("AUDI",f"Preload oversize {filename} ({file_size} bytes)")
                    continue

                # Open the file and create a RawSample object
                f = open(filepath, "rb")
                try:
                    # WaveFile will read and decode the WAV file
                    raw_sample = audiocore.RawSample(f)
                    self._cache[filepath] = raw_sample
                    JEBLogger.info("AUDI",f"Preloaded {filename} ({file_size} bytes)")
                finally:
                    # Always close the file handle
                    f.close()
            except OSError as e:
                JEBLogger.error("AUDI",f"Could not preload {filename}")
                JEBLogger.error("AUDI",f"Error details: {e}")

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
                    wav = audiocore.WaveFile(f, bytearray(1024))
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
        self.mixer.voice[channel].level = level
