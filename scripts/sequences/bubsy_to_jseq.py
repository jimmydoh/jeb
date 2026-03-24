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
out.extend(struct.pack('<H', 130)) # 130 BPM for a jazzy title screen strut
out.append(3)                      # 3 Channels

# --- 2. Channel 1: BUBSY_TITLE_LEAD (32 Beats) ---
out.append(0) # Patch 0: RETRO_LEAD
ch1_seq = [
    # Bar 1: The classic bluesy climb (128 units)
    ('C5', Q), ('D5', Q), ('D#5', E), ('E5', Q), ('C5', E),
    # Bar 2: The tail end of the phrase (128 units)
    ('A4', E), ('C5', E), ('G4', H), ('-', Q),

    # Bar 3: Repeat the climb (128 units)
    ('C5', Q), ('D5', Q), ('D#5', E), ('E5', Q), ('C5', E),
    # Bar 4: An upward jazzy flick (128 units)
    ('A4', E), ('C5', E), ('A5', H), ('-', Q),

    # Bar 5: Descending turnaround (128 units)
    ('G5', E), ('F5', E), ('E5', E), ('C5', E), ('D5', Q), ('C5', Q),
    # Bar 6: Resolution setup (128 units)
    ('E5', E), ('C5', E), ('A4', E), ('G4', E), ('C5', H),

    # Bar 7: Final climb to the loop point (128 units)
    ('C5', Q), ('D5', Q), ('D#5', E), ('E5', E), ('G5', Q),
    # Bar 8: The big hit (128 units)
    ('C6', H), ('C6', H)
]

out.extend(struct.pack('<H', len(ch1_seq)))
for n, d in ch1_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 3. Channel 2: BUBSY_TITLE_BASS (32 Beats) ---
out.append(1) # Patch 1: RETRO_BASS
ch2_seq = [
    # A standard 4/4 walking bassline to give it that big band feel.
    # Every bar is strictly 128 units.

    # Bars 1 & 2: C Major outline
    ('C3', Q), ('E3', Q), ('G3', Q), ('A3', Q),
    ('C3', Q), ('E3', Q), ('G3', Q), ('A3', Q),

    # Bars 3 & 4: F Major outline
    ('F3', Q), ('A3', Q), ('C4', Q), ('D4', Q),
    ('F3', Q), ('A3', Q), ('C4', Q), ('D4', Q),

    # Bar 5: G Major outline (The V chord)
    ('G3', Q), ('B3', Q), ('D4', Q), ('E4', Q),
    # Bar 6: Back to C Major (The I chord)
    ('C3', Q), ('E3', Q), ('G3', Q), ('A3', Q),

    # Bar 7: Descending walkdown back to the root
    ('G3', Q), ('F3', Q), ('E3', Q), ('D3', Q),
    # Bar 8: Solid anchor on the root
    ('C3', Q), ('G2', Q), ('C3', H)
]

out.extend(struct.pack('<H', len(ch2_seq)))
for n, d in ch2_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 4. Channel 3: BUBSY_TITLE_PERC (32 Beats) ---
out.append(2) # Patch 2: RETRO_NOISE
ch3_seq = []

# A 1-bar jazzy shuffle drum pattern repeated 8 times (8 x 4 beats = 32 beats).
# C3 = Kick, C4 = Snare, A3 = Hi-Hat on the off-beats.
for _ in range(8):
    ch3_seq.extend([
        ('C3', Q),             # Beat 1: Kick
        ('C4', E), ('A3', E),  # Beat 2: Snare, then an off-beat hat
        ('C3', E), ('A3', E),  # Beat 3: Kick, then an off-beat hat
        ('C4', Q)              # Beat 4: Solid Snare
    ])

out.extend(struct.pack('<H', len(ch3_seq)))
for n, d in ch3_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 5. Write to File ---
with open('bubsy_title.jseq', 'wb') as f:
    f.write(out)

print("Successfully compiled the 32-beat bubsy_title.jseq!")
