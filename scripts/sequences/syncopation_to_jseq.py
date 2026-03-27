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
# COMPOSITION: SYNCOPATION PROTOCOL V2
# ==========================================

compiler = JSEQCompilerV22(bpm=120)

# Timing Shortcuts
S = compiler.S    # 1/16 note (8 duration units)
E = compiler.E    # 1/8 note (16 duration units)
Q = compiler.Q    # 1/4 note (32 duration units)
H = compiler.H    # 1/2 note (64 duration units)
W = compiler.W    # Whole note / 4 beats (128 duration units)

# ---------------------------------------------------------------------------
# 1. Voice 0: The Funky Lead (Patch 0 = RETRO_LEAD)
# ---------------------------------------------------------------------------
# ADSR Override: (Attack 0x, Decay 1x, Sustain 1x, Release 0.5x)
# Zeroing the attack removes the 10ms ramp, making the transient instant.
lead_adsr = (0, 100, 50, 50)

# Motif A (4 beats): Drives the downbeat, then dances around the snare
lead_a = [
    ('C5', S), ('D#5', S), ('-', E),            # Beat 1: Quick double hit on the downbeat! (1, e)
    ('-', S), ('F5', S), ('-', S), ('D#5', S),  # Beat 2: Dances around the snare (e, a)
    ('C5', E), ('-', E),                        # Beat 3: Solid anchor on the 3
    ('-', E), ('A#4', S), ('C5', S)             # Beat 4: 16th notes that "push" into the next bar (&, a)
]

# Motif B (4 beats): Higher variation
lead_b = [
    ('C5', S), ('D#5', S), ('-', E),            # Beat 1: Anchored downbeat
    ('-', S), ('G5', S), ('-', S), ('F5', S),   # Beat 2: Reaches higher
    ('D#5', E), ('-', E),                       # Beat 3: Solid anchor
    ('-', E), ('C5', S), ('-', S)               # Beat 4: Ends short to leave space for the bass
]

lead_steps = []
lead_steps.extend([('-', W)] * 8)                      # Phase 1: Intro (32 beats silence)
lead_steps.extend(lead_a * 8)                          # Phase 2: A Section (32 beats)
lead_steps.extend(lead_b * 8)                          # Phase 3: B Section (32 beats)
lead_steps.extend((lead_a + lead_b) * 4)               # Phase 4: Breakdown (32 beats mixed)
lead_steps.extend((lead_a + lead_b) * 4)               # Phase 5: The Drop (32 beats mixed)
lead_steps.extend([('-', W)] * 8)                      # Phase 6: Outro (32 beats silence)

compiler.add_audio_track(patch=0, steps=lead_steps, adsr=lead_adsr)

# ---------------------------------------------------------------------------
# 2. Voice 1: The Slap Bass (Patch 1 = RETRO_BASS) (UNCHANGED)
# ---------------------------------------------------------------------------
bass_a = [
    ('C2', S), ('-', E), ('C2', S),
    ('-', S), ('D#2', S), ('-', S), ('C2', S),
    ('-', E), ('F2', S), ('-', S),
    ('F#2', S), ('G2', S), ('-', S), ('A#1', S)
]

bass_b = [
    ('C2', S), ('-', E), ('C2', S),
    ('-', S), ('D#2', S), ('-', S), ('C2', S),
    ('-', E), ('G2', S), ('-', S),
    ('F2', S), ('D#2', S), ('-', S), ('C2', S)
]

bass_steps = []
bass_steps.extend(bass_a * 8)
bass_steps.extend(bass_a * 8)
bass_steps.extend(bass_b * 8)
bass_steps.extend([('-', W * 8)])
bass_steps.extend((bass_a + bass_b) * 4)
bass_steps.extend(bass_a * 4 + [('C2', S), ('-', W*4 - S)])

compiler.add_audio_track(patch=1, steps=bass_steps)

# ---------------------------------------------------------------------------
# 3. Voice 2: The Glitch Drums (Patch 2 = RETRO_NOISE) (UNCHANGED)
# ---------------------------------------------------------------------------
drum_groove = [
    ('C3', S), ('C6', S), ('C6', S), ('C3', S),
    ('C5', S), ('C6', S), ('-', S), ('C6', S),
    ('C6', S), ('C3', S), ('C6', S), ('C6', S),
    ('C5', S), ('-', S), ('C6', S), ('C6', S)
]

drum_light = [
    ('-', S), ('C6', S), ('-', S), ('C6', S),
    ('-', S), ('C6', S), ('-', S), ('C6', S),
    ('-', S), ('C6', S), ('-', S), ('C6', S),
    ('-', S), ('C6', S), ('-', S), ('C6', S)
]

drum_steps = []
drum_steps.extend(drum_groove * 8)
drum_steps.extend(drum_groove * 8)
drum_steps.extend(drum_groove * 8)
drum_steps.extend(drum_light * 8)
drum_steps.extend(drum_groove * 8)
drum_steps.extend(drum_groove * 4 + [('C3', S), ('-', W*4 - S)])

compiler.add_audio_track(patch=2, steps=drum_steps)

# ---------------------------------------------------------------------------
# 5. Global Automation: The Breakdown Filter Sweep (UNCHANGED)
# ---------------------------------------------------------------------------
auto_steps = []

# Phases 1-3 (96 beats): Filter fully open (255)
auto_steps.extend([(compiler.PARAM_LPF, 255)] * (96 * 32))

# Phase 4: Breakdown Sweep (32 beats / 1024 steps)
for i in range(1024):
    if i < 768:
        val = int(255 - (i / 768) * 205)
    else:
        val = int(50 + ((i - 768) / 256) * 205)
    auto_steps.append((compiler.PARAM_LPF, val))

# Phases 5-6 (64 beats): Filter fully open
auto_steps.extend([(compiler.PARAM_LPF, 255)] * (64 * 32))

compiler.add_automation_track(target='GLOBAL', steps=auto_steps)

# Export!
compiler.build("syncopation_protocol_v2.jseq")
