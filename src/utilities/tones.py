# File: src/utilities/tones.py
"""
Tone utility functions and constants for synthio playback.
Defines note frequencies, standard durations, and pre-built tone sequences.
Designed for use with SynthManager via AudioManager and BuzzerManager.
"""

import re

from utilities.synth_registry import Patches

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
N32 = 0.125 # Thirty-second
N64 = 0.0625 # Sixty-fourth
N128 = 0.03125 # One hundred twenty-eighth
T = 0.33 # Triplet

# Note Length Examples
# 90  BPM -> Q = 667ms, E = 333ms, S = 167ms, N32 = 83ms, N64 = 42ms, N128 = 21ms
# 120 BPM -> Q = 500ms, E = 250ms, S = 125ms, N32 = 62ms, N64 = 31ms, N128 = 15ms
# 150 BPM -> Q = 400ms, E = 200ms, S = 100ms, N32 = 50ms, N64 = 25ms, N128 = 12ms
# 200 BPM -> Q = 300ms, E = 150ms, S = 75ms, N32 = 37ms, N64 = 18ms, N128 = 9ms
#
# Or just set to 60 bpm and use decimals of a second

# =================================
#       --- TONE LIBRARY ---
# =================================

# --- User Interface Tones ---
# A quick, optimistic ascending major triad (C-E-G)
SYSTEM_BOOT = {
    'bpm': 120,
    'patch': Patches.SELECT, # Clean Square or Sine
    'sequence': [('C4', S), ('E4', S), ('G4', Q)]
}

# A "Windows-style" shutdown (Descending)
SYSTEM_SHUTDOWN = {
    'bpm': 100,
    'patch': Patches.IDLE_HUM, # Softer, fading sound
    'sequence': [('G4', E), ('E4', E), ('C4', H)]
}

# "Critical Error" - The classic "Windows Dong" interval
CRITICAL_STOP = {
    'bpm': 120,
    'patch': Patches.ERROR, # Harsh Saw wave
    'sequence': [('A3', Q)] # Just one abrupt low note
}

# "Message Received" (Similar to iOS Tri-tone)
NOTIFY_INBOX = {
    'bpm': 180,
    'patch': Patches.SUCCESS, # Bell-like
    'sequence': [('E5', S), ('C5', S), ('A5', Q)]
}

# Play this very fast when scrolling through a menu
UI_TICK = {
    'bpm': 200,
    'patch': Patches.CLICK, # Ultra short envelope
    'sequence': [('C6', N64)]
}

# "Save Complete" / Checkpoint
SAVE_OK = {
    'bpm': 140,
    'patch': Patches.SUCCESS,
    'sequence': [('A4', S), ('A4', S), ('E5', H)]
}

BEEP = {
    'bpm': 120,
    'patch': Patches.BEEP,
    'sequence': [('C5', S)]
}

ERROR = {
    'bpm': 120,
    'sequence': [('C5', S), ('C5', S), ('A4', S)]
}

SUCCESS = {
    'bpm': 60,
    'sequence': [('E5', 0.1), ('-', 0.05), ('B5', 0.3)]
}

POWER_UP = {
    'bpm': 150,
    'sequence': [
        ('C5', S), ('E5', S), ('G5', S),
        ('C6', S), ('E6', S), ('G6', H)
    ]
}

