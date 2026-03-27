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
# COMPOSITION: ISLA PROTOCOL (REGGAETON)
# ==========================================

# Standard reggaeton tempo
compiler = JSEQCompilerV22(bpm=95)

# Timing Shortcuts
S = compiler.S    # 1/16 note (8 duration units)
E = compiler.E    # 1/8 note (16 duration units)
Q = compiler.Q    # 1/4 note (32 duration units)
H = compiler.H    # 1/2 note (64 duration units)
W = compiler.W    # Whole note / 4 beats (128 duration units)

# ---------------------------------------------------------------------------
# 1. Voice 0: The "Steel Drum" Lead (Patch 3 = BEEP / Sine Wave)
# ---------------------------------------------------------------------------
# ADSR Override to turn a flat beep into a Caribbean Mallet:
# 0 Attack (Instant strike), 100 Decay, 30 Sustain (plucky), 40 Release (smooth tail)
lead_adsr = (0, 100, 30, 40)

# Motif A (16 beats): A bouncy, syncopated melody hitting the 3-3-2 rhythm
lead_cm = [('G5', S), ('-', E), ('C6', S), ('-', E), ('G5', S), ('-', S)] * 2
lead_ab = [('G#5', S), ('-', E), ('C6', S), ('-', E), ('G#5', S), ('-', S)] * 2
lead_eb = [('G5', S), ('-', E), ('A#5', S), ('-', E), ('G5', S), ('-', S)] * 2
lead_bb = [('F5', S), ('-', E), ('A#5', S), ('-', E), ('F5', S), ('-', S)] * 2
lead_motif_a = lead_cm + lead_ab + lead_eb + lead_bb

# Motif B (16 beats): Faster 16th-note mallet rolls for the chorus
roll_cm = [('C6', S), ('G5', S), ('D#5', S), ('G5', S)] * 4
roll_ab = [('C6', S), ('G#5', S), ('D#5', S), ('G#5', S)] * 4
roll_eb = [('A#5', S), ('G5', S), ('D#5', S), ('G5', S)] * 4
roll_bb = [('A#5', S), ('F5', S), ('D5', S), ('F5', S)] * 4
lead_motif_b = roll_cm + roll_ab + roll_eb + roll_bb

lead_steps = []
lead_steps.extend([('-', W)] * 4)                      # Phase 1: Intro (16 beats rest)
lead_steps.extend(lead_motif_a * 2)                    # Phase 2: Verse (32 beats)
lead_steps.extend(lead_motif_b * 2)                    # Phase 3: Chorus (32 beats)
lead_steps.extend(lead_motif_a)                        # Phase 4: Breakdown (16 beats)
lead_steps.extend(lead_motif_b * 2)                    # Phase 5: The Drop (32 beats)
lead_steps.extend([('-', W)] * 4)                      # Phase 6: Outro (16 beats rest)

compiler.add_audio_track(patch=3, steps=lead_steps, adsr=lead_adsr)

# ---------------------------------------------------------------------------
# 2. Voice 1: The Sub Bass (Patch 1 = RETRO_BASS)
# ---------------------------------------------------------------------------
# The bass mimics the Dembow rhythm exactly to create that heavy bounce
bass_cm = [('C2', S), ('-', E), ('C2', S), ('-', E), ('C2', S), ('-', S)] * 2
bass_ab = [('G#1', S), ('-', E), ('G#1', S), ('-', E), ('G#1', S), ('-', S)] * 2
bass_eb = [('D#2', S), ('-', E), ('D#2', S), ('-', E), ('D#2', S), ('-', S)] * 2
bass_bb = [('A#1', S), ('-', E), ('A#1', S), ('-', E), ('A#1', S), ('-', S)] * 2
bass_prog = bass_cm + bass_ab + bass_eb + bass_bb

bass_steps = []
bass_steps.extend(bass_prog)                           # Phase 1: Intro (16 beats)
bass_steps.extend(bass_prog * 2)                       # Phase 2: Verse (32 beats)
bass_steps.extend(bass_prog * 2)                       # Phase 3: Chorus (32 beats)
bass_steps.extend(bass_prog)                           # Phase 4: Breakdown (16 beats)
bass_steps.extend(bass_prog * 2)                       # Phase 5: The Drop (32 beats)
bass_steps.extend(bass_prog)                           # Phase 6: Outro (16 beats)

compiler.add_audio_track(patch=1, steps=bass_steps)

# ---------------------------------------------------------------------------
# 3. Voice 2: The Dembow Beat (Patch 2 = RETRO_NOISE)
# ---------------------------------------------------------------------------
# The holy grail of Reggaeton: Kick on 1 and 2, Snare on the off-16ths.
# 2 Beats per loop.
dembow_loop = [
    ('C3', S), ('C6', S), ('C6', S), ('C5', S), # Kick, hat, hat, Snare (Beat 1)
    ('C3', S), ('C6', S), ('C5', S), ('C6', S)  # Kick, hat, Snare, hat (Beat 2)
]

# A simplified breakdown beat (Kick on 1, 2, 3, 4 only)
breakdown_beat = [('C3', Q), ('-', Q), ('C3', Q), ('-', Q)]

drum_steps = []
drum_steps.extend(dembow_loop * 8)                     # Phase 1: Intro (16 beats)
drum_steps.extend(dembow_loop * 16)                    # Phase 2: Verse (32 beats)
drum_steps.extend(dembow_loop * 16)                    # Phase 3: Chorus (32 beats)
drum_steps.extend(breakdown_beat * 4)                  # Phase 4: Breakdown (16 beats)
drum_steps.extend(dembow_loop * 16)                    # Phase 5: The Drop (32 beats)
drum_steps.extend(dembow_loop * 8)                     # Phase 6: Outro (16 beats)

compiler.add_audio_track(patch=2, steps=drum_steps)

# ---------------------------------------------------------------------------
# 4. Master Event Track (95 BPM Constant)
# ---------------------------------------------------------------------------
# 144 beats total
compiler.add_bpm_change(95, wait_units=144 * Q)

# ---------------------------------------------------------------------------
# 5. Global Automation: The Filter Sweeps
# ---------------------------------------------------------------------------
auto_steps = []

# Phase 1: Intro Sweep Up (16 beats / 512 steps)
auto_steps.extend([(compiler.PARAM_LPF, int(50 + (i/512)*205)) for i in range(512)])

# Phases 2 & 3: Verse & Chorus - Fully Open (64 beats / 2048 steps)
auto_steps.extend([(compiler.PARAM_LPF, 255)] * 2048)

# Phase 4: Breakdown Sweep Down (16 beats / 512 steps)
auto_steps.extend([(compiler.PARAM_LPF, int(255 - (i/512)*155)) for i in range(512)])

# Phase 5: The Drop - Snaps back to Fully Open (32 beats / 1024 steps)
auto_steps.extend([(compiler.PARAM_LPF, 255)] * 1024)

# Phase 6: Outro Sweep Down to silence (16 beats / 512 steps)
auto_steps.extend([(compiler.PARAM_LPF, int(255 - (i/512)*205)) for i in range(512)])

compiler.add_automation_track(target='GLOBAL', steps=auto_steps)

# Export!
compiler.build("isla_protocol.jseq")
