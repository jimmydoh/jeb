# File: src/managers/buzzer_manager.py
"""
Manages a passive piezo buzzer for hardware alerts and simple UI feedback.
"""
import audiopwmio
from managers.synth_manager import SynthManager
from utilities.synth_registry import Waveforms

class BuzzerManager:
    """Manages a passive piezo buzzer using PWM and asyncio."""

    # Note Frequencies (Hz)
    def __init__(self, pin):
        # Setup Hardware
        self.audio = audiopwmio.PWMAudioOut(pin)

        # Setup Logic (The Synth Manager)
        self.engine = SynthManager(
            sample_rate=22050,
            channel_count=1,
            waveform_override=Waveforms.SQUARE
        )

        self.audio.play(self.engine.source)

    async def stop(self):
        """Immediately silences the buzzer and cancels running tasks."""
        self.engine.release_all()

    def play_note(self, frequency, duration=None):
        """Plays a single non-blocking tone."""
        # Delegate logic to the engine
        self.engine.play_note(frequency, duration=duration)

    async def play_sequence(self, sequence_data):
        """Plays a sequence of notes [(freq, dur), ...]."""
        await self.engine.play_sequence(sequence_data)
