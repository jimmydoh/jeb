import struct

# Duration constants (1/32nd beat units)
S = 8     # Sixteenth note (0.25 beats)
E = 16    # Eighth note (0.5 beats)
Q = 32    # Quarter note (1.0 beats)
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
out.extend(struct.pack('<H', 170)) # 170 BPM for fast bluegrass picking
out.append(3)                      # 3 Channels

# --- 2. Channel 1: BOBCAT_LEAD (32 Beats) ---
out.append(0) # Patch 0: RETRO_LEAD
ch1_seq = [
    # Bar 1: G Major Banjo Roll (128 units)
    ('G5', E), ('D5', E), ('B4', E), ('G4', E), ('G4', S), ('A#4', S), ('B4', S), ('D5', S), ('G5', Q),
    # Bar 2: C Major Banjo Roll (128 units)
    ('C5', E), ('G5', E), ('E5', E), ('C5', E), ('C5', S), ('D#5', S), ('E5', S), ('G5', S), ('C6', Q),
    # Bar 3: G Major Banjo Roll (128 units)
    ('G5', E), ('D5', E), ('B4', E), ('G4', E), ('G4', S), ('A#4', S), ('B4', S), ('D5', S), ('G5', Q),
    # Bar 4: D Major turnaround (128 units)
    ('D5', E), ('A5', E), ('F#5', E), ('D5', E), ('D5', S), ('F5', S), ('F#5', S), ('A5', S), ('D6', Q),

    # Bar 5: G Major Banjo Roll (128 units)
    ('G5', E), ('D5', E), ('B4', E), ('G4', E), ('G4', S), ('A#4', S), ('B4', S), ('D5', S), ('G5', Q),
    # Bar 6: C Major Banjo Roll (128 units)
    ('C5', E), ('G5', E), ('E5', E), ('C5', E), ('C5', S), ('D#5', S), ('E5', S), ('G5', S), ('C6', Q),
    # Bar 7: G to D walkdown (128 units)
    ('B4', E), ('G4', E), ('A4', E), ('F#4', E), ('G4', S), ('A#4', S), ('B4', S), ('D5', S), ('G5', Q),
    # Bar 8: G Major Big Finish (128 units)
    ('G5', H), ('-', H)
]

out.extend(struct.pack('<H', len(ch1_seq)))
for n, d in ch1_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 3. Channel 2: BOBCAT_BASS (32 Beats) ---
out.append(1) # Patch 1: RETRO_BASS
ch2_seq = [
    # A bouncy, alternating root-fifth acoustic bassline.
    # We use rests between the eighth notes to make it staccato.
    # Every bar is strictly 128 units.

    # Bar 1 (G Major)
    ('G2', E), ('-', E), ('D3', E), ('-', E), ('G2', E), ('-', E), ('D3', E), ('-', E),
    # Bar 2 (C Major)
    ('C3', E), ('-', E), ('G3', E), ('-', E), ('C3', E), ('-', E), ('G3', E), ('-', E),
    # Bar 3 (G Major)
    ('G2', E), ('-', E), ('D3', E), ('-', E), ('G2', E), ('-', E), ('D3', E), ('-', E),
    # Bar 4 (D Major)
    ('D3', E), ('-', E), ('A3', E), ('-', E), ('D3', E), ('-', E), ('A3', E), ('-', E),

    # Bar 5 (G Major)
    ('G2', E), ('-', E), ('D3', E), ('-', E), ('G2', E), ('-', E), ('D3', E), ('-', E),
    # Bar 6 (C Major)
    ('C3', E), ('-', E), ('G3', E), ('-', E), ('C3', E), ('-', E), ('G3', E), ('-', E),
    # Bar 7 (G Major to D Major)
    ('G2', E), ('-', E), ('D3', E), ('-', E), ('D3', E), ('-', E), ('A3', E), ('-', E),
    # Bar 8 (G Major resolution)
    ('G2', Q), ('D3', Q), ('G2', H)
]

out.extend(struct.pack('<H', len(ch2_seq)))
for n, d in ch2_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 4. Channel 3: BOBCAT_PERC (32 Beats) ---
out.append(2) # Patch 2: RETRO_NOISE
ch3_seq = []

# A classic "Train Beat" mimicking snare brushes.
# C3 = Kick on the downbeats, C4 = Snare on the upbeats.
for _ in range(7):
    ch3_seq.extend([
        ('C3', E), ('C4', E), ('C3', E), ('C4', E),
        ('C3', E), ('C4', E), ('C3', E), ('C4', E)
    ])

# For Bar 8, we do a quick snare hit and rest for the loop turnaround.
ch3_seq.extend([
    ('C3', E), ('C4', E), ('C3', E), ('C4', E), ('C4', Q), ('-', Q)
])

out.extend(struct.pack('<H', len(ch3_seq)))
for n, d in ch3_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 5. Write to File ---
with open('bluegrass_bobcat.jseq', 'wb') as f:
    f.write(out)

print("Successfully compiled the 32-beat bluegrass_bobcat.jseq!")
