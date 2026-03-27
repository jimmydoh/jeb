import struct
import re

class JSEQCompilerV22:
    N32, S, E, Q, H, DQ, W = 4, 8, 16, 32, 64, 48, 128

    def __init__(self, bpm=120):
        self.bpm = bpm
        self.audio_tracks = []
        self.auto_tracks = []
        self.master_events = []
        self.PARAM_LPF = 0x00
        self.PARAM_AMP = 0x01

    @staticmethod
    def note_to_index(note_str):
        if isinstance(note_str, int): return note_str
        if str(note_str) in ['-', '0']: return 0
        if note_str == 'TIE': return 255
        semitones = {'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5, 'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11}
        match = re.match(r"([A-G]#?)", note_str)
        if not match: return 0
        note = match.group(1)
        octave = int(note_str[-1])
        return ((octave + 1) * 12) + semitones[note] + 1

    def add_audio_track(self, patch, steps, adsr=None):
        if len(self.audio_tracks) < 3:
            self.audio_tracks.append({'patch': patch, 'steps': steps, 'adsr': adsr})

    def add_automation_track(self, target, steps):
        tid = 255 if target == 'GLOBAL' else int(target)
        self.auto_tracks.append({'target': tid, 'steps': steps})

    def add_bpm_change(self, new_bpm, wait_units=0):
        self.master_events.append((0x01, new_bpm))
        if wait_units > 0:
            self.master_events.append((0x00, wait_units))

    def _pack_step(self, val1, val2, track_type):
        if track_type == 0x00:
            p = self.note_to_index(val1)
            d = int(val2)
            packed = []
            while d > 255:
                packed.append(struct.pack('<BB', p, 255))
                d -= 255
            if d > 0: packed.append(struct.pack('<BB', p, d))
            return b"".join(packed)
        elif track_type == 0x01:
            return struct.pack('<BB', int(val1), int(val2))
        elif track_type == 0x02:
            cmd, val = int(val1), int(val2)
            if cmd == 0x00:
                packed = []
                while val > 255:
                    packed.append(struct.pack('<BB', cmd, 255))
                    val -= 255
                if val > 0: packed.append(struct.pack('<BB', cmd, val))
                return b"".join(packed)
            else:
                return struct.pack('<BB', cmd, val)

    def build(self, filename):
        while len(self.audio_tracks) < 3:
            self.audio_tracks.append({'patch': 0, 'steps': [], 'adsr': None})

        channels = []
        for ch in self.audio_tracks:
            channels.append({'id': ch['patch'], 'type': 0x00, 'adsr': ch['adsr'], 'steps': ch['steps']})
        for ch in self.auto_tracks:
            channels.append({'id': ch['target'], 'type': 0x01, 'adsr': None, 'steps': ch['steps']})
        if self.master_events:
            channels.append({'id': 255, 'type': 0x02, 'adsr': None, 'steps': self.master_events})

        out = bytearray(b'JSEQ')
        out.append(2)
        out.extend(struct.pack('<H', self.bpm))
        out.append(len(channels))

        for ch in channels:
            out.append(ch['id'])
            out.append(ch['type'])
            if ch['adsr'] and ch['type'] == 0x00:
                out.append(1)
                out.extend(struct.pack('<BBBB', *ch['adsr']))
            else:
                out.append(0)

            packed_data = b"".join([self._pack_step(v1, v2, ch['type']) for v1, v2 in ch['steps']])
            step_count = len(packed_data) // 2
            out.extend(struct.pack('<H', step_count))
            out.extend(packed_data)

        with open(filename, 'wb') as f:
            f.write(out)
        print(f"Generated {filename}")

# ==========================================
# COMPOSITION: LUNAR PROTOCOL V2 (2 MINUTE CUT)
# ==========================================

compiler = JSEQCompilerV22(bpm=80)

# The Triplet Grid (All under the 255 limit!)
TRP = 16   # 1 Triplet Note (16 units)
B = 48     # 1 Quarter Note Beat (3 triplets = 48 units)
BAR = 192  # 1 Full Measure (12 triplets = 192 units)

