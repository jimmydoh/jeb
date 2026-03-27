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
out.extend(struct.pack('<H', 150)) # 150 BPM for hard rock energy
out.append(3)                      # 3 Channels

# --- 2. Channel 1: WILY_LEAD (64 Beats) ---
out.append(0) # Patch 0: RETRO_LEAD
ch1_seq = [
    # --- Part A (8 bars) ---
    # Bar 1 (Am)
    ('A4', E), ('B4', E), ('C5', E), ('D5', E), ('E5', Q), ('A5', Q),
    # Bar 2 (F)
    ('G5', E), ('F5', E), ('E5', E), ('D5', E), ('C5', H),
    # Bar 3 (G)
    ('B4', E), ('C5', E), ('D5', E), ('E5', E), ('F5', Q), ('D5', Q),
    # Bar 4 (Am)
    ('E5', H), ('-', H),

    # Bar 5 (Am)
    ('A4', E), ('B4', E), ('C5', E), ('D5', E), ('E5', Q), ('A5', Q),
    # Bar 6 (F)
    ('G5', E), ('F5', E), ('E5', E), ('D5', E), ('C5', H),
    # Bar 7 (G)
    ('B4', E), ('C5', E), ('D5', E), ('E5', E), ('F5', Q), ('D5', Q),
    # Bar 8 (Am)
    ('E5', H), ('-', H),

    # --- Part B / Bridge (8 bars) ---
    # Bar 9 (F)
    ('F5', Q), ('E5', Q), ('D5', Q), ('C5', Q),
    # Bar 10 (G)
    ('G5', Q), ('F5', Q), ('E5', Q), ('D5', Q),
    # Bar 11 (Am)
    ('E5', H), ('A5', H),
    # Bar 12 (Am)
    ('G#5', H), ('-', H),

    # Bar 13 (F)
    ('F5', Q), ('E5', Q), ('D5', Q), ('C5', Q),
    # Bar 14 (G)
    ('G5', Q), ('F5', Q), ('E5', Q), ('D5', Q),
    # Bar 15 (C)
    ('C6', H), ('G5', H),
    # Bar 16 (E - The tense turnaround)
    ('G#5', H), ('-', H)
]

out.extend(struct.pack('<H', len(ch1_seq)))
for n, d in ch1_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 3. Channel 2: WILY_BASS (64 Beats) ---
out.append(1) # Patch 1: RETRO_BASS
ch2_seq = []

# A relentless 8th-note driving rock bassline.
# 16 bars total, each bar is 8 eighth-notes (8 * 16 = 128 units per bar)
bass_progression = [
    'A2', 'F2', 'G2', 'A2',  # Bars 1-4
    'A2', 'F2', 'G2', 'A2',  # Bars 5-8
    'F2', 'G2', 'A2', 'A2',  # Bars 9-12
    'F2', 'G2', 'C3', 'E3'   # Bars 13-16
]

for root_note in bass_progression:
    for _ in range(8):
        ch2_seq.append((root_note, E))

out.extend(struct.pack('<H', len(ch2_seq)))
for n, d in ch2_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 4. Channel 3: WILY_PERC (64 Beats) ---
out.append(2) # Patch 2: RETRO_NOISE
ch3_seq = []

# Standard high-energy rock drum beat.
# C3 = Kick, C4 = Snare, A3 = Hi-Hat.
# Loops 16 times to cover all 16 bars.
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
with open('wily_castle.jseq', 'wb') as f:
    f.write(out)

print("Successfully compiled the driving 64-beat wily_castle.jseq!")
