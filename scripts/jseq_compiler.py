"""JSEQ v2.2 Diagnostic: The Slow Motion Microscope
Direct procedural generation to guarantee perfect byte alignment.
"""
import struct

# ---------------------------------------------------------------------------
# Duration constants (1/32nd beat units)
# ---------------------------------------------------------------------------
S  = 8    # Sixteenth note  (0.25 beats)
Q  = 32   # Quarter note    (1.00 beats)
W  = 128  # Whole note      (4.00 beats)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def note_to_idx(note_str):
    if note_str == '-': return 0
    semitones = {'C':0, 'C#':1, 'D':2, 'D#':3, 'E':4, 'F':5, 'F#':6, 'G':7, 'G#':8, 'A':9, 'A#':10, 'B':11}
    name = note_str[:-1]
    octave = int(note_str[-1])
    return ((octave + 1) * 12) + semitones[name] + 1

# ---------------------------------------------------------------------------
# 1. Global Header — JSEQ v2.2 (5 channels total)
# ---------------------------------------------------------------------------
out = bytearray(b'JSEQ')
out.append(2)                        # Version 2
out.extend(struct.pack('<H', 60))    # Start at a crawling 60 BPM!
out.append(5)                        # 5 channels

# ---------------------------------------------------------------------------
# 2. Channel 1 (idx 0): THE DRONE
#    4 contiguous whole notes (16 beats total) to provide a wall of sound.
# ---------------------------------------------------------------------------
out.append(6)   # Patch = PUNCH (lots of buzz for the filter to grab)
out.append(0)   # Type = Audio
out.append(0)   # No ADSR override

drone_seq = [('C3', W), ('C3', W), ('C3', W), ('C3', W)]
out.extend(struct.pack('<H', len(drone_seq)))
for n, d in drone_seq:
    out.append(note_to_idx(n))
    out.append(d)

# ---------------------------------------------------------------------------
# 3. Channel 2 (idx 1): THE METRONOME
#    A sharp click exactly on the beat, 16 times in a row.
# ---------------------------------------------------------------------------
out.append(13)  # Patch = SCANNER
out.append(0)   # Type = Audio
out.append(0)   # No ADSR override

# 4 units of click, 28 units of rest = 32 units (1 beat)
click_seq = [('C5', 4), ('-', 28)] * 16
out.extend(struct.pack('<H', len(click_seq)))
for n, d in click_seq:
    out.append(note_to_idx(n))
    out.append(d)

# ---------------------------------------------------------------------------
# 4. Channel 3 (idx 2): EMPTY AUDIO
# ---------------------------------------------------------------------------
out.append(0)
out.append(0)
out.append(0)
out.extend(struct.pack('<H', 0))   # step_count = 0

# ---------------------------------------------------------------------------
# 5. Channel 4 (idx 3): SLOW LPF SWEEP (Targeting Ch 0)
#    Ramps from 0 to 255 over 256 steps, then down to 0 over 256 steps.
# ---------------------------------------------------------------------------
out.append(0)   # Target Audio Channel 0 (The Drone)
out.append(1)   # Type = Automation
out.append(0)   # No override

auto_steps = []
for i in range(512):
    if i < 256:
        val = i             # Ramp up over 8 beats
    else:
        val = 255 - (i - 256) # Ramp down over 8 beats
    auto_steps.append((0x00, val)) # Param 0x00 = LPF Cutoff

out.extend(struct.pack('<H', len(auto_steps)))
for pid, val in auto_steps:
    out.append(pid)
    out.append(val)

# ---------------------------------------------------------------------------
# 6. Channel 5 (idx 4): THE TEMPO ROLLERCOASTER (Master Event Track)
# ---------------------------------------------------------------------------
out.append(0xFF) # Target = Global Master Bus
out.append(2)    # Type = Global Event Track
out.append(0)

master_steps = [
    (0x00, 128), # Rest for 4 beats (at 60 BPM)
    (0x01, 180), # Snap to 180 BPM
    (0x00, 128), # Rest for 4 beats (at 180 BPM)
    (0x01, 30),  # Slam down to 30 BPM
    (0x00, 128), # Rest for 4 beats (at 30 BPM)
    (0x01, 240), # Snap to 240 BPM
    (0x00, 128), # Rest for final 4 beats
]

out.extend(struct.pack('<H', len(master_steps)))
for cid, val in master_steps:
    out.append(cid)
    out.append(val)

# ---------------------------------------------------------------------------
# Write to disk
# ---------------------------------------------------------------------------
with open('jseq_diagnostic_slow.jseq', 'wb') as f:
    f.write(out)

print("Generated jseq_diagnostic_slow.jseq")
