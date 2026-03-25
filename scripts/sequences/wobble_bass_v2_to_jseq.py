"""JSEQ v2.2 example: Dubstep wobble bass with automation + ADSR override.

Demonstrates the key v2.2 features:
  1. Automation track  — LPF cutoff wobble targeting Audio Channel 0 (target_scope=0x00)
  2. Inline ADSR override — slow-attack PAD (Channel 2)
  3. BPM change via Type 0x02 Master Event Track — tempo drop at bar 5 (140 → 110 BPM)

In v2.2 the first byte of an Automation channel header is the ``target_scope``:
  - 0x00–0x0F: targets a specific audio channel by index
  - 0xFF     : targets the Global Master Bus (all audio output)

BPM changes are no longer embedded as pitch 0xFF in audio tracks.  Instead they
live in a dedicated Type 0x02 Master Event Track (scope 0xFF, track_type 0x02).
The SynthManager ``_play_master_events`` coroutine updates ``_shared_bpm`` in
real time; all concurrent audio channel tasks pick up the new tempo on their
next note (no self-referential clock problem).

Total channel count in the global header = 3 Audio + 1 Automation + 1 Master Event = 5.

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
# Calculate bar offsets in 1/32-beat units (used by the master event track).
# ---------------------------------------------------------------------------
BEATS_PER_BAR  = 4
STEPS_PER_BEAT = 32          # 1/32-beat resolution
STEPS_PER_BAR  = BEATS_PER_BAR * STEPS_PER_BEAT   # 128 steps
TOTAL_BARS     = 8
NUM_STEPS      = TOTAL_BARS * STEPS_PER_BAR         # 1024 steps

# Bar 5 starts at step index 4 * STEPS_PER_BAR = 512.
BAR5_STEP = 4 * STEPS_PER_BAR   # 512

# ---------------------------------------------------------------------------
# 1. Global Header — JSEQ v2 (5 channels total)
# ---------------------------------------------------------------------------
out = bytearray(b'JSEQ')
out.append(2)                        # Version 2 (v2.2 is a revision within v2)
out.extend(struct.pack('<H', 140))   # 140 BPM
out.append(5)                        # 5 channels: 3 Audio + 1 Automation + 1 Master Event

# ---------------------------------------------------------------------------
# 2. Channel 1 (idx 0): WOBBLE BASS (Audio, no meta-events)
#    Patch 6 = PUNCH (Saw + punchy envelope)
#    BPM change at bar 5 is handled by the Master Event Track below.
# ---------------------------------------------------------------------------
out.append(6)   # scope_or_patch = PUNCH
out.append(0)   # track_type = Audio (0x00)
out.append(0)   # override_flag = off

ch1_seq = []

# Bars 1-4: 16th-note descending octave bassline at 140 BPM
bassline = ['A2', 'G2', 'E2', 'D2', 'A2', 'G2', 'F2', 'E2']
for _ in range(4):
    for n in bassline:
        ch1_seq.append((note_to_index(n), S))

# Bars 5-8: slower, heavier bassline (tempo will be 110 BPM via master event track)
slow_bass = [('A1', H), ('E2', H), ('D2', H), ('F2', H),
             ('A1', H), ('E2', H), ('G2', H), ('A2', H)]
for n, d in slow_bass:
    ch1_seq.append((note_to_index(n), d))

out.extend(struct.pack('<H', len(ch1_seq)))
for b0, b1 in ch1_seq:
    out.append(b0)
    out.append(b1)

# ---------------------------------------------------------------------------
# 3. Channel 2 (idx 1): ATMOSPHERIC PAD (Audio, ADSR override — slow attack ×2)
#    Patch 5 = PAD (Triangle + slow envelope)
#    ADSR multipliers: Attack ×2 (200), Decay ×1 (100), Sustain ×1 (100), Release ×2 (200)
# ---------------------------------------------------------------------------
out.append(5)   # scope_or_patch = PAD
out.append(0)   # track_type = Audio (0x00)
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
# 4. Channel 3 (idx 2): EMPTY AUDIO (mandatory 3rd audio slot — silence)
#    The format requires three audio track slots (indices 0, 1, 2).
#    Unused slots are written as an empty step list.
# ---------------------------------------------------------------------------
out.append(0)   # scope_or_patch = RETRO_LEAD (irrelevant for empty channel)
out.append(0)   # track_type = Audio (0x00)
out.append(0)   # override_flag = off
out.extend(struct.pack('<H', 0))   # step_count = 0 (no steps)

# ---------------------------------------------------------------------------
# 5. Channel 4 (idx 3): LPF AUTOMATION (target_scope=0x00 → Audio Channel 0)
#    track_type 0x01 = Automation; steps are [param_id, value] pairs.
#    param_id 0x00 = LPF cutoff (0-255 → 0-20 000 Hz)
#
#    Shape: a "saw-down" LFO repeating every 8 steps (1/4 beat),
#    descending from 255 → 0 to mimic a falling low-pass filter cutoff.
#    1024 automation steps cover all 8 bars at 1/32-beat resolution.
# ---------------------------------------------------------------------------
out.append(0)   # target_scope = 0x00 → targets Audio Channel 0 (bass line)
out.append(1)   # track_type = Automation (0x01)
out.append(0)   # override_flag = off (automation channels never carry ADSR overrides)

LFO_PERIOD = 32   # steps per LFO cycle (= 1 beat)

ch4_steps = []
for s in range(NUM_STEPS):
    phase = s % LFO_PERIOD
    value = int(255 * (1.0 - phase / LFO_PERIOD))
    ch4_steps.append((0x00, value))   # param_id=LPF, value=0-255

out.extend(struct.pack('<H', len(ch4_steps)))
for param_id, value in ch4_steps:
    out.append(param_id)
    out.append(value)

# ---------------------------------------------------------------------------
# 6. Channel 5 (idx 4): MASTER EVENT TRACK (scope 0xFF, track_type 0x02)
#    Event-based global commands: [command_id, value] pairs.
#      0x00 (JSEQ_CMD_REST)       — wait `value` / 32 beats
#      0x01 (JSEQ_CMD_BPM_CHANGE) — set global BPM to `value`
#
#    We want: wait until bar 5 (step 512 = 16 beats at 140 BPM), then drop to 110.
#    REST 255 steps + REST 255 steps + REST 2 steps = 512 total, then BPM_CHANGE 110.
#    (REST steps are capped at 255 because the value byte is uint8.)
# ---------------------------------------------------------------------------
out.append(0xFF)  # scope_or_patch = 0xFF (Global Master Bus)
out.append(0x02)  # track_type = Global Event (0x02)
out.append(0x00)  # override_flag = off

master_steps = []
rest_remaining = BAR5_STEP   # 512 steps
while rest_remaining > 0:
    chunk = min(255, rest_remaining)
    master_steps.append((0x00, chunk))   # JSEQ_CMD_REST
    rest_remaining -= chunk
master_steps.append((0x01, 110))         # JSEQ_CMD_BPM_CHANGE to 110

out.extend(struct.pack('<H', len(master_steps)))
for cmd_id, val in master_steps:
    out.append(cmd_id)
    out.append(val)

# ---------------------------------------------------------------------------
# 7. Write to file
# ---------------------------------------------------------------------------
output_path = 'wobble_bass.jseq'
with open(output_path, 'wb') as f:
    f.write(out)

print(f"Compiled {len(out)} bytes -> {output_path}")
print(f"   Format:   JSEQ v2.2")
print(f"   Channels: 5")
print(f"   Ch1 (idx 0): PUNCH (Audio) — descending bassline")
print(f"   Ch2 (idx 1): PAD   (Audio + ADSR override) — slow attack/release atmospheric pad")
print(f"   Ch3 (idx 2): Empty (Audio) — mandatory 3rd audio slot")
print(f"   Ch4 (idx 3): LPF Automation (target Audio Ch0) — saw-down LFO every beat")
print(f"   Ch5 (idx 4): Master Event Track — BPM 140 -> 110 at bar 5 (step {BAR5_STEP})")
