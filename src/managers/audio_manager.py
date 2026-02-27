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
    def __init__(self, sck, ws, sd, root_data_dir="/"):

        # Bus ID Aliases for code readability
        self.CH_ATMO = AudioChannels.CH_ATMO
        self.CH_SFX = AudioChannels.CH_SFX
        self.CH_VOICE = AudioChannels.CH_VOICE
        self.CH_SYNTH = AudioChannels.CH_SYNTH

        # Map buses to pools
        self.pools = {
            self.CH_ATMO: [0, 1],
            self.CH_VOICE: [2],
            self.CH_SYNTH: [3],
            self.CH_SFX: [4, 5, 6]
        }

        # Track the round-robin index for each pool
        self._pool_rr_index = {bus_id: 0 for bus_id in self.pools}

        # Voice count for mixer
        self.voice_count = max(v for pool in self.pools.values() for v in pool) + 1

        # Data storage root
        self.root_data_dir = root_data_dir

        JEBLogger.info("AUDI", f"[INIT] AudioManager - voice_count: {self.voice_count} root_data_dir: '{self.root_data_dir}'")

        self.audio = audiobusio.I2SOut(sck, ws, sd)
        self.mixer = audiomixer.Mixer(
            voice_count=self.voice_count,
            sample_rate=22050,
            channel_count=1,
            bits_per_sample=16,
            samples_signed=True
        )
        self.audio.play(self.mixer)

        # Cache for frequently used small sound files
        # Format: {"filename": RawSampleObject}
        self._cache = {}

        # Stream buffer for files played from SD
        self._stream_buffer = bytearray(1024)

        # Track open file handles for streaming audio (by channel)
        # Format: {channel_number: file_handle}
        self._stream_files = {}

    # --- Helper Methods ---
    def _allocate_voice(self, bus_id):
        """
        Determines the best physical voice to use for a given logical bus.
        """
        pool = self.pools.get(bus_id)
        if not pool:
            raise ValueError(f"Unknown audio bus: {bus_id}")

        # If it's a single-voice pool (VOICE, SYNTH), just return it
        if len(pool) == 1:
            return pool[0]

        # For multi-voice pools, try to find a completely silent voice first
        for voice_idx in pool:
            if not self.mixer.voice[voice_idx].playing:
                return voice_idx

        # If all voices in the pool are busy, use Round-Robin to overwrite the oldest
        allocated_idx = pool[self._pool_rr_index[bus_id]]

        # Advance the index for the next request
        self._pool_rr_index[bus_id] = (self._pool_rr_index[bus_id] + 1) % len(pool)

        return allocated_idx

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

    async def play(self, file, bus_id=1, loop=False, level=1.0, wait=False, interrupt=True):
        """
        Plays a sound file.
        - file: Filename string.
        - bus_id: Logical bus ID (0=Atmo, 1=SFX, 2=Voice).
        - interrupt: If False, will not play if bus is busy.
        """

        # 1. Allocate a physical voice using the new pool logic
        try:
            voice_idx = self._allocate_voice(bus_id)
        except ValueError as e:
            JEBLogger.error("AUDI", str(e))
            return

        voice = self.mixer.voice[voice_idx]

        # 1. Manage Channel State
        if voice.playing:
            if not interrupt and not wait:
                JEBLogger.info("AUDI", f"Voice {voice_idx} busy on bus {bus_id}, skipping '{file}'")
                return
            elif wait:
                JEBLogger.info("AUDI", f"Waiting for voice {voice_idx} on bus {bus_id} to finish before playing '{file}'")
                while voice.playing:
                    await asyncio.sleep(0.05)
            elif interrupt:
                JEBLogger.info("AUDI", f"Interrupting voice {voice_idx} on bus {bus_id} for '{file}'")

        voice.level = level

        # Source Selection (Cache vs Stream)
        full_path = self.root_data_dir + file

        if full_path in self._cache:
            # --- CACHED AUDIO ---
            # Close any existing stream for this PHYSICAL voice before playing cached audio
            if voice_idx in self._stream_files:
                try:
                    self._stream_files[voice_idx].close()
                except Exception:
                    pass
                del self._stream_files[voice_idx]

            JEBLogger.info("AUDI", f"Playing cached '{file}' on voice {voice_idx} (Bus {bus_id})")
            voice.play(self._cache[full_path], loop=loop)

        else:
            # --- STREAMED AUDIO ---
            # Close any existing stream for this PHYSICAL voice before opening a new one
            if voice_idx in self._stream_files:
                try:
                    self._stream_files[voice_idx].close()
                except Exception:
                    pass
                del self._stream_files[voice_idx]

            try:
                f = open(full_path, "rb")
            except OSError as e:
                JEBLogger.error("AUDI", f"File not found: {full_path} - {e}")
            else:
                try:
                    wav = audiocore.WaveFile(f, self._stream_buffer)
                    JEBLogger.info("AUDI", f"Streaming '{file}' on voice {voice_idx} (Bus {bus_id})")
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
                    self._stream_files[voice_idx] = f

    async def fade_out(self, bus_id, duration=1.0):
        """
        Gradually fades out an entire logical bus over the specified duration (in seconds),
        then cleanly stops playback and releases file handles.
        """
        JEBLogger.info("AUDI", f"Fading out bus {bus_id} over {duration}s")

        pool = self.pools.get(bus_id)
        if not pool:
            JEBLogger.error("AUDI", f"Cannot fade out unknown bus {bus_id}")
            return

        # 1. Target only the actively playing voices in this pool
        voices_to_fade = []
        initial_levels = []

        for voice_idx in pool:
            if self.mixer.voice[voice_idx].playing:
                voices_to_fade.append(voice_idx)
                initial_levels.append(self.mixer.voice[voice_idx].level)

        # Exit early if the bus is already silent
        if not voices_to_fade:
            return

        # 2. Calculate fade steps
        update_interval = 0.05
        steps = max(1, int(duration / update_interval))

        # 3. The Async Fade Loop
        for step in range(steps):
            progress = step / steps

            for i, v_idx in enumerate(voices_to_fade):
                if self.mixer.voice[v_idx].playing:
                    # Linearly interpolate volume toward zero
                    current_vol = initial_levels[i] * (1.0 - progress)
                    self.mixer.voice[v_idx].level = max(0.0, current_vol)

            await asyncio.sleep(update_interval)

        # 4. Final Cleanup
        # self.stop() handles stopping the hardware and closing all file streams in the pool
        self.stop(bus_id)

        # Reset the channel volumes back to their defaults for future plays
        for i, v_idx in enumerate(voices_to_fade):
            self.mixer.voice[v_idx].level = initial_levels[i]

    async def crossfade(self, new_file, bus_id=0, duration=2.0, level=1.0, loop=True):
        """
        Smoothly transitions between the currently playing track and a new one
        on a multi-voice bus (like ATMO) using pool allocation.
        """
        pool = self.pools.get(bus_id)

        # Guard: Ensure the bus actually supports crossfading
        if not pool or len(pool) < 2:
            JEBLogger.warning("AUDI", f"Bus {bus_id} lacks the voices for crossfading. Falling back to hard cut.")
            await self.play(new_file, bus_id=bus_id, loop=loop, level=level)
            return

        # 1. Identify the currently active voice (the one fading out)
        active_voice_idx = next((v for v in pool if self.mixer.voice[v].playing), None)

        if active_voice_idx is None:
            # If the bus is silent, just fade/play it in normally
            JEBLogger.info("AUDI", f"Bus {bus_id} is silent. Starting '{new_file}'.")
            await self.play(new_file, bus_id=bus_id, loop=loop, level=level)
            return

        JEBLogger.info("AUDI", f"Crossfading bus {bus_id} to '{new_file}'")

        # 2. Start the new track at zero volume
        # Our _allocate_voice helper handles finding the free secondary voice perfectly
        await self.play(new_file, bus_id=bus_id, loop=loop, level=0.0)

        # 3. Identify the newly activated voice (the one fading in)
        free_voice_idx = next((v for v in pool if self.mixer.voice[v].playing and v != active_voice_idx), None)

        if free_voice_idx is None:
            JEBLogger.error("AUDI", f"Crossfade failed: Could not allocate a secondary voice on bus {bus_id}.")
            return

        # 4. The Async Crossfade Loop
        update_interval = 0.05
        steps = max(1, int(duration / update_interval))

        start_level_out = self.mixer.voice[active_voice_idx].level
        target_level_in = level

        for step in range(steps):
            progress = step / steps

            # Fade OUT the old active voice
            if self.mixer.voice[active_voice_idx].playing:
                current_out = start_level_out * (1.0 - progress)
                self.mixer.voice[active_voice_idx].level = max(0.0, current_out)

            # Fade IN the new free voice
            if self.mixer.voice[free_voice_idx].playing:
                current_in = target_level_in * progress
                self.mixer.voice[free_voice_idx].level = min(target_level_in, current_in)

            await asyncio.sleep(update_interval)

        # 5. Final Cleanup
        # We MUST manually close the old voice specifically.
        # Calling self.stop(bus_id) would kill the entire pool, destroying our new track!
        JEBLogger.info("AUDI", f"Cleaning up old crossfade voice {active_voice_idx}")
        self.mixer.voice[active_voice_idx].stop()

        if active_voice_idx in self._stream_files:
            try:
                self._stream_files[active_voice_idx].close()
            except Exception:
                pass
            del self._stream_files[active_voice_idx]

        # Ensure the new voice lands exactly on the target volume to avoid rounding errors
        self.mixer.voice[free_voice_idx].level = target_level_in

    def stop(self, bus_id):
        """Stops playback on an entire logical bus."""
        JEBLogger.info("AUDI", f"Stopping bus {bus_id}")

        if bus_id in self.pools:
            for voice_idx in self.pools[bus_id]:
                self.mixer.voice[voice_idx].stop()

                # Close any open file handle for this voice
                if voice_idx in self._stream_files:
                    try:
                        self._stream_files[voice_idx].close()
                    except Exception:
                        pass
                    del self._stream_files[voice_idx]

    def stop_all(self):
        """Stops playback on all buses."""
        JEBLogger.info("AUDI", "Stopping all buses")
        for voice in self.mixer.voice:
            voice.stop()
        # Close all open file handles
        for voice_idx in list(self._stream_files.keys()):
            try:
                self._stream_files[voice_idx].close()
            except Exception:
                pass
        self._stream_files.clear()

    def set_level(self, bus_id, level):
        """Set volume level for an entire logical bus."""
        # Clamp level to safe bounds (0.0 to 1.0)
        level = max(0.0, min(1.0, level))

        pool = self.pools.get(bus_id)
        if not pool:
            JEBLogger.warning("AUDI", f"Cannot set level for unknown bus {bus_id}")
            return

        JEBLogger.info("AUDI", f"Setting bus {bus_id} level to {level}")

        # Apply the new volume to every physical voice assigned to this bus
        for voice_idx in pool:
            self.mixer.voice[voice_idx].level = level

    def update(self):
        """
        Polls the hardware voices to clean up file handles for streams
        that have finished playing naturally.
        """
        # Iterate over a list of keys so we can safely delete from the dict
        for voice_idx in list(self._stream_files.keys()):
            if not self.mixer.voice[voice_idx].playing:
                # The stream hit EOF naturally. Close the file.
                try:
                    self._stream_files[voice_idx].close()
                except Exception:
                    pass
                del self._stream_files[voice_idx]
