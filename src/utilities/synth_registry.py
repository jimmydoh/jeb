# File: src/utilities/synth_registry.py
"""
Registry for Synthesizer Waveforms, Envelopes, and Patches.
Generates single-cycle waveforms and stores ADSR configurations.
"""

import array
import math
import synthio

class Waveforms:
    """Generates and stores single-cycle waveforms."""

    SAMPLE_SIZE = 512
    MAX_AMP = 32000 # Keep strictly under 32767 to avoid clipping

    @staticmethod
    def _generate_sine():
        b = array.array("h", [0] * Waveforms.SAMPLE_SIZE)
        for i in range(Waveforms.SAMPLE_SIZE):
            b[i] = int(math.sin(math.pi * 2 * i / Waveforms.SAMPLE_SIZE) * Waveforms.MAX_AMP)
        return b

    @staticmethod
    def _generate_square():
        b = array.array("h", [0] * Waveforms.SAMPLE_SIZE)
        half = Waveforms.SAMPLE_SIZE // 2
        for i in range(Waveforms.SAMPLE_SIZE):
            b[i] = Waveforms.MAX_AMP if i < half else -Waveforms.MAX_AMP
        return b

    @staticmethod
    def _generate_saw():
        b = array.array("h", [0] * Waveforms.SAMPLE_SIZE)
        for i in range(Waveforms.SAMPLE_SIZE):
            # Scale 0..SIZE to -MAX..MAX
            b[i] = int(-Waveforms.MAX_AMP + (2 * Waveforms.MAX_AMP * i / Waveforms.SAMPLE_SIZE))
        return b

    @staticmethod
    def _generate_triangle():
        b = array.array("h", [0] * Waveforms.SAMPLE_SIZE)
        quarter = Waveforms.SAMPLE_SIZE // 4
        three_quarter = 3 * Waveforms.SAMPLE_SIZE // 4
        for i in range(Waveforms.SAMPLE_SIZE):
            if i < quarter:
                val = i / quarter
            elif i < three_quarter:
                val = 2 - (i - quarter) / quarter
            else:
                val = -1 + (i - three_quarter) / quarter
            b[i] = int(val * Waveforms.MAX_AMP)
        return b

    # Lazy-loaded singletons
    SINE = _generate_sine()
    SQUARE = _generate_square()
    SAW = _generate_saw()
    TRIANGLE = _generate_triangle()


class Envelopes:
    """Pre-defined ADSR Envelopes."""

    # Click / Blip (Instant attack, fast decay)
    CLICK = synthio.Envelope(
        attack_time=0.001,
        decay_time=0.05,
        release_time=0.05,
        attack_level=1.0,
        sustain_level=0.0
    )

    # Standard Beep (Short attack, full sustain, short release)
    BEEP = synthio.Envelope(
        attack_time=0.01,
        decay_time=0.0,
        release_time=0.1,
        attack_level=1.0,
        sustain_level=1.0
    )

    # Soft Pad / Hum (Slow attack, slow release)
    PAD = synthio.Envelope(
        attack_time=0.5,
        decay_time=0.2,
        release_time=0.5,
        attack_level=0.8,
        sustain_level=0.8
    )

    # Retro "Laser" or Alarm (Punchy)
    PUNCHY = synthio.Envelope(
        attack_time=0.005,
        decay_time=0.1,
        release_time=0.1,
        attack_level=1.0,
        sustain_level=0.6
    )


class Patches:
    """Named combinations of Waveforms and Envelopes."""

    UI_SELECT = {
        "wave": Waveforms.SQUARE,
        "envelope": Envelopes.CLICK
    }

    UI_ERROR = {
        "wave": Waveforms.SAW,
        "envelope": Envelopes.PUNCHY
    }

    ALARM = {
        "wave": Waveforms.SAW,
        "envelope": Envelopes.BEEP
    }

    IDLE_HUM = {
        "wave": Waveforms.SINE,
        "envelope": Envelopes.PAD
    }

    SCANNER = {
        "wave": Waveforms.TRIANGLE,
        "envelope": Envelopes.BEEP
    }

    ENGINE_HUM = {
        "wave": Waveforms.TRIANGLE, # Triangle has slightly more 'grit' than Sine
        "envelope": synthio.Envelope(
            attack_time=1.5,    # Takes 1.5s to reach full volume (Smooth)
            decay_time=0.0,
            release_time=1.5,   # Takes 1.5s to fade out (No sudden cuts)
            attack_level=0.4,   # Keep volume low (40%) so it doesn't overpower voice/SFX
            sustain_level=0.4
        )
    }

    DATA_STREAM = {
        "wave": Waveforms.SQUARE,
        "envelope": synthio.Envelope(
            attack_time=0.05,
            decay_time=0.1,
            release_time=0.1,
            attack_level=0.15,  # Very quiet
            sustain_level=0.0
        )
    }
