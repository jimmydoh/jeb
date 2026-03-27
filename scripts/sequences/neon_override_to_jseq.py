import struct

# Duration constants (1/32nd beat units)
# Max duration byte is 255. W (128) is 4 full beats.
S = 8     # Sixteenth note (0.25 beats)
E = 16    # Eighth note (0.5 beats)
Q = 32    # Quarter note (1.0 beats)
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
out.append(1)                      # Version 1
out.extend(struct.pack('<H', 140)) # 140 BPM (High Energy)
out.append(3)                      # 3 Channels

# =====================================================================
# "NEON OVERRIDE" - 256 BEATS TOTAL
# Structured: Intro -> Verse 1 -> Chorus -> Verse 2 -> Chorus -> Break -> Climax -> Outro
# =====================================================================

# --- HELPER ARRAYS (8 Beats Each) ---
# Basslines
bass_drive_E = [('E3', E)] * 16
bass_drive_C = [('C3', E)] * 16
bass_drive_G = [('G2', E)] * 16
bass_drive_D = [('D3', E)] * 16

bass_oct_E = [('E2', E), ('E3', E)] * 8
bass_oct_C = [('C2', E), ('C3', E)] * 8
bass_oct_G = [('G1', E), ('G2', E)] * 8
bass_oct_D = [('D2', E), ('D3', E)] * 8

# Noise Patterns
drums_basic = [('C4', E), ('-', E)] * 8             # 8 Beats
drums_heavy = [('C4', E), ('-', S), ('C4', S)] * 8  # 8 Beats
drums_roll  = [('C4', S)] * 32                      # 8 Beats

# Chorus Lead Melody (32 Beats Total)
chorus_melody = [
    # Em (8 beats)
    ('B4', Q), ('E5', Q), ('G5', Q), ('F#5', E), ('D5', E),
    ('E5', H), ('B4', H),
    # C (8 beats)
    ('C5', Q), ('E5', Q), ('G5', Q), ('F#5', E), ('D5', E),
    ('C5', H), ('G4', H),
    # G (8 beats)
    ('D5', Q), ('G5', Q), ('B5', Q), ('A5', E), ('G5', E),
    ('A5', H), ('D5', H),
    # D (8 beats)
    ('F#5', Q), ('A5', Q), ('D6', Q), ('C6', E), ('B5', E),
    ('A5', W)
]

# --- 2. Channel 1: RETRO LEAD (256 Beats) ---
out.append(0) # Patch 0: RETRO_LEAD
ch1_seq = []

# Sec 1: Intro (32 Beats) - Slow rising tension
ch1_seq.extend([('-', W)] * 4)
ch1_seq.extend([('E4', W), ('G4', W), ('B4', W), ('D5', W)])

# Sec 2: Verse 1 (32 Beats) - Fast Arpeggios
ch1_seq.extend([('E4', S), ('G4', S), ('B4', S), ('E5', S)] * 8)
ch1_seq.extend([('C4', S), ('E4', S), ('G4', S), ('C5', S)] * 8)
ch1_seq.extend([('G4', S), ('B4', S), ('D5', S), ('G5', S)] * 8)
ch1_seq.extend([('D4', S), ('F#4', S), ('A4', S), ('D5', S)] * 8)

# Sec 3: Chorus 1 (32 Beats) - Main Anthem
ch1_seq.extend(chorus_melody)

# Sec 4: Verse 2 (32 Beats) - Syncopated Stabs
ch1_seq.extend([('E5', E), ('-', E), ('B4', Q), ('-', H), ('-', W)])
ch1_seq.extend([('C5', E), ('-', E), ('G4', Q), ('-', H), ('-', W)])
ch1_seq.extend([('G5', E), ('-', E), ('D5', Q), ('-', H), ('-', W)])
ch1_seq.extend([('F#5', E), ('-', E), ('A4', Q), ('-', H), ('-', W)])

# Sec 5: Chorus 2 (32 Beats) - Main Anthem Returns
ch1_seq.extend(chorus_melody)

