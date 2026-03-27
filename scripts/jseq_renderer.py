import struct
import array
import math
import random
import os
import argparse
import numpy as np
from scipy.io import wavfile

# --- THE SYNTHIO MOCK ---
# We must inject a fake 'synthio' module into CPython before importing the registry
import sys
import types

# 1. Create a dummy module
mock_synthio = types.ModuleType('synthio')

# 2. Define a fake Envelope class that just stores the ADSR values
class MockEnvelope:
    def __init__(self, attack_time=0.0, decay_time=0.0, release_time=0.0, attack_level=1.0, sustain_level=1.0):
        self.attack_time = attack_time
        self.decay_time = decay_time
        self.release_time = release_time
        self.attack_level = attack_level
        self.sustain_level = sustain_level

# 3. Attach the class and inject the module into the system
mock_synthio.Envelope = MockEnvelope
sys.modules['synthio'] = mock_synthio
# ------------------------

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

def _generate_noise(sample_size=4096, max_amp=32767):
    """Generate a pseudo-random noise waveform for percussion and SFX."""
    b = array.array("h", [0] * sample_size)
    for i in range(sample_size):
        b[i] = random.randint(-max_amp, max_amp)
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
    _NOISE = None  # Lazy-generated on first use to reduce boot latency

    @classmethod
    def get_noise(cls):
        """Return the NOISE waveform, generating it on first use.

        Safe to call from the asyncio event loop: CircuitPython uses cooperative
        multitasking so no preemptive race can occur between the None check and
        the assignment.
        """
        if cls._NOISE is None:
            cls._NOISE = _generate_noise(sample_size=4096, max_amp=32767)
        return cls._NOISE

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

    CUSTOM_BLANK = synthio.Envelope(
        attack_time=1.0,
        decay_time=1.0,
        release_time=1.0,
        attack_level=1.0,
        sustain_level=1.0
    )

class Patches:
    """Named combinations of Waveforms and Envelopes."""

    SELECT = {
        "name": "SELECT",
        "wave": Waveforms.SQUARE,
        "envelope": Envelopes.CLICK
    }

    ERROR = {
        "name": "ERROR",
        "wave": Waveforms.SAW,
        "envelope": Envelopes.PUNCHY
    }

    CLICK = {
        "name": "CLICK",
        "wave": Waveforms.SQUARE,
        "envelope": Envelopes.CLICK
    }

    BEEP = {
        "name": "BEEP",
        "wave": Waveforms.SINE,
        "envelope": Envelopes.BEEP
    }

    BEEP_SQUARE = {
        "name": "BEEP_SQUARE",
        "wave": Waveforms.SQUARE,
        "envelope": Envelopes.BEEP
    }

    NOISE = None  # Lazily initialized on first access via get_noise_patch()

    @classmethod
    def get_noise_patch(cls):
        """Return the NOISE patch, generating the waveform on first use.

        Safe under CircuitPython's cooperative asyncio scheduler.
        """
        if cls.NOISE is None:
            cls.NOISE = {
                "name": "NOISE",
                "wave": Waveforms.get_noise(),
                "envelope": Envelopes.PERCUSSION
            }
        return cls.NOISE

    PAD = {
        "name": "PAD",
        "wave": Waveforms.TRIANGLE,
        "envelope": Envelopes.PAD
    }

    PUNCH = {
        "name": "PUNCH",
        "wave": Waveforms.SAW,
        "envelope": Envelopes.PUNCHY
    }

    SUCCESS = {
        "name": "SUCCESS",
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
        "name": "ALARM",
        "wave": Waveforms.SAW,
        "envelope": Envelopes.BEEP
    }

    SONAR = {
        "name": "SONAR",
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
        "name": "RETRO_LEAD",
        "wave": Waveforms.SQUARE, # The authentic Mario waveform
        "envelope": Envelopes.GAME_LEAD
    }

    RETRO_SFX = {
        "name": "RETRO_SFX",
        "wave": Waveforms.PULSE,
        "envelope": Envelopes.GAME_SFX
    }

    RETRO_COIN = {
        "name": "RETRO_COIN",
        "wave": Waveforms.PULSE,
        "envelope": Envelopes.GAME_SFX
    }



    TEXT_SCROLL = {
        "name": "TEXT_SCROLL",
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
        "name": "ETHEREAL",
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
        "name": "IDLE_HUM",
        "wave": Waveforms.SINE,
        "envelope": Envelopes.PAD
    }

    SCANNER = {
        "name": "SCANNER",
        "wave": Waveforms.TRIANGLE,
        "envelope": Envelopes.BEEP
    }

    ENGINE_HUM = {
        "name": "ENGINE_HUM",
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
        "name": "DATA_STREAM",
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
        "name": "RETRO_BASS",
        "wave": Waveforms.TRIANGLE,
        "envelope": Envelopes.GAME_LEAD
    }

    # 3-channel chiptune: noise/percussion channel (short burst of noise)
    RETRO_NOISE = None  # Lazily initialized on first access via get_retro_noise_patch()

    @classmethod
    def get_retro_noise_patch(cls):
        """Return the RETRO_NOISE patch, generating the waveform on first use.

        Safe under CircuitPython's cooperative asyncio scheduler.
        """
        if cls.RETRO_NOISE is None:
            cls.RETRO_NOISE = {
                "name": "RETRO_NOISE",
                "wave": Waveforms.get_noise(),
                "envelope": synthio.Envelope(
                    attack_time=0.001,
                    decay_time=0.05,
                    release_time=0.02,
                    attack_level=0.6,
                    sustain_level=0.0
                )
            }
        return cls.RETRO_NOISE

    CUSTOM_SQUARE = {
        "name": "CUSTOM_SQUARE",
        "wave": Waveforms.SQUARE,
        "envelope": Envelopes.CUSTOM_BLANK
    }

    CUSTOM_SINE = {
        "name": "CUSTOM_SINE",
        "wave": Waveforms.SINE,
        "envelope": Envelopes.CUSTOM_BLANK
    }

    CUSTOM_SAW = {
        "name": "CUSTOM_SAW",
        "wave": Waveforms.SAW,
        "envelope": Envelopes.CUSTOM_BLANK
    }

    CUSTOM_TRIANGLE = {
        "name": "CUSTOM_TRIANGLE",
        "wave": Waveforms.TRIANGLE,
        "envelope": Envelopes.CUSTOM_BLANK
    }

    CUSTOM_NOISE = {
        "name": "CUSTOM_NOISE",
        "wave": Waveforms.get_noise(),
        "envelope": Envelopes.CUSTOM_BLANK
    }

