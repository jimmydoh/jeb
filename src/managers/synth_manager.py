# File: src/managers/synth_manager.py
"""
Manager for Generative Audio using synthio.
"""

import asyncio
import random
import synthio
from utilities.logger import JEBLogger
from utilities.synth_registry import Patches, Waveforms
from utilities.tones import note

# Ordered patch name list for .jseq file encoding.
# Index must stay in sync with the Audio Studio web UI.
JSEQ_PATCH_NAMES = [
    'RETRO_LEAD', 'RETRO_BASS', 'RETRO_NOISE',
    'BEEP', 'BEEP_SQUARE', 'PAD', 'PUNCH',
    'ALARM', 'SCANNER', 'CLICK', 'NOISE', 'SELECT',
]


def _jseq_midi_to_freq(midi_note):
    """Convert a MIDI note number (0-127) to frequency in Hz."""
    return 440.0 * (2.0 ** ((midi_note - 69) / 12.0))

class SynthManager:
    """
    A reusable SynthIO engine.
    Can be instantiated for Hi-Fi (I2S) or Lo-Fi (PWM/Piezo).
    """

    def __init__(self, sample_rate=22050, channel_count=1, waveform_override=None):
        JEBLogger.info("SYNTH", f"[INIT] SynthManager - sample_rate: {sample_rate}, channel_count: {channel_count}, waveform_override: {waveform_override}")
        self.override = waveform_override

        # Create the synthesizer object
        # mode=synthio.Mode.POLYPHONIC allows multiple notes at once
        self.synth = synthio.Synthesizer(sample_rate=sample_rate, channel_count=channel_count)

        # Background chiptune sequencer task handle
        self._chiptune_task = None

        # Note: Active notes are managed directly by the synthesizer
        # using press() and release() methods

    @property
    def source(self):
        """Returns the synth object to be fed into AudioMixer."""
        return self.synth

    def play_note(self, frequency, patch=None, duration=None):
        """
        Trigger a note.

        Args:
            frequency (float): Frequency in Hz.
            patch (dict): The synth patch to use.
            duration (float): If set, note auto-releases after seconds.
                              If None, note holds until stop_note is called.
        """
        JEBLogger.debug("SYNTH", f"Playing note - frequency: {frequency}, patch: {patch}, duration: {duration}")
        patch = patch or Patches.SELECT
        wave = self.override if self.override else patch["wave"]

        # Create the note object
        # We assume standard amplitude; ADSR handles the rest
        n = synthio.Note(
            frequency=frequency,
            waveform=wave,
            envelope=patch["envelope"]
        )

        # Press the note (start playing)
        self.synth.press(n)

        if duration:
            # If duration is provided, schedule the release
            asyncio.create_task(self._auto_release(n, duration))

        return n

    def stop_note(self, note_obj):
        """Stops a specific note object."""
        self.synth.release(note_obj)

    def release_all(self):
        """Immediately stops all playing notes."""
        self.synth.release_all()

    async def _auto_release(self, note_obj, duration):
        """Background task to release a note after duration."""
        await asyncio.sleep(duration)
        self.synth.release(note_obj)

    async def play_sequence(self, sequence_data, patch=None):
        """
        Play a sequence of notes defined in Tones format.

        Args:
            sequence_data (dict): Dict with 'bpm' and 'sequence' list.
            patch (dict): The synth patch to use.
        """
        bpm = sequence_data.get('bpm', 120)
        beat_duration = 60.0 / bpm

        # LOGIC UPDATE:
        # sequence_data.get('patch') -> Returns Patch Object or None
        # patch -> Returns Patch Object or None
        # Patches.SELECT -> The guaranteed fallback
        active_patch = sequence_data.get('patch') or patch or Patches.SELECT

        wave = self.override if self.override else active_patch["wave"]

        for item in sequence_data['sequence']:
            # Handle both (freq, dur) and ('NoteName', dur) formats
            tone_val, duration_beats = item
            freq = note(tone_val)
            duration_sec = duration_beats * beat_duration

            if freq > 0:
                # Play note
                n = synthio.Note(
                    frequency=freq,
                    waveform=wave,
                    envelope=active_patch["envelope"]
                )
                self.synth.press(n)
                await asyncio.sleep(duration_sec)
                self.synth.release(n)
            else:
                # Rest
                await asyncio.sleep(duration_sec)

            # Small gap between notes for articulation
            await asyncio.sleep(0.01)

    async def start_generative_drone(self):
        """Creates an infinite, shifting background drone."""
        # Frequencies for a C Minor chord (C3, Eb3, G3)
        # We detune them slightly for a 'chorus' effect
        freqs = [130.81, 155.56, 196.00]

        while True:
            # Pick a random note from the chord
            f = random.choice(freqs)

            # Jitter the frequency slightly (+/- 2 Hz) for analog realism
            f_jitter = f + random.uniform(-2, 2)

            # Play it using the ENGINE_HUM patch
            # Duration is random between 3 and 6 seconds
            duration = random.uniform(3.0, 6.0)

            # Fire and forget (the auto_release handles cleanup)
            self.play_note(f_jitter, Patches.ENGINE_HUM, duration)

            # Wait a bit before layering the next note
            # Overlapping notes creates chords
            await asyncio.sleep(random.uniform(2.0, 4.0))

    async def _run_chiptune_channel(self, sequence_data, patch=None):
        """Runs a single chiptune channel in a loop until cancelled."""
        try:
            while True:
                await self.play_sequence(sequence_data, patch=patch)
        except asyncio.CancelledError:
            raise

    async def _run_chiptune_sequencer(self, channels):
        """Runs all chiptune channels concurrently using asyncio.gather."""
        tasks = []
        if 'melody' in channels:
            tasks.append(self._run_chiptune_channel(channels['melody'], Patches.RETRO_LEAD))
        if 'bass' in channels:
            tasks.append(self._run_chiptune_channel(channels['bass'], Patches.RETRO_BASS))
        if 'noise' in channels:
            tasks.append(self._run_chiptune_channel(channels['noise'], Patches.RETRO_NOISE))
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            self.release_all()
            raise

    def start_chiptune_sequencer(self, channels):
        """Starts a 3-channel chiptune sequencer as a background asyncio task.

        Args:
            channels (dict): Channel data with optional keys:
                'melody': sequence_data dict (Square wave lead, RETRO_LEAD patch)
                'bass':   sequence_data dict (Triangle wave bass, RETRO_BASS patch)
                'noise':  sequence_data dict (Noise percussion, RETRO_NOISE patch)

        Returns:
            asyncio.Task: The running task, which can be cancelled to stop playback.
        """
        self.stop_chiptune()
        self._chiptune_task = asyncio.create_task(self._run_chiptune_sequencer(channels))
        return self._chiptune_task

    def stop_chiptune(self):
        """Stops the chiptune sequencer and silences all active notes."""
        if self._chiptune_task and not self._chiptune_task.done():
            self._chiptune_task.cancel()
        self._chiptune_task = None
        self.release_all()

    def load_jseq(self, filepath):
        """Load a .jseq binary sequence file and return a list of channel dicts.

        Each returned dict has 'bpm', 'patch', and 'sequence' keys and is
        compatible with play_sequence().

        Args:
            filepath (str): Path to the .jseq file.

        Returns:
            list: List of channel sequence dicts.

        Raises:
            ValueError: If the file has an invalid format.
        """
        with open(filepath, 'rb') as f:
            data = f.read()

        if len(data) < 8 or data[:4] != b'JSEQ' or data[4] != 1:
            raise ValueError("Invalid or unsupported .jseq file format")

        bpm = data[5] | (data[6] << 8)
        num_channels = data[7]

        channels = []
        pos = 8
        for _ in range(num_channels):
            if pos + 3 > len(data):
                break
            patch_idx = data[pos]
            note_count = data[pos + 1] | (data[pos + 2] << 8)
            pos += 3

            patch_name = JSEQ_PATCH_NAMES[patch_idx] if 0 <= patch_idx < len(JSEQ_PATCH_NAMES) else 'SELECT'
            patch = getattr(Patches, patch_name, Patches.SELECT)

            sequence = []
            for _ in range(note_count):
                if pos + 2 > len(data):
                    break
                note_idx = data[pos]
                dur_units = data[pos + 1]
                pos += 2

                freq = 0 if note_idx == 0 else _jseq_midi_to_freq(note_idx - 1)
                duration_beats = dur_units / 32.0
                sequence.append((freq, duration_beats))

            channels.append({'bpm': bpm, 'patch': patch, 'sequence': sequence})

        return channels

    async def play_jseq(self, filepath):
        """Load and play a .jseq file, running all channels concurrently.

        Args:
            filepath (str): Path to the .jseq file on the filesystem.
        """
        channels_data = self.load_jseq(filepath)
        if not channels_data:
            return
        tasks = [asyncio.create_task(self.play_sequence(ch)) for ch in channels_data]
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            self.release_all()
            raise

    def preview_channels(self, channels_data):
        """Start a one-shot playback of multichannel sequence data.

        Non-blocking: creates an asyncio task and returns immediately.
        Any currently running chiptune or preview is stopped first.

        Args:
            channels_data (list): List of dicts, each with 'bpm', 'patch'
                (patch name string or Patches dict), and 'sequence' list.

        Returns:
            asyncio.Task: The running playback task.
        """
        self.stop_chiptune()

        async def _run_once():
            resolved = []
            for ch in channels_data:
                p = ch.get('patch', Patches.SELECT)
                if isinstance(p, str):
                    p = getattr(Patches, p, Patches.SELECT)
                resolved.append(dict(ch, patch=p))
            tasks = [asyncio.create_task(self.play_sequence(ch)) for ch in resolved]
            try:
                await asyncio.gather(*tasks)
            except asyncio.CancelledError:
                self.release_all()
                raise

        self._chiptune_task = asyncio.create_task(_run_once())
        return self._chiptune_task
