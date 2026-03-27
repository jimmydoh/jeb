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
# COMPOSITION: MOUNTAIN KING PROTOCOL
# ==========================================

# Starts at a very sneaky 80 BPM
compiler = JSEQCompilerV22(bpm=80)

# Timing Shortcuts
S = compiler.S    # 1/16 note (8 duration units)
E = compiler.E    # 1/8 note (16 duration units)
Q = compiler.Q    # 1/4 note (32 duration units)
W = compiler.W    # Whole note / 4 beats (128 duration units)

# Helper function to easily transpose sequences up an octave for the buildup!
def shift_octave(sequence, oct_shift):
    out = []
    for note, dur in sequence:
        if note == '-':
            out.append((note, dur))
        else:
            name = note[:-1]
            octave = int(note[-1])
            out.append((f"{name}{octave + oct_shift}", dur))
    return out

# ---------------------------------------------------------------------------
# 1. Voice 0: The Creeping Lead (Patch 0 = RETRO_LEAD)
# ---------------------------------------------------------------------------
# We use our optimized ADSR (0 attack, 50 release) for perfect staccato plucks
lead_adsr = (0, 100, 100, 50)

# Phrase A: The classic creeping motif (8 beats)
phrase_a = [
    ('C3', E), ('D3', E), ('D#3', E), ('F3', E),
    ('G3', E), ('D#3', E), ('G3', E), ('-', E),
    ('F3', E), ('D3', E), ('F3', E), ('-', E),
    ('D#3', E), ('C3', E), ('D#3', E), ('-', E)
]

# Phrase B: The turnaround (8 beats)
phrase_b = [
    ('C3', E), ('D3', E), ('D#3', E), ('F3', E),
    ('G3', E), ('D#3', E), ('G3', E), ('-', E),
    ('G3', E), ('D#3', E), ('C3', E), ('G2', E),
    ('C3', Q), ('-', Q)
]

# Phrase C: The B-Section, shifted up a fifth (8 beats)
phrase_c = [
    ('G3', E), ('A3', E), ('A#3', E), ('C4', E),
    ('D4', E), ('A#3', E), ('D4', E), ('-', E),
    ('C4', E), ('A3', E), ('C4', E), ('-', E),
    ('A#3', E), ('G3', E), ('A#3', E), ('-', E)
]

# 1 Full Block = 32 Beats
theme_block = phrase_a + phrase_b + phrase_c + phrase_b

lead_steps = []
lead_steps.extend(shift_octave(theme_block, 0)) # Phase 1 (80 BPM)  - Octave 3
lead_steps.extend(shift_octave(theme_block, 1)) # Phase 2 (110 BPM) - Octave 4
lead_steps.extend(shift_octave(theme_block, 2)) # Phase 3 (150 BPM) - Octave 5
lead_steps.extend(shift_octave(theme_block, 3)) # Phase 4 (200 BPM) - Octave 6
lead_steps.extend(shift_octave(theme_block, 4)) # Phase 5 (250 BPM) - Octave 7 (Chaos!)

compiler.add_audio_track(patch=0, steps=lead_steps, adsr=lead_adsr)

# ---------------------------------------------------------------------------
# 2. Voice 1: The Tuba/Cellos (Patch 1 = RETRO_BASS)
# ---------------------------------------------------------------------------
bass_steps = []

# Phase 1 & 2: Plodding Quarter Notes (64 beats)
bass_steps.extend([('C2', Q), ('-', Q)] * 32)

# Phase 3: Doubles to 8th Notes as tension rises (32 beats)
bass_steps.extend([('C2', E), ('-', E)] * 32)

# Phase 4 & 5: Driving, relentless 8th notes mimicking a timpani roll (64 beats)
bass_steps.extend([('C2', E), ('G2', E)] * 64)

compiler.add_audio_track(patch=1, steps=bass_steps)

# ---------------------------------------------------------------------------
# 3. Voice 2: The Percussion (Patch 2 = RETRO_NOISE)
# ---------------------------------------------------------------------------
drum_steps = []

# Phase 1: Pure Silence. Uses W chunking to prevent the 255 limit bug!
drum_steps.extend([('-', W)] * 8)

# Phase 2: Sneaky Hi-Hats on the offbeats
drum_steps.extend([('-', E), ('C6', E)] * 32)

# Phase 3: Marching snare enters
drum_steps.extend([('C4', E), ('C6', E)] * 32)

# Phase 4: A frantic 4-on-the-floor dance beat
drum_steps.extend([('C3', E), ('C6', E), ('C5', E), ('C6', E)] * 16)

# Phase 5: Complete Blast Beat Meltdown! (16th notes)
drum_steps.extend([('C3', S), ('C6', S)] * 64)

compiler.add_audio_track(patch=2, steps=drum_steps)

# ---------------------------------------------------------------------------
# 4. Master Event Track (The Great Accelerando)
# ---------------------------------------------------------------------------
# We step the BPM up every 32 beats (1 Block = 32 * Q duration units)
block_len = 32 * Q

compiler.add_bpm_change(80, wait_units=block_len)
compiler.add_bpm_change(110, wait_units=block_len)
compiler.add_bpm_change(150, wait_units=block_len)
compiler.add_bpm_change(200, wait_units=block_len)
compiler.add_bpm_change(250, wait_units=block_len) # MAXIMUM OVERDRIVE

# ---------------------------------------------------------------------------
# 5. Global Automation: The Rising Orchestra (Filter Sweep)
# ---------------------------------------------------------------------------
auto_steps = []

# The track is 5 blocks long (5 * 32 = 160 beats total).
# At 32 automation steps per beat, that's exactly 5120 steps.
# We sweep the filter from heavily muffled (30) to piercingly open (255).
for i in range(5120):
    val = int(30 + (i / 5120) * 225)
    auto_steps.append((compiler.PARAM_LPF, val))

compiler.add_automation_track(target='GLOBAL', steps=auto_steps)

# Export!
compiler.build("mountain_king_protocol.jseq")
