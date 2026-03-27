import struct

# Duration constants (1/32nd beat units)
N32 = 4   # Thirty-second note (0.125 beats) - Ultra short transient

def note_to_index(note_str):
    """Converts 'C4', 'A3', etc. into the 1-255 JSEQ pitch index."""
    if note_str == '-':
        return 0
    semitones = {'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5, 'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11}
    note, octave = note_str[:-1], int(note_str[-1])
    return ((octave + 1) * 12) + semitones[note] + 1

# --- 1. Global Header ---
out = bytearray(b'JSEQ')
out.append(1)                      # Version 1
out.extend(struct.pack('<H', 240)) # 240 BPM (Fast engine tick)
out.append(3)                      # 3 Channels

# =====================================================================
# "MENU TICK" - 4 UNITS TOTAL (Ultra-short UI Transient)
# =====================================================================

# --- 2. Channel 1: THE TICK (4 Units) ---
out.append(15) # Patch 15: TEXT_SCROLL (Soft 30% volume, 0.03s decay)
ch1_seq = [
    ('C6', N32) # High pitch, but softened by the envelope
]
out.extend(struct.pack('<H', len(ch1_seq)))
for n, d in ch1_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 3. Channel 2: SILENCE (4 Units) ---
out.append(0) # Patch doesn't matter for a rest
ch2_seq = [
    ('-', N32) # Padded to match Channel 1 perfectly
]
out.extend(struct.pack('<H', len(ch2_seq)))
for n, d in ch2_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 4. Channel 3: SILENCE (4 Units) ---
out.append(0) # Patch doesn't matter for a rest
ch3_seq = [
    ('-', N32) # Padded to match Channel 1 perfectly
]
out.extend(struct.pack('<H', len(ch3_seq)))
for n, d in ch3_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 5. Write to File ---
with open('menu_tick.jseq', 'wb') as f:
    f.write(out)

print("Successfully compiled menu_tick.jseq! (4 Units, 3 Channels)")