# Polyrhythm Math for the Melody
DOT_8 = 36 # Dotted 8th note
SXT = 12   # 16th note

# Helper function to rapidly generate triplet arpeggios
def arp(n1, n2, n3, beats=4):
    return [(n1, TRP), (n2, TRP), (n3, TRP)] * beats

# ---------------------------------------------------------------------------
# 1. Voice 0: The Piano Arpeggios (Patch 3 = BEEP / Sine Wave)
# ---------------------------------------------------------------------------
# "Muted Piano" ADSR: Instant attack, fast decay, quiet sustain, medium release
piano_adsr = (0, 25, 15, 15)
arp_steps = []

# Part A (Measures 1-8): The C#m Theme
arp_steps.extend(arp('G#3', 'C#4', 'E4', 4)) # M1: C#m
arp_steps.extend(arp('G#3', 'C#4', 'E4', 4)) # M2: C#m/B
arp_steps.extend(arp('A3', 'C#4', 'E4', 2) + arp('A3', 'D4', 'F#4', 2)) # M3: A -> D/F#
arp_steps.extend(arp('G#3', 'C4', 'D#4', 1) + arp('G#3', 'C#4', 'E4', 1) + arp('G#3', 'C4', 'D#4', 1) + arp('F#3', 'C4', 'D#4', 1)) # M4: G# climbs
arp_steps.extend(arp('G#3', 'C#4', 'E4', 4)) # M5: C#m
arp_steps.extend(arp('G#3', 'C#4', 'E4', 4)) # M6: C#m/B
arp_steps.extend(arp('A3', 'C#4', 'E4', 2) + arp('A3', 'D4', 'F#4', 2)) # M7: A -> D/F#
arp_steps.extend(arp('G#3', 'C4', 'D#4', 4)) # M8: G# Maj

# Part B (Measures 9-16): Modulation to E Major & Em
arp_steps.extend(arp('G#3', 'B3', 'E4', 4)) # M9: E Maj
arp_steps.extend(arp('G#3', 'B3', 'E4', 4)) # M10: E Maj / D#
arp_steps.extend(arp('A3', 'C#4', 'E4', 2) + arp('A3', 'C4', 'D#4', 2)) # M11: F#m -> B
arp_steps.extend(arp('G#3', 'B3', 'E4', 4)) # M12: E Maj
arp_steps.extend(arp('G3', 'B3', 'E4', 4))  # M13: E Minor (Darkness returns)
arp_steps.extend(arp('G3', 'B3', 'E4', 4))  # M14: Em / D
arp_steps.extend(arp('F#3', 'A3', 'C4', 4)) # M15: Diminished
arp_steps.extend(arp('G#3', 'B3', 'E4', 4)) # M16: E Maj

# Part C (Measures 17-24): The Climbing Climax
arp_steps.extend(arp('G#3', 'C#4', 'E4', 4)) # M17: C#m
arp_steps.extend(arp('A3', 'C#4', 'F#4', 4)) # M18: F#m/A
arp_steps.extend(arp('A#3', 'C#4', 'G4', 4)) # M19: Diminished climb
arp_steps.extend(arp('B3', 'D#4', 'F#4', 4)) # M20: B Maj
arp_steps.extend(arp('C4', 'D#4', 'A4', 4))  # M21: Diminished climb
arp_steps.extend(arp('C#4', 'E4', 'G#4', 4)) # M22: C#m
arp_steps.extend(arp('D#4', 'F#4', 'A4', 4)) # M23: Diminished
arp_steps.extend(arp('G#3', 'C4', 'D#4', 4)) # M24: G# Dominant (The Peak)

