# File: src/core/managers/audio_manager.py
"""Audio Manager Module"""

import asyncio
import audiobusio
import audiocore
import audiomixer

# Maximum file size (in bytes) for preloading into RAM
# Files larger than this will be streamed from disk to prevent MemoryError
MAX_PRELOAD_SIZE_BYTES = 20 * 1024  # 20KB

class AudioManager:
    """Manages audio playback and mixing."""
    def __init__(self, sck, ws, sd, voice_count=4, root_data_dir="/"):
        self.root_data_dir = root_data_dir
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
        self.CH_SYNTH = 3

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
                except OSError:
                    print(f"Audio Error: Could not stat {filename}")
                    continue

                # Only preload files smaller than 20KB
                if file_size > MAX_PRELOAD_SIZE_BYTES:
                    print(f"Audio Info: Skipping preload of {filename} ({file_size} bytes > {MAX_PRELOAD_SIZE_BYTES} bytes). Will stream from disk.")
                    continue

                # Open the file and create a RawSample object
                f = open(filepath, "rb")
                try:
                    # WaveFile will read and decode the WAV file
                    raw_sample = audiocore.RawSample(f)
                    self._cache[filepath] = raw_sample
                    print(f"Audio Info: Preloaded {filename} ({file_size} bytes)")
                finally:
                    # Always close the file handle
                    f.close()
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
        file = self.root_data_dir + file

        if file in self._cache:
            # Use pre-loaded object (Fast, no allocation)
            # Close any existing stream for this channel before playing cached audio
            if channel in self._stream_files:
                try:
                    self._stream_files[channel].close()
                except:
                    pass
                del self._stream_files[channel]
            voice.play(self._cache[file], loop=loop)
        else:
            # Stream from disk (For long narration/music)
            # Close any existing stream for this channel before opening a new one
            if channel in self._stream_files:
                try:
                    self._stream_files[channel].close()
                except:
                    pass
                del self._stream_files[channel]
            
            try:
                f = open(file, "rb")
                wav = audiocore.WaveFile(f, bytearray(1024))
                voice.play(wav, loop=loop)
                # Track the file handle so we can close it later
                self._stream_files[channel] = f
            except OSError:
                print(f"Audio Error: File {file} not found")

    def stop(self, channel):
        """Stops playback on a specific channel."""
        self.mixer.voice[channel].stop()
        # Close any open file handle for this channel
        if channel in self._stream_files:
            try:
                self._stream_files[channel].close()
            except:
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
            except:
                pass
        self._stream_files.clear()

    def set_level(self, channel, level):
        """Set volume level for a specific channel."""
        self.mixer.voice[channel].level = level
