# File: src/utilities/synth_registry.py
"""
Registry for Synthesizer Waveforms, Envelopes, and Patches.
Generates single-cycle waveforms and stores ADSR configurations.
"""

import array
import math
import random
import synthio

#region --- Waveform Maths ---
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
        shifted_i = (i + sample_size // 2) % sample_size
        val = -1 + 2 * (shifted_i / sample_size)
        b[i] = int(val * max_amp)
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

def _generate_pulse(sample_size=512, max_amp=32000, duty=0.25):
    b = array.array("h", [0] * sample_size)
    cutoff = int(sample_size * duty)
    for i in range(sample_size):
        b[i] = max_amp if i < cutoff else -max_amp
    return b

def _generate_noise(sample_size=4096, max_amp=32767, seed=42):
    """Generate a pseudo-random noise waveform for percussion and SFX."""
    rng = random.Random(seed)
    b = array.array("h", [0] * sample_size)
    for i in range(sample_size):
        b[i] = rng.randint(-max_amp, max_amp)
    return b
#endregion

class Waveforms:
    """Generates and stores single-cycle waveforms."""

    SAMPLE_SIZE = 512
    MAX_AMP = 32000 # Keep strictly under 32767 to avoid clipping

    # Pre-generated waveform singletons
    SINE = _generate_sine(SAMPLE_SIZE, MAX_AMP)
    SQUARE = _generate_square(SAMPLE_SIZE, MAX_AMP)
    SAW = _generate_saw(SAMPLE_SIZE, MAX_AMP)
    TRIANGLE = _generate_triangle(SAMPLE_SIZE, MAX_AMP)
    PULSE = _generate_pulse(SAMPLE_SIZE, MAX_AMP)
    PULSE_125 = _generate_pulse(SAMPLE_SIZE, MAX_AMP, duty=0.125)
    NOISE = _generate_noise(sample_size=4096, max_amp=32767)

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

    # 8-Bit Game Lead (Instant ON, Full Volume, Quick Release)
    GAME_LEAD = synthio.Envelope(
        attack_time=0.01,   # Almost instant (prevents popping)
        decay_time=0.0,     # No volume drop
        release_time=0.1,   # Crisp end, no muddy overlapping
        attack_level=0.8,   # 80% volume (saves headroom for chords)
        sustain_level=0.8
    )

    # SFX: Punchy start, quick fade to 50%, sharp release
    GAME_SFX = synthio.Envelope(
        attack_time=0.01,
        decay_time=0.1,    # The "Ping" effect
        release_time=0.2,  # Ring out slightly when finished
        attack_level=1.0,  # Max volume impact
        sustain_level=0.5  # Echo/Ring level
    )

    PERCUSSION = synthio.Envelope(
        attack_time=0.01,
        decay_time=0.15,
        release_time=0.1,
        attack_level=1.0,
        sustain_level=0.0
    )

class Patches:
    """Named combinations of Waveforms and Envelopes."""

    SELECT = {
        "wave": Waveforms.SQUARE,
        "envelope": Envelopes.CLICK
    }

    ERROR = {
        "wave": Waveforms.SAW,
        "envelope": Envelopes.PUNCHY
    }

    CLICK = {
        "wave": Waveforms.SQUARE,
        "envelope": Envelopes.CLICK
    }

    BEEP = {
        "wave": Waveforms.SINE,
        "envelope": Envelopes.BEEP
    }

    BEEP_SQUARE = {
        "wave": Waveforms.SQUARE,
        "envelope": Envelopes.BEEP
    }

    NOISE = {
        "wave": Waveforms.NOISE,
        "envelope": Envelopes.PERCUSSION
    }

    PAD = {
        "wave": Waveforms.TRIANGLE,
        "envelope": Envelopes.PAD
    }

    PUNCH = {
        "wave": Waveforms.SAW,
        "envelope": Envelopes.PUNCHY
    }

    SUCCESS = {
        "wave": Waveforms.SINE,
        "envelope": synthio.Envelope(
            attack_time=0.01,
            decay_time=0.2,
            release_time=0.4,
            attack_level=0.8,
            sustain_level=0.0 # Bell-like ring out
        )
    }

    ALARM = {
        "wave": Waveforms.SAW,
        "envelope": Envelopes.BEEP
    }

    SONAR = {
        "wave": Waveforms.SINE,
        "envelope": synthio.Envelope(
            attack_time=0.001,
            decay_time=0.5,
            release_time=0.5,
            attack_level=1.0,
            sustain_level=0.0
        )
    }

    # Classic NES Melody
    RETRO_LEAD = {
        "wave": Waveforms.SQUARE, # The authentic Mario waveform
        "envelope": Envelopes.GAME_LEAD
    }

    RETRO_SFX = {
        "wave": Waveforms.PULSE,
        "envelope": Envelopes.GAME_SFX
    }

    RETRO_COIN = {
        "wave": Waveforms.PULSE,
        "envelope": Envelopes.GAME_SFX
    }



    TEXT_SCROLL = {
        "wave": Waveforms.TRIANGLE,
        "envelope": synthio.Envelope(
            attack_time=0.001,
            decay_time=0.03,
            release_time=0.03,
            attack_level=0.3, # Very quiet
            sustain_level=0.0
        )
    }

    ETHEREAL = {
        "wave": Waveforms.TRIANGLE,
        "envelope": synthio.Envelope(
            attack_time=1.0,  # Slow fade in
            decay_time=0.5,
            release_time=2.0, # Long fade out
            attack_level=0.7,
            sustain_level=0.7
        )
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

    # 3-channel chiptune: bass channel (Triangle, instant response)
    RETRO_BASS = {
        "wave": Waveforms.TRIANGLE,
        "envelope": Envelopes.GAME_LEAD
    }

    # 3-channel chiptune: noise/percussion channel (short burst of noise)
    RETRO_NOISE = {
        "wave": Waveforms.NOISE,
        "envelope": synthio.Envelope(
            attack_time=0.001,
            decay_time=0.05,
            release_time=0.02,
            attack_level=0.6,
            sustain_level=0.0
        )
    }
