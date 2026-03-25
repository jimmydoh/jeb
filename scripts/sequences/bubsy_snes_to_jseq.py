import struct

# Duration constants (1/32nd beat units)
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
out.extend(struct.pack('<H', 180)) # 180 BPM for zany mascot energy
out.append(3)                      # 3 Channels

# --- 2. Channel 1: BUBSY_TRUE_TITLE_LEAD (32 Beats) ---
out.append(0) # Patch 0: RETRO_LEAD
ch1_seq = [
    # Bar 1: The fast, bouncy major climb (128 units)
    ('C5', E), ('E5', E), ('G5', E), ('C6', E), ('E6', Q), ('C6', Q),
    # Bar 2: The answering high phrase (128 units)
    ('A5', E), ('C6', E), ('E6', E), ('A6', E), ('G6', Q), ('E6', Q),
    # Bar 3: The chaotic descent (128 units)
    ('F6', E), ('D6', E), ('B5', E), ('G5', E), ('E5', E), ('G5', E), ('C6', Q),
    # Bar 4: The turnaround hook (128 units)
    ('D6', E), ('G5', E), ('B5', E), ('D6', E), ('G6', H),

    # Bar 5: Repeat the bouncy climb (128 units)
    ('C5', E), ('E5', E), ('G5', E), ('C6', E), ('E6', Q), ('C6', Q),
    # Bar 6: Repeat the high phrase (128 units)
    ('A5', E), ('C6', E), ('E6', E), ('A6', E), ('G6', Q), ('E6', Q),
    # Bar 7: The final sweeping descent (128 units)
    ('F6', E), ('D6', E), ('B5', E), ('G5', E), ('A5', E), ('B5', E), ('D6', Q),
    # Bar 8: The big resolving hit (128 units)
    ('C6', H), ('-', H),
]

out.extend(struct.pack('<H', len(ch1_seq)))
for n, d in ch1_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 3. Channel 2: BUBSY_TRUE_TITLE_BASS (32 Beats) ---
out.append(1) # Patch 1: RETRO_BASS
ch2_seq = [
    # A bouncy, slap-bass style progression on the quarter notes.
    # Every bar is strictly 128 units.

    # Bar 1 (C Major)
    ('C3', Q), ('G3', Q), ('C4', Q), ('G3', Q),
    # Bar 2 (A Minor)
    ('A2', Q), ('E3', Q), ('A3', Q), ('E3', Q),
    # Bar 3 (F Major descending)
    ('F2', Q), ('C3', Q), ('E2', Q), ('C3', Q),
    # Bar 4 (G Major hook)
    ('G2', Q), ('D3', Q), ('G3', H),

    # Bar 5 (C Major)
    ('C3', Q), ('G3', Q), ('C4', Q), ('G3', Q),
    # Bar 6 (A Minor)
    ('A2', Q), ('E3', Q), ('A3', Q), ('E3', Q),
    # Bar 7 (F to G turnaround)
    ('F2', Q), ('G2', Q), ('F3', Q), ('G3', Q),
    # Bar 8 (C Major resolution)
    ('C3', H), ('-', H),
]

out.extend(struct.pack('<H', len(ch2_seq)))
for n, d in ch2_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 4. Channel 3: BUBSY_TRUE_TITLE_PERC (32 Beats) ---
out.append(2) # Patch 2: RETRO_NOISE
ch3_seq = []

# A frantic platformer drum beat.
# For the first 7 bars, we play a standard driving rhythm.
for _ in range(7):
    ch3_seq.extend([
        ('C3', Q), ('A3', E), ('A3', E), ('C4', Q), ('A3', E), ('A3', E)
    ])

# For Bar 8, we do a quick drum fill to set up the loop back to the start.
ch3_seq.extend([
    ('C3', E), ('C3', E), ('C4', E), ('C4', E), ('C5', H)
])

out.extend(struct.pack('<H', len(ch3_seq)))
for n, d in ch3_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 5. Write to File ---
with open('bubsy_snes_title.jseq', 'wb') as f:
    f.write(out)

print("Successfully compiled the 32-beat bubsy_snes_title.jseq!")