# Part A2 (Measures 25-32): Return to Main Theme
arp_steps.extend(arp('G#3', 'C#4', 'E4', 4)) # M25
arp_steps.extend(arp('G#3', 'C#4', 'E4', 4)) # M26
arp_steps.extend(arp('A3', 'C#4', 'E4', 2) + arp('A3', 'D4', 'F#4', 2)) # M27
arp_steps.extend(arp('G#3', 'C4', 'D#4', 1) + arp('G#3', 'C#4', 'E4', 1) + arp('G#3', 'C4', 'D#4', 1) + arp('F#3', 'C4', 'D#4', 1)) # M28
arp_steps.extend(arp('G#3', 'C#4', 'E4', 4)) # M29
arp_steps.extend(arp('G#3', 'C#4', 'E4', 4)) # M30
arp_steps.extend(arp('A3', 'C#4', 'E4', 2) + arp('A3', 'D4', 'F#4', 2)) # M31
arp_steps.extend(arp('G#3', 'C4', 'D#4', 4)) # M32

# Outro (Measures 33-40): Fading away
for i in range(7):
    arp_steps.extend(arp('G#3', 'C#4', 'E4', 4)) # M33-39
arp_steps.extend([('C#3', B), ('G#3', B), ('C#4', B*2)]) # M40: Final rolled chord

compiler.add_audio_track(patch=20, steps=arp_steps, adsr=piano_adsr)

# ---------------------------------------------------------------------------
# 2. Voice 1: The Left Hand Bass (Patch 1 = RETRO_BASS / Triangle)
# ---------------------------------------------------------------------------
# "Cello" ADSR: Slower attack to swell slightly, full sustain.
bass_adsr = (25, 50, 50, 50)
bass_steps = []

# Part A (1-8)
bass_steps.extend([('C#2', BAR), ('B1', BAR), ('A1', B*2), ('F#1', B*2), ('G#1', BAR)])
bass_steps.extend([('C#2', BAR), ('B1', BAR), ('A1', B*2), ('F#1', B*2), ('G#1', BAR)])

# Part B (9-16)
bass_steps.extend([('E2', BAR), ('D#2', BAR), ('C#2', B*2), ('F#1', B*2), ('B1', BAR)])
bass_steps.extend([('E2', BAR), ('D2', BAR), ('D#2', BAR), ('E2', BAR)])

# Part C (17-24)
bass_steps.extend([('C#2', BAR), ('C#2', BAR), ('C#2', BAR), ('B1', BAR)])
bass_steps.extend([('B1', BAR), ('C#2', BAR), ('D#2', BAR), ('G#1', BAR)])

# Part A2 (25-32)
bass_steps.extend([('C#2', BAR), ('B1', BAR), ('A1', B*2), ('F#1', B*2), ('G#1', BAR)])
bass_steps.extend([('C#2', BAR), ('B1', BAR), ('A1', B*2), ('F#1', B*2), ('G#1', BAR)])

# Outro (33-40)
for i in range(7):
    bass_steps.extend([('C#2', BAR)])
bass_steps.extend([('C#1', BAR)])

compiler.add_audio_track(patch=22, steps=bass_steps, adsr=bass_adsr)

# ---------------------------------------------------------------------------
# 3. Voice 2: The Lush Melody (Patch 18 = SONAR / Pad)
# ---------------------------------------------------------------------------
# "Sonorous Ring" ADSR: Fast but softened attack, DOUBLE release multiplier!
melody_adsr = (10, 100, 70, 100)
melody = []

# Part A (1-8)
melody.extend([('-', BAR)] * 4)
melody.extend([('-', B*3), ('G#4', DOT_8), ('G#4', SXT)]) # M5
melody.extend([('G#4', B*2), ('-', B), ('G#4', DOT_8), ('G#4', SXT)]) # M6
melody.extend([('A4', B*2), ('-', B), ('F#4', DOT_8), ('F#4', SXT)]) # M7
melody.extend([('G#4', B*2), ('-', B*2)]) # M8

# Part B (9-16)
melody.extend([('-', B*3), ('B4', DOT_8), ('B4', SXT)]) # M9
melody.extend([('B4', B*2), ('-', B), ('B4', DOT_8), ('B4', SXT)]) # M10
melody.extend([('C5', B*2), ('-', B), ('A4', DOT_8), ('A4', SXT)]) # M11
melody.extend([('B4', B*2), ('-', B*2)]) # M12
melody.extend([('-', B*3), ('E5', DOT_8), ('E5', SXT)]) # M13
melody.extend([('E5', B*2), ('-', B), ('D5', DOT_8), ('D5', SXT)]) # M14
melody.extend([('C5', B*2), ('-', B), ('A4', DOT_8), ('A4', SXT)]) # M15
melody.extend([('B4', B*2), ('-', B*2)]) # M16

