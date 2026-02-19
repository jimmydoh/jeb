"""Cyber Snake Game Mode - Classic Snake for 16x16 LED Matrix."""

import asyncio
import random
from adafruit_ticks import ticks_ms, ticks_diff

from utilities.palette import Palette
from utilities import tones
from .game_mode import GameMode

class CyberSnakeMode(GameMode):
    """
    Cyber Snake Game Mode.
    
    Features:
    - Dial-based relative steering (Turn right = Snake turns right)
    - Grid-stepped physics (speed increases as you eat)
    - Wrap vs Wall edge mechanics
    - Synthio audio feedback for movement and eating
    - Core LEDs act as a level-up progress bar
    """
    
    METADATA = {
        "id": "SNAKE",
        "name": "CYBER SNAKE",
        "icon": "GAME",
        "requires": ["CORE"],
        "settings": [
            {
                "key": "difficulty",
                "label": "DIFF",
                "options": ["NORMAL", "HARD", "INSANE"],
                "default": "NORMAL"
            },
            {
                "key": "edges",
                "label": "EDGES",
                "options": ["WRAP", "WALLS"],
                "default": "WRAP"
            }
        ]
    }

    # 0: UP, 1: RIGHT, 2: DOWN, 3: LEFT
    DIRECTIONS = [(0, -1), (1, 0), (0, 1), (-1, 0)]

    def __init__(self, core):
        super().__init__(core, "CYBER SNAKE", "Classic Grid Crawler")
        
        self.snake = []       # List of (x, y) tuples. Index 0 is the head.
        self.apple = (0, 0)
        
        self.current_facing = 0
        self.target_facing = 0
        self.last_encoder_pos = 0
        
        self.move_delay_ms = 300
        self.apples_eaten = 0
        self.apples_to_level = 4
        self.level = 1
        
    async def run(self):
        """Main game loop."""
        self.difficulty = self.core.data.get_setting("SNAKE", "difficulty", "NORMAL")
        self.edges = self.core.data.get_setting("SNAKE", "edges", "WRAP")
        
        self.variant = f"{self.edges}_{self.difficulty}"
        
        # Base speeds
        if self.difficulty == "NORMAL": self.move_delay_ms = 350
        elif self.difficulty == "HARD": self.move_delay_ms = 250
        elif self.difficulty == "INSANE": self.move_delay_ms = 150
            
        self.core.display.use_standard_layout()
        await self.core.display.update_status("CYBER SNAKE", f"{self.edges} / {self.difficulty}")
        asyncio.create_task(self.core.synth.play_sequence(tones.POWER_UP, patch="SCANNER"))
        await asyncio.sleep(2.0)
        
        self.core.hid.reset_encoder(0)
        self.last_encoder_pos = self.core.hid.encoder_positions[0]
        
        # Initialize Game State
        self.score = 0
        self.level = 1
        self.apples_eaten = 0
        
        # Start in the middle, 3 segments long, facing UP
        cx = self.core.matrix.width // 2 - 1
        cy = self.core.matrix.height // 2 - 1
        self.snake = [(cx, cy), (cx, cy + 1), (cx, cy + 2)]
        self.current_facing = 0
        self.target_facing = 0
        
        self.spawn_apple()
        self.update_leds()
        
        last_tick = ticks_ms()
        last_move_tick = ticks_ms()
        game_running = True
        
        while game_running:
            now = ticks_ms()
            delta_ms = ticks_diff(now, last_tick)
            
            # 1. 60 FPS INPUT & RENDER LOOP
            if delta_ms >= 16:  
                self.handle_input()
                self.render(now)
                last_tick = now
                
            # 2. SLOW PHYSICS LOOP (Grid Movement)
            if ticks_diff(now, last_move_tick) >= self.move_delay_ms:
                crashed = self.update_physics()
                
                if crashed:
                    await self.handle_death()
                    return await self.game_over()
                    
                await self.core.display.update_status(f"SCORE: {self.score}", f"SPEED: {self.level}")
                last_move_tick = now
            
            await asyncio.sleep(0.01)

    # --- GAME LOGIC ---

    def handle_input(self):
        """Reads rotary encoder and buttons to queue a 90-degree turn."""
        current_encoder = self.core.hid.encoder_positions[0]
        delta = current_encoder - self.last_encoder_pos
        
        # We only allow the target_facing to diverge by 90 degrees per grid-step. 
        # This prevents instantly turning 180 degrees into your own neck if you spin the dial fast.
        if delta != 0 and self.target_facing == self.current_facing:
            if delta > 0: # Turn Right
                self.target_facing = (self.current_facing + 1) % 4
                self.core.synth.play_note(1000.0, "UI_SELECT", duration=0.01)
            else:         # Turn Left
                self.target_facing = (self.current_facing - 1) % 4
                self.core.synth.play_note(800.0, "UI_SELECT", duration=0.01)
                
        self.last_encoder_pos = current_encoder
        
        # Optional: Button 0 (Rotate Left) and Button 1 (Rotate Right) overrides
        if hasattr(self.core.hid, 'button_pressed'):
            if self.core.hid.button_pressed(0) and self.target_facing == self.current_facing:
                self.target_facing = (self.current_facing - 1) % 4
            elif self.core.hid.button_pressed(1) and self.target_facing == self.current_facing:
                self.target_facing = (self.current_facing + 1) % 4

    def update_physics(self):
        """Moves the snake 1 grid unit. Returns True if died."""
        # Commit the targeted turn
        self.current_facing = self.target_facing
        
        dx, dy = self.DIRECTIONS[self.current_facing]
        head_x, head_y = self.snake[0]
        
        new_head_x = head_x + dx
        new_head_y = head_y + dy
        
        # Handle Edges
        if self.edges == "WRAP":
            new_head_x = new_head_x % self.core.matrix.width
            new_head_y = new_head_y % self.core.matrix.height
        else:
            # WALLS
            if not (0 <= new_head_x < self.core.matrix.width and 0 <= new_head_y < self.core.matrix.height):
                return True # Wall Crash
                
        new_head = (new_head_x, new_head_y)
        
        # Check self-collision (exclude the tail, because the tail will move forward this frame)
        if new_head in self.snake[:-1]:
            return True # Cannibal Crash
            
        # Move snake
        self.snake.insert(0, new_head)
        
        # Soft tactile click for every grid movement
        self.core.synth.play_note(150.0, "CLICK", duration=0.01)
        
        # Check Apple
        if new_head == self.apple:
            self.handle_eat_apple()
        else:
            # Didn't eat, pop the tail to maintain length
            self.snake.pop()
            
        return False

    def handle_eat_apple(self):
        """Processes scoring, leveling up, and audio when eating an apple."""
        self.score += (10 * self.level)
        self.apples_eaten += 1
        
        # Tasty data ping!
        self.core.synth.play_note(880.0, "SUCCESS", duration=0.08)
        
        if self.apples_eaten >= self.apples_to_level:
            self.apples_eaten = 0
            self.level += 1
            # Decrease move delay to speed up game, clamping at 60ms (insanely fast)
            self.move_delay_ms = max(int(self.move_delay_ms * 0.85), 60)
            
            # Level up sequence
            asyncio.create_task(self.core.synth.play_sequence(tones.ONE_UP))
            
        self.update_leds()
        self.spawn_apple()

    def spawn_apple(self):
        """Spawns an apple on a free grid square."""
        available_spots = []
        for x in range(self.core.matrix.width):
            for y in range(self.core.matrix.height):
                if (x, y) not in self.snake:
                    available_spots.append((x, y))
                    
        if available_spots:
            self.apple = random.choice(available_spots) 

    # --- HARDWARE & RENDERING ---

    def update_leds(self):
        """Updates the 4 core NeoPixels to act as a level-up progress bar."""
        if not hasattr(self.core, 'leds'): return
            
        for i in range(4):
            if i < self.apples_eaten:
                color = Palette.GREEN
            else:
                color = Palette.OFF
                
            if hasattr(self.core.leds, 'set_pixel'):
                self.core.leds.set_pixel(i, color)
            else:
                self.core.leds[i] = color
                
        if hasattr(self.core.leds, 'show'):
            self.core.leds.show()

    async def handle_death(self):
        """Cinematic death sequence."""
        # Red screen flash
        self.core.matrix.fill(Palette.RED)
        self.update_leds_death()
        asyncio.create_task(self.core.synth.play_sequence(tones.CRITICAL_STOP))
        await asyncio.sleep(0.5)
        
        # Draw dead snake in white
        self.core.matrix.clear()
        for i, segment in enumerate(self.snake):
            self.core.matrix.draw_pixel(segment[0], segment[1], Palette.WHITE)
            self.core.synth.play_note(200.0 - (i * 5), "UI_ERROR", duration=0.05)
            await asyncio.sleep(0.05)
            
        await asyncio.sleep(1.0)

    def update_leds_death(self):
        """Sets all core LEDs to red during the death sequence."""
        if not hasattr(self.core, 'leds'): return
        for i in range(4):
            if hasattr(self.core.leds, 'set_pixel'):
                self.core.leds.set_pixel(i, Palette.RED)
            else:
                self.core.leds[i] = Palette.RED
        if hasattr(self.core.leds, 'show'):
            self.core.leds.show()

    def render(self, now):
        """Draws the current game state to the matrix."""
        self.core.matrix.clear()
        
        # 1. Draw Apple (Pulsing Red)
        pulse = (now % 600) > 300
        apple_color = Palette.RED if pulse else Palette.PINK
        self.core.matrix.draw_pixel(self.apple[0], self.apple[1], apple_color)
            
        # 2. Draw Snake Body (Green)
        for i in range(1, len(self.snake)):
            seg = self.snake[i]
            # Fade the tail slightly for visual depth (Cyan->Green->Darker Green)
            if i == len(self.snake) - 1:
                color = (0, 80, 0) # Dim tail
            else:
                color = Palette.GREEN
            self.core.matrix.draw_pixel(seg[0], seg[1], color)
            
        # 3. Draw Snake Head (White/Cyan to clearly show facing direction)
        head = self.snake[0]
        self.core.matrix.draw_pixel(head[0], head[1], Palette.CYAN)
