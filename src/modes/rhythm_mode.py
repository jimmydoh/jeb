"""Rhythm Game Mode - NEON BEATS time-synced rhythm game for the JEB framework.

Uses a master time anchor (ticks_ms) to synchronise falling-note visuals with
background audio streamed from the SD card.  All note positioning and hit
detection are calculated from elapsed wall-clock time so that display frame
rate jitter never drifts against the music.

Designed for a 16x16 LED matrix.  Column positions and the hit-zone row are
derived from the live matrix dimensions at runtime so the mode adapts to any
matrix size.

Beatmap files are pre-compiled JSON arrays (one entry per note) and are loaded
from the SD card at startup.  A companion PC script (examples/extract_beatmap.py)
converts Clone Hero / MIDI charts into the required format.

SD card layout::

    /sd/data/rhythm/
        <song_slug>.wav               – audio file
        <song_slug>_easy.json         – easy beatmap
        <song_slug>_normal.json       – normal beatmap
        <song_slug>_hard.json         – hard beatmap

Beatmap entry format::

    {"time": <ms_from_song_start>, "col": <0 to matrix.width-1>, "state": "WAITING"}

Button → lane mapping (4 physical buttons on CORE):
    Button 0 → lane 0  (leftmost column)
    Button 1 → lane 1
    Button 2 → lane 2
    Button 3 → lane 3  (rightmost column)

On a 16-wide matrix the 4 lane columns are evenly distributed:
    lane 0 → col  2
    lane 1 → col  6
    lane 2 → col 10
    lane 3 → col 14
"""

import asyncio
import json
import os
from adafruit_ticks import ticks_ms, ticks_diff

from utilities.palette import Palette
from .game_mode import GameMode


