# File: src/managers/buzzer_manager.py
"""
Manages a passive piezo buzzer for hardware alerts and simple UI feedback.
"""
import asyncio
import pwmio

from utilities import tones

class BuzzerManager:
    """Manages a passive piezo buzzer using PWM and asyncio."""

    # Note Frequencies (Hz)
    def __init__(self, pin):
        # Initialize PWM with 0 duty cycle (silence)
        # Variable frequency is required for changing tones
        self.buzzer = pwmio.PWMOut(pin, duty_cycle=0, frequency=440, variable_frequency=True)
        self._current_task = None

        # Standard Duty Cycle (50% is max volume for a piezo)
        self.VOLUME_ON = 2**15
        self.VOLUME_OFF = 0

    def stop(self):
        """Immediately silences the buzzer and cancels running tasks."""
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()

        self.buzzer.duty_cycle = self.VOLUME_OFF

    async def _play_tone_logic(self, frequency, duration):
        """Internal logic to play a single tone."""
        try:
            self.buzzer.frequency = frequency
            self.buzzer.duty_cycle = self.VOLUME_ON
            await asyncio.sleep(duration)
        except asyncio.CancelledError:
            pass
        finally:
            self.buzzer.duty_cycle = self.VOLUME_OFF

    async def _play_sequence_logic(self, sequence, tempo=1.0):
        """
        Internal logic to play a list of (frequency, duration) tuples.
        tempo: Speed multiplier (1.0 = normal, 0.5 = double speed)
        """
        try:
            for freq, dur in sequence:
                if freq == 0:
                    self.buzzer.duty_cycle = self.VOLUME_OFF
                else:
                    self.buzzer.frequency = freq
                    self.buzzer.duty_cycle = self.VOLUME_ON

                await asyncio.sleep(dur * tempo)

                # Tiny gap between notes for articulation
                self.buzzer.duty_cycle = self.VOLUME_OFF
                await asyncio.sleep(0.02)

        except asyncio.CancelledError:
            self.buzzer.duty_cycle = self.VOLUME_OFF
        except ValueError:
            self.buzzer.duty_cycle = self.VOLUME_OFF

    # --- PUBLIC TRIGGERS ---

    def tone(self, frequency, duration=0.1):
        """Plays a single non-blocking tone."""
        self.stop() # Preempt any existing sound
        self._current_task = asyncio.create_task(
            self._play_tone_logic(frequency, duration)
        )

    def sequence(self, sequence, tempo=1.0):
        """Plays a sequence of notes [(freq, dur), ...]."""
        self.stop()
        self._current_task = asyncio.create_task(
            self._play_sequence_logic(sequence, tempo)
        )

    def play_song(self, song_data):
        """Plays a predefined song from tones library."""
        bpm = song_data.get('bpm',120)
        sequence = song_data.get('sequence', [])

        # Calculate beat duration in seconds
        beat_duration = 60.0 / bpm

        # Convert sequence to (frequency, duration in seconds)
        seq_converted = []
        for note_name, beat_length in sequence:
            freq = tones.note(note_name)
            dur = beat_length * beat_duration
            seq_converted.append((freq, dur))

        self.sequence(seq_converted, tempo=1.0)