# Sec 6: Breakdown (32 Beats) - Half-time, floating
ch1_seq.extend([('B4', W), ('E5', W), ('C5', W), ('G5', W)])
ch1_seq.extend([('D5', W), ('A5', W), ('F#5', W), ('D6', W)])

# Sec 7: Climax (32 Beats) - Frantic Solo
ch1_seq.extend([('E6', S), ('D6', S), ('B5', S), ('A5', S)] * 8)
ch1_seq.extend([('G5', S), ('A5', S), ('B5', S), ('D6', S)] * 8)
ch1_seq.extend([('E6', S), ('F#6', S), ('G6', S), ('F#6', S)] * 8)
ch1_seq.extend([('A6', W), ('G6', W)])

# Sec 8: Outro (32 Beats) - Fade Out
ch1_seq.extend(chorus_melody[:14]) # Play just the first 16 beats of melody
ch1_seq.extend([('E4', W), ('-', W), ('-', W), ('-', W)])

out.extend(struct.pack('<H', len(ch1_seq)))
for n, d in ch1_seq:
    out.append(note_to_index(n))
    out.append(int(d))


# --- 3. Channel 2: RETRO BASS (256 Beats) ---
out.append(1) # Patch 1: RETRO_BASS
ch2_seq = []

# Sec 1: Intro
ch2_seq.extend([('E3', W)] * 8)
# Sec 2: Verse 1
ch2_seq.extend(bass_drive_E + bass_drive_C + bass_drive_G + bass_drive_D)
# Sec 3: Chorus 1
ch2_seq.extend(bass_oct_E + bass_oct_C + bass_oct_G + bass_oct_D)
# Sec 4: Verse 2
ch2_seq.extend(bass_drive_E + bass_drive_C + bass_drive_G + bass_drive_D)
# Sec 5: Chorus 2
ch2_seq.extend(bass_oct_E + bass_oct_C + bass_oct_G + bass_oct_D)
# Sec 6: Breakdown
ch2_seq.extend([('E3', W), ('-', W), ('C3', W), ('-', W), ('G2', W), ('-', W), ('D3', W), ('-', W)])
# Sec 7: Climax
ch2_seq.extend(bass_oct_E + bass_oct_C + bass_oct_G + bass_oct_D)
# Sec 8: Outro
ch2_seq.extend(bass_drive_E + bass_drive_C)
ch2_seq.extend([('E2', W), ('-', W), ('-', W), ('-', W)])

out.extend(struct.pack('<H', len(ch2_seq)))
for n, d in ch2_seq:
    out.append(note_to_index(n))
    out.append(int(d))


# --- 4. Channel 3: NOISE PERCUSSION (256 Beats) ---
out.append(2) # Patch 2: RETRO_NOISE
ch3_seq = []

# Sec 1: Intro (Tick on the quarter note)
ch3_seq.extend([('C4', Q), ('-', Q)] * 16)
# Sec 2: Verse 1
ch3_seq.extend(drums_basic * 4)
# Sec 3: Chorus 1
ch3_seq.extend(drums_heavy * 4)
# Sec 4: Verse 2 (Off-beat hi-hats)
ch3_seq.extend([('-', E), ('C4', E)] * 16)
# Sec 5: Chorus 2
ch3_seq.extend(drums_heavy * 4)
# Sec 6: Breakdown
ch3_seq.extend([('-', W)] * 8)
# Sec 7: Climax (Intense 16th note rolls)
ch3_seq.extend(drums_roll * 4)
# Sec 8: Outro
ch3_seq.extend(drums_basic * 2)
ch3_seq.extend([('-', W)] * 4)

out.extend(struct.pack('<H', len(ch3_seq)))
for n, d in ch3_seq:
    out.append(note_to_index(n))
    out.append(int(d))


# --- 5. Write to File ---
with open('neon_override.jseq', 'wb') as f:
    f.write(out)

print("Successfully compiled neon_override.jseq! (256 Beats, 3 Channels)")
