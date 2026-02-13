# File: src/modes/pong.py
"""Pong Game Mode - Classic Mini Pong for 8x8 LED Matrix."""

import asyncio
import math
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
    - 2-pixel bats on each side (player bottom, top player/CPU)
    - Player 1 controls bottom bat with core rotary encoder
    - Player 2 controls top bat with industrial satellite encoder (2P mode)
    - CPU opponent with difficulty-based AI (1P mode)
    - Score display on OLED in middle info section
    - Scoring system for 1P mode based on win margin
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
        self.player_bat_x = 3  # Bottom bat (player 1)
        self.cpu_bat_x = 3     # Top bat (CPU or player 2)
        
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
        
    async def run(self):
        """Main game loop for Pong."""
        
        # Load settings
        self.game_mode = self.core.data.get_setting("PONG", "mode", "1P")
        self.difficulty = self.core.data.get_setting("PONG", "difficulty", "NORMAL")
        
        # Set variant for high score tracking (only for 1P mode)
        self.variant = f"{self.game_mode}_{self.difficulty}" if self.game_mode == "1P" else "2P"
        
        # Check for Industrial satellite if in 2P mode
        if self.game_mode == "2P":
            for sat in self.core.satellites.values():
                if sat.sat_type_name == "INDUSTRIAL" and sat.is_connected:
                    self.industrial_sat = sat
                    break
            
            if not self.industrial_sat:
                await self.core.display.update_status("ERROR", "INDUSTRIAL SAT REQUIRED FOR 2P")
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
        mode_text = f"{self.game_mode} MODE"
        if self.game_mode == "1P":
            mode_text += f" - {self.difficulty}"
        await self.core.display.update_status("MINI PONG", mode_text)
        await self.core.matrix.show_icon("PONG", anim_mode="PULSE", speed=2.0)
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
        self.ball_x = 4.0
        self.ball_y = 4.0
        
        # Random starting angle (avoid too horizontal)
        angle = random.choice([30, 45, 60, 120, 135, 150, 210, 225, 240, 300, 315, 330])
        self.ball_dx = self.ball_speed * math.cos(math.radians(angle))
        self.ball_dy = self.ball_speed * math.sin(math.radians(angle))
    
    def update_player_bat(self):
        """Update player bat position from encoder."""
        # Get encoder position and map to bat position (0-6)
        encoder_pos = self.core.hid.encoder_positions[0]
        # Map encoder to 0-6 range (allows 2-pixel bat to fit in 8-pixel width)
        # Python's modulo handles negative values correctly (wraps naturally)
        self.player_bat_x = encoder_pos % 7
    
    def update_cpu_bat(self, now):
        """Update CPU bat position with AI."""
        # CPU reacts with a delay based on difficulty
        if ticks_diff(now, self.last_cpu_update) < self.cpu_reaction_delay:
            return
        
        self.last_cpu_update = now
        
        # Simple AI: Move towards ball X position
        # Center 2-pixel bat on ball: bat occupies [target_x, target_x+1]
        # Ball at 4.0 should center at [3, 4] or [4, 5], so target = int(ball_x - 0.5) ≈ int(ball_x)
        # This gives reasonable tracking without being perfect
        if self.ball_x < 0.5:
            target_x = 0
        elif self.ball_x > 6.5:
            target_x = 6
        else:
            target_x = int(self.ball_x)
        
        # Move CPU bat towards target
        if self.cpu_bat_x < target_x:
            self.cpu_bat_x = min(self.cpu_bat_x + 1, target_x)
        elif self.cpu_bat_x > target_x:
            self.cpu_bat_x = max(self.cpu_bat_x - 1, target_x)
    
    def update_player2_bat(self):
        """Update player 2 bat position from industrial satellite encoder."""
        if not self.industrial_sat:
            return
        
        # Get encoder position from satellite (index 0)
        encoder_pos = self.industrial_sat.hid.encoder_positions[0]
        # Map encoder to 0-6 range (allows 2-pixel bat to fit in 8-pixel width)
        self.cpu_bat_x = encoder_pos % 7
    
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
                # Bat center is at position + 0.5 (between the two pixels)
                offset = self.ball_x - (self.cpu_bat_x + 0.5)
                self.ball_dx += offset * 0.05
        
        # Bottom bat collision (player at y=7)
        if self.ball_y >= 6.5 and self.ball_dy > 0:
            ball_x_int = int(self.ball_x)
            if self.player_bat_x <= ball_x_int <= self.player_bat_x + 1:
                self.ball_y = 6.5
                self.ball_dy = -abs(self.ball_dy)
                # Add slight angle based on where ball hits bat
                # Bat center is at position + 0.5 (between the two pixels)
                offset = self.ball_x - (self.player_bat_x + 0.5)
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
        if self.game_mode == "1P":
            await self.core.display.update_status(
                f"P1: {self.player_score}  CPU: {self.cpu_score}",
                f"FIRST TO 7 WINS"
            )
        else:
            await self.core.display.update_status(
                f"P1: {self.player_score}  P2: {self.cpu_score}",
                f"FIRST TO 7 WINS"
            )
    
    def calculate_1p_score(self):
        """Calculate final score for 1P mode based on win margin and difficulty.
        
        Scoring system:
        - Base score: 100 points for winning
        - Win margin bonus: +50 points per game lead (7-0 = +300, 7-6 = +0)
        - Difficulty multiplier: EASY=0.75x, NORMAL=1.0x, HARD=1.5x, INSANE=2.0x
        """
        base_score = 100
        win_margin = self.player_score - self.cpu_score  # Will be 1-7
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
        if self.game_mode == "1P":
            # Show score for 1P mode
            await self.core.display.update_status(
                f"YOU WIN! SCORE: {self.score}",
                f"FINAL: {self.player_score}-{self.cpu_score}"
            )
        else:
            # 2P mode - Player 1 wins
            await self.core.display.update_status(
                "PLAYER 1 WINS!",
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
            interrupt=True
        )
        await asyncio.sleep(3)
    
    async def show_defeat(self):
        """Show defeat animation."""
        if self.game_mode == "1P":
            await self.core.display.update_status(
                "CPU WINS",
                f"FINAL: {self.player_score}-{self.cpu_score}"
            )
        else:
            # 2P mode - Player 2 wins
            await self.core.display.update_status(
                "PLAYER 2 WINS!",
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
            interrupt=True
        )
        await asyncio.sleep(3)
