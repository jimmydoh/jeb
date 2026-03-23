import struct

# Duration constants (1/32nd beat units)
S = 8     # Sixteenth note (0.25 beats)
E = 16    # Eighth note (0.5 beats)
Q = 32    # Quarter note (1.0 beats)
DQ = 48   # Dotted quarter (1.5 beats)
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
out.append(1)
out.extend(struct.pack('<H', 180)) # 180 BPM
out.append(3)                      # 3 Channels

# --- 2. Channel 1: UNDERWORLD_LEAD (32 Beats) ---
out.append(0) # Patch 0: RETRO_LEAD
ch1_seq = [
    # Bar 1: Base Riff (1.5 beats) + Rest (2.5 beats = 80 units)
    ('C4', S), ('A3', S), ('A#3', S), ('A3', S), ('F3', S), ('G3', S), ('-', 80),

    # Bar 2: Base Riff
    ('C4', S), ('A3', S), ('A#3', S), ('A3', S), ('F3', S), ('G3', S), ('-', 80),

    # Bar 3: High Riff (Shifted up a fourth)
    ('F4', S), ('D4', S), ('D#4', S), ('D4', S), ('A#3', S), ('C4', S), ('-', 80),

    # Bar 4: Base Riff
    ('C4', S), ('A3', S), ('A#3', S), ('A3', S), ('F3', S), ('G3', S), ('-', 80),

    # Bar 5: Highest Riff (Shifted up a fifth)
    ('G4', S), ('E4', S), ('F4', S), ('E4', S), ('C4', S), ('D4', S), ('-', 80),

    # Bar 6: Base Riff
    ('C4', S), ('A3', S), ('A#3', S), ('A3', S), ('F3', S), ('G3', S), ('-', 80),

    # Bars 7 & 8: Sparse descending outro (8 beats)
    ('C4', Q), ('-', Q), ('G3', Q), ('-', Q),
    ('C3', W)
]

out.extend(struct.pack('<H', len(ch1_seq)))
for n, d in ch1_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 3. Channel 2: UNDERWORLD_BASS (32 Beats) ---
out.append(1) # Patch 1: RETRO_BASS
ch2_seq = [
    # The bass counters the melody by playing sparse notes in the gaps.
    # Each bar is strictly 128 units (4 beats).

    # Bar 1 (C minor implied)
    ('-', DQ), ('C3', E), ('G2', E), ('-', DQ),
    # Bar 2 (C minor implied)
    ('-', DQ), ('C3', E), ('G2', E), ('-', DQ),
    # Bar 3 (F minor implied)
    ('-', DQ), ('F3', E), ('C3', E), ('-', DQ),
    # Bar 4 (C minor implied)
    ('-', DQ), ('C3', E), ('G2', E), ('-', DQ),
    # Bar 5 (G minor implied)
    ('-', DQ), ('G3', E), ('D3', E), ('-', DQ),
    # Bar 6 (C minor implied)
    ('-', DQ), ('C3', E), ('G2', E), ('-', DQ),

    # Bars 7 & 8: Holding down the root
    ('C2', W),
    ('G2', W)
]

out.extend(struct.pack('<H', len(ch2_seq)))
for n, d in ch2_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 4. Channel 3: UNDERWORLD_NOISE (32 Beats) ---
out.append(2) # Patch 2: RETRO_NOISE
ch3_seq = []

# A minimalist, echoing "tick" to enhance the cavernous feel.
# C4 = higher snap, A3 = lower thud.
# 8 bars * 128 units = 1024 total units.
for _ in range(8):
    ch3_seq.extend([
        ('C4', E), ('-', E), ('C4', E), ('-', E),
        ('A3', Q), ('-', Q)
    ])

out.extend(struct.pack('<H', len(ch3_seq)))
for n, d in ch3_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 5. Write to File ---
with open('mario_underworld.jseq', 'wb') as f:
    f.write(out)

print("Successfully compiled the 32-beat mario_underworld.jseq!")