class JSEQRenderer:
    def __init__(self, sample_rate=44100):
        self.sample_rate = sample_rate

        # 1:1 Mapping to the JSEQ Format Spec
        self.patch_map = {
            0: Patches.RETRO_LEAD,
            1: Patches.RETRO_BASS,
            2: Patches.get_retro_noise_patch(),
            3: Patches.BEEP,
            4: Patches.BEEP_SQUARE,
            5: Patches.PAD,
            6: Patches.PUNCH,
            7: Patches.ALARM,
            8: Patches.SCANNER,
            9: Patches.CLICK,
            10: Patches.get_noise_patch(),
            11: Patches.SELECT,
            12: Patches.DATA_STREAM,
            13: Patches.ETHEREAL,
            14: Patches.ENGINE_HUM,
            15: Patches.TEXT_SCROLL,
            16: Patches.SUCCESS,
            17: Patches.ERROR,
            18: Patches.SONAR,
            19: Patches.CUSTOM_SQUARE,
            20: Patches.CUSTOM_SINE,
            21: Patches.CUSTOM_SAW,
            22: Patches.CUSTOM_TRIANGLE,
            23: Patches.CUSTOM_NOISE
        }

    def _infer_wave_type(self, wave_obj):
        """Matches the synth_registry array object to a NumPy math generator."""
        if wave_obj == Waveforms.SINE: return 'sine'
        if wave_obj == Waveforms.SQUARE: return 'square'
        if wave_obj == Waveforms.SAW: return 'saw'
        if wave_obj == Waveforms.TRIANGLE: return 'triangle'
        if wave_obj == Waveforms.PULSE: return 'pulse'
        if wave_obj == Waveforms.PULSE_125: return 'pulse_125'
        return 'noise'

    def parse_jseq(self, filename):
        """Parses the custom JSEQ binary format."""
        with open(filename, 'rb') as f:
            data = f.read()

        if data[0:4] != b'JSEQ':
            raise ValueError("Invalid JSEQ file: Magic bytes missing.")

        jseq = {
            'version': data[4],
            'initial_bpm': struct.unpack('<H', data[5:7])[0],
            'channels': []
        }

        num_channels = data[7]
        offset = 8

        for _ in range(num_channels):
            patch_id = data[offset]
            trk_type = data[offset+1]
            has_adsr = data[offset+2]
            offset += 3

            adsr = None
            if has_adsr == 1:
                adsr = struct.unpack('<BBBB', data[offset:offset+4])
                offset += 4

            step_count = struct.unpack('<H', data[offset:offset+2])[0]
            offset += 2

            steps = []
            for _ in range(step_count):
                val1, val2 = struct.unpack('<BB', data[offset:offset+2])
                steps.append((val1, val2))
                offset += 2

            # Pre-process steps to handle TIE commands (0xFF)
            merged_steps = []
            for pitch, dur in steps:
                if pitch == 255 and merged_steps and merged_steps[-1][0] not in (0, 255):
                    # Extend the duration of the previous note
                    merged_steps[-1] = (merged_steps[-1][0], merged_steps[-1][1] + dur)
                else:
                    merged_steps.append((pitch, dur))

            jseq['channels'].append({
                'patch': patch_id,
                'type': trk_type,
                'adsr': adsr,
                'steps': merged_steps
            })

        return jseq

    def build_timeline(self, jseq):
        """Calculates exact timestamp (in seconds) for every 1/32nd duration unit."""
        # 1. Calculate the absolute longest track in the sequence (in duration units)
        max_units = 0
        for ch in jseq['channels']:
            if ch['type'] != 0x00:  # <--- ADD THIS (Ignore Automation/Master)
                continue

            ch_units = sum(dur for pitch, dur in ch['steps'])
            if ch_units > max_units:
                max_units = ch_units

        master_track = next((c for c in jseq['channels'] if c['type'] == 0x02), None)

        timeline = []
        current_bpm = jseq['initial_bpm']
        current_time = 0.0

        if not master_track:
            # Fallback: Generate a static timeline perfectly sized for the longest track
            unit_dur = (60.0 / current_bpm) / 32.0
            timeline = [i * unit_dur for i in range(max_units + 100)]
            return timeline

        # Parse Master Events for dynamic BPM changes
        for cmd, val in master_track['steps']:
            if cmd == 0x01: # BPM Change
                current_bpm = val
            elif cmd == 0x00: # Wait/Rest
                unit_dur = (60.0 / current_bpm) / 32.0
                for _ in range(val):
                    timeline.append(current_time)
                    current_time += unit_dur

        # 2. The Dynamic Fix: Pad the timeline with the final BPM until it covers
        # the absolute longest audio track in the file (plus a tiny safety buffer).
        if len(timeline) <= max_units + 100:
            unit_dur = (60.0 / current_bpm) / 32.0
            shortfall = (max_units + 100) - len(timeline)
            for _ in range(shortfall):
                timeline.append(current_time)
                current_time += unit_dur

        return timeline

    def generate_oscillator(self, wave_type, freq, duration_sec):
        """Generates raw waveform arrays using NumPy math."""
        t = np.linspace(0, duration_sec, int(self.sample_rate * duration_sec), endpoint=False)

        if wave_type == 'sine':
            return np.sin(2 * np.pi * freq * t)
        elif wave_type == 'square':
            return np.sign(np.sin(2 * np.pi * freq * t))
        elif wave_type == 'saw':
            return 2 * (t * freq - np.floor(0.5 + t * freq))
        elif wave_type == 'triangle':
            return 2 * np.abs(2 * (t * freq - np.floor(0.5 + t * freq))) - 1
        elif wave_type == 'pulse':
            return np.where(np.mod(t * freq, 1.0) < 0.25, 1.0, -1.0)
        elif wave_type == 'pulse_125':
            return np.where(np.mod(t * freq, 1.0) < 0.125, 1.0, -1.0)
        elif wave_type == 'noise':
            return np.random.uniform(-1, 1, len(t))
        return np.zeros_like(t)

    def generate_adsr_envelope(self, hardware_env, override_multipliers, duration_sec):
        """Replicates the synthio.Envelope logic with JSEQ overrides."""
        a_t = hardware_env.attack_time
        d_t = hardware_env.decay_time
        r_t = hardware_env.release_time
        a_l = hardware_env.attack_level
        s_l = hardware_env.sustain_level

        # Apply JSEQ Inline Overrides
        if override_multipliers:
            a_t *= (override_multipliers[0] / 100.0)
            d_t *= (override_multipliers[1] / 100.0)
            s_l *= (override_multipliers[2] / 100.0)
            r_t *= (override_multipliers[3] / 100.0)
            s_l = max(0.0, min(1.0, s_l)) # Clamp sustain

        pressed_samples = int(duration_sec * self.sample_rate)

        # 1. Attack Phase
        attack_samples = int(a_t * self.sample_rate)
        actual_attack = min(attack_samples, pressed_samples)
        env_a = np.linspace(0.0, a_l, actual_attack, endpoint=False)

        # 2. Decay Phase
        decay_samples = int(d_t * self.sample_rate)
        remaining_pressed = pressed_samples - actual_attack
        actual_decay = min(decay_samples, remaining_pressed)
        env_d = np.linspace(a_l, s_l, actual_decay, endpoint=False)

        # 3. Sustain Phase
        sustain_samples = pressed_samples - actual_attack - actual_decay
        env_s = np.full(sustain_samples, s_l) if sustain_samples > 0 else np.array([])

        # 4. Release Phase (Appended AFTER the pressed duration)
        release_samples = int(r_t * self.sample_rate)

        # Calculate where the release actually starts if note was cut short
        rel_start = s_l
        if sustain_samples <= 0 and actual_decay > 0:
            rel_start = env_d[-1] if len(env_d) > 0 else a_l
        elif sustain_samples <= 0 and actual_attack > 0:
            rel_start = env_a[-1] if len(env_a) > 0 else 0.0

        env_r = np.linspace(rel_start, 0.0, release_samples, endpoint=False)

        # Combine all phases
        return np.concatenate([env_a, env_d, env_s, env_r]), release_samples

    def render(self, input_file, output_file):
        print(f"Parsing {input_file}...")
        jseq = self.parse_jseq(input_file)
        timeline = self.build_timeline(jseq)

        # Determine total length of the song in samples
        total_time_sec = timeline[-1] if timeline else 0
        total_samples = int(total_time_sec * self.sample_rate) + (self.sample_rate * 5) # 5 sec safety tail

        master_mix = np.zeros(total_samples, dtype=np.float32)

        for idx, ch in enumerate(jseq['channels']):
            if ch['type'] != 0x00: # Skip automation tracks
                continue

            patch = self.patch_map.get(ch['patch'], Patches.RETRO_LEAD)
            wave_type = self._infer_wave_type(patch['wave'])
            print(f"Rendering Track {idx} -> {patch['name']} ({wave_type})")

            unit_cursor = 0

            for pitch_idx, duration_units in ch['steps']:
                if pitch_idx in (0, 255): # Rest or orphan TIE
                    unit_cursor += duration_units
                    continue

                start_time = timeline[unit_cursor]
                end_time = timeline[unit_cursor + duration_units]
                dur_sec = end_time - start_time

                # MIDI Math
                midi_note = pitch_idx - 1
                freq = 440.0 * (2.0 ** ((midi_note - 69) / 12.0))

                # Generate ADSR
                envelope, release_samples = self.generate_adsr_envelope(patch['envelope'], ch['adsr'], dur_sec)

                # Generate Sound (Note duration + Release tail)
                total_osc_time = dur_sec + (release_samples / self.sample_rate)
                audio = self.generate_oscillator(wave_type, freq, total_osc_time)

                # Apply Envelope
                min_len = min(len(audio), len(envelope))
                audio = audio[:min_len] * envelope[:min_len] * 0.2 # Headroom mix

                # Mix into master buffer
                start_sample = int(start_time * self.sample_rate)
                end_sample = start_sample + len(audio)

                if end_sample <= total_samples:
                    master_mix[start_sample:end_sample] += audio

                unit_cursor += duration_units

        # Normalize and Export
        print("Mastering and exporting...")
        master_mix = np.clip(master_mix, -1.0, 1.0)
        wav_data = np.int16(master_mix * 32767)

        wavfile.write(output_file, self.sample_rate, wav_data)
        print(f"Successfully generated {output_file}!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render JSEQ to WAV using Native Hardware Patches.")
    parser.add_argument("input_file", help="Path to the input .jseq file")
    parser.add_argument("-o", "--output", help="Path to the output .wav file (Optional)", default=None)
    parser.add_argument("--sample-rate", type=int, default=44100, help="Sample rate for output WAV (default: 44100)")

    args = parser.parse_args()

    in_file = args.input_file
    out_file = args.output

    if out_file is None:
        base_name, _ = os.path.splitext(in_file)
        out_file = base_name + ".wav"

    if not os.path.exists(in_file):
        print(f"Error: Input file '{in_file}' not found.")
        exit(1)

    renderer = JSEQRenderer(sample_rate=args.sample_rate)
    try:
        renderer.render(in_file, out_file)
    except Exception as e:
        print(f"Error rendering sequence: {e}")
