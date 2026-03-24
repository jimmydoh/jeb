import struct

# Duration constants (1/32nd beat units)
E = 16    # Eighth note (0.5 beats)
Q = 32    # Quarter note (1.0 beats)
H = 64    # Half note (2.0 beats)
DQ = 48   # Dotted quarter (1.5 beats)

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
out.extend(struct.pack('<H', 140)) # 140 BPM
out.append(3)                      # 3 Channels

# --- 2. Channel 1: TETRIS_THEME (32 Beats) ---
out.append(0) # Patch 0: RETRO_LEAD
ch1_seq = [
    # --- A Section ---
    ('E5', Q), ('B4', E), ('C5', E), ('D5', Q),
    ('C5', E), ('B4', E), ('A4', Q), ('A4', E),
    ('C5', E), ('E5', Q), ('D5', E), ('C5', E),
    ('B4', DQ), ('C5', E), ('D5', Q), ('E5', Q),
    ('C5', Q), ('A4', Q), ('A4', H),

    # --- B Section (The Chorus) ---
    ('D5', DQ), ('F5', E), ('A5', Q), ('G5', E), ('F5', E),
    ('E5', DQ), ('C5', E), ('E5', Q), ('D5', E), ('C5', E),
    ('B4', DQ), ('C5', E), ('D5', Q), ('E5', Q),
    ('C5', Q), ('A4', Q), ('A4', H)
]
out.extend(struct.pack('<H', len(ch1_seq)))
for n, d in ch1_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 3. Channel 2: TETRIS_BASS (32 Beats) ---
out.append(1) # Patch 1: RETRO_BASS
ch2_seq = [
    # --- A Section (Am, F, G, E) ---
    ('A3', H), ('E3', H),
    ('A3', H), ('E3', H),
    ('F3', H), ('C4', H),
    ('G3', H), ('E3', H),

    # --- B Section (Dm, Am, E, Am) ---
    ('D3', H), ('A3', H),
    ('C4', H), ('E3', H),
    ('B3', H), ('E3', H),
    ('A3', H), ('E3', H)
]
out.extend(struct.pack('<H', len(ch2_seq)))
for n, d in ch2_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 4. Channel 3: TETRIS_NOISE (32 Beats) ---
out.append(2) # Patch 2: RETRO_NOISE
ch3_seq = []
# 32 consecutive hi-hat hits on the eighth notes
for _ in range(32):
    ch3_seq.append(('A3', E))
    ch3_seq.append(('-', E))

out.extend(struct.pack('<H', len(ch3_seq)))
for n, d in ch3_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 5. Write to File ---
with open('tetris.jseq', 'wb') as f:
    f.write(out)

print("Successfully compiled the complete 8-bar tetris.jseq!")
