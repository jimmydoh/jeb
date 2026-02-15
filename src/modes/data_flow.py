"""Data Flow Game Mode - Procedural Laser Deflection Puzzle."""

import asyncio
import random
from adafruit_ticks import ticks_ms, ticks_diff

from utilities.palette import Palette
from utilities import tones
from .game_mode import GameMode

class DataFlowMode(GameMode):
    """
    Data Flow Game Mode.
    
    Features:
    - Procedurally generated laser-routing puzzles
    - Rotary encoder seamlessly maps 1D rotation to a 2D cursor (0-63)
    - Buttons 1 & 2 act as UP/DOWN to jump entire rows at a time
    - Instant ray-casting physics to trace the data stream
    - Synthio audio for tactile cursor movement and routing
    """
    
    # Game constants
    AMBIENT_HUM_PROBABILITY = 0.05  # 5% chance per frame to play ambient hum
    MAX_BEAM_PATH_LENGTH = 64  # Maximum beam path length (prevents infinite loops)
    MAX_GENERATION_ATTEMPTS = 100  # Maximum attempts to generate a valid level
    
    METADATA = {
        "id": "DATA_FLOW",
        "name": "DATA FLOW",
        "icon": "GAME", 
        "requires": ["CORE"],
        "settings": [
            {
                "key": "difficulty",
                "label": "DIFF",
                "options": ["NORMAL", "HARD"],
                "default": "NORMAL"
            }
        ]
    }

    def __init__(self, core):
        super().__init__(core, "DATA FLOW", "Optical Routing Puzzle")
        
        self.cursor_pos = 0  # 0 to 63 (maps to 8x8 grid)
        self.last_encoder_pos = 0
        
        # Track edge-triggers for Button 0 (Rotate), Button 1 (Up), Button 2 (Down)
        self.last_btn_states = {0: False, 1: False, 2: False}
        
        self.source = (0, 0)
        self.target = (7, 7)
        self.mirrors = {} # dict of (x,y) -> {'type': int} (0 = '/', 1 = '\')
        self.beam_path = []
        
        self.level = 1
        self.score = 0
        
        # Colors
        self.COLOR_SOURCE = Palette.GREEN
        self.COLOR_TARGET = Palette.GOLD
        self.COLOR_MIRROR_0 = Palette.CYAN     # '/' mirror
        self.COLOR_MIRROR_1 = Palette.MAGENTA  # '\' mirror
        self.COLOR_BEAM = (80, 80, 0)          # Dim yellow data stream
        
    async def run(self):
        """Main game loop."""
        self.difficulty = self.core.data.get_setting("DATA_FLOW", "difficulty", "NORMAL")
        self.variant = f"PUZZLE_{self.difficulty}"
        
        self.core.display.use_standard_layout()
        await self.core.display.update_status("DATA FLOW", "INITIALIZING...")
        asyncio.create_task(self.core.synth.play_sequence(tones.SYSTEM_BOOT))
        await asyncio.sleep(1.5)
        
        self.core.hid.reset_encoder(0)
        self.last_encoder_pos = self.core.hid.encoder_positions[0]
        self.level = 1
        self.score = 0
        
        self.generate_level()
        self.calculate_beam()
        
        last_tick = ticks_ms()
        game_running = True
        
        while game_running:
            now = ticks_ms()
            delta_ms = ticks_diff(now, last_tick)
            
            if delta_ms >= 16:  # ~60 FPS
                self.update_cursor()
                self.handle_input()
                
                # Check Win Condition
                if self.target in self.beam_path:
                    await self.handle_victory(now)
                
                # Render
                await self.core.display.update_status(f"ROUTER SEC: {self.level}", f"NODES: {len(self.mirrors)}")
                self.render(now)
                
                # Background ambient hum
                if random.random() < self.AMBIENT_HUM_PROBABILITY:
                    self.core.synth.play_note(60.0, "ENGINE_HUM", duration=0.1)
                
                last_tick = now
            
            await asyncio.sleep(0.01)

    # --- GAME LOGIC ---

    def update_cursor(self):
        """Map 1D encoder rotation to 2D grid position."""
        current_encoder = self.core.hid.encoder_positions[0]
        
        if current_encoder != self.last_encoder_pos:
            delta = current_encoder - self.last_encoder_pos
            self.cursor_pos = (self.cursor_pos + delta) % 64
            self.last_encoder_pos = current_encoder
            
            # Ultra-short tactile click for dial rotation
            self.core.synth.play_note(1000.0, "UI_SELECT", duration=0.01)

    def handle_input(self):
        """Check for button presses to rotate mirrors or jump rows."""
        btn_pressed = {0: False, 1: False, 2: False}
        
        if hasattr(self.core.hid, 'button_pressed'):
            for i in range(3):
                current_btn = self.core.hid.button_pressed(i)
                if current_btn and not self.last_btn_states[i]:
                    btn_pressed[i] = True
                self.last_btn_states[i] = current_btn

        # Button 0: Rotate Mirror
        if btn_pressed[0]:
            cx = self.cursor_pos % 8
            cy = self.cursor_pos // 8
            
            if (cx, cy) in self.mirrors:
                self.mirrors[(cx, cy)]['type'] = 1 - self.mirrors[(cx, cy)]['type']
                self.core.synth.play_note(600.0, "UI_SELECT", duration=0.05)
                self.calculate_beam()
            else:
                self.core.synth.play_note(200.0, "UI_ERROR", duration=0.05)
                
        # Button 1: Jump UP one row (-8)
        if btn_pressed[1]:
            self.cursor_pos = (self.cursor_pos - 8) % 64
            # Slightly higher pitch to distinguish from normal rotation
            self.core.synth.play_note(1200.0, "UI_SELECT", duration=0.015)

        # Button 2: Jump DOWN one row (+8)
        if btn_pressed[2]:
            self.cursor_pos = (self.cursor_pos + 8) % 64
            # Slightly lower pitch
            self.core.synth.play_note(800.0, "UI_SELECT", duration=0.015)

    def calculate_beam(self):
        """Ray-casts the data stream from source through the mirrors."""
        self.beam_path.clear()
        
        x, y = self.source
        dx, dy = 1, 0  # Source always faces right
        
        for _ in range(self.MAX_BEAM_PATH_LENGTH):
            x += dx
            y += dy
            
            if not (0 <= x < 8 and 0 <= y < 8):
                break
                
            self.beam_path.append((x, y))
            
            if (x, y) == self.target:
                break 
                
            if (x, y) in self.mirrors:
                m_type = self.mirrors[(x, y)]['type']
                if m_type == 0:
                    dx, dy = -dy, -dx # '/' Mirror
                else:
                    dx, dy = dy, dx   # '\' Mirror

    # --- LEVEL GENERATOR ---

    def generate_level(self):
        """Procedurally generate a solvable puzzle by walking backward from source."""
        base_mirrors = 3
        if self.difficulty == "HARD":
            base_mirrors = 5
            
        num_mirrors = min(base_mirrors + (self.level // 2), 12)
        
        for attempt in range(self.MAX_GENERATION_ATTEMPTS):
            self.mirrors.clear()
            
            x, y = 0, random.randint(1, 6)
            self.source = (x, y)
            dx, dy = 1, 0
            
            valid_path = True
            
            for _ in range(num_mirrors):
                steps = random.randint(1, 3)
                for _ in range(steps):
                    x += dx
                    y += dy
                    if not (0 <= x < 8 and 0 <= y < 8):
                        valid_path = False
                        break
                
                if not valid_path: break
                
                if (x, y) == self.source or (x, y) in self.mirrors:
                    valid_path = False
                    break
                    
                m_type = random.choice([0, 1])
                if m_type == 0:
                    dx, dy = -dy, -dx
                else:
                    dx, dy = dy, dx
                    
                self.mirrors[(x, y)] = {'type': m_type}
                
            if valid_path:
                steps = random.randint(1, 3)
                for _ in range(steps):
                    x += dx
                    y += dy
                    if not (0 <= x < 8 and 0 <= y < 8):
                        valid_path = False
                        break
                        
                if valid_path and (x, y) not in self.mirrors and (x, y) != self.source:
                    self.target = (x, y)
                    
                    for pos in self.mirrors:
                        self.mirrors[pos]['type'] = random.choice([0, 1])
                    return
                    
        self.generate_fallback_level()

    def generate_fallback_level(self):
        """A simple hardcoded level in case procedural generation fails."""
        self.mirrors.clear()
        self.source = (0, 3)
        self.target = (7, 5)
        self.mirrors[(3, 3)] = {'type': 0}
        self.mirrors[(3, 5)] = {'type': 1}

    # --- RENDERING & SEQUENCES ---

    async def handle_victory(self, now):
        """Plays victory animation and advances level."""
        self.render(now)
        self.core.matrix.draw_pixel(self.target[0], self.target[1], Palette.WHITE)
        
        asyncio.create_task(self.core.synth.play_sequence(tones.NOTIFY_INBOX, patch="SUCCESS"))
        
        for pos in self.beam_path:
            self.core.matrix.draw_pixel(pos[0], pos[1], Palette.WHITE)
            await asyncio.sleep(0.05)
            
        await asyncio.sleep(1.0)
        
        self.score += (100 * self.level)
        self.level += 1
        
        self.generate_level()
        self.calculate_beam()
        self.cursor_pos = 0

    def render(self, now):
        self.core.matrix.clear()
        
        for pos in self.beam_path:
            self.core.matrix.draw_pixel(pos[0], pos[1], self.COLOR_BEAM)
            
        for (mx, my), mirror in self.mirrors.items():
            color = self.COLOR_MIRROR_0 if mirror['type'] == 0 else self.COLOR_MIRROR_1
            self.core.matrix.draw_pixel(mx, my, color)
            
        pulse = (now % 1000) > 500
        source_color = Palette.WHITE if pulse else self.COLOR_SOURCE
        target_color = Palette.WHITE if not pulse else self.COLOR_TARGET
        
        self.core.matrix.draw_pixel(self.source[0], self.source[1], source_color)
        self.core.matrix.draw_pixel(self.target[0], self.target[1], target_color)
        
        if (now % 400) > 200:
            cx = self.cursor_pos % 8
            cy = self.cursor_pos // 8
            self.core.matrix.draw_pixel(cx, cy, Palette.WHITE)
