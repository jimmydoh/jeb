import struct

# Duration constants (1/32nd beat units)
# Note: Max duration byte is 255. W (128) is 4 full beats.
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
out.extend(struct.pack('<H', 60))  # 60 BPM (1 beat = 1 second)
out.append(3)                      # 3 Channels

# =====================================================================
# ALL CHANNELS MUST EXACTLY EQUAL 64 BEATS (2048 UNITS) FOR PERFECT SYNC
# =====================================================================

# --- 2. Channel 1: ETHEREAL HIGHS (64 Beats) ---
# Slowly drifting upper chord extensions and suspended notes
out.append(13) # Patch 13: ETHEREAL
ch1_seq = [
    # Bar 1-4: C minor add 9 feel (16 beats)
    ('D4', W), ('D#4', W), ('C4', W), ('-', W),

    # Bar 5-8: D# Lydian drift (16 beats)
    ('F4', W), ('G4', W), ('D4', W), ('-', H), ('A#3', H),

    # Bar 9-12: F minor suspended (16 beats)
    ('G#4', W), ('G4', W), ('F4', W), ('C5', W),

    # Bar 13-16: G# Maj to G dominant resolution (16 beats)
    ('D#5', W), ('D5', W), ('B4', W), ('G4', W)
]
out.extend(struct.pack('<H', len(ch1_seq)))
for n, d in ch1_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 3. Channel 2: PAD MIDRANGE (64 Beats) ---
# Harmonic anchor providing the thick, sustaining chord bodies
out.append(5) # Patch 5: PAD
ch2_seq = [
    # Bar 1-4 (16 beats)
    ('G3', W), ('G3', W), ('G3', W), ('G3', W),

    # Bar 5-8 (16 beats)
    ('A#3', W), ('A#3', W), ('A#3', W), ('A#3', W),

    # Bar 9-12 (16 beats)
    ('C4', W), ('C4', W), ('C4', W), ('C4', W),

    # Bar 13-16 (16 beats)
    ('D#4', W), ('D#4', W), ('D4', W), ('D4', W)
]
out.extend(struct.pack('<H', len(ch2_seq)))
for n, d in ch2_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 4. Channel 3: ENGINE HUM DRONE (64 Beats) ---
# Sub-bass root notes simulating a massive starship reactor
out.append(14) # Patch 14: ENGINE_HUM
ch3_seq = [
    # Bar 1-4: Root C (16 beats)
    ('C2', W), ('C2', W), ('C2', W), ('C2', W),

    # Bar 5-8: Root D# (16 beats)
    ('D#2', W), ('D#2', W), ('D#2', W), ('D#2', W),

    # Bar 9-12: Root F (16 beats)
    ('F2', W), ('F2', W), ('F2', W), ('F2', W),

    # Bar 13-16: Root G# -> G (16 beats)
    ('G#2', W), ('G#2', W), ('G2', W), ('G2', W)
]
out.extend(struct.pack('<H', len(ch3_seq)))
for n, d in ch3_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 5. Write to File ---
with open('deep_space.jseq', 'wb') as f:
    f.write(out)

print("Successfully compiled deep_space.jseq! (64 seconds, 3 Channels)")
