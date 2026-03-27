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
# COMPOSITION: OVERCLOCKED BEE (1 MINUTE CUT + TREMOLO)
# ==========================================

compiler = JSEQCompilerV22(bpm=150)

# Timing Shortcuts
S = compiler.S    # 1/16 note (8 duration units)
E = compiler.E    # 1/8 note (16 duration units)
Q = compiler.Q    # 1/4 note (32 duration units)

# ---------------------------------------------------------------------------
# 1. Voice 0: The Lead (Patch 0 = RETRO_LEAD)
# ---------------------------------------------------------------------------
lead_adsr = (100, 50, 50, 50)
loop_a = [('E5', S)] * 6 + [('F5', S), ('D#5', S)] + [('E5', S)] * 6 + [('C5', S), ('B4', S)]
loop_b = [
    ('A4', S), ('A#4', S), ('B4', S), ('C5', S),
    ('C#5', S), ('D5', S), ('D#5', S), ('E5', S),
    ('F5', S), ('F#5', S), ('G5', S), ('G#5', S),
    ('A5', S), ('A#5', S), ('B5', S), ('C6', S)
]

lead_steps = []
lead_steps.extend((loop_a * 3 + loop_b * 1) * 4) # Phase 1 (64 beats)
lead_steps.extend((loop_a * 2 + loop_b * 2) * 4) # Phase 2 (64 beats)
lead_steps.extend((loop_b * 3 + loop_a * 1) * 4) # Phase 3 (64 beats)

compiler.add_audio_track(patch=0, steps=lead_steps, adsr=lead_adsr)

# ---------------------------------------------------------------------------
# 2. Voice 1: The Driving Bass (Patch 1 = RETRO_BASS)
# ---------------------------------------------------------------------------
bass_a = [('A2', E), ('E2', E)] * 4
bass_steps = []
bass_steps.extend(bass_a * 48) # 192 total beats (48 loops of 4 beats)

compiler.add_audio_track(patch=1, steps=bass_steps)

# ---------------------------------------------------------------------------
# 3. Voice 2: The Rhythm Section (Patch 2 = RETRO_NOISE)
# ---------------------------------------------------------------------------
drum_standard = [('C4', E), ('-', E)] * 4
drum_blast = [('C4', S), ('-', S)] * 8

drum_steps = []
drum_steps.extend(drum_standard * 32) # Phases 1 & 2 (128 beats)
drum_steps.extend(drum_blast * 16)    # Phase 3 (64 beats)

compiler.add_audio_track(patch=2, steps=drum_steps)

# ---------------------------------------------------------------------------
# 4. Master Event Track (The Tempo Escalation)
# ---------------------------------------------------------------------------
compiler.add_bpm_change(150, wait_units=64 * Q)
compiler.add_bpm_change(200, wait_units=64 * Q)
compiler.add_bpm_change(240, wait_units=64 * Q)

# ---------------------------------------------------------------------------
# 5. Global Automation: Intro Filter Sweep
# ---------------------------------------------------------------------------
auto_steps = []
for i in range(1024): # 32 beats worth of 1/32nd steps
    val = int((i / 1024) * 255)
    auto_steps.append((compiler.PARAM_LPF, val))

compiler.add_automation_track(target='GLOBAL', steps=auto_steps)

# ---------------------------------------------------------------------------
# 6. Channel 1 Automation: The Escalating Bass Tremolo
# ---------------------------------------------------------------------------
# Target Scope: 1 (Applies specifically to Voice 1: The Bass)
# We are building cyclic waveforms out of 1/32nd beat automation steps.

# Phase 1: 8th Note Wobble (16 steps per cycle)
trem_phase1 = []
for i in range(16):
    val = int(255 - abs(i - 8) * (205 / 8)) # Triangle wave from 50 to 255
    trem_phase1.append((compiler.PARAM_AMP, val))

# Phase 2: 16th Note Flutter (8 steps per cycle)
trem_phase2 = []
for i in range(8):
    val = int(255 - abs(i - 4) * (205 / 4)) # Triangle wave from 50 to 255
    trem_phase2.append((compiler.PARAM_AMP, val))

# Phase 3: 32nd Note Machine-Gun Stutter (4 steps per cycle)
# Hard, choppy square-ish wave for maximum chaos
trem_phase3 = [
    (compiler.PARAM_AMP, 255),
    (compiler.PARAM_AMP, 180),
    (compiler.PARAM_AMP, 50),
    (compiler.PARAM_AMP, 180)
]

bass_tremolo_steps = []
# 64 beats per phase. 32 steps per beat = 2048 steps per phase.
bass_tremolo_steps.extend(trem_phase1 * (2048 // 16)) # 128 cycles
bass_tremolo_steps.extend(trem_phase2 * (2048 // 8))  # 256 cycles
bass_tremolo_steps.extend(trem_phase3 * (2048 // 4))  # 512 cycles

compiler.add_automation_track(target=1, steps=bass_tremolo_steps)

# Export!
compiler.build("overclocked_bee_1min.jseq")