POWER_FAIL = {
    'bpm': 150,
    'sequence': [
        ('G6', S), ('E6', S), ('C6', S),
        ('G5', S), ('E5', S), ('C5', W)
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
    'bpm': 200,
    'patch': Patches.RETRO_COIN,
    'sequence': [(1000, S), (1333, Q * 1.5)]
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

# --- ICONIC THEMES ---

# The "Nokia Tune" (Gran Vals)
NOKIA_TUNE = {
    'bpm': 160,
    'patch': Patches.BEEP,
    'sequence': [
        ('E6', E), ('D6', E), ('F#5', Q), ('G#5', Q),
        ('C#6', E), ('B5', E), ('D5', Q), ('E5', Q),
        ('B5', E), ('A5', E), ('C#5', Q), ('E5', Q),
        ('A5', W)
    ]
}

# Star Wars - Imperial March
IMPERIAL_MARCH = {
    'bpm': 105,
    'patch': Patches.ERROR, # Saw wave fits the aggressive tone
    'sequence': [
        ('G4', Q), ('G4', Q), ('G4', Q),
        ('D#4', E), ('A#4', S), ('G4', Q),
        ('D#4', E), ('A#4', S), ('G4', H)
    ]
}

MARIO_THEME = {
    'bpm': 100,
    'patch': Patches.RETRO_LEAD, # Square wave with instant attack
    'sequence': [
        # --- INTRO ---
        ('E6', E), ('E6', E), ('-', E), ('E6', E),
        ('-', E), ('C6', E), ('E6', Q),
        ('G6', Q), ('-', Q), ('G5', Q),
        ('-', Q),

        # --- THEME A ---
        ('C6', Q * 1.5), ('G5', E), ('-', Q), ('E5', Q),
        ('-', E), ('A5', Q), ('B5', Q), ('A#5', E), ('A5', Q),
        ('G5', T*2), ('E6', T*2), ('G6', T*2),
        ('A6', Q), ('F6', E), ('G6', E),
        ('-', E), ('E6', Q), ('C6', E), ('D6', E), ('B5', Q * 1.5),

        # --- THEME A Repeated ---
        ('C6', Q * 1.5), ('G5', E), ('-', Q), ('E5', Q),
        ('-', E), ('A5', Q), ('B5', Q), ('A#5', E), ('A5', Q),
        ('G5', T*2), ('E6', T*2), ('G6', T*2),
        ('A6', Q), ('F6', E), ('G6', E),
        ('-', E), ('E6', Q), ('C6', E), ('D6', E), ('B5', Q * 1.5),

        # --- THEME B ---
        # The Descent (G6 -> F#6 -> F6 -> D#6 -> E6)
        ('-', Q),
        ('G6', E), ('F#6', E), ('F6', E), ('D#6', Q), ('E6', E),
        # The Climb (G#5 -> A5 -> C6 -> A5 -> C6 -> D6)
        ('-', E), ('G#5', E), ('A5', E), ('C6', E),
        ('-', E), ('A5', E), ('C6', E), ('D6', E),
        # The Descent Again
        ('-', Q),
        ('G6', E), ('F#6', E), ('F6', E), ('D#6', Q), ('E6', E),
        # High C hits
        ('-', E), ('C7', Q), ('C7', E), ('C7', Q),
        # The Descent Once More
        ('-', Q),
        ('G6', E), ('F#6', E), ('F6', E), ('D#6', Q), ('E6', E),
        # The Climb Once More
        ('-', E), ('G#5', E), ('A5', E), ('C6', E),
        ('-', E), ('A5', E), ('C6', E), ('D6', E),
        # Finale
        ('-', Q), ('D#6', Q), ('-', E), ('D6', Q), ('-', E), ('C6', Q)
    ]
}

MARIO_THEME_ALT = {
    'bpm': 100,
    'patch': Patches.RETRO_LEAD, # Square wave with instant attack
    'sequence': [
        # Intro
        ('E6', E), ('E6', E), ('-', E), ('E6', E), ('-', E), ('C6', E), ('E6', Q),
        ('G6', Q), ('-', Q), ('G5', Q), ('-', Q),
        # Theme A
        ('C6', Q * 1.5), ('G5', E), ('-', Q), ('E5', Q),
        ('-', E), ('A5', Q), ('B5', Q), ('A#5', E), ('A5', Q),
        ('G5', T*2), ('E6', T*2), ('G6', T*2),
        ('A6', Q), ('F6', E), ('G6', E),
        ('-', E), ('E6', Q), ('C6', E), ('D6', E), ('B5', Q * 1.5),
    ]
}


MARIO_UNDERGROUND = {
    'bpm': 100,
    'patch': Patches.RETRO_LEAD, # Square wave with instant attack
    'sequence': [
        ('C4', S), ('A3', S), ('A#3', S), ('A3', S),
        ('F3', S), ('G3', S),
        ('C4', S), ('A3', S), ('A#3', S), ('A3', S),
        ('F3', S), ('G3', S)
    ]
}

TETRIS_THEME = {
    'bpm': 140,
    'patch': Patches.RETRO_LEAD, # Square wave with instant attack
    'sequence': [
        ('E5', Q), ('B4', E), ('C5', E), ('D5', Q),
        ('C5', E), ('B4', E), ('A4', Q), ('A4', E),
        ('C5', E), ('E5', Q), ('D5', E), ('C5', E),
        ('B4', Q*1.5), ('C5', E), ('D5', Q), ('E5', Q),
        ('C5', Q), ('A4', Q), ('A4', Q)
    ]
}

# -- SYNTHIO SCORES ---

WARP_CORE_IDLE = {
    'bpm': 30,  # Very slow tempo
    'sequence': [
        # (Note, Beats) - At 30 BPM, 1 beat = 2 seconds
        ('C3', 4.0),   # 8 seconds of low C
        ('G2', 4.0),   # 8 seconds of lower G (creates depth)
        ('C3', 4.0),   # Return to C
        ('A#2', 4.0),  # A dissonant interval for "sci-fi" tension
    ]
}

MAINFRAME_THINKING = {
    'bpm': 600, # Ultra fast
    'sequence': [
        ('C6', 1), ('-', 1), ('E6', 1), ('C6', 1), # Random high blips
        ('-', 2), ('G5', 1), ('-', 4),
        ('C7', 1), ('-', 1), ('B6', 1)
    ]
}

# "Radiation Leak" - High pitched anxiety
# Uses a dissonant tritone interval (C to F#)
RADIATION_WARNING = {
    'bpm': 240,
    'patch': Patches.ALARM,
    'sequence': [
        ('C6', S), ('F#6', S), ('C6', S), ('F#6', S),
        ('C6', S), ('F#6', S), ('C6', S), ('F#6', S)
    ]
}

# "Warp Drive Engaging" - Shephard Tone illusion (simplified)
# Rapidly rising pitch
WARP_ENGAGE = {
    'bpm': 300, # Ultra fast
    'patch': Patches.ENGINE_HUM, # Slow attack smoothes this out
    'sequence': [
        ('C3', S), ('E3', S), ('G3', S),
        ('C4', S), ('E4', S), ('G4', S),
        ('C5', S), ('E5', S), ('G5', S),
        ('C6', W) # End on high drone
    ]
}

# --- TONE CALCULATOR ---
def note(note_name):
    """Converts a note name (e.g., 'A4', 'C#5') to its frequency in Hz."""

    # Pass raw frequency
    if isinstance(note_name, (int, float)):
        return note_name

    # Handle rests
    if str(note_name) in ['0', '-', '_', ' ']:
        return 0

    # Regex: Capture (A-G followed by optional # or b) and (digits)
    match = re.match(r"^([A-G][#b]?)(-?\d+)$", str(note_name).strip().upper())

    if not match:
        return 0

    key, octave_str = match.groups()
    octave = int(octave_str)

    # Handle flats conversion
    if key.endswith('B'):
        flat_map = {'DB': 'C#', 'EB': 'D#', 'GB': 'F#', 'AB': 'G#', 'BB': 'A#'}
        key = flat_map.get(key, key)

    base_key = f"{key}4"  # Reference octave
    base_freq = NOTE_FREQUENCIES.get(base_key, 0)

    # Adjust frequency for the specified octave
    return base_freq * (2 ** (octave - 4))
