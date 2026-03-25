"""JSEQ v2 example: Dubstep wobble bass with automation + ADSR override.

Demonstrates the three key v2 features:
  1. Automation track — LPF cutoff wobble (Channel 3)
  2. Inline ADSR override — slow-attack PAD (Channel 2)
  3. BPM meta-event — tempo drop mid-sequence (Channel 1)

Run this script with CPython 3 to produce ``wobble_bass.jseq``:

    python3 wobble_bass_v2_to_jseq.py

Copy the resulting file to ``/sd/sequences/`` on the JEB device.
"""

import struct

# ---------------------------------------------------------------------------
# Duration constants (1/32nd beat units)
# ---------------------------------------------------------------------------
S  = 8    # Sixteenth note  (0.25 beats)
E  = 16   # Eighth note     (0.50 beats)
Q  = 32   # Quarter note    (1.00 beats)
H  = 64   # Half note       (2.00 beats)
W  = 128  # Whole note      (4.00 beats)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
SEMITONES = {'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4,
             'F': 5, 'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11}

def note_to_index(note_str):
    """Convert 'C4', 'A#3', etc. into a 1-255 JSEQ pitch index."""
    if note_str == '-':
        return 0
    name  = note_str[:-1]
    octave = int(note_str[-1])
    return ((octave + 1) * 12) + SEMITONES[name] + 1

# ---------------------------------------------------------------------------
# 1. Global Header — JSEQ v2
# ---------------------------------------------------------------------------
out = bytearray(b'JSEQ')
out.append(2)                        # Version 2
out.extend(struct.pack('<H', 140))   # 140 BPM
out.append(3)                        # 3 channels

# ---------------------------------------------------------------------------
# 2. Channel 1: WOBBLE BASS (Audio, BPM meta-event at bar 5)
#    Patch 6 = PUNCH (Saw + punchy envelope)
# ---------------------------------------------------------------------------
out.append(6)   # patch_idx = PUNCH
out.append(0)   # track_type = Audio
out.append(0)   # override_flag = off

ch1_seq = []

# Bars 1-4: 16th-note descending octave bassline at 140 BPM
bassline = ['A2', 'G2', 'E2', 'D2', 'A2', 'G2', 'F2', 'E2']
for _ in range(4):
    for n in bassline:
        ch1_seq.append((note_to_index(n), S))

# BPM Meta-Event at bar 5: drop to 110 BPM for a half-time feel.
# Pitch 0xFF (255) = meta-event; second byte = new BPM.
ch1_seq.append((255, 110))   # Meta-event: BPM → 110

# Bars 5-8: slower, heavier bassline at 110 BPM
slow_bass = [('A1', H), ('E2', H), ('D2', H), ('F2', H),
             ('A1', H), ('E2', H), ('G2', H), ('A2', H)]
for n, d in slow_bass:
    ch1_seq.append((note_to_index(n), d))

out.extend(struct.pack('<H', len(ch1_seq)))
for b0, b1 in ch1_seq:
    out.append(b0)
    out.append(b1)

# ---------------------------------------------------------------------------
# 3. Channel 2: ATMOSPHERIC PAD (Audio, ADSR override — slow attack ×2)
#    Patch 5 = PAD (Triangle + slow envelope)
#    ADSR multipliers: Attack ×2 (200), Decay ×1 (100), Sustain ×1 (100), Release ×2 (200)
# ---------------------------------------------------------------------------
out.append(5)   # patch_idx = PAD
out.append(0)   # track_type = Audio
out.append(1)   # override_flag = ON → 4 ADSR multiplier bytes follow
out.extend([200, 100, 100, 200])  # attack ×2, release ×2

ch2_seq = []
pad_chords = [('A3', W), ('A3', W), ('F3', W), ('F3', W),
              ('D3', W), ('D3', W), ('E3', W), ('E3', W)]
for n, d in pad_chords:
    ch2_seq.append((note_to_index(n), d))

out.extend(struct.pack('<H', len(ch2_seq)))
for b0, b1 in ch2_seq:
    out.append(b0)
    out.append(b1)

# ---------------------------------------------------------------------------
# 4. Channel 3: LPF AUTOMATION (Automation track — dubstep wobble)
#    Track type 1 = Automation; steps are [param_id, value] pairs.
#    param_id 0x00 = LPF cutoff (0-255 → 0-20 000 Hz)
#
#    We fill audioNumSteps steps at 1/32-beat resolution.
#    At 140 BPM, 1/32 beat = (60/140)/32 ≈ 13.4 ms per automation step.
#    8 bars × 4 beats/bar × 32 steps/beat = 1024 automation steps.
#
#    Shape: a "saw-down" LFO pattern repeating every 8 steps (1/4 beat),
#    descending from 255 → 0 to mimic a falling low-pass filter cutoff.
# ---------------------------------------------------------------------------
out.append(0)   # patch_idx (unused for automation but required by format)
out.append(1)   # track_type = Automation
out.append(0)   # override_flag = off

TOTAL_BARS   = 8
BEATS_PER_BAR = 4
STEPS_PER_BEAT = 32
NUM_STEPS = TOTAL_BARS * BEATS_PER_BAR * STEPS_PER_BEAT  # 1024

LFO_PERIOD = 32   # steps per LFO cycle (= 1 beat at finest resolution)

ch3_steps = []
for s in range(NUM_STEPS):
    phase = s % LFO_PERIOD
    # Descending sawtooth: starts at 255, falls to 0 over one period
    value = int(255 * (1.0 - phase / LFO_PERIOD))
    ch3_steps.append((0x00, value))   # param_id=LPF, value=0-255

out.extend(struct.pack('<H', len(ch3_steps)))
for param_id, value in ch3_steps:
    out.append(param_id)
    out.append(value)

# ---------------------------------------------------------------------------
# 5. Write to file
# ---------------------------------------------------------------------------
output_path = 'wobble_bass.jseq'
with open(output_path, 'wb') as f:
    f.write(out)

print(f"✅ Compiled {len(out)} bytes → {output_path}")
print(f"   Format:   JSEQ v2")
print(f"   Channels: 3")
print(f"   Ch1: PUNCH (Audio) — descending bassline, BPM meta-event 140→110 at bar 5")
print(f"   Ch2: PAD   (Audio + ADSR override) — slow attack/release atmospheric pad")
print(f"   Ch3: LPF Automation — 1024 wobble steps (saw-down LFO every beat)")
