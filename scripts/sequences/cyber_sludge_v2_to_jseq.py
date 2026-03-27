"""JSEQ v2.2.1: Cybernetic Sludge (Remastered)
128 Beats. 3 Audio Channels. 2 Automation Channels. 1 Master Event Track.
"""
import struct
import re

class JSEQCompilerV22:
    # ... (Compiler class logic remains identical to the previous diagnostic script) ...
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
        if track_type == 0x00: # Audio
            p = self.note_to_index(val1)
            d = int(val2)
            packed = []
            while d > 255:
                packed.append(struct.pack('<BB', p, 255))
                d -= 255
            if d > 0: packed.append(struct.pack('<BB', p, d))
            return b"".join(packed)

        elif track_type == 0x01: # Automation
            return struct.pack('<BB', int(val1), int(val2))

        elif track_type == 0x02: # Master Event
            cmd = int(val1)
            val = int(val2)
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
        print(f"✅ Generated {filename}")

# --- The New Cyber Sludge ---
compiler = JSEQCompilerV22(bpm=140)

# CHANNEL 1: THE FILTH (Mid-Bass Stabs & Screeches)
# 128 Beats = 32 bars.
ch1_seq = []
# Sec 1: Intro (32 Beats)
ch1_seq.extend([('F2', 16), ('-', 48)] * 16)
# Sec 2: The Build (32 Beats)
ch1_seq.extend([('F2', 32)] * 16)
ch1_seq.extend([('F2', 16), ('-', 16)] * 8)
ch1_seq.extend([('F2', 8), ('-', 8)] * 16)

# Sec 3: The Drop (32 Beats)
drop_riff = [
    ('F2', 16), ('-', 16),
    ('F1', 16), ('-', 16),
    ('G#2', 8), ('-', 8), ('G2', 8), ('-', 8),
    ('F2', 8), ('-', 8), ('D#2', 8), ('-', 8),
    ('F1', 8), ('-', 8), ('F1', 8), ('-', 8),
    ('F2', 16), ('-', 16),
    ('C3', 8), ('G#2', 8), ('F2', 8), ('D#2', 8),
    ('C2', 8), ('-', 8), ('-', 16)
]
ch1_seq.extend(drop_riff * 4)

# Sec 4: Drop Variation (32 Beats)
ch1_seq.extend(drop_riff * 3)
ch1_seq.extend([('F5', 8), ('E5', 8), ('D#5', 8), ('D5', 8)] * 8)
compiler.add_audio_track(17, ch1_seq)

# CHANNEL 2: THE SUB (Deep Foundation)
ch2_seq = []
ch2_seq.extend([('F1', 128)] * 8) # Intro
ch2_seq.extend([('F1', 128)] * 4) # Build
ch2_seq.extend([('F1', 64)] * 4)
ch2_seq.extend([('F1', 32)] * 4)
ch2_seq.extend([('-', 128)])      # Silence before drop

sub_riff = [
    ('F1', 64),
    ('G#1', 32), ('F1', 32),
    ('F1', 64),
    ('D#1', 32), ('C1', 32)
]
ch2_seq.extend(sub_riff * 8) # Drop + Var
compiler.add_audio_track(1, ch2_seq)

# CHANNEL 3: THE DRUMS (Half-Time Groove)
ch3_seq = []
ch3_seq.extend([('-', 32), ('C4', 16), ('-', 16)] * 16) # Intro
ch3_seq.extend([('C4', 32)] * 16)                       # Build
ch3_seq.extend([('C4', 16), ('-', 16)] * 8)
ch3_seq.extend([('C4', 8), ('-', 8)] * 8)
ch3_seq.extend([('C4', 4)] * 32)

drop_drums = [
    ('C4', 16), ('-', 16),
    ('C4', 8), ('-', 8), ('C4', 8), ('-', 8),
    ('C4', 16), ('-', 16),
    ('C4', 8), ('-', 8), ('C4', 8), ('-', 8),
    ('C4', 16), ('-', 16),
    ('-', 16), ('C4', 16),
    ('C4', 16), ('-', 16),
    ('C4', 8), ('-', 8), ('C4', 8), ('-', 8)
]
ch3_seq.extend(drop_drums * 8) # Drop + Var
compiler.add_audio_track(2, ch3_seq)

# AUTOMATION 0: LPF Wobble on The Sub (Ch 1)
# Wobble the sub during the drop!
wob_steps = []
# Intro + Build (64 Beats = 2048 units)
for _ in range(2048):
    wob_steps.append((compiler.PARAM_LPF, 255)) # Keep open

# Drop (64 Beats = 2048 units)
# Wobble every 16th note (8 units)
for _ in range(128):
    for i in range(8): wob_steps.append((compiler.PARAM_LPF, 255))
    for i in range(8): wob_steps.append((compiler.PARAM_LPF, 100))
compiler.add_automation_track(1, wob_steps)

# AUTOMATION 1: Master Volume Pump
# Pump the master volume on the snare hits during the drop
amp_steps = []
for _ in range(2048): amp_steps.append((compiler.PARAM_AMP, 255)) # Intro + Build
# Drop pumping
for _ in range(64):
    for i in range(16): amp_steps.append((compiler.PARAM_AMP, 255)) # Kick
    for i in range(16): amp_steps.append((compiler.PARAM_AMP, 150)) # Duck
compiler.add_automation_track('GLOBAL', amp_steps)

# MASTER EVENT: Tempo manipulation
# Intro & Build: 140
# Drop: Slow down to 100 for a massive feel
compiler.add_bpm_change(140, wait_units=2048) # Wait 64 beats
compiler.add_bpm_change(100, wait_units=2048) # Wait 64 beats

compiler.build("cyber_sludge_v2_2.jseq")