class RhythmMode(GameMode):
    """
    Rhythm Game Mode - NEON BEATS (16x16 LED Matrix).

    Features:
    - 16x16 matrix support: column positions and hit-zone row adapt to matrix size
    - Song selection screen: encoder scrolls through songs discovered on the SD card
    - Per-difficulty beatmaps: <song>_easy.json / _normal.json / _hard.json
    - Master time anchor: all rendering and hit detection are elapsed-time based
    - PERFECT / GOOD / MISS grade windows with LED and synth feedback
    - Beatmap loaded from a pre-compiled JSON file on the SD card
    - Background WAV played via AudioManager CH_ATMO; synth hits via SynthManager
    - Configurable latency offset to calibrate SD card / DAC start-up delay
    """

    METADATA = {
        "id": "RHYTHM",
        "name": "NEON BEATS",
        "icon": "RHYTHM",
        "requires": ["CORE"],
        "settings": [
            {
                "key": "difficulty",
                "label": "DIFF",
                "options": ["EASY", "NORMAL", "HARD"],
                "default": "NORMAL"
            },
            {
                "key": "latency",
                "label": "LATENCY",
                "options": ["0", "20", "45", "70", "100"],
                "default": "45"
            }
        ]
    }

    # SD card base path for all rhythm-game assets
    SONGS_PATH = "/sd/data/rhythm"

    # Hit detection windows in milliseconds
    PERFECT_WINDOW_MS = 50
    GOOD_WINDOW_MS = 150

    # Fall duration defaults per difficulty
    DEFAULT_FALL_DURATION_MS = 1000
    EASY_FALL_DURATION_MS = 1400
    HARD_FALL_DURATION_MS = 800

    def __init__(self, core):
        super().__init__(core, "NEON BEATS", "Rhythm Game")

        self.fall_duration_ms = self.DEFAULT_FALL_DURATION_MS
        self.hit_window_ms = self.GOOD_WINDOW_MS
        self.latency_offset_ms = 45

        self.start_anchor = 0
        self.beatmap = []
        self.combo = 0
        self.selected_song = None

    # ------------------------------------------------------------------
    # Properties derived from live matrix dimensions
    # ------------------------------------------------------------------

    @property
    def hit_zone_row(self):
        """Bottom row of the LED matrix – the hit target line."""
        return self.core.matrix.height - 1

    @property
    def button_columns(self):
        """4 evenly-spaced matrix columns driven by the 4 hardware buttons.

        For a 16-wide matrix: [2, 6, 10, 14]
        For an  8-wide matrix: [1, 3,  5,  7]
        """
        w = self.core.matrix.width
        step = w // 4
        return [step // 2 + i * step for i in range(4)]

    # ------------------------------------------------------------------
    # Song discovery
    # ------------------------------------------------------------------

    def _discover_songs(self):
        """Return a sorted list of song slugs found on the SD card.

        A song is any .wav file in SONGS_PATH.  Falls back to a single
        built-in "demo" entry when no SD card is available or the directory
        is empty.
        """
        songs = []
        try:
            for entry in os.listdir(self.SONGS_PATH):
                if entry.lower().endswith(".wav"):
                    songs.append(entry[:-4])  # strip .wav
            songs.sort()
        except OSError:
            pass

        return songs if songs else ["demo"]

    @staticmethod
    def _slug_to_display_name(slug):
        """Convert a filesystem slug to a human-readable title.

        Example: "cyber_track" → "CYBER TRACK"
        """
        return slug.replace("_", " ").upper()

    # ------------------------------------------------------------------
    # Beatmap loading
    # ------------------------------------------------------------------

    def _beatmap_path(self, slug, difficulty):
        """Return the expected path for a difficulty-specific beatmap JSON."""
        return f"{self.SONGS_PATH}/{slug}_{difficulty.lower()}.json"

    def _load_beatmap(self, slug, difficulty):
        """Load a difficulty-specific beatmap, with fallbacks.

        Load order:
        1. <slug>_<difficulty>.json  (e.g. cyber_track_normal.json)
        2. <slug>.json               (no-difficulty-suffix generic file)
        3. Built-in demo beatmap     (only when slug == "demo")
        Returns an empty list if no beatmap can be found.
        """
        for path in (
            self._beatmap_path(slug, difficulty),
            f"{self.SONGS_PATH}/{slug}.json",
        ):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except OSError:
                pass

        if slug == "demo":
            return self._demo_beatmap()

        return []

    # ------------------------------------------------------------------
    # Song selection screen
    # ------------------------------------------------------------------

    async def _select_song(self, songs):
        """Display a scrollable song list; return the chosen slug.

        Encoder rotation scrolls through songs; encoder button confirms.
        """
        self.core.display.use_standard_layout()
        self.core.matrix.show_icon("RHYTHM")
        self.core.hid.flush()
        self.core.hid.reset_encoder(0)

        idx = 0
        last_pos = 0

        while True:
            curr_pos = self.core.hid.encoder_position()
            diff = curr_pos - last_pos
            if diff != 0:
                idx = (idx + diff) % len(songs)
                last_pos = curr_pos

            name = self._slug_to_display_name(songs[idx])
            self.core.display.update_header("NEON BEATS")
            self.core.display.update_status(name, f"{idx + 1}/{len(songs)}")

            if self.core.hid.is_encoder_button_pressed(action="tap"):
                return songs[idx]

            await asyncio.sleep(0.05)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def run(self):
        """Song selection → load beatmap → start audio → game loop."""

        # Read settings
        self.difficulty = self.core.data.get_setting("RHYTHM", "difficulty", "NORMAL")
        latency_str = self.core.data.get_setting("RHYTHM", "latency", "45")
        self.latency_offset_ms = int(latency_str)

        if self.difficulty == "EASY":
            self.hit_window_ms = 200
            self.fall_duration_ms = self.EASY_FALL_DURATION_MS
        elif self.difficulty == "HARD":
            self.hit_window_ms = 100
            self.fall_duration_ms = self.HARD_FALL_DURATION_MS
        else:
            self.hit_window_ms = self.GOOD_WINDOW_MS
            self.fall_duration_ms = self.DEFAULT_FALL_DURATION_MS

        # Discover available songs on the SD card
        self.core.display.update_status("NEON BEATS", "SCANNING...")
        songs = self._discover_songs()

        # Show selection screen only when multiple songs are available
        if len(songs) > 1:
            self.selected_song = await self._select_song(songs)
        else:
            self.selected_song = songs[0]

        # Load the difficulty-appropriate beatmap
        self.core.display.update_status("NEON BEATS", "LOADING...")
        self.beatmap = self._load_beatmap(self.selected_song, self.difficulty)

        if not self.beatmap:
            self.core.display.update_status("NEON BEATS", "NO BEATMAP")
            await asyncio.sleep(2)
            return "FAILURE"

        # Sort by time and reset per-note state
        self.beatmap.sort(key=lambda n: n["time"])
        self.score = 0
        self.combo = 0
        for note in self.beatmap:
            note["state"] = "WAITING"

        # Show song title + difficulty, then start audio
        song_title = self._slug_to_display_name(self.selected_song)
        self.core.display.update_status(song_title, f"{self.difficulty} - GET READY")
        await asyncio.sleep(0.5)

        audio_path = f"{self.SONGS_PATH}/{self.selected_song}.wav"
        await self.core.audio.play(audio_path, self.core.audio.CH_ATMO, level=0.8)

        # Master time anchor – set immediately after play() is called
        self.start_anchor = ticks_ms()

        self.core.hid.flush()
        self.core.display.update_status("NEON BEATS", f"SCORE: {self.score}")

        # Main game loop
        end_time_ms = self.beatmap[-1]["time"] + 3000
        while True:
            now = ticks_ms()
            elapsed = ticks_diff(now, self.start_anchor)
            current_song_time = elapsed - self.latency_offset_ms

            # --- Input handling ---
            for btn_idx, col in enumerate(self.button_columns):
                if self.core.hid.is_button_pressed(btn_idx, action="tap"):
                    self._process_hit(current_song_time, col)

            # --- Rendering ---
            self._render(current_song_time)

            # --- End condition ---
            if current_song_time > end_time_ms:
                return await self.victory()

            await asyncio.sleep(0.016)  # ~60 fps target

    # ------------------------------------------------------------------
    # Hit processing
    # ------------------------------------------------------------------

    def _process_hit(self, current_time, col):
        """Find the closest waiting note in *col* and grade the hit."""
        closest_note = None
        smallest_diff = float('inf')

        for note in self.beatmap:
            if note["col"] == col and note["state"] == "WAITING":
                diff = abs(current_time - note["time"])
                if diff < smallest_diff:
                    smallest_diff = diff
                    closest_note = note

        if closest_note is not None and smallest_diff <= self.hit_window_ms:
            closest_note["state"] = "HIT"
            self.combo += 1

            if smallest_diff <= self.PERFECT_WINDOW_MS:
                self.score += 100
                self.core.leds.set_pixel(col % 4, Palette.GREEN)
                self.core.synth.play_note(880.0, "UI_SELECT", duration=0.05)
            else:
                self.score += 50
                self.core.leds.set_pixel(col % 4, Palette.YELLOW)
                self.core.synth.play_note(660.0, "UI_SELECT", duration=0.05)

            self.core.display.update_status("NEON BEATS", f"SCORE: {self.score}")
        else:
            # Miss / stray press
            self.combo = 0
            self.core.leds.set_pixel(col % 4, Palette.RED)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render(self, current_time):
        """Draw notes and hit zone on the LED matrix."""
        self.core.matrix.clear()

        cols = self.button_columns
        hz = self.hit_zone_row

        # Draw hit-zone markers at the bottom row
        for col in cols:
            self.core.matrix.draw_pixel(col, hz, Palette.WHITE)

        for note in self.beatmap:
            if note["state"] != "WAITING":
                continue

            spawn_time = note["time"] - self.fall_duration_ms

            if spawn_time <= current_time <= note["time"]:
                # Map elapsed fall time to a y position (0 → hit_zone_row)
                progress = (current_time - spawn_time) / self.fall_duration_ms
                y_pos = int(progress * hz)
                self.core.matrix.draw_pixel(note["col"], y_pos, Palette.CYAN)

            elif current_time > note["time"] + self.hit_window_ms:
                # Note has passed without being hit
                note["state"] = "MISSED"
                self.combo = 0
                self.core.synth.play_note(150.0, "UI_ERROR", duration=0.1)

    # ------------------------------------------------------------------
    # Demo beatmap (used when no SD card beatmap is found)
    # ------------------------------------------------------------------

    def _demo_beatmap(self):
        """Return a built-in beatmap using the live button column positions."""
        cols = self.button_columns
        return [
            {"time": 2000, "col": cols[0], "state": "WAITING"},
            {"time": 2500, "col": cols[1], "state": "WAITING"},
            {"time": 3000, "col": cols[2], "state": "WAITING"},
            {"time": 3500, "col": cols[3], "state": "WAITING"},
            {"time": 4000, "col": cols[0], "state": "WAITING"},
            {"time": 4000, "col": cols[2], "state": "WAITING"},
            {"time": 4500, "col": cols[1], "state": "WAITING"},
            {"time": 4500, "col": cols[3], "state": "WAITING"},
            {"time": 5000, "col": cols[0], "state": "WAITING"},
            {"time": 5500, "col": cols[2], "state": "WAITING"},
            {"time": 6000, "col": cols[1], "state": "WAITING"},
            {"time": 6000, "col": cols[3], "state": "WAITING"},
        ]
