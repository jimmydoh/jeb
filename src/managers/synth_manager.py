# File: src/managers/synth_manager.py
"""
Manager for Generative Audio using synthio.
"""

import asyncio
import random
import synthio
from utilities.synth_registry import Patches
from utilities.tones import note

class SynthManager:
    """
    Controls real-time audio synthesis.
    Must be connected to the Mixer in AudioManager or CoreManager.
    """

    def __init__(self, sample_rate=22050):
        # Create the synthesizer object
        # mode=synthio.Mode.POLYPHONIC allows multiple notes at once
        self.synth = synthio.Synthesizer(sample_rate=sample_rate)

        # Note: Active notes are managed directly by the synthesizer
        # using press() and release() methods

    @property
    def source(self):
        """Returns the synth object to be fed into AudioMixer."""
        return self.synth

    def play_note(self, frequency, patch_name="UI_SELECT", duration=None):
        """
        Trigger a note.

        Args:
            frequency (float): Frequency in Hz.
            patch_name (str): Key from Patches registry (e.g., 'UI_SELECT').
            duration (float): If set, note auto-releases after seconds.
                              If None, note holds until stop_note is called.
        """
        patch = getattr(Patches, patch_name, None)
        if patch is None:
            print(f"Warning: Patch '{patch_name}' not found, using UI_SELECT")
            patch = Patches.UI_SELECT

        # Create the note object
        # We assume standard amplitude; ADSR handles the rest
        n = synthio.Note(
            frequency=frequency,
            waveform=patch["wave"],
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

    async def play_sequence(self, sequence_data, patch_name="UI_SELECT"):
        """
        Play a sequence of notes defined in Tones format.

        Args:
            sequence_data (dict): Dict with 'bpm' and 'sequence' list.
            patch_name (str): The synth patch to use.
        """
        bpm = sequence_data.get('bpm', 120)
        beat_duration = 60.0 / bpm

        patch = getattr(Patches, patch_name, None)
        if patch is None:
            print(f"Warning: Patch '{patch_name}' not found, using UI_SELECT")
            patch = Patches.UI_SELECT

        for item in sequence_data['sequence']:
            # Handle both (freq, dur) and ('NoteName', dur) formats
            tone_val, duration_beats = item
            freq = note(tone_val)
            duration_sec = duration_beats * beat_duration

            if freq > 0:
                # Play note
                n = synthio.Note(
                    frequency=freq,
                    waveform=patch["wave"],
                    envelope=patch["envelope"]
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
            self.play_note(f_jitter, "ENGINE_HUM", duration)

            # Wait a bit before layering the next note
            # Overlapping notes creates chords
            await asyncio.sleep(random.uniform(2.0, 4.0))
