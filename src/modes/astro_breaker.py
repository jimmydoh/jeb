"""Astro Breaker Game Mode - Sci-Fi Brick Breaker for 8x8 LED Matrix."""

import asyncio
import math
import random
from adafruit_ticks import ticks_ms, ticks_diff

from utilities.palette import Palette
from utilities import tones
from utilities.synth_registry import Patches
from .game_mode import GameMode

class AstroBreakerMode(GameMode):
    """
    Astro Breaker Game Mode.
    
    Features:
    - 8x8 LED matrix playing field
    - 2-pixel wide ship shield (paddle) controlled by core rotary encoder
    - Plasma bolt (ball) physics
    - Multiple Brick Types (Normal, Multi-hit, Indestructible Cores)
    - Synthio procedural audio for physical interactions
    - 4 Core LEDs track lives (Green = Alive, Red = Spent)
    - 4 Core Buttons trigger 'Smart Bomb' (spends a life, clears board with wave)
    - Fully integrated with the CoreManager High Score system
    """
    
    METADATA = {
        "id": "ASTRO_BREAKER",
        "name": "ASTRO BREAKER",
        "icon": "ASTRO_BREAKER",
        "requires": ["CORE"],
        "settings": [
            {
                "key": "difficulty",
                "label": "DIFF",
                "options": ["NORMAL", "HARD", "INSANE"],
                "default": "NORMAL"
            }
        ]
    }

    def __init__(self, core):
        super().__init__(core, "ASTRO BREAKER", "Sci-Fi Brick Breaker")
        
        self.paddle_x = 3
        self.paddle_width = 2
        
        self.ball_x = 4.0
        self.ball_y = 6.0
        self.ball_dx = 0.0
        self.ball_dy = 0.0
        
        self.base_speed = 0.10
        self.current_speed = self.base_speed
        
        self.max_lives = 4
        self.lives = self.max_lives
        self.level = 1
        
        self.bricks = {}
        
    async def run(self):
        """Main game loop."""
        self.difficulty = self.core.data.get_setting("ASTRO_BREAKER", "difficulty", "NORMAL")
        self.variant = f"SOLO_{self.difficulty}"
        
        if self.difficulty == "HARD":
            self.base_speed = 0.14
        elif self.difficulty == "INSANE":
            self.base_speed = 0.18
        
        self.core.display.use_standard_layout()
        
        await self.core.display.update_status("ASTRO BREAKER", f"DIFF: {self.difficulty}")
        asyncio.create_task(self.core.synth.play_sequence(tones.POWER_UP, patch=Patches.SCANNER))
        await asyncio.sleep(2.0)
        
        self.core.hid.reset_encoder(0)
        self.score = 0
        self.lives = self.max_lives
        self.level = 1
        
        self.update_leds()
        self.generate_bricks()
        self.reset_ball()
        
        last_tick = ticks_ms()
        game_running = True
        
        while game_running:
            now = ticks_ms()
            delta_ms = ticks_diff(now, last_tick)
            
            if delta_ms >= 16:  # ~60 FPS Target
                
                # 1. Hardware Interrupt: Check for Smart Bomb trigger
                if self.check_buttons():
                    status = await self.trigger_smart_bomb()
                    
                    # If they used their last life for the bomb, end the game
                    if status == "GAME_OVER":
                        return status
                        
                    # Flush HID inputs to prevent accidental double-detonation if held down
                    if hasattr(self.core.hid, 'flush'):
                        self.core.hid.flush()
                        
                else:
                    # Normal game physics updates
                    self.update_paddle()
                    life_lost = self.update_ball()
                    
                    if life_lost:
                        self.lives -= 1
                        self.update_leds()
                        
                        if self.lives <= 0:
                            asyncio.create_task(self.core.synth.play_sequence(tones.GAME_OVER))
                            return await self.game_over()
                        else:
                            await self.core.display.update_status("HULL BREACH!", f"SHIELDS: {self.lives}")
                            asyncio.create_task(self.core.synth.play_sequence(tones.ERROR))
                            await asyncio.sleep(1.5)
                            self.reset_ball()
                
                # Check for sector clear (via paddle or surviving a smart bomb)
                if not self.bricks:
                    self.level += 1
                    self.current_speed = min(self.base_speed + (self.level * 0.02), 0.3)
                    await self.core.display.update_status("SECTOR CLEARED", f"WARPING TO SEC {self.level}")
                    asyncio.create_task(self.core.synth.play_sequence(tones.SECRET_FOUND))
                    await asyncio.sleep(2.0)
                    self.generate_bricks()
                    self.reset_ball()
                
                await self.core.display.update_status(f"SCORE: {self.score}", f"LIVES: {self.lives}  SEC: {self.level}")
                self.render()
                
                last_tick = now
            
            await asyncio.sleep(0.01)

    # --- HARDWARE INTEGRATION ---

    def check_buttons(self):
        """Check if any of the 4 core buttons were pressed."""
        # Note: Adjust 'button_pressed(i)' to match your exact hid_manager.py API
        for i in range(4):
            if hasattr(self.core.hid, 'is_button_pressed') and self.core.hid.is_button_pressed(i):
                return True
        return False
        
    def update_leds(self):
        """Update the 4 core NeoPixels to reflect current shields (lives)."""
        for i in range(4):
            # i = 0, 1, 2, 3
            if i < self.lives:
                if hasattr(self.core.leds, 'set_pixel'):
                    self.core.leds.set_pixel(i, Palette.GREEN)
                else:
                    self.core.leds[i] = Palette.GREEN
            else:
                if hasattr(self.core.leds, 'set_pixel'):
                    self.core.leds.set_pixel(i, Palette.RED)
                else:
                    self.core.leds[i] = Palette.RED
                    
        if hasattr(self.core.leds, 'show'):
            self.core.leds.show()

    async def trigger_smart_bomb(self):
        """Spends a life to clear the board with a massive visual shockwave."""
        if self.lives <= 0:
            return None
            
        # 1. Deduct life and update hardware instantly
        self.lives -= 1
        self.update_leds()
        
        # Determine narrative
        if self.lives == 0:
            await self.core.display.update_status("HEROIC SACRIFICE", "CORE OVERLOAD...")
        else:
            await self.core.display.update_status("SMART BOMB", "DETONATING...")
            
        # 2. Audio sweep trigger (runs async)
        asyncio.create_task(self.core.synth.play_sequence(tones.FIREBALL, patch=Patches.ALARM))
        
        # 3. Visual Shockwave animation from bottom (y=7) to top (y=0)
        for y in range(7, -1, -1):
            self.core.matrix.clear()
            
            # Draw remaining bricks so they don't vanish before the wave hits them
            self.render_bricks()
            
            # Draw the bright shockwave line
            for x in range(8):
                self.core.matrix.draw_pixel(x, y, Palette.WHITE)
            
            # Deep bass rumble that rises in pitch as the wave moves up
            freq = 100.0 + ((7 - y) * 20.0)
            self.core.synth.play_note(freq, Patches.ENGINE_HUM, duration=0.05)
            
            # Destroy bricks hit by the wave this frame
            bricks_to_remove = [pos for pos in self.bricks.keys() if pos[1] == y]
            for pos in bricks_to_remove:
                del self.bricks[pos]
                self.score += 5  # Give a reduced score for bombing vs playing normally
            
            await asyncio.sleep(0.08)
            
        # Ensure all bricks are truly cleared
        self.bricks.clear()
        
        if self.lives == 0:
            # The heroic sacrifice ends the run
            asyncio.create_task(self.core.synth.play_sequence(tones.GAME_OVER))
            return await self.game_over()
            
        await asyncio.sleep(0.5)
        return "CLEARED"

    # --- GAME LOGIC ---

    def generate_bricks(self):
        """Spawns different brick types based on row placement."""
        self.bricks.clear()
        
        for x in range(8):
            if x in [3, 4]:
                self.bricks[(x, 0)] = {'type': 'CORE', 'hp': 1}
            else:
                self.bricks[(x, 0)] = {'type': 'TOUGH', 'hp': 3}
                
            self.bricks[(x, 1)] = {'type': 'TOUGH', 'hp': 2}
            self.bricks[(x, 2)] = {'type': 'NORMAL', 'hp': 1}

    def reset_ball(self):
        """Reset plasma bolt to paddle position."""
        self.ball_x = self.paddle_x + 0.5
        self.ball_y = 6.0
        
        angle = random.choice([210, 225, 240, 300, 315, 330])
        self.ball_dx = self.current_speed * math.cos(math.radians(angle))
        self.ball_dy = self.current_speed * math.sin(math.radians(angle))
        
    def update_paddle(self):
        """Update shield position from encoder."""
        encoder_pos = self.core.hid.encoder_positions[0]
        self.paddle_x = encoder_pos % 7 

    def update_ball(self):
        """Update physics and handle collisions. Returns True if ball falls off bottom."""
        self.ball_x += self.ball_dx
        self.ball_y += self.ball_dy
        
        # Wall collisions
        if self.ball_x <= 0:
            self.ball_x = 0
            self.ball_dx = abs(self.ball_dx)
            self.core.synth.play_note(300.0, Patches.CLICK, duration=0.02)
        elif self.ball_x >= 7:
            self.ball_x = 7
            self.ball_dx = -abs(self.ball_dx)
            self.core.synth.play_note(300.0, Patches.CLICK, duration=0.02)
            
        if self.ball_y <= 0:
            self.ball_y = 0
            self.ball_dy = abs(self.ball_dy)
            self.core.synth.play_note(300.0, Patches.CLICK, duration=0.02)
            
        # Paddle collision
        if self.ball_y >= 6.5 and self.ball_dy > 0:
            ball_x_int = int(self.ball_x)
            if self.paddle_x <= ball_x_int <= self.paddle_x + 1:
                self.ball_y = 6.5
                self.ball_dy = -abs(self.ball_dy)
                
                offset = self.ball_x - (self.paddle_x + 0.5)
                self.ball_dx += offset * 0.1
                
                speed = math.sqrt(self.ball_dx**2 + self.ball_dy**2)
                self.ball_dx = (self.ball_dx / speed) * self.current_speed
                self.ball_dy = (self.ball_dy / speed) * self.current_speed
                
                self.core.synth.play_note(600.0, Patches.CLICK, duration=0.05)
        
        # Brick collisions
        ball_pos = (int(self.ball_x + 0.5), int(self.ball_y + 0.5))
        if ball_pos in self.bricks:
            brick = self.bricks[ball_pos]
            self.ball_dy = -self.ball_dy
            
            if brick['type'] == 'CORE':
                cores_protected = any(b['type'] != 'CORE' for b in self.bricks.values())
                if cores_protected:
                    self.core.synth.play_note(150.0, Patches.ERROR, duration=0.1)
                else:
                    del self.bricks[ball_pos]
                    self.score += 50
                    self.core.synth.play_note(1200.0, Patches.ALARM, duration=0.1)
            else: 
                brick['hp'] -= 1
                if brick['hp'] <= 0:
                    del self.bricks[ball_pos]
                    self.score += 10
                    self.core.synth.play_note(880.0, Patches.RETRO_SFX, duration=0.05)
                else:
                    self.score += 2
                    self.core.synth.play_note(440.0, Patches.RETRO_SFX, duration=0.05)
            
        if self.ball_y > 8:
            return True
            
        return False

    # --- RENDERING ---

    def render_bricks(self):
        """Draw the bricks (separated so the shockwave animation can reuse it)."""
        cores_protected = any(b['type'] != 'CORE' for b in self.bricks.values())
        
        for (bx, by), brick in self.bricks.items():
            if brick['type'] == 'CORE':
                color = Palette.RED if cores_protected else Palette.AMBER
            elif brick['type'] == 'TOUGH':
                if brick['hp'] >= 3: color = Palette.PURPLE
                elif brick['hp'] == 2: color = Palette.MAGENTA
                else: color = Palette.PINK
            else:
                color = Palette.CYAN
                
            self.core.matrix.draw_pixel(bx, by, color)

    def render(self):
        """Draw the full game state."""
        self.core.matrix.clear()
        self.render_bricks()
            
        # Draw Paddle
        for i in range(self.paddle_width):
            x = self.paddle_x + i
            if 0 <= x < 8:
                self.core.matrix.draw_pixel(x, 7, Palette.GREEN)
                
        # Draw Ball
        bx, by = int(self.ball_x + 0.5), int(self.ball_y + 0.5)
        if 0 <= bx < 8 and 0 <= by < 8:
            self.core.matrix.draw_pixel(bx, by, Palette.YELLOW)
