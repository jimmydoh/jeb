import struct

# Duration constants (1/32nd beat units)
N32 = 4   # Thirty-second note (0.125 beats) - Ultra fast!
S = 8     # Sixteenth note (0.25 beats)
E = 16    # Eighth note (0.5 beats)
Q = 32    # Quarter note (1.0 beats)

def note_to_index(note_str):
    if note_str == '-':
        return 0
    semitones = {'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5, 'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11}
    note, octave = note_str[:-1], int(note_str[-1])
    return ((octave + 1) * 12) + semitones[note] + 1

# --- 1. Global Header ---
out = bytearray(b'JSEQ')
out.append(1)
out.extend(struct.pack('<H', 300)) # 300 BPM for high-speed data processing
out.append(3)                      # 3 Channels

# --- 2. Channel 1: DATA_STREAM (192 Units / 6 Beats) ---
# Assuming Index 12 is mapped to DATA_STREAM in your engine.
out.append(12)
ch1_seq = [
    # Beat 1: Frantic crunching (32 units)
    ('C6', N32), ('-', N32), ('E6', N32), ('G6', N32),
    ('C7', N32), ('-', N32), ('B6', N32), ('A6', N32),

    # Beat 2: More crunching (32 units)
    ('F6', N32), ('-', N32), ('D6', N32), ('F6', N32),
    ('G6', N32), ('-', N32), ('E6', N32), ('C6', N32),

    # Beat 3: Final data burst (32 units)
    ('A6', N32), ('B6', N32), ('-', N32), ('G6', N32),
    ('E6', N32), ('F6', N32), ('-', N32), ('D6', N32),

    # Beat 4: Processing pause / lock-in (32 units)
    ('C6', E), ('-', E),

    # Beats 5 & 6: "Access Granted" ascending chime (64 units)
    ('C6', S), ('E6', S), ('G6', S), ('C7', 40)
]

out.extend(struct.pack('<H', len(ch1_seq)))
for n, d in ch1_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 3. Channel 2: BACKGROUND_HUM (192 Units / 6 Beats) ---
# Patch 5 (PAD) acts as a low, ominous computer fan / mainframe hum.
out.append(5)
ch2_seq = [
    # A single, sustained C3 note lasting exactly 192 units.
    # Note: 192 is under the 255 max value for a single JSEQ duration byte!
    ('C3', 192)
]

out.extend(struct.pack('<H', len(ch2_seq)))
for n, d in ch2_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 4. Channel 3: SILENCE (192 Units / 6 Beats) ---
# We pad the third channel with pure silence to ensure the JSEQ format
# stays perfectly synced across all 3 tracks.
out.append(2) # Doesn't matter which patch, it's just a rest!
ch3_seq = [
    ('-', 192)
]

out.extend(struct.pack('<H', len(ch3_seq)))
for n, d in ch3_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 5. Write to File ---
with open('sfx_terminal_access.jseq', 'wb') as f:
    f.write(out)

print("Successfully compiled the terminal access sound effect!")
