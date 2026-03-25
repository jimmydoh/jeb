import struct

# Duration constants (1/32nd beat units)
S = 8     # Sixteenth note (0.25 beats)
E = 16    # Eighth note (0.5 beats)
Q = 32    # Quarter note (1.0 beats)
DQ = 48   # Dotted quarter (1.5 beats)
H = 64    # Half note (2.0 beats)
W = 128   # Whole note (4.0 beats)

def note_to_index(note_str):
    if note_str == '-':
        return 0
    semitones = {'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5, 'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11}
    note, octave = note_str[:-1], int(note_str[-1])
    return ((octave + 1) * 12) + semitones[note] + 1

# ==========================================
# TRANCE SECTIONS (8 Bars / 1024 units each)
# Progression: Fm -> Eb -> Db -> Eb
# ==========================================

# --- 1. THE PULSE (Intro) ---
# Deep, filtering bass and sparse kicks. Pad swells on the root.
sec1_lead = [('F2', E), ('-', E)] * 32

sec1_pad = [('F3', W)] * 8

sec1_perc = [('C3', Q), ('-', Q), ('-', H)] * 8


# --- 2. THE ARP (Build 1) ---
# Bass opens up into a jumping 16th-note octave arpeggiator.
sec2_lead = ([('F2', S), ('F3', S), ('F2', S), ('F3', S)] * 8 +
             [('D#2', S), ('D#3', S), ('D#2', S), ('D#3', S)] * 8 +
             [('C#2', S), ('C#3', S), ('C#2', S), ('C#3', S)] * 8 +
             [('D#2', S), ('D#3', S), ('D#2', S), ('D#3', S)] * 8)

# Pad begins the massive chord progression
sec2_pad = [('F3', W), ('F3', W), ('D#3', W), ('D#3', W),
            ('C#3', W), ('C#3', W), ('D#3', W), ('D#3', W)]

sec2_perc = [('C3', Q), ('A3', Q)] * 16 # Add the hi-hat


# --- 3. THE DROP (Groove) ---
# Heavy, syncopated 16th note bassline.
sync_bass_F = [('F2', S), ('-', S), ('F2', S), ('F2', S), ('-', S), ('F3', S), ('F2', S), ('-', S)] * 4
sync_bass_Eb = [('D#2', S), ('-', S), ('D#2', S), ('D#2', S), ('-', S), ('D#3', S), ('D#2', S), ('-', S)] * 4
sync_bass_Db = [('C#2', S), ('-', S), ('C#2', S), ('C#2', S), ('-', S), ('C#3', S), ('C#2', S), ('-', S)] * 4

sec3_lead = sync_bass_F + sync_bass_Eb + sync_bass_Db + sync_bass_Eb

sec3_pad = sec2_pad[:]

# Full 4-on-the-floor club beat (Kick, Hat, Snare, Hat)
club_beat = [('C3', E), ('A3', E), ('C4', E), ('A3', E)]
sec3_perc = club_beat * 16


# --- 4. THE VOID (Breakdown) ---
# Bass drops out. Replaced by a high, echoing melody pluck.
pluck_F = [('F4', E), ('G4', E), ('G#4', E), ('C5', E)] * 4
pluck_Eb = [('D#4', E), ('F4', E), ('G4', E), ('A#4', E)] * 4
pluck_Db = [('C#4', E), ('D#4', E), ('F4', E), ('G#4', E)] * 4

sec4_lead = pluck_F + pluck_Eb + pluck_Db + pluck_Eb

sec4_pad = sec2_pad[:] # Chords continue to swell in the silence

sec4_perc = [('-', W)] * 8 # Complete percussion silence


# --- 5. THE RISER (Build 2) ---
# Pluck shifts an octave higher to build immense tension.
sec5_lead = ([('F5', E), ('G5', E), ('G#5', E), ('C6', E)] * 4 +
             [('D#5', E), ('F5', E), ('G5', E), ('A#5', E)] * 4 +
             [('C#5', E), ('D#5', E), ('F5', E), ('G#5', E)] * 4 +
             [('D#5', E), ('F5', E), ('G5', E), ('A#5', E)] * 4)

sec5_pad = sec2_pad[:]

# Classic EDM Snare Roll (Quarter -> Eighth -> Sixteenth)
sec5_perc = ([('C4', Q)] * 8 +                 # Bars 1-2
             [('C4', E)] * 16 +                # Bars 3-4
             [('C4', S)] * 32 +                # Bars 5-6
             [('C4', S)] * 16 +                # Bar 7
             [('C4', S)] * 8 + [('-', H)])     # Bar 8 (Stop for the drop)


# --- 6. THE ANTHEM (Climax) ---
# The PUNCH saw-wave plays a massive, soaring festival melody.
sec6_lead = [
    # Fm
    ('F5', DQ), ('D#5', E), ('F5', Q), ('G#5', Q),
    ('C6', H), ('A#5', Q), ('G#5', Q),
    # Eb
    ('G5', DQ), ('F5', E), ('G5', Q), ('A#5', Q),
    ('D#5', H), ('F5', Q), ('G5', Q),
    # Db
    ('F5', DQ), ('D#5', E), ('F5', Q), ('G#5', Q),
    ('C#5', H), ('D#5', Q), ('F5', Q),
    # Eb
    ('G5', DQ), ('F5', E), ('G5', Q), ('A#5', Q),
    ('C6', Q), ('A#5', Q), ('G#5', Q), ('G5', Q)
]

sec6_pad = sec2_pad[:]

sec6_perc = club_beat * 16 # Full beat returns


# --- 7. THE FADE (Outro) ---
# Drops immediately back to the intro pulse to cool down.
sec7_lead = sec1_lead[:]
sec7_pad = sec1_pad[:]
sec7_perc = sec1_perc[:]


# ==========================================
# TRACK ASSEMBLY & COMPILATION
# ==========================================

full_lead = sec1_lead + sec2_lead + sec3_lead + sec4_lead + sec5_lead + sec6_lead + sec7_lead
full_pad = sec1_pad + sec2_pad + sec3_pad + sec4_pad + sec5_pad + sec6_pad + sec7_pad
full_perc = sec1_perc + sec2_perc + sec3_perc + sec4_perc + sec5_perc + sec6_perc + sec7_perc

# --- Compilation ---
out = bytearray(b'JSEQ')
out.append(1)
out.extend(struct.pack('<H', 130)) # 130 BPM Trance Tempo
out.append(3)

# Channel 1: The Saw Lead / Bass
out.append(6) # Patch 6: PUNCH (Aggressive Saw)
out.extend(struct.pack('<H', len(full_lead)))
for n, d in full_lead:
    out.append(note_to_index(n))
    out.append(int(d))

# Channel 2: The Breathing Atmosphere
out.append(5) # Patch 5: PAD (Slow Triangle Swell)
out.extend(struct.pack('<H', len(full_pad)))
for n, d in full_pad:
    out.append(note_to_index(n))
    out.append(int(d))

# Channel 3: The Club Beat
out.append(10) # Patch 10: NOISE (Standard Percussion)
out.extend(struct.pack('<H', len(full_perc)))
for n, d in full_perc:
    out.append(note_to_index(n))
    out.append(int(d))

with open('neon_horizon_trance.jseq', 'wb') as f:
    f.write(out)

print("Successfully compiled the epic 1m 43s progressive trance track!")
