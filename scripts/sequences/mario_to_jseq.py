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
out.extend(struct.pack('<H', 200)) # 200 BPM for Cut-Time feel
out.append(3)                      # 3 Channels

# --- 2. Channel 1: MARIO_LEAD (72 Beats) ---
out.append(0) # Patch 0: RETRO_LEAD
ch1_seq = [
    # --- Intro (8 Beats) ---
    ('E6', E), ('E6', E), ('-', E), ('E6', E), ('-', E), ('C6', E), ('E6', Q),
    ('G6', Q), ('-', Q), ('G5', Q), ('-', Q),

    # --- Theme A (16 Beats) ---
    ('C6', DQ), ('G5', E), ('-', Q), ('E5', Q),
    ('-', E), ('A5', Q), ('B5', Q), ('A#5', E), ('A5', Q),
    ('G5', E), ('-', S), ('E6', E), ('-', S), ('G6', E), ('A6', Q), ('F6', E), ('G6', E),
    ('-', E), ('E6', Q), ('C6', E), ('D6', E), ('B5', DQ),

    # --- Theme A Repeated (16 Beats) ---
    ('C6', DQ), ('G5', E), ('-', Q), ('E5', Q),
    ('-', E), ('A5', Q), ('B5', Q), ('A#5', E), ('A5', Q),
    ('G5', E), ('-', S), ('E6', E), ('-', S), ('G6', E), ('A6', Q), ('F6', E), ('G6', E),
    ('-', E), ('E6', Q), ('C6', E), ('D6', E), ('B5', DQ),

    # --- Theme B (Bridge) (32 Beats) ---
    ('-', Q), ('G6', E), ('F#6', E), ('F6', E), ('D#6', Q), ('E6', E),
    ('-', E), ('G#5', E), ('A5', E), ('C6', E), ('-', E), ('A5', E), ('C6', E), ('D6', E),
    ('-', Q), ('G6', E), ('F#6', E), ('F6', E), ('D#6', Q), ('E6', E),
    ('-', E), ('C7', Q), ('C7', E), ('C7', Q), ('-', Q),

    ('-', Q), ('G6', E), ('F#6', E), ('F6', E), ('D#6', Q), ('E6', E),
    ('-', E), ('G#5', E), ('A5', E), ('C6', E), ('-', E), ('A5', E), ('C6', E), ('D6', E),
    ('-', Q), ('D#6', Q), ('-', E), ('D6', Q), ('-', E),
    ('C6', H), ('-', H)
]
out.extend(struct.pack('<H', len(ch1_seq)))
for n, d in ch1_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 3. Channel 2: MARIO_BASS (72 Beats) ---
out.append(1) # Patch 1: RETRO_BASS
ch2_seq = [
    # --- Intro (8 Beats) ---
    ('D3', E), ('D3', E), ('-', E), ('D3', E), ('-', E), ('C3', E), ('D3', Q),
    ('G3', Q), ('-', Q), ('G2', Q), ('-', Q),

    # --- Theme A (16 Beats) ---
    ('C3', E), ('-', E), ('G2', E), ('-', E), ('C3', E), ('-', E), ('E3', E), ('-', E),
    ('F3', E), ('-', E), ('C3', E), ('-', E), ('F3', E), ('-', E), ('A3', E), ('-', E),
    ('C3', E), ('-', E), ('G2', E), ('-', E), ('C3', E), ('-', E), ('E3', E), ('-', E),
    ('F3', E), ('-', E), ('G3', E), ('-', E), ('C3', Q), ('-', Q),

    # --- Theme A Repeated (16 Beats) ---
    ('C3', E), ('-', E), ('G2', E), ('-', E), ('C3', E), ('-', E), ('E3', E), ('-', E),
    ('F3', E), ('-', E), ('C3', E), ('-', E), ('F3', E), ('-', E), ('A3', E), ('-', E),
    ('C3', E), ('-', E), ('G2', E), ('-', E), ('C3', E), ('-', E), ('E3', E), ('-', E),
    ('F3', E), ('-', E), ('G3', E), ('-', E), ('C3', Q), ('-', Q),

    # --- Theme B (Bridge) (32 Beats) ---
    ('C3', Q), ('G2', Q), ('C3', Q), ('G2', Q),
    ('F3', Q), ('C3', Q), ('F3', Q), ('C3', Q),
    ('C3', Q), ('G2', Q), ('C3', Q), ('G2', Q),
    ('G3', Q), ('D3', Q), ('G3', Q), ('D3', Q),

    ('C3', Q), ('G2', Q), ('C3', Q), ('G2', Q),
    ('F3', Q), ('C3', Q), ('F3', Q), ('C3', Q),
    ('G#2', Q), ('A#2', Q), ('C3', H),
    ('G3', Q), ('G2', Q), ('C3', H)
]
out.extend(struct.pack('<H', len(ch2_seq)))
for n, d in ch2_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 4. Channel 3: MARIO_PERC (72 Beats) ---
out.append(2) # Patch 2: RETRO_NOISE
ch3_seq = [
    # --- Intro (8 Beats) ---
    ('A3', E), ('A3', E), ('-', E), ('A3', E), ('-', E), ('A3', E), ('A3', Q),
    ('C3', Q), ('-', Q), ('C3', Q), ('-', Q)
]

# --- Main Drum Loop (16 Bars x 4 Beats = 64 Beats) ---
# C3 = Kick, A3 = Hi-Hat, C4 = Snare
for _ in range(16):
    ch3_seq.extend([
        ('C3', Q), ('A3', E), ('A3', E), ('C4', Q), ('A3', E), ('A3', E)
    ])

out.extend(struct.pack('<H', len(ch3_seq)))
for n, d in ch3_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 5. Write to File ---
with open('mario_overworld.jseq', 'wb') as f:
    f.write(out)

print("Successfully compiled the 72-beat mario_overworld.jseq!")
