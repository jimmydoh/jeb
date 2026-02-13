# File: src/utilities/synth_registry.py
"""
Registry for Synthesizer Waveforms, Envelopes, and Patches.
Generates single-cycle waveforms and stores ADSR configurations.
"""

import array
import math
import synthio

def _generate_sine(sample_size=512, max_amp=32000):
    b = array.array("h", [0] * sample_size)
    for i in range(sample_size):
        b[i] = int(math.sin(math.pi * 2 * i / sample_size) * max_amp)
    return b

def _generate_square(sample_size=512, max_amp=32000):
    b = array.array("h", [0] * sample_size)
    half = sample_size // 2
    for i in range(sample_size):
        b[i] = max_amp if i < half else -max_amp
    return b

def _generate_saw(sample_size=512, max_amp=32000):
    b = array.array("h", [0] * sample_size)
    for i in range(sample_size):
        # Scale 0..SIZE to -MAX..MAX
        b[i] = int(-max_amp + (2 * max_amp * i / sample_size))
    return b

def _generate_triangle(sample_size=512, max_amp=32000):
    b = array.array("h", [0] * sample_size)
    for i in range(sample_size):
        # 1. Create a ramp from 0.0 to 1.0
        phase = i / sample_size
        # 2. Shift and use absolute value to create the 'V' shape
        # 4 * abs(phase - 0.5) - 1  gives a range of -1 to 1
        val = 1 - 4 * abs(0.5 - ((phase + 0.25) % 1.0))
        b[i] = int(val * max_amp)
    return b

class Waveforms:
    """Generates and stores single-cycle waveforms."""

    SAMPLE_SIZE = 512
    MAX_AMP = 32000 # Keep strictly under 32767 to avoid clipping

    # Pre-generated waveform singletons
    SINE = _generate_sine(SAMPLE_SIZE, MAX_AMP)
    SQUARE = _generate_square(SAMPLE_SIZE, MAX_AMP)
    SAW = _generate_saw(SAMPLE_SIZE, MAX_AMP)
    TRIANGLE = _generate_triangle(SAMPLE_SIZE, MAX_AMP)

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
