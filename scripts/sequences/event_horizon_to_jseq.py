import struct

# Duration constants (1/32nd beat units)
# Max duration byte is 255. W (128) is 4 full beats.
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
out.extend(struct.pack('<H', 100)) # 100 BPM (Majestic, sweeping tempo)
out.append(3)                      # 3 Channels

# =====================================================================
# "EVENT HORIZON" - 256 BEATS TOTAL (2m 33s)
# Chord Progression: Am -> F -> C -> G
# =====================================================================

# --- 2. Channel 1: ETHEREAL (256 Beats) ---
# Sweeping, slow-attack high melodies.
out.append(13) # Patch 13: ETHEREAL
ch1_seq = []

# Sec 1: The Void (64 Beats) - Silence to let the bass breathe
ch1_seq.extend([('-', W)] * 16)

# Sec 2: The Approach (64 Beats) - Slow, drifting upper melody
ch1_seq.extend([('A5', W), ('E6', W)] * 2) # Am
ch1_seq.extend([('C6', W), ('A5', W)] * 2) # F
ch1_seq.extend([('E6', W), ('C6', W)] * 2) # C
ch1_seq.extend([('B5', W), ('G5', W)] * 2) # G

# Sec 3: The Ignition (64 Beats) - Faster harmonic movement
ch1_seq.extend([('C6', H), ('B5', H), ('E6', W)] * 2) # Am
ch1_seq.extend([('A5', H), ('G5', H), ('C6', W)] * 2) # F
ch1_seq.extend([('G5', H), ('F5', H), ('E6', W)] * 2) # C
ch1_seq.extend([('D6', H), ('C6', H), ('B5', W)] * 2) # G

# Sec 4: The Supernova (64 Beats) - Massive high octaves
ch1_seq.extend([('A6', W), ('E6', W)] * 2) # Am
ch1_seq.extend([('A6', W), ('F6', W)] * 2) # F
ch1_seq.extend([('G6', W), ('E6', W)] * 2) # C
ch1_seq.extend([('G6', W), ('D6', W)] * 2) # G

out.extend(struct.pack('<H', len(ch1_seq)))
for n, d in ch1_seq:
    out.append(note_to_index(n))
    out.append(int(d))


# --- 3. Channel 2: PAD (256 Beats) ---
# Thick, sustaining mid-range chords.
out.append(5) # Patch 5: PAD
ch2_seq = []

# Sec 1: The Void (64 Beats) - Intermittent minor swells
ch2_seq.extend([('A3', W), ('-', W), ('F3', W), ('-', W)] * 4)

# Sec 2: The Approach (64 Beats) - Solidifying the progression
ch2_seq.extend([('A3', W)] * 4) # Am
ch2_seq.extend([('F3', W)] * 4) # F
ch2_seq.extend([('C4', W)] * 4) # C
ch2_seq.extend([('G3', W)] * 4) # G

# Sec 3: The Ignition (64 Beats) - Breathing pulses
ch2_seq.extend([('A3', H), ('C4', H), ('E4', H), ('C4', H)] * 2) # Am
ch2_seq.extend([('F3', H), ('A3', H), ('C4', H), ('A3', H)] * 2) # F
ch2_seq.extend([('C4', H), ('E4', H), ('G4', H), ('E4', H)] * 2) # C
ch2_seq.extend([('G3', H), ('B3', H), ('D4', H), ('B3', H)] * 2) # G

# Sec 4: The Supernova (64 Beats) - Dense chord clusters
ch2_seq.extend([('E4', W), ('C4', W)] * 2) # Am
ch2_seq.extend([('F4', W), ('C4', W)] * 2) # F
ch2_seq.extend([('G4', W), ('E4', W)] * 2) # C
ch2_seq.extend([('D4', W), ('B3', W)] * 2) # G

out.extend(struct.pack('<H', len(ch2_seq)))
for n, d in ch2_seq:
    out.append(note_to_index(n))
    out.append(int(d))


# --- 4. Channel 3: ENGINE_HUM (256 Beats) ---
# Deep, rumbling sub-bass foundation (1.5s attack).
out.append(14) # Patch 14: ENGINE_HUM
ch3_seq = []

# Sec 1: The Void (64 Beats)
ch3_seq.extend([('A1', W)] * 8)
ch3_seq.extend([('F1', W)] * 8)

# Sec 2: The Approach (64 Beats)
ch3_seq.extend([('A1', W)] * 4)
ch3_seq.extend([('F1', W)] * 4)
ch3_seq.extend([('C2', W)] * 4)
ch3_seq.extend([('G1', W)] * 4)

# Sec 3: The Ignition (64 Beats) - Slow octave leaps for tension
ch3_seq.extend([('A1', W), ('A1', W), ('A2', W), ('A2', W)]) # Am
ch3_seq.extend([('F1', W), ('F1', W), ('F2', W), ('F2', W)]) # F
ch3_seq.extend([('C2', W), ('C2', W), ('C3', W), ('C3', W)]) # C
ch3_seq.extend([('G1', W), ('G1', W), ('G2', W), ('G2', W)]) # G

# Sec 4: The Supernova (64 Beats) - Heavy, sustained roots
ch3_seq.extend([('A1', W)] * 4)
ch3_seq.extend([('F1', W)] * 4)
ch3_seq.extend([('C2', W)] * 4)
ch3_seq.extend([('G1', W)] * 4)

out.extend(struct.pack('<H', len(ch3_seq)))
for n, d in ch3_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 5. Write to File ---
with open('event_horizon.jseq', 'wb') as f:
    f.write(out)

print("Successfully compiled event_horizon.jseq! (256 Beats, 3 Channels)")
