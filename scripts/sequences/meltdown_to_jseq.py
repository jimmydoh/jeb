import struct

# Duration constants (1/32nd beat units)
# Max duration byte is 255. W (128) is 4 full beats.
S = 8     # Sixteenth note (0.25 beats)
E = 16    # Eighth note (0.5 beats)
Q = 32    # Quarter note (1.0 beats)
H = 64    # Half note (2.0 beats)
W = 128   # Whole note (4.0 beats)

def note_to_index(note_str):
    """Converts 'C4', 'A3', etc. into the 1-255 JSEQ pitch index."""
    if note_str == '-':
        return 0
    semitones = {'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5, 'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11}
    note, octave = note_str[:-1], int(note_str[-1])
    return ((octave + 1) * 12) + semitones[note] + 1

# --- 1. Global Header ---
out = bytearray(b'JSEQ')
out.append(1)                      # Version 1
out.extend(struct.pack('<H', 180)) # 180 BPM (Urgent, fast pace)
out.append(3)                      # 3 Channels

# =====================================================================
# "REACTOR MELTDOWN" - 64 BEATS TOTAL (21.3 Seconds @ 180 BPM)
# Phase 1: Warning (32 Beats)
# Phase 2: Critical Failure (32 Beats)
# =====================================================================

# --- 2. Channel 1: TRITONE SIREN (64 Beats) ---
out.append(7) # Patch 7: ALARM
ch1_seq = []

# Phase 1 (32 Beats): Standard alternating 8th notes
# C6 to F#6 is the classic highly dissonant tritone interval
ch1_seq.extend([('C6', E), ('F#6', E)] * 32)

# Phase 2 (32 Beats): Double-time 16th notes (Panic mode)
ch1_seq.extend([('C6', S), ('F#6', S)] * 64)

out.extend(struct.pack('<H', len(ch1_seq)))
for n, d in ch1_seq:
    out.append(note_to_index(n))
    out.append(int(d))


# --- 3. Channel 2: HEAVY KLAXON (64 Beats) ---
out.append(17) # Patch 17: ERROR (Harsh Sawtooth)
ch2_seq = []

# Phase 1 (32 Beats): Slow, heavy half-note blasts on the downbeat
ch2_seq.extend([('C3', H), ('-', H)] * 8)

# Phase 2 (32 Beats): Accelerates to quarter-note blasts
ch2_seq.extend([('C3', Q), ('-', Q)] * 16)

out.extend(struct.pack('<H', len(ch2_seq)))
for n, d in ch2_seq:
    out.append(note_to_index(n))
    out.append(int(d))


# --- 4. Channel 3: RADIATION GEIGER COUNTER (64 Beats) ---
out.append(12) # Patch 12: DATA_STREAM (Short, quiet digital blips)
ch3_seq = []

# Phase 1 (32 Beats): Nervous, erratic 8th note clicking
ch3_seq.extend([('C5', E), ('-', E)] * 32)

# Phase 2 (32 Beats): Frantic, continuous 16th note glitching
ch3_seq.extend([('C5', S), ('C6', S)] * 64)

out.extend(struct.pack('<H', len(ch3_seq)))
for n, d in ch3_seq:
    out.append(note_to_index(n))
    out.append(int(d))


# --- 5. Write to File ---
with open('reactor_meltdown.jseq', 'wb') as f:
    f.write(out)

print("Successfully compiled reactor_meltdown.jseq! (64 Beats, 3 Channels)")
