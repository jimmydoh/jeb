# File: src/utilities/tones.py
"""
Tone utility functions and constants for buzzer management.
"""

# --- FREQUENCIES (4th Octave Reference) ---
NOTE_FREQUENCIES = {
        'C4': 261.63, 'C#4': 277.18, 'D4': 293.66, 'D#4': 311.13,
        'E4': 329.63, 'F4': 349.23, 'F#4': 369.99, 'G4': 392.00,
        'G#4': 415.30, 'A4': 440.00, 'A#4': 466.16, 'B4': 493.88
    }

# --- STANDARD DURATIONS (in 'beats') ---
W = 4.0  # Whole
H = 2.0  # Half
Q = 1.0  # Quarter
E = 0.5  # Eighth
S = 0.25 # Sixteenth
T = 0.33 # Triplet

# --- TONE LIBRARY ---
BEEP = {
    'bpm': 120,
    'sequence': [('C5', S)]
}

ERROR = {
    'bpm': 120,
    'sequence': [('C5', S), ('C5', S), ('A4', S)]
}

SUCCESS = {
    'bpm': 120,
    'sequence': [('E5', S), ('G5', S), ('C6', H)]
}

POWER_UP = {
    'bpm': 150,
    'sequence': [
        ('C5', S), ('E5', S), ('G5', S),
        ('C6', S), ('E6', S), ('G6', H)
    ]
}

ALARM = {
    'bpm': 240,
    'sequence': [
        ('C6', E), ('-', E), ('C6', E), ('-', E)
    ]
}

UI_CONFIRM = {
    'bpm': 120,
    'sequence': [('C5', S), ('E5', S)]
}

# --- SOUND FX LIBRARY ---
# Mario Coin (Fast B5 -> E6)
COIN = {
    'bpm': 120, # Base speed
    'sequence': [('B5', S), ('E6', H)]
}

# Jump (Rising Sweep - Unrolled to data)
# Originally: range(150, 600, 50)
JUMP = {
    'bpm': 200, # Very fast playback for smooth sweep
    'sequence': [
        (150, S), (200, S), (250, S), (300, S),
        (350, S), (400, S), (450, S), (500, S),
        (550, S), (600, S)
    ]
}

# Fireball (Descending Sweep)
# Originally: range(800, 200, -100)
FIREBALL = {
    'bpm': 200,
    'sequence': [
        (800, S), (700, S), (600, S), (500, S),
        (400, S), (300, S), (200, S)
    ]
}

# One Up (Arpeggio: E-G-E-C-D-G)
ONE_UP = {
    'bpm': 150,
    'sequence': [
        ('E5', S), ('G5', S), ('E6', S),
        ('C6', S), ('D6', S), ('G6', Q)
    ]
}

# Secret Found (Zelda-style)
SECRET_FOUND = {
    'bpm': 160,
    'sequence': [
        ('G4', S), ('F#4', S), ('D#4', S), ('A3', S),
        ('G#3', S), ('E4', S), ('G#4', S), ('C5', H)
    ]
}

# Game Over (Sad descending tones)
GAME_OVER = {
    'bpm': 100,
    'sequence': [
        ('C5', E), ('G4', E), ('E4', Q),
        ('A4', Q), ('B4', Q), ('A3', W)
    ]
}

# --- SONG LIBRARY ---

MARIO_THEME = {
    'bpm': 180,
    'sequence': [
        # Intro
        ('E5', E), ('E5', E), ('-', E), ('E5', E),
        ('-', E), ('C5', E), ('E5', Q),
        ('G5', Q), ('-', Q), ('G4', Q),
        ('-', Q),
        # Theme A
        ('C5', Q * 1.5), ('G4', E), ('-', Q), ('E4', Q),
        ('-', E), ('A4', Q), ('B4', Q), ('A#4', E), ('A4', Q),
        ('G4', T*2), ('E5', T*2), ('G5', T*2),
        ('A5', Q), ('F5', E), ('G5', E),
        ('-', E), ('E5', Q), ('C5', E), ('D5', E), ('B4', Q * 1.5)
    ]
}

MARIO_UNDERGROUND = {
    'bpm': 100,
    'sequence': [
        ('C4', S), ('A3', S), ('A#3', S), ('A3', S),
        ('F3', S), ('G3', S),
        ('C4', S), ('A3', S), ('A#3', S), ('A3', S),
        ('F3', S), ('G3', S)
    ]
}

TETRIS_THEME = {
    'bpm': 140,
    'sequence': [
        ('E5', Q), ('B4', E), ('C5', E), ('D5', Q),
        ('C5', E), ('B4', E), ('A4', Q), ('A4', E),
        ('C5', E), ('E5', Q), ('D5', E), ('C5', E),
        ('B4', Q*1.5), ('C5', E), ('D5', Q), ('E5', Q),
        ('C5', Q), ('A4', Q), ('A4', Q)
    ]
}

# --- TONE CALCULATOR ---
@staticmethod
def note(note_name):
    """Converts a note name (e.g., 'A4', 'C#5') to its frequency in Hz."""

    # Pass raw frequency
    if isinstance(note_name, (int, float)):
        return note_name

    # Handle rests
    if str(note_name) in ['0', '-', '_', ' ']:
        return 0

    note_name = str(note_name).strip().upper()

    # Handle flats
    flat_map = {'DB': 'C#', 'EB': 'D#', 'GB': 'F#', 'AB': 'G#', 'BB': 'A#'}
    if len(note_name) == 3 and note_name[:2] in flat_map:
        note_name = flat_map[note_name[:2]] + note_name[2]

    # Parse Note/Octave
    try:
        if len(note_name) == 2:   # e.g. "A4"
            base_key = note_name[0] + '4'
            octave = int(note_name[1])
        elif len(note_name) == 3: # e.g. "C#5"
            base_key = note_name[0:2] + '4'
            octave = int(note_name[2])
        else:
            return 0
    except ValueError:
        return 0

    base_freq = NOTE_FREQUENCIES.get(base_key)
    if base_freq is None:
        return 0

    # Adjust frequency for the specified octave
    return base_freq * (2 ** (octave - 4))
