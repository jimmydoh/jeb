"""extract_beatmap.py – PC utility: convert a Clone Hero / Rock Band MIDI chart
to the JSON beatmap format consumed by RhythmMode on the JEB device.

Run on your development computer (NOT on the Pico):

    pip install mido
    python extract_beatmap.py notes.mid cyber_track_expert.json

The output JSON is an array of note objects::

    [{"time": <ms_from_song_start>, "col": <0-7>, "state": "WAITING"}, ...]

Drop the resulting .json file onto the Pico's SD card at::

    /sd/data/rhythm/<filename>.json

Then update the beatmap_path in RhythmMode.run() if you use a custom filename.

MIDI pitch → JEB matrix column mapping (Expert difficulty, 4-button layout):
    96  Green  → col 0
    97  Red    → col 2
    98  Yellow → col 5
    99  Blue   → col 7
    100 Orange → (ignored for 4-button layout; map to col 3 if desired)

For other difficulties adjust the NOTE_TO_COLUMN dict:
    Easy   pitches: 60–64
    Medium pitches: 72–76
    Hard   pitches: 84–88
    Expert pitches: 96–100
"""

import json
import sys


def extract_clone_hero_notes(midi_path, output_json_path, difficulty="expert"):
    """Extract timed note events from a Clone Hero MIDI chart.

    Args:
        midi_path (str): Path to the input .mid file.
        output_json_path (str): Path for the output .json beatmap file.
        difficulty (str): One of 'easy', 'medium', 'hard', 'expert'.
    """
    try:
        import mido
    except ImportError:
        print("ERROR: 'mido' is not installed.  Run: pip install mido")
        sys.exit(1)

    # MIDI pitch numbers for each difficulty and lane
    difficulty_offsets = {
        "easy":   60,
        "medium": 72,
        "hard":   84,
        "expert": 96,
    }

    base = difficulty_offsets.get(difficulty.lower())
    if base is None:
        print(f"ERROR: Unknown difficulty '{difficulty}'. "
              f"Choose from: easy, medium, hard, expert")
        sys.exit(1)

    # Map the first 4 Clone Hero lanes to JEB matrix columns.
    note_to_column = {
        base + 0: 0,  # Green  → col 0
        base + 1: 2,  # Red    → col 2
        base + 2: 5,  # Yellow → col 5
        base + 3: 7,  # Blue   → col 7
        # base + 4 (Orange) ignored for 4-button layout
    }

    print(f"Loading {midi_path} (difficulty: {difficulty})...")
    mid = mido.MidiFile(midi_path)

    beatmap = []
    current_time_ms = 0.0

    # Iterating over MidiFile merges all tracks and yields messages with
    # delta-time in seconds, automatically handling tempo map changes.
    for msg in mid:
        current_time_ms += msg.time * 1000.0

        # Only "note_on" with velocity > 0 represents a note press
        if msg.type == "note_on" and msg.velocity > 0:
            if msg.note in note_to_column:
                beatmap.append({
                    "time": int(current_time_ms),
                    "col": note_to_column[msg.note],
                    "state": "WAITING",
                })

    with open(output_json_path, "w") as f:
        json.dump(beatmap, f)

    print(f"Extracted {len(beatmap)} notes → {output_json_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python extract_beatmap.py <input.mid> <output.json> [difficulty]")
        print("       difficulty: easy | medium | hard | expert  (default: expert)")
        sys.exit(1)

    midi_file = sys.argv[1]
    json_file = sys.argv[2]
    diff = sys.argv[3] if len(sys.argv) >= 4 else "expert"

    extract_clone_hero_notes(midi_file, json_file, diff)