# Part C (17-24): The Climbing Progression
melody.extend([('-', B*2), ('G#4', B*2)]) # M17
melody.extend([('TIE', B), ('A4', B), ('F#4', B*2)]) # M18 (TIE glides the G# over the bar line)
melody.extend([('TIE', B), ('A#4', B), ('G4', B*2)]) # M19
melody.extend([('TIE', B), ('B4', B), ('F#4', B*2)]) # M20
melody.extend([('TIE', B), ('C5', B), ('D#5', B*2)]) # M21
melody.extend([('TIE', B), ('C#5', B), ('E5', B*2)]) # M22
melody.extend([('TIE', B), ('F#5', B), ('A5', B*2)]) # M23
melody.extend([('G#5', BAR)]) # M24 (The Peak)

# Part A2 (25-32)
melody.extend([('TIE', B*2), ('-', B), ('G#4', DOT_8), ('G#4', SXT)]) # M25
melody.extend([('G#4', B*2), ('-', B), ('G#4', DOT_8), ('G#4', SXT)]) # M26
melody.extend([('A4', B*2), ('-', B), ('F#4', DOT_8), ('F#4', SXT)]) # M27
melody.extend([('G#4', B*2), ('-', B*2)]) # M28
melody.extend([('-', B*3), ('G#4', DOT_8), ('G#4', SXT)]) # M29
melody.extend([('G#4', B*2), ('-', B), ('G#4', DOT_8), ('G#4', SXT)]) # M30
melody.extend([('A4', B*2), ('-', B), ('F#4', DOT_8), ('F#4', SXT)]) # M31
melody.extend([('G#4', BAR)]) # M32

# Outro (33-40)
melody.extend([('TIE', BAR)] * 3) # M33-35 (Rings out over 3 measures)
melody.extend([('TIE', B*2), ('-', B*2)]) # M36
melody.extend([('-', BAR)] * 4) # M37-40

compiler.add_audio_track(patch=20, steps=melody, adsr=melody_adsr)

# ---------------------------------------------------------------------------
# 4. Master Event Track (Constant 80 BPM)
# ---------------------------------------------------------------------------
# 40 Measures * 4 Beats = 160 Beats Total
compiler.add_bpm_change(80, wait_units=160 * B)

# ---------------------------------------------------------------------------
# 5. Global Automation: The Sustain Pedal (Filter Sweep)
# ---------------------------------------------------------------------------
# 40 Measures * 192 units = 7680 steps. We divide this into 5 chunks of 1536 steps.
auto_steps = []

# Part A (1536 steps): Slowly waking up (70 -> 120)
auto_steps.extend([(compiler.PARAM_LPF, int(70 + (i/1536)*50)) for i in range(1536)])

# Part B (1536 steps): Rising tension (120 -> 180)
auto_steps.extend([(compiler.PARAM_LPF, int(120 + (i/1536)*60)) for i in range(1536)])

# Part C (1536 steps): The Climax! Opens fully (180 -> 255)
auto_steps.extend([(compiler.PARAM_LPF, int(180 + (i/1536)*75)) for i in range(1536)])

# Part A2 (1536 steps): The melody returns, filter backs off slightly (255 -> 140)
auto_steps.extend([(compiler.PARAM_LPF, int(255 - (i/1536)*115)) for i in range(1536)])

# Outro (1536 steps): Fading back into the darkness (140 -> 40)
auto_steps.extend([(compiler.PARAM_LPF, int(140 - (i/1536)*100)) for i in range(1536)])

compiler.add_automation_track(target='GLOBAL', steps=auto_steps)

# Export!
compiler.build("lunar_protocol.jseq")
