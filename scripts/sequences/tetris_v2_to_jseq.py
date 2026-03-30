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
# COMPOSITION: TETRIS PROTOCOL (TYPE A)
# ==========================================

compiler = JSEQCompilerV22(bpm=145)

S, E, Q, H, DQ, W = compiler.S, compiler.E, compiler.Q, compiler.H, compiler.DQ, compiler.W

def shift_octave(sequence, oct_shift):
    out = []
    for note, dur in sequence:
        if note == '-': out.append((note, dur))
        else:
            name, octave = note[:-1], int(note[-1])
            out.append((f"{name}{octave + oct_shift}", dur))
    return out

# ---------------------------------------------------------------------------
# 1. Voice 0: The Classic Lead (Patch 0 = RETRO_LEAD)
# ---------------------------------------------------------------------------
lead_adsr = (0, 100, 100, 50) # Instant punch, quick release

theme_a = [
    ('E5', Q), ('B4', E), ('C5', E), ('D5', Q), ('C5', E), ('B4', E),
    ('A4', Q), ('A4', E), ('C5', E), ('E5', Q), ('D5', E), ('C5', E),
    ('B4', DQ), ('C5', E), ('D5', Q), ('E5', Q),
    ('C5', Q), ('A4', Q), ('A4', Q), ('-', Q)
] # 16 beats

theme_b = [
    ('D5', DQ), ('F5', E), ('A5', Q), ('G5', E), ('F5', E),
    ('E5', DQ), ('C5', E), ('E5', Q), ('D5', E), ('C5', E),
    ('B4', DQ), ('C5', E), ('D5', Q), ('E5', Q),
    ('C5', Q), ('A4', Q), ('A4', Q), ('-', Q)
] # 16 beats

lead_steps = []
lead_steps.extend([('-', W)] * 4)                      # Intro (16 beats)
lead_steps.extend(theme_a)                             # Phase A1
lead_steps.extend(shift_octave(theme_a, 1))            # Phase A2 (Octave Up!)
lead_steps.extend(theme_b)                             # Phase B1
lead_steps.extend(shift_octave(theme_b, 1))            # Phase B2 (Octave Up!)
lead_steps.extend(theme_a)                             # Breakdown (Quiet A1)
lead_steps.extend(shift_octave(theme_b, 1))            # Build-Up (B2)
lead_steps.extend(shift_octave(theme_a, 1) + shift_octave(theme_b, 1)) # The Drop (32 beats)
lead_steps.extend([('A5', W), ('-', W)])               # Outro (8 beats)

compiler.add_audio_track(patch=0, steps=lead_steps, adsr=lead_adsr)

# ---------------------------------------------------------------------------
# 2. Voice 1: The Driving Bass (Patch 1 = RETRO_BASS)
# ---------------------------------------------------------------------------
bass_a = [('E2', E), ('E3', E)] * 4 + [('A1', E), ('A2', E)] * 4 + \
         [('E2', E), ('E3', E)] * 4 + [('A1', E), ('A2', E)] * 2 + [('A1', Q), ('-', Q)]

bass_b = [('D2', E), ('D3', E)] * 4 + [('C2', E), ('C3', E)] * 4 + \
         [('E2', E), ('E3', E)] * 4 + [('A1', E), ('A2', E)] * 2 + [('A1', Q), ('-', Q)]

bass_steps = []
bass_steps.extend(bass_a)                              # Intro
bass_steps.extend(bass_a * 2)                          # Phase A1 & A2
bass_steps.extend(bass_b * 2)                          # Phase B1 & B2
bass_steps.extend([('E2', W), ('A1', W), ('E2', W), ('A1', W)]) # Breakdown (Long holds)
bass_steps.extend(bass_b)                              # Build-Up
bass_steps.extend(bass_a + bass_b)                     # The Drop
bass_steps.extend([('A1', W), ('-', W)])               # Outro

compiler.add_audio_track(patch=1, steps=bass_steps)

# ---------------------------------------------------------------------------
# 3. Voice 2: The Percussion (Patch 2 = RETRO_NOISE)
# ---------------------------------------------------------------------------
# C3 = Low noise (Kick), C5 = Mid noise (Snare), C6 = High noise (Hat)
drum_base = [('C3', E), ('C6', E), ('C5', E), ('C6', E)] * 2 # 4 beats
drum_drop = [('C3', E), ('C6', S), ('C6', S), ('C5', E), ('C6', S), ('C6', S)] * 2 # 4 beats

drum_steps = []
drum_steps.extend(drum_base * 4)                       # Intro
drum_steps.extend(drum_base * 4)                       # Phase A1
drum_steps.extend(drum_drop * 4)                       # Phase A2 (Busy hats)
drum_steps.extend(drum_base * 4)                       # Phase B1
drum_steps.extend(drum_drop * 4)                       # Phase B2 (Busy hats)
drum_steps.extend([('-', W)] * 4)                      # Breakdown (Drums cut out)

# The Build-Up: Kick on quarters -> Kick on 8ths -> 16th Snare Roll
drum_steps.extend([('C3', Q), ('-', Q)] * 4)           # 8 beats
drum_steps.extend([('C3', E)] * 8)                     # 4 beats
drum_steps.extend([('C5', S)] * 16)                    # 4 beats

drum_steps.extend(drum_drop * 8)                       # The Drop
drum_steps.extend([('C3', Q), ('-', Q), ('-', H), ('-', W)]) # Outro (One final kick)

compiler.add_audio_track(patch=2, steps=drum_steps)

# ---------------------------------------------------------------------------
# 4. Master Event Track (The Accelerando!)
# ---------------------------------------------------------------------------
# Starts fast, drops down, and gradually speeds up to maximum chaos
compiler.add_bpm_change(145, wait_units=80 * Q)  # Intro -> B2 (80 beats)
compiler.add_bpm_change(100, wait_units=16 * Q)  # Breakdown drops to 100 BPM
compiler.add_bpm_change(120, wait_units=8 * Q)   # Build-Up starts accelerating
compiler.add_bpm_change(150, wait_units=8 * Q)   # Build-Up peak
compiler.add_bpm_change(175, wait_units=40 * Q)  # The Drop & Outro (Max Speed!)

# ---------------------------------------------------------------------------
# 5. Global Automation: The EDM Filter Sweep
# ---------------------------------------------------------------------------
auto_steps = []

# Intro (16 beats / 512 steps): Sweep up from muffled to full
auto_steps.extend([(compiler.PARAM_LPF, int(50 + (i/512)*205)) for i in range(512)])

# Main Phases A1 to B2 (64 beats / 2048 steps): Fully Open
auto_steps.extend([(compiler.PARAM_LPF, 255)] * 2048)

# Breakdown (16 beats / 512 steps): Slam closed to 80, stay muffled
auto_steps.extend([(compiler.PARAM_LPF, int(255 - (i/512)*175)) for i in range(256)])
auto_steps.extend([(compiler.PARAM_LPF, 80)] * 256)

# Build-Up (16 beats / 512 steps): Sweep back up to max
auto_steps.extend([(compiler.PARAM_LPF, int(80 + (i/512)*175)) for i in range(512)])

# The Drop & Outro (40 beats / 1280 steps): Fully Open
auto_steps.extend([(compiler.PARAM_LPF, 255)] * 1280)

compiler.add_automation_track(target='GLOBAL', steps=auto_steps)

# Export!
compiler.build("tetris_protocol.jseq")
