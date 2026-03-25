import struct

# Duration constants (1/32nd beat units)
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
out.extend(struct.pack('<H', 60))  # 60 BPM for a slow, breathing tempo
out.append(3)                      # 3 Channels

# --- 2. Channel 1: HIGH_THEREMIN (32 Beats) ---
# Patch 5 (PAD) uses a slow swelling envelope to simulate a theremin fading in.
out.append(5)
ch1_seq = [
    # Bars 1 & 2 (A Minor focus)
    ('E4', H), ('A4', H), ('C5', H), ('B4', H),
    # Bars 3 & 4 (F Major focus)
    ('E4', H), ('G4', H), ('F4', H), ('E4', H),
    # Bars 5 & 6 (D Minor focus)
    ('A4', H), ('F4', H), ('D5', H), ('C5', H),
    # Bars 7 & 8 (E Dominant tension)
    ('B4', H), ('G#4', H), ('F4', H), ('E4', H)
]

out.extend(struct.pack('<H', len(ch1_seq)))
for n, d in ch1_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 3. Channel 2: MID_THEREMIN (32 Beats) ---
out.append(5) # Patch 5 (PAD)
ch2_seq = [
    # Middle harmony moving in slow, whole notes to anchor the floating lead.
    # Bar 1 & 2
    ('C4', W), ('E4', W),
    # Bar 3 & 4
    ('A3', W), ('C4', W),
    # Bar 5 & 6
    ('F3', W), ('A3', W),
    # Bar 7 & 8
    ('G#3', W), ('B3', W)
]

out.extend(struct.pack('<H', len(ch2_seq)))
for n, d in ch2_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 4. Channel 3: LOW_THEREMIN (32 Beats) ---
out.append(5) # Patch 5 (PAD)
ch3_seq = [
    # Deep, resonant bass roots.
    # Because they are re-triggered every whole note (W), the slow
    # attack envelope will make the bassline sound like it is slowly breathing.

    # Bar 1 & 2 (Root A)
    ('A2', W), ('A2', W),
    # Bar 3 & 4 (Root F)
    ('F2', W), ('F2', W),
    # Bar 5 & 6 (Root D)
    ('D2', W), ('D2', W),
    # Bar 7 & 8 (Root E)
    ('E2', W), ('E2', W)
]

out.extend(struct.pack('<H', len(ch3_seq)))
for n, d in ch3_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 5. Write to File ---
with open('ghost_choir.jseq', 'wb') as f:
    f.write(out)

print("Successfully compiled the haunting 32-beat ghost_choir.jseq!")
