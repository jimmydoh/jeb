import struct

# Duration constants (1/32nd beat units)
S = 8     # Sixteenth note (0.25 beats)
E = 16    # Eighth note (0.5 beats)
Q = 32    # Quarter note (1.0 beats)
DQ = 48   # Dotted quarter (1.5 beats)
H = 64    # Half note (2.0 beats)
W = 128   # Whole note (4.0 beats)

def note_to_index(note_str):
    """Converts 'C4', 'A3', etc. into the 1-255 JSEQ pitch index."""
    if note_str == '-':
        return 0
    semitones = {'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5, 'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11}
    note, octave = note_str[:-1], int(note_str[-1])
    return ((octave + 1) * 12) + semitones[note] + 1

# ==========================================
# MUSICAL SECTIONS (Each exactly 1024 units)
# ==========================================

# --- Section 1: The Gathering Storm (8 Bars) ---
sec1_lead = [('-', W)] * 4 + [('D5', W), ('D5', W), ('D#5', W), ('D5', W)]

sec1_bass = []
# Fast 16th note Phrygian Dominant ostinato
for _ in range(6): # 6 bars of D minor
    sec1_bass.extend([('D2', S), ('A2', S), ('D3', S), ('A2', S)] * 4)
for _ in range(1): # 1 bar of Eb Major
    sec1_bass.extend([('D#2', S), ('A#2', S), ('D#3', S), ('A#2', S)] * 4)
for _ in range(1): # 1 bar of D minor
    sec1_bass.extend([('D2', S), ('A2', S), ('D3', S), ('A2', S)] * 4)

sec1_perc = [('C3', Q), ('-', Q), ('C3', Q), ('-', Q)] * 8 # Ominous tribal tom


# --- Section 2: The Duel Begins (8 Bars) ---
sec2_lead = [
    # Epic brass melody (Bars 1-4)
    ('D5', H), ('A5', H),
    ('G5', DQ), ('F5', E), ('E5', H),
    ('F5', Q), ('D5', Q), ('A4', H),
    ('D#5', W),
    # Epic brass melody continuation (Bars 5-8)
    ('D5', H), ('A5', H),
    ('G5', DQ), ('F5', E), ('E5', H),
    ('F5', Q), ('E5', Q), ('F5', Q), ('G5', Q),
    ('A5', W)
]

sec2_bass = sec1_bass[:] # Continue the relentless 16th note ostinato

sec2_perc = [('C3', Q), ('C4', Q), ('C3', Q), ('C4', Q)] * 8 # Add snare on beats 2 and 4


# --- Section 3: Choir of the Ancients (8 Bars) ---
sec3_lead = []
# Frantic 16th-note 'choir' chanting arpeggios
for _ in range(2): # Loop this 4-bar phrase twice
    sec3_lead.extend([('D6', S), ('C6', S), ('A5', S), ('C6', S)] * 4) # Dm
    sec3_lead.extend([('F6', S), ('E6', S), ('C6', S), ('E6', S)] * 4) # F
    sec3_lead.extend([('D6', S), ('C6', S), ('A5', S), ('C6', S)] * 4) # Dm
    sec3_lead.extend([('D#6', S), ('A#5', S), ('G5', S), ('A#5', S)] * 4) # Eb

sec3_bass = [('D3', W), ('D3', W), ('F3', W), ('D#3', W)] * 2 # Heavy whole notes anchoring the chaos

sec3_perc = [('C3', S), ('A3', S), ('A3', S), ('A3', S)] * 32 # Frantic 16th note hi-hats with driving kick


# --- Section 4: The Climax (8 Bars) ---
sec4_lead = [
    # High soaring climax
    ('D6', W),
    ('A6', W),
    ('G6', DQ), ('F6', E), ('E6', H),
    ('F6', Q), ('E6', Q), ('D6', Q), ('C#6', Q), # Tension turnaround
    ('D6', W), ('-', W), ('D6', W), ('-', W)     # Dramatic hits and silence
]

sec4_bass = [('D2', E), ('D3', E)] * 32 # Driving 8th-note octaves

sec4_perc = [('C3', E), ('A3', E), ('C4', E), ('A3', E)] * 16 # High-energy crash/rock beat


# ==========================================
# TRACK ASSEMBLY & COMPILATION
# ==========================================

# We assemble the massive arrays by simply adding the Python lists together,
# and then we multiply by 2 to loop the entire 32-bar structure twice!
ch1_full = (sec1_lead + sec2_lead + sec3_lead + sec4_lead) * 2
ch2_full = (sec1_bass + sec2_bass + sec3_bass + sec4_bass) * 2
ch3_full = (sec1_perc + sec2_perc + sec3_perc + sec4_perc) * 2


# --- 1. Global Header ---
out = bytearray(b'JSEQ')
out.append(1)
out.extend(struct.pack('<H', 150)) # 150 BPM for intense action
out.append(3)                      # 3 Channels

# --- 2. Channel 1: EPIC_LEAD ---
out.append(6) # Patch 6: PUNCH (Harsh Saw wave for epic brass/choir feel)
out.extend(struct.pack('<H', len(ch1_full)))
for n, d in ch1_full:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 3. Channel 2: EPIC_BASS ---
out.append(1) # Patch 1: RETRO_BASS (Triangle wave to support the heavy low end)
out.extend(struct.pack('<H', len(ch2_full)))
for n, d in ch2_full:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 4. Channel 3: EPIC_PERC ---
out.append(2) # Patch 2: RETRO_NOISE
out.extend(struct.pack('<H', len(ch3_full)))
for n, d in ch3_full:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 5. Write to File ---
with open('epic_duel.jseq', 'wb') as f:
    f.write(out)

print("Successfully compiled the massive 64-bar epic_duel.jseq!")
