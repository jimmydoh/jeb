# File: src/managers/buzzer_manager.py
"""
Manages a passive piezo buzzer for hardware alerts and simple UI feedback.
"""
import asyncio
import pwmio

from utilities import tones

class BuzzerManager:
    """Manages a passive piezo buzzer using PWM and asyncio."""

    def __init__(self, pin, volume=0.5, testing=False):
        # Initialize PWM with 0 duty cycle (silence)
        # Variable frequency is required for changing tones
        self.testing = testing
        self.buzzer = pwmio.PWMOut(pin, duty_cycle=0, frequency=440, variable_frequency=True)
        self._current_task = None

        # Standard Duty Cycle (50% is max volume for a piezo)
        if volume < 0.0 or volume > 1.0:
            raise ValueError("Volume must be between 0.0 and 1.0")

        # Map volume [0.0, 1.0] directly to 16-bit duty cycle range [0, 65535]
        self.VOLUME_ON = int(volume * (2**16 - 1))
        self.VOLUME_OFF = 0

    async def stop(self):
        """Immediately silences the buzzer and cancels running tasks."""
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            try:
                await self._current_task
            except asyncio.CancelledError:
                pass

        self.buzzer.duty_cycle = self.VOLUME_OFF

    async def _play_tone_logic(self, frequency, duration=None):
        """Internal logic to play a single tone."""
        try:
            self.buzzer.frequency = frequency
            self.buzzer.duty_cycle = self.VOLUME_ON
            if duration is not None and duration > 0:
                await asyncio.sleep(duration)
                self.buzzer.duty_cycle = self.VOLUME_OFF
        except asyncio.CancelledError:
            self.buzzer.duty_cycle = self.VOLUME_OFF

    async def _play_sequence_logic(self, sequence, tempo=1.0, loop=False):
        """
        Internal logic to play a list of (frequency, duration) tuples.
        
        Args:
            sequence: List of (frequency, duration) tuples to play
            tempo: Duration multiplier applied to each note's length
                - 1.0 = normal timing
                - < 1.0 = faster playback (e.g., 0.5 = double speed: half the duration)
                - > 1.0 = slower playback (e.g., 2.0 = half speed: double the duration)
            loop: If True, repeat the sequence indefinitely
        """
        try:
            while True:
                for freq, dur in sequence:
                    freq_rounded = int(round(freq))
                    if self.testing:
                        print(f"Playing freq: {freq_rounded} Hz for {dur} sec")
                    if freq <= 0:
                        self.buzzer.duty_cycle = self.VOLUME_OFF
                    else:
                        self.buzzer.frequency = freq_rounded
                        self.buzzer.duty_cycle = self.VOLUME_ON

                    await asyncio.sleep(dur * tempo)

                    # Tiny gap between notes for articulation
                    self.buzzer.duty_cycle = self.VOLUME_OFF
                    await asyncio.sleep(0.01)

                if not loop:
                    break

                await asyncio.sleep(0.1)  # Short pause before repeating

        except asyncio.CancelledError:
            self.buzzer.duty_cycle = self.VOLUME_OFF
        except ValueError as e:
            print(f"🔊 BuzzerManager Error: Buzzer sequence ValueError: {e}")
            self.buzzer.duty_cycle = self.VOLUME_OFF

    # --- PUBLIC TRIGGERS ---

    async def _play_tone(self, frequency, duration=None):
        """Plays a single non-blocking tone."""
        await self.stop()  # Preempt any existing sound
        self._current_task = asyncio.create_task(
            self._play_tone_logic(frequency, duration)
        )

    async def _play_sequence(self, sequence, tempo=1.0, loop=False):
        """Plays a sequence of notes [(freq, dur), ...]."""
        await self.stop()
        self._current_task = asyncio.create_task(
            self._play_sequence_logic(sequence, tempo, loop)
        )

    def play_note(self, frequency, duration=None):
        """Public method to play a single note."""
        asyncio.create_task(self._play_tone(frequency, duration))

    def play_sequence(self, sequence_data, loop=None):
        """Plays a sequence in JEB tones format."""

        # Handle string input for convenience
        if isinstance(sequence_data, str):
            # Normalize to uppercase to be safe
            song_name = sequence_data.upper()

            # Check if this exists in the imported 'tones' library
            if hasattr(tones, song_name):
                sequence_data = getattr(tones, song_name)
            else:
                print(f"🔊 BuzzerManager Warning: Song '{song_name}' not found in tones.py")
                return

        if not isinstance(sequence_data, dict):
            print(f"🔊 BuzzerManager Warning: Invalid sequence_data format: expected dict, got {type(sequence_data).__name__}")
            return

        bpm = sequence_data.get('bpm', 120)
        sequence = sequence_data.get('sequence', [])

        should_loop = loop if loop is not None else sequence_data.get('loop', False)

        print(f"Playing song at {bpm} BPM with {len(sequence)} notes.")

        # Calculate beat duration in seconds
        beat_duration = 60.0 / bpm

        # Convert sequence to (frequency, duration in seconds)
        seq_converted = []
        for note_name, beat_length in sequence:
            freq = tones.note(note_name)
            dur = beat_length * beat_duration
            seq_converted.append((freq, dur))

        asyncio.create_task(self._play_sequence(seq_converted, tempo=1.0, loop=should_loop))