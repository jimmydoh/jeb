# File: src/modes/jebris.py
"""JEBris Game Mode - A Tetris-inspired Falling Block Game for an 8x8 LED Matrix."""

import time
import random
import asyncio

from utilities import Palette

from .game_mode import GameMode


class JEBris(GameMode):
    """JEBris: A Tetris-inspired Falling Block Game."""
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

    async def run(self):
        """Main Game Loop"""
        print(f"Starting {self.name}")
        self.reset_game()

        last_tick = time.monotonic()

        if self.music_on:
            await self.core.buzzer.play_song("TETRIS_THEME", loop=True)

        while True:
            now = time.monotonic()

            # 1. INPUT HANDLING
            # We assume Core Buttons 0-3. Remap as needed.
            # 0: Left, 1: Rotate, 2: Drop/Down, 3: Right
            self.handle_input()

            # 2. GRAVITY LOGIC
            # Calculate speed based on level (faster as score goes up)
            tick_interval = max(0.1, (self.base_tick_ms - (self.score * 50)) / 1000.0)

            if now - last_tick > tick_interval:
                if not self.move_piece(0, 1):
                    # Piece hit bottom/stack
                    self.lock_piece()
                    self.clear_lines()
                    self.spawn_piece()

                    if self.check_collision(self.current_piece, self.piece_x, self.piece_y):
                        self.is_game_over = True
                        await self.game_over()
                        self.reset_game()

                last_tick = now

            # 3. RENDER
            self.draw()

            # Yield control for async background tasks (like HID updates)
            await asyncio.sleep(0.05)

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

    def handle_input(self):
        """Checks for button presses."""
        # Note: Depending on your HIDManager update logic, you might use
        # is_pressed() (continuous) or check a queue.
        # Here we use 'was_pressed' logic if available, or simple state checks with debouncing.

        hid = self.core.hid

        # LEFT (Btn 0)
        if hid.is_pressed(0): # You might need a debounce helper here
            self.move_piece(-1, 0)
            # Simple debounce sleep to prevent flying across screen
            time.sleep(0.1)

        # ROTATE (Btn 1)
        if hid.is_pressed(1):
            self.rotate_piece()
            time.sleep(0.2)

        # FAST DROP (Btn 2)
        if hid.is_pressed(2):
            self.move_piece(0, 1)
            # No sleep, allow fast dropping

        # RIGHT (Btn 3)
        if hid.is_pressed(3):
            self.move_piece(1, 0)
            time.sleep(0.1)

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

    def clear_lines(self):
        """Checks for full rows, removes them, and shifts grid down."""
        lines_cleared = 0
        # Iterate from bottom up
        y = self.height - 1
        while y >= 0:
            if Palette.OFF not in self.grid[y]:
                # Flash White Line
                for x in range(self.width):
                    self.core.matrix.set_pixel(x, y, Palette.WHITE)
                self.core.matrix.show()
                time.sleep(0.05)

                # Remove row
                del self.grid[y]
                # Add new empty row at top
                self.grid.insert(0, [Palette.OFF for _ in range(self.width)])
                lines_cleared += 1
                # Don't decrement y, check this index again (it's a new row now)
            else:
                y -= 1

        if lines_cleared > 0:
            self.score += lines_cleared
            # Optional: Play Sound
            # self.core.audio.play("line_clear")

    async def game_over(self):
        """Standard Fail State."""

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
        if self.score > self.prev_highscore:
            self.core.data.set_setting("JEBRIS", "highscore", self.score)
            await self.core.display.update_status("NEW HIGHSCORE!", f"SCORE: {self.score}")
        else:
            await self.core.display.update_status(f"YOUR SCORE: {self.score}", f"HIGHSCORE: {self.prev_highscore}")
            await asyncio.sleep(1)
        await asyncio.sleep(2)
        return "GAME_OVER"


    def draw(self):
        """Renders the grid and active piece to the matrix."""
        # 1. Clear buffer (not display)
        self.core.matrix.clear()

        # 2. Draw Static Grid
        for y in range(self.height):
            for x in range(self.width):
                if self.grid[y][x] != Palette.OFF:
                    self.core.matrix.set_pixel(x, y, self.grid[y][x])

        # 3. Draw Active Piece
        if self.current_piece:
            for x, y in self.current_piece:
                nx = self.piece_x + x
                ny = self.piece_y + y
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    self.core.matrix.set_pixel(nx, ny, self.piece_color)

        # 4. Push to Hardware
        self.core.matrix.show()
