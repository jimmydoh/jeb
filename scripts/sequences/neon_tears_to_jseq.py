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
# COMPOSITION: NEON TEARS (CYBERPUNK AMBIENT)
# ==========================================

# A glacial 70 BPM to give the delays and envelopes room to breathe.
compiler = JSEQCompilerV22(bpm=70)

# Timing Shortcuts
N32 = compiler.N32 # 1/32 note (4 duration units)
S = compiler.S     # 1/16 note (8 duration units)
Q = compiler.Q     # 1/4 note  (32 duration units)
W = compiler.W     # Whole note (128 duration units, or 4 beats)

# ---------------------------------------------------------------------------
# 1. Voice 0: The Soaring Lead Pad (Patch 13 = ETHEREAL)
# ---------------------------------------------------------------------------
# A slow, majestic Vangelis-style melody.
# We trigger the note for 1 quarter note, then use TIE to hold it indefinitely
# so the slow attack/release envelope isn't interrupted.
pad_steps = [
    # Chord 1 (C minor vibes) - 8 beats total
    ('C5', Q), ('TIE', (W*2) - Q),

    # Chord 2 - 8 beats total
    ('D#5', Q), ('TIE', (W*2) - Q),

    # Chord 3 (Soaring) - 16 beats total
    ('F5', Q), ('TIE', (W*4) - Q),

    # The Descent - 8 beats each
    ('G#4', Q), ('TIE', (W*2) - Q),
    ('A#4', Q), ('TIE', (W*2) - Q),

    # Resolve - 16 beats total
    ('C5', Q), ('TIE', (W*4) - Q),
]

# We boost the decay and sustain to let the ETHEREAL patch really sing
compiler.add_audio_track(patch=13, steps=pad_steps, adsr=(100, 150, 200, 100))

# ---------------------------------------------------------------------------
# 2. Voice 1: The Sub-City Drone (Patch 14 = ENGINE_HUM)
# ---------------------------------------------------------------------------
# A massive, vibrating low-end drone that only changes pitch once.
# 32 beats per note.
bass_steps = [
    ('C2', Q), ('TIE', (W*8) - Q), # Rumble on C for 32 beats
    ('G1', Q), ('TIE', (W*8) - Q), # Drop to an abyssal G for the last 32 beats
]

compiler.add_audio_track(patch=14, steps=bass_steps)

# ---------------------------------------------------------------------------
# 3. Voice 2: The Data Stream (Patch 8 = SCANNER)
# ---------------------------------------------------------------------------
# Random-sounding, sparse high-pitched 32nd note computing blips.
# 1 beat of blips, 3 beats of silence.
scanner_burst = [
    ('C6', N32), ('G6', N32), ('D#6', N32), ('A6', N32),
    ('F6', N32), ('D6', N32), ('A#5', N32), ('C7', N32),
    ('-', W - Q) # Rest for the remaining 3 beats of the measure
]

scanner_steps = scanner_burst * 16 # Repeat 16 times = 64 beats total

# Reduce the attack and decay to make it sharp and plucky
compiler.add_audio_track(patch=8, steps=scanner_steps, adsr=(0, 50, 0, 50))

# ---------------------------------------------------------------------------
# 4. Master Event Track (The Cinematic Slowdown)
# ---------------------------------------------------------------------------
# We hold 70 BPM for most of the track, then slowly ritardando at the end.
# 1 beat = Q = 32 duration units.

compiler.add_bpm_change(70, wait_units=48 * Q) # Hold 70 BPM for 48 beats
compiler.add_bpm_change(65, wait_units=8 * Q)  # Drop to 65 BPM for 8 beats
compiler.add_bpm_change(60, wait_units=8 * Q)  # Finish at a crawling 60 BPM

# ---------------------------------------------------------------------------
# 5. Channel 0 Automation: The Breath (Tremolo)
# ---------------------------------------------------------------------------
# Applies specifically to Voice 0 (The Pad).
# A very slow, 4-beat triangular volume swell to make the synth "breathe".
breath_cycle = []
for i in range(128): # 128 steps = 4 beats
    # Triangle wave drifting between 150 and 255 volume
    val = int(255 - abs(i - 64) * (105 / 64))
    breath_cycle.append((compiler.PARAM_AMP, val))

pad_tremolo_steps = breath_cycle * 16 # 16 cycles = 64 beats total
compiler.add_automation_track(target=0, steps=pad_tremolo_steps)

# ---------------------------------------------------------------------------
# 6. Global Automation: The Slow Filter Sweep
# ---------------------------------------------------------------------------
# Opens the filter up for the first half, and closes it for the second half.
auto_steps = []
for i in range(1024): # First 32 beats (Ramp up)
    val = int(50 + (i / 1024) * 150) # 50 to 200
    auto_steps.append((compiler.PARAM_LPF, val))

for i in range(1024): # Last 32 beats (Ramp down)
    val = int(200 - (i / 1024) * 150) # 200 to 50
    auto_steps.append((compiler.PARAM_LPF, val))

compiler.add_automation_track(target='GLOBAL', steps=auto_steps)

# Export!
compiler.build("neon_tears_ambient.jseq")
