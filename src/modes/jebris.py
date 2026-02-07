# File: src/modes/jebris.py
"""JEBris Game Mode - A Tetris-inspired Falling Block Game for an 8x8 LED Matrix."""

import random
import asyncio
from adafruit_ticks import ticks_ms, ticks_diff

from utilities import Palette

from .game_mode import GameMode


class JEBris(GameMode):
    """JEBris: A Tetris-inspired Falling Block Game."""

    METADATA = {
        "id": "JEBRIS",
        "name": "JEBRIS",
        "icon": "JEBRIS",
        "requires": ["CORE"],
        "settings": [
            {
                "key": "difficulty",
                "label": "SPEED",
                "options": ["EASY", "NORMAL", "HARD", "INSANE"],
                "default": "NORMAL"
            },
            {
                "key": "music",
                "label": "MUSIC",
                "options": ["ON", "OFF"],
                "default": "ON"
            }
        ]
    }

    # State machine constants
    STATE_PLAYING = "PLAYING"
    STATE_CLEARING_LINES = "CLEARING_LINES"

    # Input debounce constants (in milliseconds)
    DEBOUNCE_LEFT_MS = 100
    DEBOUNCE_ROTATE_MS = 200
    DEBOUNCE_DROP_MS = 0  # No debounce for fast drop
    DEBOUNCE_RIGHT_MS = 100

    def __init__(self, core):
        super().__init__(core, "JEBRIS", "Tetris-inspired Falling Block Game")

        # --- GAME SETTINGS ---
        difficulty = self.core.data.get_setting("JEBRIS", "difficulty", "NORMAL")
        self.music_on = self.core.data.get_setting("JEBRIS", "music", "ON")
        self.prev_highscore = self.core.data.get_setting("JEBRIS", "highscore", 0)

        if difficulty == "EASY":
            self.base_tick_ms = 1000
        elif difficulty == "HARD":
            self.base_tick_ms = 400
        elif difficulty == "INSANE":
            self.base_tick_ms = 200
        else:
            self.base_tick_ms = 800

        self.width = 8
        self.height = 8

        # --- SHAPES (Standard Tetrominoes) ---
        # Defined as (x, y) offsets relative to a center point
        self.shapes = [
            [(0, 0), (-1, 0), (1, 0), (2, 0)],   # I (Cyan)
            [(0, 0), (1, 0), (0, 1), (1, 1)],    # O (Yellow)
            [(0, 0), (-1, 0), (1, 0), (0, 1)],   # T (Magenta)
            [(0, 0), (-1, 0), (0, 1), (1, 1)],   # S (Green)
            [(0, 0), (1, 0), (0, 1), (-1, 1)],   # Z (Red)
            [(0, 0), (-1, 0), (1, 0), (-1, 1)],  # J (Blue)
            [(0, 0), (-1, 0), (1, 0), (1, 1)],   # L (Orange)
        ]
        self.colors = [
            Palette.CYAN,
            Palette.YELLOW,
            Palette.MAGENTA,
            Palette.GREEN,
            Palette.RED,
            Palette.BLUE,
            Palette.ORANGE
        ]

        # --- STATE ---
        self.grid = [[Palette.OFF for _ in range(self.width)] for _ in range(self.height)]
        self.score = 0
        self.is_game_over = False

        # Active Piece
        self.current_piece = None
        self.piece_x = 0
        self.piece_y = 0
        self.piece_color = Palette.OFF

        # --- TIMING STATE (for non-blocking input debouncing) ---
        # Track last input time for each button (0: Left, 1: Rotate, 2: Drop, 3: Right)
        self.last_input_time = [0, 0, 0, 0]
        self.input_debounce_ms = [
            self.DEBOUNCE_LEFT_MS,
            self.DEBOUNCE_ROTATE_MS,
            self.DEBOUNCE_DROP_MS,
            self.DEBOUNCE_RIGHT_MS
        ]

        # --- STATE MACHINE for line clearing ---
        self.game_state = self.STATE_PLAYING
        self.lines_to_clear = set()  # Set for O(1) lookup during rendering
        self.clear_animation_start = 0
        self.clear_animation_duration_ms = 50

    async def run(self):
        """Main Game Loop"""
        print(f"Starting {self.name}")
        self.reset_game()

        last_tick = ticks_ms()

        if self.music_on:
            await self.core.buzzer.play_song("TETRIS_THEME", loop=True)

        while True:
            now = ticks_ms()

            # STATE MACHINE: Handle different game states
            if self.game_state == self.STATE_PLAYING:
                # 1. INPUT HANDLING (non-blocking)
                self.handle_input(now)

                # 2. GRAVITY LOGIC
                # Calculate speed based on level (faster as score goes up)
                # Cap score multiplier to prevent nonsensical tick intervals
                score_speedup = min(self.score * 50, self.base_tick_ms - 100)
                tick_interval_ms = max(100, self.base_tick_ms - score_speedup)

                if ticks_diff(now, last_tick) > tick_interval_ms:
                    if not self.move_piece(0, 1):
                        # Piece hit bottom/stack
                        self.lock_piece()
                        # Start line clearing state machine
                        self.start_clear_lines()
                        if not self.lines_to_clear:
                            # No lines to clear, spawn immediately
                            self.spawn_piece()
                            if self.check_collision(self.current_piece, self.piece_x, self.piece_y):
                                self.is_game_over = True
                                await self.pre_game_over()

                    last_tick = now

            elif self.game_state == self.STATE_CLEARING_LINES:
                # Handle line clearing animation (non-blocking)
                if ticks_diff(now, self.clear_animation_start) > self.clear_animation_duration_ms:
                    # Animation done, remove lines and return to playing
                    self.finish_clear_lines()
                    self.spawn_piece()
                    if self.check_collision(self.current_piece, self.piece_x, self.piece_y):
                        self.is_game_over = True
                        await self.pre_game_over()
                    self.game_state = self.STATE_PLAYING

            # 3. RENDER
            self.draw()

            # Yield control for async background tasks (like HID updates)
            await asyncio.sleep(0.01)  # Reduced from 0.05 for more responsive gameplay

    def reset_game(self):
        """Resets the game state."""
        self.grid = [[Palette.OFF for _ in range(self.width)] for _ in range(self.height)]
        self.score = 0
        self.is_game_over = False
        self.spawn_piece()

    def spawn_piece(self):
        """Selects and positions a new piece at the top of the board."""
        shape_idx = int(random.randrange(len(self.shapes)))
        self.current_piece = self.shapes[shape_idx]
        self.piece_color = self.colors[shape_idx]

        # Center at top
        self.piece_x = self.width // 2
        self.piece_y = 0 # Might spawn slightly inside logic, check collision immediately

    def handle_input(self, now):
        """Checks for button presses with non-blocking debouncing."""
        hid = self.core.hid

        # LEFT (Btn 0)
        if hid.is_pressed(0):
            if ticks_diff(now, self.last_input_time[0]) > self.input_debounce_ms[0]:
                self.move_piece(-1, 0)
                self.last_input_time[0] = now

        # ROTATE (Btn 1)
        if hid.is_pressed(1):
            if ticks_diff(now, self.last_input_time[1]) > self.input_debounce_ms[1]:
                self.rotate_piece()
                self.last_input_time[1] = now

        # FAST DROP (Btn 2)
        if hid.is_pressed(2):
            # No debounce for fast drop to allow continuous dropping
            self.move_piece(0, 1)

        # RIGHT (Btn 3)
        if hid.is_pressed(3):
            if ticks_diff(now, self.last_input_time[3]) > self.input_debounce_ms[3]:
                self.move_piece(1, 0)
                self.last_input_time[3] = now

    def move_piece(self, dx, dy):
        """Attempts to move the piece. Returns True if successful."""
        if not self.check_collision(self.current_piece, self.piece_x + dx, self.piece_y + dy):
            self.piece_x += dx
            self.piece_y += dy
            return True
        return False

    def rotate_piece(self):
        """Rotates 90 degrees clockwise."""
        # Rotate logic: (x, y) -> (-y, x)
        new_shape = []
        for x, y in self.current_piece:
            new_shape.append((-y, x))

        if not self.check_collision(new_shape, self.piece_x, self.piece_y):
            self.current_piece = new_shape
        # Wall kick (simple): Try moving left/right if rotation fails near wall
        elif not self.check_collision(new_shape, self.piece_x - 1, self.piece_y):
            self.piece_x -= 1
            self.current_piece = new_shape
        elif not self.check_collision(new_shape, self.piece_x + 1, self.piece_y):
            self.piece_x += 1
            self.current_piece = new_shape

    def check_collision(self, shape, off_x, off_y):
        """Checks if the given shape at the given offset collides with walls or stack."""
        for x, y in shape:
            nx = off_x + x
            ny = off_y + y

            # Wall Collision
            if nx < 0 or nx >= self.width or ny >= self.height:
                return True

            # Stack Collision (ignore if above board, e.g. spawning)
            if ny >= 0:
                if self.grid[ny][nx] != Palette.OFF:
                    return True
        return False

    def lock_piece(self):
        """Locks the current piece into the static grid."""
        for x, y in self.current_piece:
            nx = self.piece_x + x
            ny = self.piece_y + y
            if 0 <= nx < self.width and 0 <= ny < self.height:
                self.grid[ny][nx] = self.piece_color

    def start_clear_lines(self):
        """Initiates line clearing animation without blocking."""
        self.lines_to_clear = set()

        # Find all full rows
        for y in range(self.height):
            if Palette.OFF not in self.grid[y]:
                self.lines_to_clear.add(y)

        if self.lines_to_clear:
            # Start animation state
            self.game_state = self.STATE_CLEARING_LINES
            self.clear_animation_start = ticks_ms()

            # Flash lines white immediately (visual feedback)
            for y in self.lines_to_clear:
                for x in range(self.width):
                    self.core.matrix.draw_pixel(x, y, Palette.WHITE)
            # Note: Hardware write is now centralized in CoreManager.render_loop()

    def finish_clear_lines(self):
        """Completes line clearing after animation finishes."""
        if not self.lines_to_clear:
            return

        lines_cleared = len(self.lines_to_clear)

        # Remove cleared rows (sort in reverse order to avoid index shifting issues)
        for y in sorted(self.lines_to_clear, reverse=True):
            del self.grid[y]
            # Add new empty row at top
            self.grid.insert(0, [Palette.OFF for _ in range(self.width)])

        # Update score
        self.score += lines_cleared

        # Clear the lines set
        self.lines_to_clear = set()

    def draw(self):
        """Renders the grid and active piece to the matrix."""
        # 1. Clear buffer (not display)
        self.core.matrix.clear()

        # 2. Draw Static Grid
        for y in range(self.height):
            for x in range(self.width):
                # If we're in clearing state, show white for lines being cleared
                if self.game_state == self.STATE_CLEARING_LINES and y in self.lines_to_clear:
                    self.core.matrix.draw_pixel(x, y, Palette.WHITE)
                elif self.grid[y][x] != Palette.OFF:
                    self.core.matrix.draw_pixel(x, y, self.grid[y][x])

        # 3. Draw Active Piece (only in PLAYING state)
        if self.game_state == self.STATE_PLAYING and self.current_piece:
            for x, y in self.current_piece:
                nx = self.piece_x + x
                ny = self.piece_y + y
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    self.core.matrix.draw_pixel(nx, ny, self.piece_color)

        # Note: Hardware write is now centralized in CoreManager.render_loop()

    async def pre_game_over(self):
        """Initial custom end game sequence before showing final score and high score."""
        # Fill matrix with flashing red
        await self.core.matrix.fill(
            Palette.RED,
            anim_mode="BLINK",
            duration=2.0,
            speed=0.5
        )
        await self.core.audio.stop_all()
        await self.core.buzzer.stop()
        await self.core.buzzer.play_song("GAME_OVER")
        await asyncio.sleep(2)
        return await self.game_over()
