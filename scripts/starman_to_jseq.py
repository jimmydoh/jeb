import struct

# Duration constants (1/32nd beat units)
E = 16    # Eighth note (0.5 beats)
Q = 32    # Quarter note (1.0 beats)

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
out.extend(struct.pack('<H', 240)) # 240 BPM for frantic cut-time feel
out.append(3)                      # 3 Channels

# --- 2. Channel 1: STARMAN_LEAD (64 Beats) ---
out.append(0) # Patch 0: RETRO_LEAD
ch1_seq = []

# The iconic 4-bar descending motif, repeated 4 times for a complete 16-bar loop.
for _ in range(4):
    ch1_seq.extend([
        # Bar 1 (F major focus)
        ('F5', E), ('-', E), ('F5', E), ('-', E), ('F5', E), ('C5', E), ('F5', E), ('G5', E),
        # Bar 2 (E minor focus)
        ('E5', E), ('-', E), ('E5', E), ('-', E), ('E5', E), ('C5', E), ('E5', E), ('F5', E),
        # Bar 3 (D minor focus)
        ('D5', E), ('-', E), ('D5', E), ('-', E), ('D5', E), ('A4', E), ('D5', E), ('E5', E),
        # Bar 4 (C major focus)
        ('C5', E), ('-', E), ('C5', E), ('-', E), ('C5', E), ('G4', E), ('C5', E), ('D5', E)
    ])

out.extend(struct.pack('<H', len(ch1_seq)))
for n, d in ch1_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 3. Channel 2: STARMAN_BASS (64 Beats) ---
out.append(1) # Patch 1: RETRO_BASS
ch2_seq = []

# A relentless, driving alternating root-fifth bassline mapped to the descending chords.
for _ in range(4):
    ch2_seq.extend([
        # Bar 1 (F)
        ('F3', E), ('C4', E), ('F3', E), ('C4', E), ('F3', E), ('C4', E), ('F3', E), ('C4', E),
        # Bar 2 (Em)
        ('E3', E), ('B3', E), ('E3', E), ('B3', E), ('E3', E), ('B3', E), ('E3', E), ('B3', E),
        # Bar 3 (Dm)
        ('D3', E), ('A3', E), ('D3', E), ('A3', E), ('D3', E), ('A3', E), ('D3', E), ('A3', E),
        # Bar 4 (C)
        ('C3', E), ('G3', E), ('C3', E), ('G3', E), ('C3', E), ('G3', E), ('C3', E), ('G3', E)
    ])

out.extend(struct.pack('<H', len(ch2_seq)))
for n, d in ch2_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 4. Channel 3: STARMAN_PERC (64 Beats) ---
out.append(2) # Patch 2: RETRO_NOISE
ch3_seq = []

# A high-speed 4-on-the-floor rock beat.
# C3 = Kick, C4 = Snare, A3 = Hi-hat
# 16 bars total to match the 4x repeats of the melody.
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
with open('starman.jseq', 'wb') as f:
    f.write(out)

print("Successfully compiled the frantic 64-beat starman.jseq!")
