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
# COMPOSITION: ARES PROTOCOL (MARS 5/4 MARCH)
# ==========================================

# A heavy, oppressive marching tempo
compiler = JSEQCompilerV22(bpm=110)

S = compiler.S    # 1/16 note (8 duration units)
E = compiler.E    # 1/8 note (16 duration units)
Q = compiler.Q    # 1/4 note (32 duration units)

# THE 5/4 MEASURE RULE:
# 1 Measure = 5 Beats = 5 Quarter Notes = 160 duration units.
M = Q * 5

# ---------------------------------------------------------------------------
# 1. Voice 1 & 2: The Col Legno Strings & Timpani (The Ostinato)
# ---------------------------------------------------------------------------
# The iconic rhythm: "da-da dun, dun, dun, da-da dun, dun"
# 8th, 8th, Quarter, Quarter, 8th, 8th, Quarter
mars_rhythm = [
    ('G1', E), ('G1', E), ('G1', Q), ('G1', Q),
    ('G1', E), ('G1', E), ('G1', Q)
]

mars_snare = [
    ('C4', E), ('C4', E), ('C4', Q), ('C4', Q),
    ('C4', E), ('C4', E), ('C4', Q)
]

# We will run this ostinato relentlessly for 32 measures
bass_steps = mars_rhythm * 32
snare_steps = mars_snare * 32

# We apply the (0, 100, 100, 50) ADSR to the Bass to make it staccato and punchy
compiler.add_audio_track(patch=1, steps=bass_steps, adsr=(0, 100, 100, 50))
compiler.add_audio_track(patch=2, steps=snare_steps)

# ---------------------------------------------------------------------------
# 2. Voice 0: The Menacing Brass (Patch 5 = PAD)
# ---------------------------------------------------------------------------
# The PAD patch has a native 0.5s attack, perfect for slow orchestral swells.
# We use TIE so the 2-measure sustains don't re-trigger that 0.5s attack.

brass_steps = []
brass_steps.extend([('-', M)] * 8) # Phase 1: Intro (8 measures of silence)

# Phase 2: The First Theme (8 Measures)
brass_steps.extend([
    ('G4', M), ('TIE', M),         # Hold G for 2 measures
    ('D5', M), ('TIE', M),         # Swell to D for 2 measures
    ('C#5', M),                    # Drop to Db (Dissonance!)
    ('C5', M),                     # Drop to C
    ('B4', M), ('TIE', M)          # Settle menacingly on B
])

# Phase 3: The Second Theme - Rising Tension (8 Measures)
brass_steps.extend([
    ('G4', M), ('TIE', M),
    ('D5', M), ('TIE', M),
    ('F5', M),                     # Reaches higher to F
    ('E5', M),
    ('D#5', M), ('TIE', M)         # Clashes on D#
])

# Phase 4: The Climax (8 Measures)
brass_steps.extend([
    ('G5', M), ('TIE', M),         # An octave higher
    ('A#5', M), ('TIE', M),
    ('C#6', M), ('TIE', M),        # Piercing dissonance
    ('D6', M), ('TIE', M)          # Massive final note
])

compiler.add_audio_track(patch=5, steps=brass_steps)

# ---------------------------------------------------------------------------
# 3. Master Event Track (110 BPM Constant)
# ---------------------------------------------------------------------------
# 32 measures * 5 beats = 160 beats
compiler.add_bpm_change(110, wait_units=160 * Q)

# ---------------------------------------------------------------------------
# 4. Global Automation: The Advancing Army (Filter Sweep)
# ---------------------------------------------------------------------------
auto_steps = []

# Sweep from muffled (40) to fully open (255) over the first 16 measures
# 16 measures * 5 beats = 80 beats. 80 beats * 32 steps = 2560 steps.
for i in range(2560):
    val = int(40 + (i / 2560) * 215)
    auto_steps.append((compiler.PARAM_LPF, val))

# Keep fully open for the final 16 measures
auto_steps.extend([(compiler.PARAM_LPF, 255)] * 2560)

compiler.add_automation_track(target='GLOBAL', steps=auto_steps)

# ---------------------------------------------------------------------------
# 5. Channel 0 Automation: The Climax Tremolo
# ---------------------------------------------------------------------------
# Specifically targets Voice 0 (The Brass) to add chaos to the final climax
trem_steps = []

# Measures 1-24: Full volume (No effect)
# 24 measures * 5 beats = 120 beats. 120 * 32 = 3840 steps.
trem_steps.extend([(compiler.PARAM_AMP, 255)] * 3840)

# Phase 4 (Measures 25-32): Harsh 16th-note stutter
# A 16th note is 8 duration units (8 steps). We alternate on/off.
stutter_pattern = [(compiler.PARAM_AMP, 255)] * 4 + [(compiler.PARAM_AMP, 0)] * 4
trem_steps.extend(stutter_pattern * (40 * 32 // 8)) # 40 beats of stuttering

compiler.add_automation_track(target=0, steps=trem_steps)

# Export!
compiler.build("ares_protocol.jseq")
