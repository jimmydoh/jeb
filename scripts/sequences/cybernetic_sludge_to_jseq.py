import struct

# Duration constants (1/32nd beat units)
# Max duration byte is 255. W (128) is 4 full beats.
N32 = 4   # Thirty-second note (0.125 beats)
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
out.extend(struct.pack('<H', 140)) # 140 BPM (Classic Dubstep Tempo)
out.append(3)                      # 3 Channels

# =====================================================================
# "CYBERNETIC SLUDGE" - 128 BEATS TOTAL
# =====================================================================

# --- 2. Channel 1: THE FILTH (Mid-Bass Stabs & Screeches) ---
out.append(17) # Patch 17: ERROR (Harsh Sawtooth, Punchy Envelope)
ch1_seq = []

# Sec 1: Intro (32 Beats) - Eerie, sparse stabs
ch1_seq.extend([('F2', E), ('-', H - E)] * 16)

# Sec 2: The Build (32 Beats) - Accelerating tension
ch1_seq.extend([('F2', Q)] * 16)                # 16 beats of quarters
ch1_seq.extend([('F2', E), ('-', E)] * 8)       # 8 beats of eighths
ch1_seq.extend([('F2', S), ('-', S)] * 16)      # 8 beats of sixteenths

# Sec 3: The Drop (32 Beats) - Aggressive stutter bass riff
drop_riff = [
    ('F2', E), ('-', E),                        # Beat 1: Heavy stab
    ('F1', E), ('-', E),                        # Beat 2: Low grunt
    ('G#2', S), ('-', S), ('G2', S), ('-', S),  # Beat 3: Descending glitch
    ('F2', S), ('-', S), ('D#2', S), ('-', S),  # Beat 4: Glitch cont.
    ('F1', S), ('-', S), ('F1', S), ('-', S),   # Beat 5: Low stutter
    ('F2', E), ('-', E),                        # Beat 6: Heavy stab
    ('C3', S), ('G#2', S), ('F2', S), ('D#2', S),# Beat 7: Fast run down
    ('C2', S), ('-', S), ('-', E)               # Beat 8: Choke
]
ch1_seq.extend(drop_riff * 4)

# Sec 4: Drop Variation (32 Beats) - Adds a screeching high synth
ch1_seq.extend(drop_riff * 3)
# Last 8 beats switch to a frantic high-pitched mechanical screech
ch1_seq.extend([('F5', S), ('E5', S), ('D#5', S), ('D5', S)] * 8)

out.extend(struct.pack('<H', len(ch1_seq)))
for n, d in ch1_seq:
    out.append(note_to_index(n))
    out.append(int(d))


# --- 3. Channel 2: THE SUB (Deep Foundation) ---
out.append(1) # Patch 1: RETRO_BASS (Clean Triangle Wave)
ch2_seq = []

# Sec 1: Intro (32 Beats)
ch2_seq.extend([('F1', W)] * 8)

# Sec 2: The Build (32 Beats) - Rhythmic pacing
ch2_seq.extend([('F1', W)] * 4)
ch2_seq.extend([('F1', H)] * 4)
ch2_seq.extend([('F1', Q)] * 4)
ch2_seq.extend([('-', W)]) # 4 beats of silence before the drop

# Sec 3 & 4: The Drop & Var (64 Beats) - Heavy, sustained roots under the stutters
sub_riff = [
    ('F1', H),                  # Beats 1-2
    ('G#1', Q), ('F1', Q),      # Beats 3-4
    ('F1', H),                  # Beats 5-6
    ('D#1', Q), ('C1', Q)       # Beats 7-8
]
ch2_seq.extend(sub_riff * 8)

out.extend(struct.pack('<H', len(ch2_seq)))
for n, d in ch2_seq:
    out.append(note_to_index(n))
    out.append(int(d))


# --- 4. Channel 3: THE DRUMS (Half-Time Groove) ---
out.append(2) # Patch 2: RETRO_NOISE
ch3_seq = []

# Sec 1: Intro (32 Beats) - Sparse ticking
ch3_seq.extend([('-', Q), ('C4', E), ('-', E)] * 16)

# Sec 2: The Build (32 Beats) - Classic snare roll build
ch3_seq.extend([('C4', Q)] * 16)                    # Quarters
ch3_seq.extend([('C4', E), ('-', E)] * 8)           # Eighths
ch3_seq.extend([('C4', S), ('-', S)] * 8)           # Sixteenths
ch3_seq.extend([('C4', N32)] * 32)                  # Thirty-second note buzz roll

# Sec 3 & 4: The Drop & Var (64 Beats) - Heavy Half-Time
# Kick on 1, Snare on 3
drop_drums = [
    ('C4', E), ('-', E),                        # Beat 1: Kick
    ('C4', S), ('-', S), ('C4', S), ('-', S),   # Beat 2: Hats
    ('C4', E), ('-', E),                        # Beat 3: Snare
    ('C4', S), ('-', S), ('C4', S), ('-', S),   # Beat 4: Hats
    ('C4', E), ('-', E),                        # Beat 5: Kick
    ('-', E), ('C4', E),                        # Beat 6: Syncopated Kick
    ('C4', E), ('-', E),                        # Beat 7: Snare
    ('C4', S), ('-', S), ('C4', S), ('-', S)    # Beat 8: Hats
]
ch3_seq.extend(drop_drums * 8)

out.extend(struct.pack('<H', len(ch3_seq)))
for n, d in ch3_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 5. Write to File ---
with open('cyber_sludge.jseq', 'wb') as f:
    f.write(out)

print("Successfully compiled cyber_sludge.jseq! (128 Beats, 3 Channels)")
