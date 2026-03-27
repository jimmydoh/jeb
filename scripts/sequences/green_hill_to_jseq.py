import struct

# Duration constants (1/32nd beat units)
E = 16    # Eighth note (0.5 beats)
Q = 32    # Quarter note (1.0 beats)
DQ = 48   # Dotted quarter (1.5 beats)
H = 64    # Half note (2.0 beats)

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
out.extend(struct.pack('<H', 180)) # 180 BPM for maximum momentum
out.append(3)                      # 3 Channels

# --- 2. Channel 1: GHZ_LEAD (64 Beats) ---
out.append(0) # Patch 0: RETRO_LEAD
ch1_seq = [
    # --- Main Melody (8 bars) ---
    # Bar 1 & 2: The classic C-major bounce (256 units total)
    ('E5', E), ('G5', E), ('C6', E), ('A5', E), ('G5', Q), ('-', Q),
    ('E5', E), ('G5', E), ('C6', E), ('A5', E), ('G5', Q), ('-', Q),

    # Bar 3: F-major shift (128 units)
    ('F5', E), ('A5', E), ('C6', E), ('A5', E), ('C6', Q), ('-', Q),
    # Bar 4: G-major turnaround (128 units)
    ('D6', E), ('B5', E), ('G5', E), ('B5', E), ('D6', Q), ('-', Q),

    # Bar 5 & 6: The bounce returns with a tail (256 units total)
    ('E5', E), ('G5', E), ('C6', E), ('A5', E), ('G5', E), ('E5', E), ('C5', Q),
    ('E5', E), ('G5', E), ('C6', E), ('A5', E), ('G5', E), ('E5', E), ('C5', Q),

    # Bar 7: F-major shift (128 units)
    ('F5', E), ('A5', E), ('C6', E), ('D6', E), ('C6', Q), ('-', Q),
    # Bar 8: Resolution to C (128 units)
    ('D6', E), ('B5', E), ('G5', E), ('B5', E), ('C6', Q), ('-', Q),

    # --- Bridge Section (8 bars) ---
    # Bar 9 & 10: A-minor soaring descent (256 units)
    ('E6', Q), ('D6', E), ('C6', E), ('B5', E), ('C6', E), ('A5', Q),
    ('A5', H), ('-', H),

    # Bar 11 & 12: E-minor echo (256 units)
    ('D6', Q), ('C6', E), ('B5', E), ('A5', E), ('B5', E), ('G5', Q),
    ('G5', H), ('-', H),

    # Bar 13: F-major climb (128 units)
    ('A5', Q), ('A5', Q), ('C6', Q), ('C6', Q),
    # Bar 14: G-major climax (128 units)
    ('B5', Q), ('B5', Q), ('D6', Q), ('D6', Q),

    # Bar 15 & 16: The big C-major finish and loop setup (256 units)
    ('E6', DQ), ('D6', E), ('C6', H),
    ('D6', Q), ('B5', Q), ('G5', H)
]

out.extend(struct.pack('<H', len(ch1_seq)))
for n, d in ch1_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 3. Channel 2: GHZ_BASS (64 Beats) ---
out.append(1) # Patch 1: RETRO_BASS
ch2_seq = []

# The iconic "running" bassline: Alternating Root and Octave on the eighth notes.
# 16 bars total, perfectly mapped to the chords.
bass_progression = [
    # Bars 1-4
    ('C3', 'C4'), ('C3', 'C4'), ('F2', 'F3'), ('G2', 'G3'),
    # Bars 5-8
    ('C3', 'C4'), ('C3', 'C4'), ('F2', 'F3'), ('G2', 'G3'),
    # Bars 9-12 (Bridge)
    ('A2', 'A3'), ('A2', 'A3'), ('E2', 'E3'), ('E2', 'E3'),
    # Bars 13-16
    ('F2', 'F3'), ('G2', 'G3'), ('C3', 'C4'), ('G2', 'G3')
]

for root, octave in bass_progression:
    # 4 pairs of eighth notes per bar (128 duration units)
    for _ in range(4):
        ch2_seq.extend([(root, E), (octave, E)])

# Fix the turnaround on Bar 8 to match the melody's rest
ch2_seq[60:64] = [('C3', Q), ('-', Q)]

out.extend(struct.pack('<H', len(ch2_seq)))
for n, d in ch2_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 4. Channel 3: GHZ_PERC (64 Beats) ---
out.append(2) # Patch 2: RETRO_NOISE
ch3_seq = []

# A driving, snappy drum pattern to simulate the fast platforming action.
# C3 = Kick, C4 = Snare, A3 = Hi-Hat.
# Loops 16 times to cover all 16 bars seamlessly.
for _ in range(16):
    ch3_seq.extend([
        ('C3', E), ('A3', E), ('C4', E), ('A3', E),
        ('C3', E), ('A3', E), ('C4', E), ('A3', E)
    ])

out.extend(struct.pack('<H', len(ch3_seq)))
for n, d in ch3_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 5. Write to File ---
with open('green_hill_zone.jseq', 'wb') as f:
    f.write(out)

print("Successfully compiled the incredibly fast 64-beat green_hill_zone.jseq!")
