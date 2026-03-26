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
# COMPOSITION: WOBBLE PROTOCOL (DUBSTEP)
# ==========================================

# The golden rule of Dubstep: 140 BPM.
compiler = JSEQCompilerV22(bpm=140)

S = compiler.S    # 1/16 note (8 units)
E = compiler.E    # 1/8 note (16 units)
Q = compiler.Q    # 1/4 note (32 units)
H = compiler.H    # 1/2 note (64 units)
W = compiler.W    # Whole note / 4 beats (128 units)

# ---------------------------------------------------------------------------
# 1. Voice 0: The Eerie Lead (Patch 0 = RETRO_LEAD)
# ---------------------------------------------------------------------------
lead_steps = []

# Phase 1 Build-up (64 beats): Ascending minor arpeggio accelerating
arp_slow = [('C5', E), ('D#5', E), ('G5', E), ('A#5', E)]
arp_fast = [('C5', S), ('D#5', S), ('G5', S), ('A#5', S)]

lead_steps.extend(arp_slow * 16) # 32 beats
lead_steps.extend(arp_fast * 32) # 32 beats

# Phase 2 The Drop (64 beats): High-pitched syncopated siren stab
drop_siren = [('C6', E), ('-', W - E)] # Hits on the downbeat, rings out
lead_steps.extend(drop_siren * 16) # 64 beats

# Phase 3 Outro (32 beats): Complete silence for the lead
lead_steps.extend([('-', W * 8)])

# Instant attack, fast decay to keep the arps plucky
compiler.add_audio_track(patch=0, steps=lead_steps, adsr=(10, 50, 20, 50))

# ---------------------------------------------------------------------------
# 2. Voice 1: The Wobble Bass (Patch 6 = PUNCH / Saw Wave)
# ---------------------------------------------------------------------------
bass_steps = []

# Phase 1 Build-up: Ominous sub drone
bass_steps.extend([('C2', W)] * 16) # 64 beats

# Phase 2 The Drop: The chord progression (4 bars / 16 beats per loop)
# Note: The actual "Wobble" is driven by the Automation Track below!
bass_drop_loop = [
    ('C2', W), ('D#2', W), ('C2', W),
    ('G1', H), ('F1', H)
]
bass_steps.extend(bass_drop_loop * 4) # 64 beats

# Phase 3 Outro: Returning to the drone
bass_steps.extend([('C2', W)] * 8) # 32 beats

compiler.add_audio_track(patch=6, steps=bass_steps)

# ---------------------------------------------------------------------------
# 3. Voice 2: The Half-Time Drums (Patch 2 = RETRO_NOISE)
# ---------------------------------------------------------------------------
drum_steps = []

# Phase 1 Build-up (64 beats)
drum_steps.extend([('C3', Q), ('-', Q)] * 16)  # Kick on 1 and 3 (32 beats)
drum_steps.extend([('C3', Q)] * 16)            # Kick every beat (16 beats)
drum_steps.extend([('C3', E)] * 16)            # 8th note kicks (8 beats)
drum_steps.extend([('C3', S)] * 16)            # 16th note kicks (4 beats)
drum_steps.extend([('C3', S)] * 8 + [('-', H)]) # Stop! "Where's the drop?" pause (4 beats)

# Phase 2 The Drop (64 beats): Heavy Half-Time Groove (Kick on 1, Snare on 3)
# 4 beats total per loop
drum_half_time = [
    ('C3', S), ('C6', S), ('C6', E), ('C6', E), ('C6', E), # Beat 1 (Kick) & 2 (Hats)
    ('C5', S), ('C6', S), ('C6', E), ('C6', E), ('C6', E)  # Beat 3 (Snare) & 4 (Hats)
]
drum_steps.extend(drum_half_time * 16)

# Phase 3 Outro (32 beats): Kick on 1 only
drum_steps.extend([('C3', Q), ('-', Q*3)] * 8)

compiler.add_audio_track(patch=2, steps=drum_steps)

# ---------------------------------------------------------------------------
# 4. Master Event Track (Constant 140 BPM)
# ---------------------------------------------------------------------------
compiler.add_bpm_change(140, wait_units=160 * Q)

# ---------------------------------------------------------------------------
# 5. Channel 1 Automation: THE WUB WUB (Target = Bass Channel)
# ---------------------------------------------------------------------------
# We manually calculate triangle waves to simulate an LFO sweeping the filter.
wob_steps = []

# Phase 1: Slow sweeping open (64 beats / 2048 steps)
wob_steps.extend([(compiler.PARAM_LPF, int((i/2048)*100) + 50) for i in range(2048)])

# Phase 2: THE DROP WOBBLES (64 beats / 2048 steps)
# 1 beat = 32 steps
wobble_Q = [(compiler.PARAM_LPF, int(255 - abs(i - 16) * (205 / 16))) for i in range(32)]
wobble_E = [(compiler.PARAM_LPF, int(255 - abs(i - 8) * (205 / 8))) for i in range(16)]
wobble_S = [(compiler.PARAM_LPF, int(255 - abs(i - 4) * (205 / 4))) for i in range(8)]

# Sequence a 4-bar "Wub" pattern (16 beats)
wobble_pattern = (wobble_Q * 4) + (wobble_E * 8) + (wobble_Q * 4) + (wobble_S * 16)

# Repeat 4 times to cover the 64 beat drop
wob_steps.extend(wobble_pattern * 4)

# Phase 3: Outro fade out (32 beats / 1024 steps)
wob_steps.extend([(compiler.PARAM_LPF, int(150 - (i/1024)*100)) for i in range(1024)])

# Target scope '1' explicitly modulates Voice 1 (The Bass)
compiler.add_automation_track(target=1, steps=wob_steps)

# Export!
compiler.build("wobble_protocol.jseq")
