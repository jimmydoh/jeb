import struct

# Duration constants (1/32nd beat units)
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
out.extend(struct.pack('<H', 140)) # 140 BPM for steady adventure momentum
out.append(3)                      # 3 Channels

# --- 2. Channel 1: MOON_LEAD (64 Beats) ---
out.append(0) # Patch 0: RETRO_LEAD
ch1_seq = [
    # --- Part A (Main Chorus) ---
    # Bar 1 (Bb Major)
    ('A#4', DQ), ('F4', E), ('D4', Q), ('F4', Q),
    # Bar 2 (C Major)
    ('C5', DQ), ('G4', E), ('E4', Q), ('G4', Q),
    # Bar 3 (D Minor)
    ('D5', H), ('A4', Q), ('F4', Q),
    # Bar 4 (A Minor Turnaround)
    ('E5', E), ('F5', E), ('E5', Q), ('C5', H),

    # Bar 5 (Bb Major)
    ('A#4', DQ), ('F4', E), ('D4', Q), ('F4', Q),
    # Bar 6 (C Major)
    ('C5', DQ), ('G4', E), ('E4', Q), ('G4', Q),
    # Bar 7 & 8 (D Minor Resolution)
    ('D5', H), ('A4', Q), ('F4', Q),
    ('D5', W),

    # --- Part B (High Soaring Bridge) ---
    # Bar 9 (F Major)
    ('F5', DQ), ('C5', E), ('A4', Q), ('C5', Q),
    # Bar 10 (G Major)
    ('G5', DQ), ('D5', E), ('B4', Q), ('D5', Q),
    # Bar 11 & 12 (A Minor climax and descend)
    ('A5', W),
    ('A5', Q), ('G5', Q), ('F5', Q), ('E5', Q),

    # Bar 13 (Bb Major)
    ('A#4', DQ), ('F4', E), ('D4', Q), ('F4', Q),
    # Bar 14 (C Major)
    ('C5', DQ), ('G4', E), ('E4', Q), ('G4', Q),
    # Bar 15 & 16 (D Minor Final Resolution)
    ('D5', H), ('A4', Q), ('F4', Q),
    ('D5', W)
]

out.extend(struct.pack('<H', len(ch1_seq)))
for n, d in ch1_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 3. Channel 2: MOON_BASS (64 Beats) ---
out.append(1) # Patch 1: RETRO_BASS
ch2_seq = []

# A classic 8-bit rolling arpeggio bassline (Root-Fifth-Octave-Fifth)
# Each bar is 8 eighth notes (8 * 16 = 128 units)
bass_progression = [
    # Bars 1-4 (A Section)
    ('A#2', 'F3', 'A#3'), ('C3', 'G3', 'C4'), ('D3', 'A3', 'D4'), ('A2', 'E3', 'A3'),
    # Bars 5-8 (A Section Repeat)
    ('A#2', 'F3', 'A#3'), ('C3', 'G3', 'C4'), ('D3', 'A3', 'D4'), ('D3', 'A3', 'D4'),
    # Bars 9-12 (B Section)
    ('F2', 'C3', 'F3'),   ('G2', 'D3', 'G3'),   ('A2', 'E3', 'A3'),   ('A2', 'E3', 'A3'),
    # Bars 13-16 (Outro)
    ('A#2', 'F3', 'A#3'), ('C3', 'G3', 'C4'), ('D3', 'A3', 'D4'), ('D3', 'A3', 'D4')
]

for root, fifth, octave in bass_progression:
    ch2_seq.extend([
        (root, E), (fifth, E), (octave, E), (fifth, E),
        (root, E), (fifth, E), (octave, E), (fifth, E)
    ])

out.extend(struct.pack('<H', len(ch2_seq)))
for n, d in ch2_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 4. Channel 3: MOON_PERC (64 Beats) ---
out.append(2) # Patch 2: RETRO_NOISE
ch3_seq = []

# A driving, continuous 8-bit drum loop.
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
with open('moon_theme.jseq', 'wb') as f:
    f.write(out)

print("Successfully compiled the cosmic 64-beat moon_theme.jseq!")
