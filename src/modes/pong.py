# File: src/modes/pong.py
"""Pong Game Mode - Classic Mini Pong for 8x8 LED Matrix."""

import asyncio
import random
from adafruit_ticks import ticks_ms, ticks_diff

from utilities.palette import Palette
from utilities import tones

from .game_mode import GameMode


class PongMode(GameMode):
    """
    Mini Pong Game Mode.
    
    Features:
    - 8x8 LED matrix as playing field
    - 2-pixel bats on each side (player bottom, CPU top)
    - Player controls bottom bat with rotary encoder
    - CPU opponent with difficulty-based AI
    - Score display on OLED in middle info section
    """
    
    def __init__(self, core):
        super().__init__(core, "PONG", "Classic Pong Game")
        
        # Game constants
        self.MATRIX_WIDTH = 8
        self.MATRIX_HEIGHT = 8
        self.BAT_WIDTH = 2  # 2-pixel wide bat
        
        # Ball state
        self.ball_x = 0.0
        self.ball_y = 0.0
        self.ball_dx = 0.0  # Ball velocity X
        self.ball_dy = 0.0  # Ball velocity Y
        
        # Bat positions (0-6, centered position of 2-pixel bat)
        self.player_bat_x = 3  # Bottom bat (player)
        self.cpu_bat_x = 3     # Top bat (CPU)
        
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
        
    async def run(self):
        """Main game loop for Pong."""
        
        # Load settings
        self.difficulty = self.core.data.get_setting("PONG", "difficulty", "NORMAL")
        
        # Apply difficulty settings
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
        
        # Use standard layout for display
        self.core.display.use_standard_layout()
        
        # Intro
        await self.core.display.update_status("MINI PONG", f"DIFFICULTY: {self.difficulty}")
        await self.core.matrix.show_icon("PONG", anim_mode="PULSE", speed=2.0)
        await asyncio.sleep(2.0)
        
        # Reset encoder
        self.core.hid.reset_encoder(0)
        
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
                
                # Update CPU bat
                self.update_cpu_bat(now)
                
                # Update ball position
                self.update_ball()
                
                # Check for scoring
                scored = self.check_score()
                if scored:
                    # Update display with scores
                    await self.update_score_display()
                    
                    # Check for game over (first to 7 points)
                    if self.player_score >= 7:
                        await self.show_victory()
                        game_running = False
                        break
                    elif self.cpu_score >= 7:
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
        self.ball_x = 4.0
        self.ball_y = 4.0
        
        # Random starting angle (avoid too horizontal)
        angle = random.choice([30, 45, 60, 120, 135, 150, 210, 225, 240, 300, 315, 330])
        import math
        self.ball_dx = self.ball_speed * math.cos(math.radians(angle))
        self.ball_dy = self.ball_speed * math.sin(math.radians(angle))
    
    def update_player_bat(self):
        """Update player bat position from encoder."""
        # Get encoder position and map to bat position (0-6)
        encoder_pos = self.core.hid.encoder_positions[0]
        # Map encoder to 0-6 range (allows 2-pixel bat to fit in 8-pixel width)
        self.player_bat_x = max(0, min(6, (encoder_pos % 7 + 7) % 7))
    
    def update_cpu_bat(self, now):
        """Update CPU bat position with AI."""
        # CPU reacts with a delay based on difficulty
        if ticks_diff(now, self.last_cpu_update) < self.cpu_reaction_delay:
            return
        
        self.last_cpu_update = now
        
        # Simple AI: Move towards ball X position
        target_x = int(self.ball_x) - 1  # Center bat on ball
        target_x = max(0, min(6, target_x))
        
        # Move CPU bat towards target
        if self.cpu_bat_x < target_x:
            self.cpu_bat_x = min(self.cpu_bat_x + 1, target_x)
        elif self.cpu_bat_x > target_x:
            self.cpu_bat_x = max(self.cpu_bat_x - 1, target_x)
    
    def update_ball(self):
        """Update ball position and handle collisions."""
        # Update position
        self.ball_x += self.ball_dx
        self.ball_y += self.ball_dy
        
        # Wall collisions (left/right)
        if self.ball_x <= 0:
            self.ball_x = 0
            self.ball_dx = abs(self.ball_dx)
        elif self.ball_x >= 7:
            self.ball_x = 7
            self.ball_dx = -abs(self.ball_dx)
        
        # Top bat collision (CPU at y=0)
        if self.ball_y <= 0.5 and self.ball_dy < 0:
            ball_x_int = int(self.ball_x)
            if self.cpu_bat_x <= ball_x_int <= self.cpu_bat_x + 1:
                self.ball_y = 0.5
                self.ball_dy = abs(self.ball_dy)
                # Add slight angle based on where ball hits bat
                offset = (ball_x_int - self.cpu_bat_x) - 0.5
                self.ball_dx += offset * 0.05
        
        # Bottom bat collision (player at y=7)
        if self.ball_y >= 6.5 and self.ball_dy > 0:
            ball_x_int = int(self.ball_x)
            if self.player_bat_x <= ball_x_int <= self.player_bat_x + 1:
                self.ball_y = 6.5
                self.ball_dy = -abs(self.ball_dy)
                # Add slight angle based on where ball hits bat
                offset = (ball_x_int - self.player_bat_x) - 0.5
                self.ball_dx += offset * 0.05
    
    def check_score(self):
        """Check if someone scored and update scores."""
        # CPU scores (ball went past player bat)
        if self.ball_y > 7:
            self.cpu_score += 1
            return True
        
        # Player scores (ball went past CPU bat)
        if self.ball_y < 0:
            self.player_score += 1
            return True
        
        return False
    
    async def update_score_display(self):
        """Update the OLED display with current scores."""
        await self.core.display.update_status(
            f"YOU: {self.player_score}  CPU: {self.cpu_score}",
            f"FIRST TO 7 WINS"
        )
    
    def render(self):
        """Render the game state to the LED matrix."""
        # Clear matrix
        self.core.matrix.clear()
        
        # Draw CPU bat (top, y=0)
        for i in range(2):
            x = self.cpu_bat_x + i
            if 0 <= x < 8:
                self.core.matrix.draw_pixel(x, 0, Palette.RED)
        
        # Draw player bat (bottom, y=7)
        for i in range(2):
            x = self.player_bat_x + i
            if 0 <= x < 8:
                self.core.matrix.draw_pixel(x, 7, Palette.GREEN)
        
        # Draw ball
        ball_x_int = int(self.ball_x)
        ball_y_int = int(self.ball_y)
        if 0 <= ball_x_int < 8 and 0 <= ball_y_int < 8:
            self.core.matrix.draw_pixel(ball_x_int, ball_y_int, Palette.WHITE)
    
    async def show_victory(self):
        """Show victory animation."""
        await self.core.display.update_status(
            "YOU WIN!",
            f"FINAL: {self.player_score}-{self.cpu_score}"
        )
        await self.core.matrix.show_icon(
            "SUCCESS",
            anim_mode="PULSE",
            speed=2.0
        )
        await self.core.audio.play(
            "audio/general/win.wav",
            self.core.audio.CH_SFX,
            level=1.0,
            Interrupt=True
        )
        await asyncio.sleep(3)
    
    async def show_defeat(self):
        """Show defeat animation."""
        await self.core.display.update_status(
            "CPU WINS",
            f"FINAL: {self.player_score}-{self.cpu_score}"
        )
        await self.core.matrix.show_icon(
            "FAILURE",
            anim_mode="PULSE",
            speed=2.0
        )
        await self.core.audio.play(
            "audio/general/fail.wav",
            self.core.audio.CH_SFX,
            level=1.0,
            Interrupt=True
        )
        await asyncio.sleep(3)
