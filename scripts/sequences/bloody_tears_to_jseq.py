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
out.extend(struct.pack('<H', 140)) # 140 BPM for driving gothic action
out.append(3)                      # 3 Channels

# --- 2. Channel 1: TEARS_LEAD (32 Beats) ---
out.append(0) # Patch 0: RETRO_LEAD
ch1_seq = [
    # Bar 1: The iconic D minor climb (128 units)
    ('D5', Q), ('A4', E), ('D5', E), ('F5', E), ('E5', E), ('D5', E), ('C#5', E),
    # Bar 2: Pushing higher (128 units)
    ('D5', Q), ('A4', E), ('D5', E), ('F5', E), ('G5', E), ('A5', E), ('A#5', E),
    # Bar 3: The C Major shift (128 units)
    ('C6', Q), ('G5', E), ('C6', E), ('E6', E), ('D6', E), ('C6', E), ('B5', E),
    # Bar 4: Descending tension (Bb to A) (128 units)
    ('A#5', Q), ('A5', Q), ('G5', Q), ('F5', Q),

    # Bar 5: Repeat the D minor climb (128 units)
    ('D5', Q), ('A4', E), ('D5', E), ('F5', E), ('E5', E), ('D5', E), ('C#5', E),
    # Bar 6: Pushing higher again (128 units)
    ('D5', Q), ('A4', E), ('D5', E), ('F5', E), ('G5', E), ('A5', E), ('A#5', E),
    # Bar 7: The C Major shift (128 units)
    ('C6', Q), ('G5', E), ('C6', E), ('E6', E), ('D6', E), ('C6', E), ('B5', E),
    # Bar 8: The haunting A Major resolution hold (128 units)
    ('A5', H), ('A4', H)
]

out.extend(struct.pack('<H', len(ch1_seq)))
for n, d in ch1_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 3. Channel 2: TEARS_BASS (32 Beats) ---
out.append(1) # Patch 1: RETRO_BASS
ch2_seq = []

# The classic Castlevania galloping bassline.
# Straight 8th notes to keep the momentum fierce.
bass_progression = [
    # Bars 1 & 2 (D Minor)
    ['D3'] * 8, ['D3'] * 8,
    # Bar 3 (C Major)
    ['C3'] * 8,
    # Bar 4 (Bb to A turn)
    ['A#2'] * 4 + ['A2'] * 4,
    # Bars 5 & 6 (D Minor)
    ['D3'] * 8, ['D3'] * 8,
    # Bar 7 (C Major)
    ['C3'] * 8,
    # Bar 8 (A Major lock)
    ['A2'] * 8
]

for bar in bass_progression:
    for note in bar:
        ch2_seq.append((note, E))

out.extend(struct.pack('<H', len(ch2_seq)))
for n, d in ch2_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 4. Channel 3: TEARS_PERC (32 Beats) ---
out.append(2) # Patch 2: RETRO_NOISE
ch3_seq = []

# A driving, whip-cracking drum beat.
# C3 = Kick, C4 = Whip/Snare, A3 = Hi-Hat.
# Loops 8 times for the full 8 bars.
for _ in range(8):
    ch3_seq.extend([
        ('C3', E), ('A3', E), ('C4', E), ('A3', E),
        ('C3', E), ('A3', E), ('C4', E), ('A3', E)
    ])

out.extend(struct.pack('<H', len(ch3_seq)))
for n, d in ch3_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 5. Write to File ---
with open('bloody_tears.jseq', 'wb') as f:
    f.write(out)

print("Successfully compiled the gothic 32-beat bloody_tears.jseq!")
