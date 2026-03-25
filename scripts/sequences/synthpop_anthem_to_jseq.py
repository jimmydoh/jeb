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
# POP SONG SECTIONS (8 Bars / 1024 units each)
# ==========================================

# --- 1. INTRO (The Hook) ---
# We use the main chorus hook to establish the melody.
intro_lead = [
    ('C6', Q), ('G5', Q), ('E5', E), ('G5', E), ('C6', Q),      # C Major
    ('D6', Q), ('B5', Q), ('G5', E), ('B5', E), ('D6', Q),      # G Major
    ('E6', DQ), ('C6', E), ('A5', H),                           # A Minor
    ('F6', E), ('E6', E), ('C6', E), ('A5', E), ('F5', H)       # F Major
] * 2

intro_bass = [('C3', E)] * 8 + [('G2', E)] * 8 + [('A2', E)] * 8 + [('F2', E)] * 8
intro_bass = intro_bass * 2

intro_perc = [('C3', Q), ('-', Q), ('C3', Q), ('-', Q)] * 8 # Four-on-the-floor kick build


# --- 2. VERSE (Rhythmic & Catchy) ---
# Am - F - C - G
verse_lead = [
    ('-', Q), ('A5', E), ('A5', E), ('C6', E), ('A5', E), ('-', Q), # Am
    ('-', Q), ('A5', E), ('A5', E), ('C6', Q), ('A5', Q),           # F
    ('-', Q), ('G5', E), ('G5', E), ('C6', E), ('G5', E), ('-', Q), # C
    ('B5', Q), ('G5', Q), ('D5', H)                                 # G
] * 2

verse_bass = [('A2', E)] * 8 + [('F2', E)] * 8 + [('C3', E)] * 8 + [('G2', E)] * 8
verse_bass = verse_bass * 2

# Standard Kick/Snare pop beat
basic_beat = [('C3', Q), ('A3', Q), ('C4', Q), ('A3', Q)]
verse_perc = basic_beat * 8


# --- 3. PRE-CHORUS (The Build-Up) ---
# F - G - Em - Am
pre_lead = [
    ('A5', DQ), ('G5', E), ('F5', H),                           # F
    ('B5', DQ), ('A5', E), ('G5', H),                           # G
    ('G#5', DQ), ('F#5', E), ('E5', H),                         # E Major (Tension!)
    ('A5', E), ('B5', E), ('C6', E), ('D6', E), ('E6', H)       # Am
] * 2

# Staccato bass to build tension
pre_bass = ([('F2', Q), ('-', Q)] * 2 + [('G2', Q), ('-', Q)] * 2 +
            [('E2', Q), ('-', Q)] * 2 + [('A2', Q), ('-', Q)] * 2) * 2

# Percussion introduces drum rolls for the buildup
pre_perc = (basic_beat * 3 + [('C4', E)] * 8 +   # 8th note snare build on bar 4
            basic_beat * 3 + [('C4', S)] * 16)   # 16th note snare roll on bar 8


# --- 4. CHORUS (The Explosive Drop) ---
# C - G - Am - F
chorus_lead = intro_lead[:] # Reuse the huge intro hook

chorus_bass = intro_bass[:] # Heavy driving 8th notes

# High-energy dance beat (Kick/Hat/Snare/Hat every beat)
dance_beat = [('C3', E), ('A3', E), ('C4', E), ('A3', E)] * 2
chorus_perc = dance_beat * 8


# --- 5. BRIDGE (Half-Time Emotion) ---
# Dm - Am - F - G
bridge_lead = [
    ('F5', W),                                                  # Dm
    ('E5', W),                                                  # Am
    ('A5', W),                                                  # F
    ('B5', H), ('G5', E), ('A5', E), ('B5', Q)                  # G
] * 2

# Whole notes on the bass to let the track breathe
bridge_bass = [('D2', W), ('A2', W), ('F2', W), ('G2', W)] * 2

# Slower, grooving percussion
bridge_perc = [('C3', H), ('C4', H)] * 8


# --- 6. FINAL HIT (1 Bar / 128 units) ---
# A solid major chord to end the song cleanly
end_lead = [('C6', W)]
end_bass = [('C3', W)]
end_perc = [('C3', Q), ('C4', Q), ('-', H)]


# ==========================================
# TRACK ASSEMBLY (Stitching it all together)
# ==========================================

# Intro -> V1 -> Pre -> Chorus -> V2 -> Pre -> Chorus -> Bridge -> Chorus -> End
full_lead = (intro_lead + verse_lead + pre_lead + chorus_lead +
             verse_lead + pre_lead + chorus_lead +
             bridge_lead + chorus_lead + end_lead)

full_bass = (intro_bass + verse_bass + pre_bass + chorus_bass +
             verse_bass + pre_bass + chorus_bass +
             bridge_bass + chorus_bass + end_bass)

full_perc = (intro_perc + verse_perc + pre_perc + chorus_perc +
             verse_perc + pre_perc + chorus_perc +
             bridge_perc + chorus_perc + end_perc)


# --- Compilation ---
out = bytearray(b'JSEQ')
out.append(1)
out.extend(struct.pack('<H', 140)) # 140 BPM Upbeat Pop Tempo
out.append(3)

# Channel 1: Lead
out.append(0) # Patch 0: RETRO_LEAD
out.extend(struct.pack('<H', len(full_lead)))
for n, d in full_lead:
    out.append(note_to_index(n))
    out.append(int(d))

# Channel 2: Bass
out.append(1) # Patch 1: RETRO_BASS
out.extend(struct.pack('<H', len(full_bass)))
for n, d in full_bass:
    out.append(note_to_index(n))
    out.append(int(d))

# Channel 3: Percussion
out.append(2) # Patch 2: RETRO_NOISE
out.extend(struct.pack('<H', len(full_perc)))
for n, d in full_perc:
    out.append(note_to_index(n))
    out.append(int(d))

with open('16bit_summer_anthem.jseq', 'wb') as f:
    f.write(out)

print("Successfully compiled the 2-minute synthpop anthem!")
