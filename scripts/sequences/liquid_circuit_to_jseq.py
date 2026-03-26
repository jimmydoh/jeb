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
# COMPOSITION: LIQUID CIRCUIT (DRUM & BASS)
# ==========================================

# Classic Jungle/DnB tempo
compiler = JSEQCompilerV22(bpm=175)

# Timing Shortcuts
S = compiler.S    # 1/16 note (8 duration units)
E = compiler.E    # 1/8 note (16 duration units)
Q = compiler.Q    # 1/4 note (32 duration units)
DQ = compiler.DQ  # Dotted 1/4 note (48 duration units)
W = compiler.W    # Whole note (128 duration units / 4 beats)

# ---------------------------------------------------------------------------
# 1. Voice 0: The Atmospheric Lead (Patch 0 = RETRO_LEAD)
# ---------------------------------------------------------------------------
# We use a custom ADSR to make it plucky during the arps, but we will use
# TIE in Phase 1 to force it to sustain as a long pad.
lead_adsr = (10, 50, 70, 50)

# Phase 1: Ominous Pad Swell using TIE (64 beats)
# Strike the note for 1 quarter note, then sustain for 15.75 beats
lead_intro = [
    ('C4', Q), ('TIE', (W*4) - Q),
    ('G3', Q), ('TIE', (W*4) - Q),
    ('F3', Q), ('TIE', (W*4) - Q),
    ('C4', Q), ('TIE', (W*4) - Q)
]

# Phase 2: Frantic 16th note Arpeggio (1 beat per loop)
arp_loop = [('C5', S), ('D#5', S), ('G5', S), ('A#5', S)]

# Phase 3: Arpeggio shifts up an octave for maximum energy
arp_high = [('C6', S), ('D#6', S), ('G6', S), ('A#6', S)]

lead_steps = []
lead_steps.extend(lead_intro)        # 64 beats
lead_steps.extend(arp_loop * 64)     # 64 beats
lead_steps.extend(arp_high * 64)     # 64 beats

compiler.add_audio_track(patch=0, steps=lead_steps, adsr=lead_adsr)

# ---------------------------------------------------------------------------
# 2. Voice 1: The Reese Bass (Patch 1 = RETRO_BASS)
# ---------------------------------------------------------------------------
# Phase 1: Sparse 8th note pulses creeping in
bass_intro = [('-', W*8)] # 32 beats of silence
bass_intro.extend([('C2', E), ('-', E)] * 32) # 32 beats of pulsing

# Phase 2: Classic heavily syncopated DnB bassline (4 beats per loop)
bass_main = [
    ('C2', DQ), ('-', S), ('D#2', S), ('F2', Q), ('C2', Q)
]

# Phase 3: Aggressive stomping stabs (4 beats per loop)
bass_stabs = [
    ('C2', E), ('-', E), ('D#2', E), ('-', E),
    ('F2', E), ('-', E), ('G2', Q), ('-', Q)
]

bass_steps = []
bass_steps.extend(bass_intro)        # 64 beats
bass_steps.extend(bass_main * 16)    # 64 beats
bass_steps.extend(bass_stabs * 16)   # 64 beats

compiler.add_audio_track(patch=1, steps=bass_steps)

# ---------------------------------------------------------------------------
# 3. Voice 2: The Amen Break (Patch 2 = RETRO_NOISE)
# ---------------------------------------------------------------------------
# Phase 1: Snare roll buildup
drum_intro = [('-', W*8)] # 32 beats of silence
drum_intro.extend([('C4', Q), ('-', Q)] * 8)    # 16 beats (quarter notes)
drum_intro.extend([('C4', E), ('-', E)] * 16)   # 8 beats (8th notes)
drum_intro.extend([('C4', S), ('-', S)] * 32)   # 8 beats (16th notes)

# Phases 2 & 3: The Jungle Breakbeat (4 beats per loop)
# Reconstructing the ghost notes, kicks, and snares with 16th note timing
drum_break = [
    ('C3', S), ('C6', S), ('C6', S), ('C6', S), # Kick, hat, hat, hat
    ('C5', S), ('C6', S), ('C6', S), ('C3', S), # Snare, hat, hat, Kick
    ('C6', S), ('C3', S), ('C6', S), ('C6', S), # Hat, Kick, hat, hat
    ('C5', S), ('C6', S), ('C6', S), ('C6', S), # Snare, hat, hat, hat
]

drum_steps = []
drum_steps.extend(drum_intro)        # 64 beats
drum_steps.extend(drum_break * 32)   # 128 beats (Phases 2 & 3)

compiler.add_audio_track(patch=2, steps=drum_steps)

# ---------------------------------------------------------------------------
# 4. Master Event Track (Constant Tempo)
# ---------------------------------------------------------------------------
compiler.add_bpm_change(175, wait_units=192 * Q)

# ---------------------------------------------------------------------------
# 5. Global Automation (Filter Sweep & Sidechain Pump)
# ---------------------------------------------------------------------------
auto_steps = []

# Phase 1: Slow sweeping open of the filter (64 beats)
for i in range(2048):
    val = int((i / 2048) * 255)
    auto_steps.append((compiler.PARAM_LPF, val))

# Phases 2 & 3: "Sidechain" pumping effect on every beat (128 beats)
pump_cycle = []
for i in range(32): # 32 steps = 1 beat
    val = int(255 - (i / 32) * 150) # Sweeps down from 255 to 105 rapidly
    pump_cycle.append((compiler.PARAM_LPF, val))

auto_steps.extend(pump_cycle * 128)

compiler.add_automation_track(target='GLOBAL', steps=auto_steps)

# Export!
compiler.build("liquid_circuit_dnb.jseq")
