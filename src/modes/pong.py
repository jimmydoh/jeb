# File: src/modes/pong.py
"""Pong Game Mode - Classic Mini Pong for 16x16 LED Matrix."""

import asyncio
import math
import random
from adafruit_ticks import ticks_ms, ticks_diff

from utilities.palette import Palette
from utilities import tones

from .game_mode import GameMode


class Pong(GameMode):
    """
    Mini Pong Game Mode.

    Features:
    - 16x16 LED matrix as playing field
    - 2-pixel bats on each side (player left, CPU/player 2 right)
    - Player 1 controls left bat with core rotary encoder
    - Player 2 controls right bat with industrial satellite encoder (2P mode)
    - CPU opponent with difficulty-based AI (1P mode)
    - Single-pixel vertical net at centre column
    - Score display on OLED in middle info section
    - Scoring system for 1P mode based on win margin
    """

    def __init__(self, core):
        super().__init__(core, "PONG", "Classic Pong Game")

        # Game constants
        self.MATRIX_WIDTH = 16
        self.MATRIX_HEIGHT = 16
        self.BAT_SIZE = 2  # 2-pixel tall bat

        # Ball state
        self.ball_x = 0.0
        self.ball_y = 0.0
        self.ball_dx = 0.0  # Ball velocity X (left-right)
        self.ball_dy = 0.0  # Ball velocity Y (up-down)

        # Bat Y positions (0 to MATRIX_HEIGHT-BAT_SIZE, centre of 2-pixel bat)
        self.player_bat_y = 7  # Left bat (player 1)
        self.cpu_bat_y = 7     # Right bat (CPU or player 2)

        # Scores
        self.player_score = 0
        self.cpu_score = 0

        # Game settings
        self.ball_speed = 0.15  # Base ball movement speed (pixels per tick)
        self.cpu_speed = 0.08   # CPU bat movement speed
        self.cpu_reaction_delay = 300  # CPU reaction time in ms
        self.last_cpu_update = 0

        # Difficulty multipliers
        self.difficulty = "NORMAL"

        # Game mode (1P or 2P)
        self.game_mode = "1P"
        self.industrial_sat = None

    async def run_tutorial(self):
        """
        A guided, non-interactive demonstration of Pong.

        The Revised Voiceover Script (audio/tutes/pong_tute.wav) ~ 25 seconds:
            [0:00] "Welcome to Mini Pong. A classic battle of reflexes."
            [0:04] "Turn the dial to move your paddle up and down."
            [0:08] "Deflect the ball past your opponent to score points. First to seven wins."
            [0:13] "In one-player mode, crush the CPU quickly to maximize your score multiplier."
            [0:18] "Or connect an expansion box to challenge a friend in two-player mode."
            [0:23] "Get ready to play!"
            [0:25] (End of file)
        """
        await self.core.clean_slate()

        self.game_state = "TUTORIAL"

        # 1. Start the voiceover track
        tute_audio = asyncio.create_task(
            self.core.audio.play("audio/tutes/pong_tute.wav", bus_id=self.core.audio.CH_VOICE)
        )

        # Initialize safe starting state for the trick shot
        self.player_bat_y = 7
        self.cpu_bat_y = 7
        self.ball_x = 7.0
        self.ball_y = 7.0
        self.player_score = 0
        self.cpu_score = 0
        self.game_mode = "1P"

        # [0:00 - 0:04] "Welcome to Mini Pong..."
        self.core.display.update_status("PONG TUTORIAL", "CLASSIC REFLEXES")
        self.core.matrix.show_icon("PONG", anim_mode="PULSE", speed=2.0)
        await asyncio.sleep(4.0)

        # [0:04 - 0:08] "Turn the dial to move your paddle..."
        self.core.display.update_status("PONG TUTORIAL", "TURN DIAL TO MOVE")

        # Wiggle the player paddle up and down programmatically
        for y_pos in [7, 6, 5, 4, 3, 4, 5, 6, 7, 8, 9, 10, 11, 10, 9, 8, 7]:
            self.player_bat_y = y_pos
            self.render()
            self.core.matrix.show_frame()
            await asyncio.sleep(0.12)

        await asyncio.sleep(1.0)

        # [0:08 - 0:13] "Deflect the ball past your opponent to score points..."
        self.core.display.update_status("PONG TUTORIAL", "DEFLECT TO SCORE")

        # Trick Shot Rally: Ball comes from the right, player hits it, CPU misses
        self.ball_x = 13.0
        self.ball_y = 10.0
        self.ball_dx = -0.5  # Moving left
        self.ball_dy = -0.2  # Moving slightly up
        self.player_bat_y = 7 # Pre-positioned to intercept

        # Ball approaches player
        while self.ball_x > 1.0:
            self.ball_x += self.ball_dx
            self.ball_y += self.ball_dy
            self.render()
            self.core.matrix.show_frame()
            await asyncio.sleep(0.04)

        # Impact!
        self.ball_x = 1.0
        self.ball_dx = 0.6  # Bounce back faster
        self.ball_dy = 0.3
        self.core.buzzer.play_sequence(tones.UI_TICK)

        # CPU paddle moves the wrong way (misses)
        self.cpu_bat_y = 2

        # Ball flies past CPU
        while self.ball_x < 15.0:
            self.ball_x += self.ball_dx
            self.ball_y += self.ball_dy
            self.render()
            self.core.matrix.show_frame()
            await asyncio.sleep(0.04)

        # Play a crunchy impact sound using the buzzer
        self.core.buzzer.play_sequence(tones.ERROR)

        await self.animate_explosion(self.MATRIX_WIDTH - 1, self.ball_y, Palette.ORANGE)

        # Point Scored!
        self.player_score = 1
        await self.update_score_display()
        self.core.buzzer.play_sequence(tones.UI_CONFIRM)

        # Flash the right goal line red to visually indicate the score
        for _ in range(3):
            for y in range(self.MATRIX_HEIGHT):
                self.core.matrix.draw_pixel(15, y, Palette.RED, show=False)
            self.core.matrix.show_frame()
            await asyncio.sleep(0.1)
            self.render()
            self.core.matrix.show_frame()
            await asyncio.sleep(0.1)

        await asyncio.sleep(1.0)

        # [0:13 - 0:18] "In one-player mode, crush the CPU quickly..."
        self.core.display.update_status("PONG TUTORIAL", "MAXIMIZE WIN MARGIN")
        self.player_score = 7
        self.cpu_score = 2
        await self.update_score_display()
        self.calculate_1p_score() # Shows off the high score multiplier math
        self.core.display.update_footer(f"BONUS SCORE: {self.score}")
        await asyncio.sleep(5.0)

        # [0:18 - 0:23] "Or connect an Industrial Satellite to challenge..."
        self.core.display.update_status("PONG TUTORIAL", "2-PLAYER MULTIPLAYER")
        self.core.display.update_footer("")

        # Quick visual of both paddles moving independently
        self.ball_x = 7.5
        self.ball_y = 7.5
        for step in range(25):
            self.player_bat_y = 7 + int(4 * math.sin(step * 0.4))
            self.cpu_bat_y = 7 + int(4 * math.cos(step * 0.4))
            self.render()
            self.core.matrix.show_frame()
            await asyncio.sleep(0.05)

        # Wait for the audio track to finish naturally
        await tute_audio

        # Clean up and return to the menu
        await self.core.clean_slate()
        return "TUTORIAL_COMPLETE"

    async def run(self):
        """Main game loop for Pong."""

        # Load settings
        self.game_mode = self.core.data.get_setting("PONG", "mode", "1P")
        self.difficulty = self.core.data.get_setting("PONG", "difficulty", "NORMAL")

        # Set variant for high score tracking
        # 1P mode tracks high scores separately per difficulty level
        # This allows fair comparison within each difficulty tier
        self.variant = f"{self.game_mode}_{self.difficulty}" if self.game_mode == "1P" else "2P"

        # Check for Industrial satellite if in 2P mode
        if self.game_mode == "2P":
            for sat in self.core.satellites.values():
                if sat.sat_type_name == "INDUSTRIAL" and sat.is_connected:
                    self.industrial_sat = sat
                    break

            if not self.industrial_sat:
                self.core.display.update_status("ERROR", "INDUSTRIAL SAT REQUIRED FOR 2P")
                await asyncio.sleep(2)
                return "FAILURE"

        # Apply difficulty settings (only for 1P mode)
        if self.game_mode == "1P":
            if self.difficulty == "EASY":
                self.cpu_speed = 0.05
                self.cpu_reaction_delay = 500
                self.ball_speed = 0.12
            elif self.difficulty == "HARD":
                self.cpu_speed = 0.12
                self.cpu_reaction_delay = 150
                self.ball_speed = 0.18
            elif self.difficulty == "INSANE":
                self.cpu_speed = 0.15
                self.cpu_reaction_delay = 50
                self.ball_speed = 0.22
            else:  # NORMAL
                self.cpu_speed = 0.08
                self.cpu_reaction_delay = 300
                self.ball_speed = 0.15
        else:
            # 2P mode uses normal speed
            self.ball_speed = 0.15

        # Use standard layout for display
        self.core.display.use_standard_layout()

        # Intro
        mode_text = f"{self.game_mode} MODE - {self.difficulty}" if self.game_mode == "1P" else f"{self.game_mode} MODE"
        self.core.display.update_status("MINI PONG", mode_text)
        self.core.matrix.show_icon("PONG", anim_mode="PULSE", speed=2.0)
        await asyncio.sleep(2.0)

        # Reset encoders
        self.core.hid.reset_encoder(0)
        if self.industrial_sat:
            # Reset satellite encoder (index 0)
            self.industrial_sat.hid.reset_encoder(0)

        # Initialize game state
        self.player_score = 0
        self.cpu_score = 0
        self.reset_ball()

        # Game loop
        last_tick = ticks_ms()
        game_running = True

        while game_running:
            now = ticks_ms()
            delta_ms = ticks_diff(now, last_tick)

            # Update at roughly 60 FPS (16ms per frame)
            if delta_ms >= 16:
                # Update player bat from encoder
                self.update_player_bat()

                # Update top bat (CPU or P2)
                if self.game_mode == "1P":
                    self.update_cpu_bat(now)
                else:
                    self.update_player2_bat()

                # Update ball position
                self.update_ball()

                # Check for scoring
                scored = self.check_score()
                if scored:
                    # Play a crunchy impact sound using the buzzer
                    self.core.buzzer.play_sequence(tones.ERROR)

                    # --- NEW EXPLOSION EFFECT ---
                    if self.ball_x < 0:
                        # Ball crossed the left edge (CPU/P2 scored) -> Blue Explosion
                        await self.animate_explosion(0, self.ball_y, Palette.BLUE)
                    else:
                        # Ball crossed the right edge (Player 1 scored) -> Orange Explosion
                        await self.animate_explosion(self.MATRIX_WIDTH - 1, self.ball_y, Palette.ORANGE)
                    # ----------------------------

                    # Update display with scores
                    await self.update_score_display()

                    # Check for game over (first to 7 points)
                    if self.player_score >= 7:
                        if self.game_mode == "1P":
                            # Calculate final score based on win margin
                            self.calculate_1p_score()
                        await self.show_victory()
                        game_running = False
                        break
                    elif self.cpu_score >= 7:
                        if self.game_mode == "1P":
                            # No points awarded for losing
                            self.score = 0
                        await self.show_defeat()
                        game_running = False
                        break

                    # Reset ball after scoring
                    self.reset_ball()
                    await asyncio.sleep(0.5)

                # Render the game
                self.render()

                last_tick = now

            # Yield control
            await asyncio.sleep(0.01)

        # Game over
        return "GAME_OVER"

    def reset_ball(self):
        """Reset ball to center with random direction."""
        self.ball_x = float(self.MATRIX_WIDTH // 2 - 1)   # centre of play area
        self.ball_y = float(self.MATRIX_HEIGHT // 2 - 1)  # centre row

        # Random starting angle (avoid too horizontal)
        angle = random.choice([30, 45, 60, 120, 135, 150, 210, 225, 240, 300, 315, 330])
        self.ball_dx = self.ball_speed * math.cos(math.radians(angle))
        self.ball_dy = self.ball_speed * math.sin(math.radians(angle))

    def update_player_bat(self):
        """Update player bat position from encoder."""
        # Get encoder position and map to bat Y position (0 to MATRIX_HEIGHT-BAT_SIZE)
        encoder_pos = self.core.hid.encoder_positions[0]
        max_bat_pos = self.MATRIX_HEIGHT - self.BAT_SIZE  # = 14
        # Python's modulo with negative numbers wraps naturally
        self.player_bat_y = encoder_pos % (max_bat_pos + 1)

    def update_cpu_bat(self, now):
        """Update CPU bat position with AI."""
        # CPU reacts with a delay based on difficulty
        if ticks_diff(now, self.last_cpu_update) < self.cpu_reaction_delay:
            return

        self.last_cpu_update = now

        # Simple AI: Move towards ball Y position
        max_bat_pos = self.MATRIX_HEIGHT - self.BAT_SIZE  # = 14
        if self.ball_y < 0.5:
            target_y = 0
        elif self.ball_y > max_bat_pos - 0.5:
            target_y = max_bat_pos
        else:
            target_y = int(self.ball_y)

        # Move CPU bat towards target
        if self.cpu_bat_y < target_y:
            self.cpu_bat_y = min(self.cpu_bat_y + 1, target_y)
        elif self.cpu_bat_y > target_y:
            self.cpu_bat_y = max(self.cpu_bat_y - 1, target_y)

    def update_player2_bat(self):
        """Update player 2 bat position from industrial satellite encoder."""
        if not self.industrial_sat:
            return

        # Get encoder position from satellite (index 0)
        # Check that encoder_positions list has at least one element
        if len(self.industrial_sat.hid.encoder_positions) > 0:
            encoder_pos = self.industrial_sat.hid.encoder_positions[0]
            # Map encoder to 0-14 range (allows 2-pixel bat to fit in 16-pixel height)
            # Python's modulo with negative numbers wraps naturally
            max_bat_pos = self.MATRIX_HEIGHT - self.BAT_SIZE  # = 14
            self.cpu_bat_y = encoder_pos % (max_bat_pos + 1)

    def update_ball(self):
        """Update ball position and handle collisions."""
        # Update position
        self.ball_x += self.ball_dx
        self.ball_y += self.ball_dy

        # Wall collisions (top/bottom)
        if self.ball_y <= 0:
            self.ball_y = 0
            self.ball_dy = abs(self.ball_dy)
        elif self.ball_y >= self.MATRIX_HEIGHT - 1:
            self.ball_y = self.MATRIX_HEIGHT - 1
            self.ball_dy = -abs(self.ball_dy)

        # Left bat collision (Player 1 at column 0)
        if self.ball_x <= 0.5 and self.ball_dx < 0:
            ball_y_int = int(self.ball_y)
            if self.player_bat_y <= ball_y_int <= self.player_bat_y + 1:
                self.ball_x = 0.5
                self.ball_dx = abs(self.ball_dx)
                # Add slight angle based on where ball hits bat
                offset = self.ball_y - (self.player_bat_y + 0.5)
                self.ball_dy += offset * 0.05

        # Right bat collision (CPU/P2 at column MATRIX_WIDTH-2)
        right_bat_x = self.MATRIX_WIDTH - 2  # column 14
        if self.ball_x >= right_bat_x - 0.5 and self.ball_dx > 0:
            ball_y_int = int(self.ball_y)
            if self.cpu_bat_y <= ball_y_int <= self.cpu_bat_y + 1:
                self.ball_x = right_bat_x - 0.5
                self.ball_dx = -abs(self.ball_dx)
                # Add slight angle based on where ball hits bat
                offset = self.ball_y - (self.cpu_bat_y + 0.5)
                self.ball_dy += offset * 0.05

    def check_score(self):
        """Check if someone scored and update scores."""
        # CPU/P2 scores (ball went past player 1 bat on the left)
        if self.ball_x < 0:
            self.cpu_score += 1
            return True

        # Player 1 scores (ball went past CPU/P2 bat on the right)
        if self.ball_x > self.MATRIX_WIDTH - 2:
            self.player_score += 1
            return True

        return False

    async def update_score_display(self):
        """Update the OLED display with current scores."""
        if self.game_mode == "1P":
            self.core.display.update_status(
                f"P1: {self.player_score}  CPU: {self.cpu_score}",
                f"FIRST TO 7 WINS"
            )
        else:
            self.core.display.update_status(
                f"P1: {self.player_score}  P2: {self.cpu_score}",
                f"FIRST TO 7 WINS"
            )

    def calculate_1p_score(self):
        """Calculate final score for 1P mode based on win margin and difficulty.

        Precondition: Called only when player wins (player_score >= 7)

        Scoring system:
        - Base score: 100 points for winning
        - Win margin bonus: +50 points per game lead (7-0 = +300, 7-6 = +0)
        - Difficulty multiplier: EASY=0.75x, NORMAL=1.0x, HARD=1.5x, INSANE=2.0x
        """
        base_score = 100
        # Win margin represents point difference at victory (1-7 range)
        # Examples: 7-6 = margin of 1, 7-0 = margin of 7
        # Since this is only called when player wins, margin is always positive
        win_margin = self.player_score - self.cpu_score
        margin_bonus = (win_margin - 1) * 50  # 0 to 300 points

        # Difficulty multiplier
        difficulty_multipliers = {
            "EASY": 0.75,
            "NORMAL": 1.0,
            "HARD": 1.5,
            "INSANE": 2.0
        }
        multiplier = difficulty_multipliers.get(self.difficulty, 1.0)

        # Calculate final score
        self.score = int((base_score + margin_bonus) * multiplier)

    async def animate_explosion(self, origin_x, origin_y, color):
        """Animate a pixel explosion at the given coordinates."""
        particles = []
        # Generate 15 particles with random outward velocities
        for _ in range(15):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(0.3, 1.2)
            particles.append([
                float(origin_x), float(origin_y),     # 0: x, 1: y
                math.cos(angle) * speed,              # 2: dx
                math.sin(angle) * speed,              # 3: dy
                random.randint(8, 20)                 # 4: life (frames)
            ])

        # Run the physics simulation for up to 25 frames
        for _ in range(25):
            # Render the static game elements (net, paddles) underneath
            self.render()

            active_particles = False
            for p in particles:
                if p[4] > 0: # If life > 0
                    p[0] += p[2] # Update X
                    p[1] += p[3] # Update Y
                    p[4] -= 1    # Decrease life

                    # Draw the particle if it's still within the matrix bounds
                    px, py = int(p[0]), int(p[1])
                    if 0 <= px < self.MATRIX_WIDTH and 0 <= py < self.MATRIX_HEIGHT:
                        self.core.matrix.draw_pixel(px, py, color, show=False)

                    active_particles = True

            self.core.matrix.show_frame()

            # Exit early if all particles are dead or off-screen
            if not active_particles:
                break

            await asyncio.sleep(0.02)

    def render(self):
        """Render the game state to the LED matrix."""
        # Clear matrix
        self.core.matrix.clear()

        # Draw single-pixel vertical net at centre column
        net_x = self.MATRIX_WIDTH // 2 - 1  # column 7
        for y in range(self.MATRIX_HEIGHT):
            self.core.matrix.draw_pixel(net_x, y, Palette.BLUE)

        # Draw player bat (left side, column 0)
        for i in range(self.BAT_SIZE):
            y = self.player_bat_y + i
            if 0 <= y < self.MATRIX_HEIGHT:
                self.core.matrix.draw_pixel(0, y, Palette.GREEN)

        # Draw CPU/P2 bat (right side, column MATRIX_WIDTH-2)
        right_bat_x = self.MATRIX_WIDTH - 2  # column 14
        for i in range(self.BAT_SIZE):
            y = self.cpu_bat_y + i
            if 0 <= y < self.MATRIX_HEIGHT:
                self.core.matrix.draw_pixel(right_bat_x, y, Palette.RED)

        # Draw ball
        ball_x_int = int(self.ball_x)
        ball_y_int = int(self.ball_y)
        if 0 <= ball_x_int < self.MATRIX_WIDTH and 0 <= ball_y_int < self.MATRIX_HEIGHT:
            self.core.matrix.draw_pixel(ball_x_int, ball_y_int, Palette.WHITE)

    async def show_victory(self):
        """Show victory animation."""
        if self.game_mode == "1P":
            # Show score for 1P mode
            self.core.display.update_status(
                f"YOU WIN! SCORE: {self.score}",
                f"FINAL: {self.player_score}-{self.cpu_score}"
            )
        else:
            # 2P mode - Player 1 wins
            self.core.display.update_status(
                "PLAYER 1 WINS!",
                f"FINAL: {self.player_score}-{self.cpu_score}"
            )

        self.core.matrix.show_icon(
            "SUCCESS",
            anim_mode="PULSE",
            speed=2.0
        )
        await self.core.audio.play(
            "audio/general/win.wav",
            self.core.audio.CH_SFX,
            level=1.0,
            interrupt=True
        )
        await asyncio.sleep(3)

    async def show_defeat(self):
        """Show defeat animation."""
        if self.game_mode == "1P":
            self.core.display.update_status(
                "CPU WINS",
                f"FINAL: {self.player_score}-{self.cpu_score}"
            )
        else:
            # 2P mode - Player 2 wins
            self.core.display.update_status(
                "PLAYER 2 WINS!",
                f"FINAL: {self.player_score}-{self.cpu_score}"
            )
        self.core.matrix.show_icon(
            "FAILURE",
            anim_mode="PULSE",
            speed=2.0
        )
        await self.core.audio.play(
            "audio/general/fail.wav",
            self.core.audio.CH_SFX,
            level=1.0,
            interrupt=True
        )
        await asyncio.sleep(3)
