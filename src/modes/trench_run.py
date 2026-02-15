"""Trench Run Game Mode - Endless Sci-Fi runner for 8x8 LED Matrix."""

import asyncio
import random
from adafruit_ticks import ticks_ms, ticks_diff

from utilities.palette import Palette
from utilities import tones
from .game_mode import GameMode

class TrenchRunMode(GameMode):
    """
    Trench Run Game Mode.
    
    Features:
    - Endless vertical scrolling dodging game
    - Perspective toggle: 3rd Person (ship moves) vs 1st Person (world moves)
    - Rotary encoder controls absolute horizontal position
    - Progressive speed and difficulty
    - Synthio procedural audio
    """
    
    METADATA = {
        "id": "TRENCH_RUN",
        "name": "TRENCH RUN",
        "icon": "game",
        "requires": ["CORE"],
        "settings": [
            {
                "key": "difficulty",
                "label": "DIFF",
                "options": ["NORMAL", "HARD", "INSANE"],
                "default": "NORMAL"
            },
            {
                "key": "perspective",
                "label": "VIEW",
                "options": ["3RD_PERSON", "1ST_PERSON"],
                "default": "3RD_PERSON"
            }
        ]
    }

    # Matrix dimensions
    MATRIX_WIDTH = 8
    MATRIX_HEIGHT = 8

    def __init__(self, core):
        super().__init__(core, "TRENCH RUN", "Endless Space Dodger")
        
        self.player_pos = 3
        
        # Walls are stored as dicts: {'y': float, 'gap_x': int}
        self.walls = []
        
        self.base_speed = 0.04
        self.current_speed = self.base_speed
        self.gap_width = 3
        self.wall_spacing = 4.0  # Vertical space between spawned walls
        
    async def run(self):
        """Main game loop."""
        self.difficulty = self.core.data.get_setting("TRENCH_RUN", "difficulty", "NORMAL")
        self.perspective = self.core.data.get_setting("TRENCH_RUN", "perspective", "3RD_PERSON")
        
        # Unique high scores for combinations of difficulty and perspective!
        self.variant = f"{self.perspective}_{self.difficulty}"
        
        if self.difficulty == "HARD":
            self.base_speed = 0.06
            self.gap_width = 2
        elif self.difficulty == "INSANE":
            self.base_speed = 0.08
            self.gap_width = 1
            
        self.current_speed = self.base_speed
            
        self.core.display.use_standard_layout()
        await self.core.display.update_status("TRENCH RUN", f"VIEW: {self.perspective}")
        asyncio.create_task(self.core.synth.play_sequence(tones.POWER_UP, patch="SCANNER"))
        await asyncio.sleep(2.0)
        
        self.core.hid.reset_encoder(0)
        self.score = 0
        self.level = 1
        self.walls.clear()
        
        # Spawn the first wall off-screen
        self.spawn_wall(y_start=-1.0)
        
        last_tick = ticks_ms()
        game_running = True
        
        while game_running:
            now = ticks_ms()
            delta_ms = ticks_diff(now, last_tick)
            
            if delta_ms >= 16:  # ~60 FPS Target
                self.update_player()
                crashed = self.update_walls()
                
                if crashed:
                    # Explode and end game
                    self.core.matrix.fill(Palette.WHITE)
                    asyncio.create_task(self.core.synth.play_sequence(tones.GAME_OVER))
                    await asyncio.sleep(0.1)
                    return await self.game_over()
                
                await self.core.display.update_status(f"SCORE: {self.score}", f"SPEED: {self.level}")
                self.render()
                
                # Engine drone that pitches up slightly as you speed up
                drone_freq = 80.0 + (self.level * 2.0)
                self.core.synth.play_note(drone_freq, "ENGINE_HUM", duration=0.05)
                
                last_tick = now
            
            await asyncio.sleep(0.01)

    def spawn_wall(self, y_start=-1.0):
        """Creates a new wall segment with a gap."""
        if not self.walls:
            gap = random.randint(0, self.MATRIX_WIDTH - 1)
        else:
            # Prevent impossible jumps by keeping the next gap close to the last one
            last_gap = self.walls[-1]['gap_x']
            shift = random.choice([-2, -1, 0, 1, 2])
            gap = (last_gap + shift) % self.MATRIX_WIDTH
            
        self.walls.append({'y': y_start, 'gap_x': gap})

    def update_player(self):
        """Update absolute ship position from encoder."""
        encoder_pos = self.core.hid.encoder_positions[0]
        # Keep player in infinite 0-(MATRIX_WIDTH-1) wrapped space
        self.player_pos = encoder_pos % self.MATRIX_WIDTH

    def update_walls(self):
        """Moves walls down and handles collisions. Returns True if crashed."""
        crashed = False
        walls_to_remove = []
        
        for wall in self.walls:
            old_y_int = int(wall['y'])
            wall['y'] += self.current_speed
            new_y_int = int(wall['y'])
            
            # If the wall just hit the bottom row (y = MATRIX_HEIGHT - 1), check collision
            if old_y_int < (self.MATRIX_HEIGHT - 1) and new_y_int >= (self.MATRIX_HEIGHT - 1):
                # Calculate the safe indices for this wall
                safe_indices = [(wall['gap_x'] + i) % self.MATRIX_WIDTH for i in range(self.gap_width)]
                
                if self.player_pos in safe_indices:
                    # Success!
                    self.score += 10
                    self.core.synth.play_note(880.0, "UI_SELECT", duration=0.05)
                    
                    # Speed up every 100 points
                    if self.score % 100 == 0:
                        self.level += 1
                        self.current_speed = min(self.base_speed + (self.level * 0.01), 0.25)
                else:
                    # Crash!
                    crashed = True
            
            # If wall goes completely off screen, mark for removal
            if wall['y'] > self.MATRIX_HEIGHT:
                walls_to_remove.append(wall)
                
        # Remove old walls
        for w in walls_to_remove:
            self.walls.remove(w)
            
        # Check if we need to spawn a new wall
        if self.walls:
            highest_wall_y = self.walls[-1]['y']
            if highest_wall_y > self.wall_spacing:
                self.spawn_wall()
                
        return crashed

    def render(self):
        """Draw the game state based on the selected perspective."""
        self.core.matrix.clear()
        
        for wall in self.walls:
            y_int = int(wall['y'])
            if 0 <= y_int < self.MATRIX_HEIGHT:
                
                if self.perspective == "3RD_PERSON":
                    render_gap = wall['gap_x']
                else: # 1ST_PERSON
                    # Shift the gap rendering so the player is effectively locked at index 3
                    render_gap = (wall['gap_x'] - self.player_pos + 3) % self.MATRIX_WIDTH
                
                # Calculate the exact indices to leave blank
                gap_indices = [(render_gap + i) % self.MATRIX_WIDTH for i in range(self.gap_width)]
                
                # Draw the wall blocks (color shifts slightly as speed increases)
                wall_color = Palette.RED if self.level < 5 else Palette.PURPLE
                for x in range(self.MATRIX_WIDTH):
                    if x not in gap_indices:
                        self.core.matrix.draw_pixel(x, y_int, wall_color)
        
        # Draw the Ship
        if self.perspective == "3RD_PERSON":
            # Ship moves across the bottom row
            self.core.matrix.draw_pixel(self.player_pos, self.MATRIX_HEIGHT - 1, Palette.CYAN)
        else:
            # Ship is anchored in the center (index 3)
            self.core.matrix.draw_pixel(3, self.MATRIX_HEIGHT - 1, Palette.CYAN)
