import struct

# Duration constants (1/32nd beat units)
S = 8     # Sixteenth note (0.25 beats)
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
out.extend(struct.pack('<H', 160)) # 160 BPM for high-stakes battle energy
out.append(3)                      # 3 Channels

# --- 2. Channel 1: GYM_LEAD (32 Beats) ---
out.append(0) # Patch 0: RETRO_LEAD
ch1_seq = []

# The Masuda Arpeggio Technique: Fast 16th notes outlining the chords.
# We will loop this 4-bar progression twice for a total of 8 bars (1024 units).
arpeggio_progression = [
    # Bar 1: A Minor
    ['A4', 'C5', 'E5', 'A5'] * 4,
    # Bar 2: F Major
    ['F4', 'A4', 'C5', 'F5'] * 4,
    # Bar 3: G Major
    ['G4', 'B4', 'D5', 'G5'] * 4,
    # Bar 4: E Major (Tension turnaround)
    ['E4', 'G#4', 'B4', 'E5'] * 4
]

for _ in range(2): # Loop twice
    for bar in arpeggio_progression:
        for note in bar:
            ch1_seq.append((note, S)) # Sixteenth notes

out.extend(struct.pack('<H', len(ch1_seq)))
for n, d in ch1_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 3. Channel 2: GYM_BASS (32 Beats) ---
out.append(1) # Patch 1: RETRO_BASS
ch2_seq = []

# A relentless 8th-note driving bass pedal.
# 8 bars total, each bar is 8 eighth-notes (8 * 16 = 128 units per bar)
bass_progression = [
    'A2', 'F2', 'G2', 'E2', # Bars 1-4
    'A2', 'F2', 'G2', 'E2'  # Bars 5-8
]

for root_note in bass_progression:
    for _ in range(8):
        ch2_seq.append((root_note, E)) # Eighth notes

out.extend(struct.pack('<H', len(ch2_seq)))
for n, d in ch2_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 4. Channel 3: GYM_PERC (32 Beats) ---
out.append(2) # Patch 2: RETRO_NOISE
ch3_seq = []

# Frantic battle drums.
# C3 = Kick, C4 = Snare, A3 = Hi-Hat.
# Loops 8 times to cover all 8 bars seamlessly.
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
with open('pokemon_gym.jseq', 'wb') as f:
    f.write(out)

print("Successfully compiled the frantic 32-beat pokemon_gym.jseq!")
