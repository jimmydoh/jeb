import struct

# Duration constants (1/32nd beat units)
S = 8     # Sixteenth note (0.25 beats)
E = 16    # Eighth note (0.5 beats)
Q = 32    # Quarter note (1.0 beats)
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
out.extend(struct.pack('<H', 110)) # 110 BPM for a brooding, cinematic pace
out.append(3)                      # 3 Channels

# --- 2. Channel 1: DRIVING_ARP (32 Beats) ---
# Patch 6 (PUNCH) uses a Saw Wave with a sharp envelope, perfect for
# a fat, aggressive synthwave bass arpeggio.
out.append(6)
ch1_seq = []

# A classic 16th-note darksynth arpeggio progression: Am -> F -> Dm -> E
arpeggios = [
    # Bars 1 & 2: A Minor (up and down the chord)
    ['A2', 'C3', 'E3', 'G3', 'A3', 'G3', 'E3', 'C3'],
    # Bars 3 & 4: F Major
    ['F2', 'A2', 'C3', 'E3', 'F3', 'E3', 'C3', 'A2'],
    # Bars 5 & 6: D Minor
    ['D2', 'F2', 'A2', 'C3', 'D3', 'C3', 'A2', 'F2'],
    # Bars 7 & 8: E Major (Tension!)
    ['E2', 'G#2', 'B2', 'D3', 'E3', 'D3', 'B2', 'G#2']
]

# Write out 2 bars (4 beats each) of each arpeggio pattern
for arp in arpeggios:
    for _ in range(4): # 4 loops of 8 sixteenth notes = 32 sixteenth notes (2 bars)
        for note in arp:
            ch1_seq.append((note, S))

out.extend(struct.pack('<H', len(ch1_seq)))
for n, d in ch1_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 3. Channel 2: SWELLING_PAD (32 Beats) ---
# Patch 5 (PAD) uses a Triangle wave with a very slow 0.5s attack/release.
# This will wash out into a massive, atmospheric drone behind the bass.
out.append(5)
ch2_seq = []

# Holding long whole notes (W) to trigger the slow envelope attack.
pad_progression = [
    ('E4', W), ('E4', W), # Bars 1 & 2
    ('F4', W), ('F4', W), # Bars 3 & 4
    ('A3', W), ('A3', W), # Bars 5 & 6
    ('B3', W), ('B3', W)  # Bars 7 & 8
]

for note, dur in pad_progression:
    ch2_seq.append((note, dur))

out.extend(struct.pack('<H', len(ch2_seq)))
for n, d in ch2_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 4. Channel 3: SYNTH_TICK (32 Beats) ---
# Patch 9 (CLICK) uses a Square wave with a 1ms attack and 50ms decay.
# It sounds like a synthetic rimshot or a ticking clock.
out.append(9)
ch3_seq = []

# A relentless, robotic 16th-note pulse to drive the tension.
# We drop the final 16th note of every bar to create a tiny "breath" in the rhythm.
for _ in range(8): # 8 Bars
    # 15 ticks
    for _ in range(15):
        ch3_seq.append(('C5', S))
    # 1 rest on the 16th tick (end of the bar)
    ch3_seq.append(('-', S))

out.extend(struct.pack('<H', len(ch3_seq)))
for n, d in ch3_seq:
    out.append(note_to_index(n))
    out.append(int(d))

# --- 5. Write to File ---
with open('darksynth.jseq', 'wb') as f:
    f.write(out)

print("Successfully compiled the atmospheric 32-beat darksynth.jseq!")
