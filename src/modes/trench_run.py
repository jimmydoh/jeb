"""Trench Run Game Mode - Endless Sci-Fi runner for 16x16 LED Matrix."""

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

    # Matrix dimensions
    MATRIX_WIDTH = 16
    MATRIX_HEIGHT = 16

    def __init__(self, core):
        super().__init__(core, "TRENCH RUN", "Endless Space Dodger")

        self.player_pos = self.MATRIX_WIDTH // 2

        # Walls are stored as dicts: {'y': float, 'gap_x': int}
        self.walls = []

        self.base_speed = 0.04
        self.current_speed = self.base_speed
        self.gap_width = 3
        self.wall_spacing = 4.0  # Vertical space between spawned walls

    async def run_tutorial(self):
        """
        A guided, non-interactive demonstration of Trench Run.

        The Voiceover Script (audio/tutes/trench_tute.wav) ~ 31 seconds:
            [0:00] "Welcome to Trench Run. A high-speed test of survival."
            [0:04] "Turn the dial to maneuver your ship through the gaps in the approaching walls."
            [0:10] "In third-person mode, your ship moves horizontally across the bottom of the screen."
            [0:15] "Press Button One at any time to seamlessly switch to first-person mode."
            [0:19] "In this view, your ship is locked in the center, and the entire trench rotates around you!"
            [0:25] "The trench will accelerate the further you go. Try to survive as long as possible."
            [0:31] (End of file)
        """
        await self.core.clean_slate()
        self.game_state = "TUTORIAL"

        # 1. Start the voiceover track
        tute_audio = asyncio.create_task(
            self.core.audio.play("audio/tutes/trench_tute.wav", bus_id=self.core.audio.CH_VOICE)
        )

        # Initial Setup (Slow speed, wide gaps)
        self.base_speed = 0.05
        self.current_speed = self.base_speed
        self.gap_width = 3
        self.wall_spacing = 6.0
        self.perspective = "3RD_PERSON"
        self.player_pos = 8
        self.walls.clear()

        # Pre-seed a few walls for the demo
        self.walls.append({'y': 0.0, 'gap_x': 8})
        self.walls.append({'y': -6.0, 'gap_x': 12})
        self.walls.append({'y': -12.0, 'gap_x': 3})

        # [0:00 - 0:04] "Welcome to Trench Run..."
        self.core.display.update_status("TRENCH RUN", "HIGH SPEED SURVIVAL")
        self.render()
        self.core.matrix.show_frame()
        await asyncio.sleep(4.0)

        # [0:04 - 0:10] "Turn the dial to maneuver your ship..."
        self.core.display.update_status("TRENCH RUN", "TURN DIAL TO DODGE")

        # Run physics for a few seconds to let the walls drop
        for _ in range(120): # ~2 seconds at 60fps
            for wall in self.walls:
                wall['y'] += self.current_speed
            self.render()
            self.core.matrix.show_frame()
            await asyncio.sleep(0.016)

        # [0:10 - 0:15] "In third-person mode, your ship moves..."
        self.core.display.update_status("PERSPECTIVE", "3RD PERSON VIEW")

        # Puppeteer the ship dodging the remaining walls
        # Move right to gap 12
        for pos in range(8, 14):
            self.player_pos = pos
            for wall in self.walls: wall['y'] += self.current_speed
            self.render()
            self.core.matrix.show_frame()
            await asyncio.sleep(0.08)

        # Wait for wall to pass
        for _ in range(60):
            for wall in self.walls: wall['y'] += self.current_speed
            self.render()
            self.core.matrix.show_frame()
            await asyncio.sleep(0.016)

        # Move left to gap 3
        for pos in range(13, 2, -1):
            self.player_pos = pos
            for wall in self.walls: wall['y'] += self.current_speed
            self.render()
            self.core.matrix.show_frame()
            await asyncio.sleep(0.05)

        await asyncio.sleep(1.0)

        # [0:15 - 0:19] "Press Button One at any time to seamlessly switch..."
        self.core.display.update_status("PERSPECTIVE", "PRESS B1 TO SWITCH")

        # Flash B1 LED to guide the player
        self.core.leds.flash_led(0, Palette.CYAN, duration=1.5)
        await asyncio.sleep(1.0)

        # Reset the walls, switch perspective, and play the toggle sound
        self.walls.clear()
        self.walls.append({'y': 0.0, 'gap_x': 8})
        self.walls.append({'y': -6.0, 'gap_x': 12})
        self.walls.append({'y': -12.0, 'gap_x': 3})

        self.perspective = "1ST_PERSON"
        self.player_pos = 8
        self.core.buzzer.play_sequence(tones.UI_TICK)

        # [0:19 - 0:25] "In this view, your ship is locked in the center..."
        # Run the exact same dodging sequence, but rendered in 1st person!
        for _ in range(120):
            for wall in self.walls: wall['y'] += self.current_speed
            self.render()
            self.core.matrix.show_frame()
            await asyncio.sleep(0.016)

        for pos in range(8, 14):
            self.player_pos = pos
            for wall in self.walls: wall['y'] += self.current_speed
            self.render()
            self.core.matrix.show_frame()
            await asyncio.sleep(0.08)

        for _ in range(60):
            for wall in self.walls: wall['y'] += self.current_speed
            self.render()
            self.core.matrix.show_frame()
            await asyncio.sleep(0.016)

        for pos in range(13, 2, -1):
            self.player_pos = pos
            for wall in self.walls: wall['y'] += self.current_speed
            self.render()
            self.core.matrix.show_frame()
            await asyncio.sleep(0.05)

        # [0:25 - 0:31] "The trench will accelerate... Try to survive..."
        self.core.display.update_status("TRENCH RUN", "SPEED INCREASES!")

        # Demonstrate the speed up
        self.current_speed = 0.15 # Turbo speed!
        self.walls.clear()
        for i in range(5):
             self.walls.append({'y': -(i*4.0), 'gap_x': random.randint(0, 15)})

        for _ in range(150):
            for wall in self.walls: wall['y'] += self.current_speed
            self.render()
            self.core.matrix.show_frame()
            await asyncio.sleep(0.016)

        # Wait for the audio track to finish naturally
        await tute_audio

        # Clean up and return to the menu
        await self.core.clean_slate()
        return "TUTORIAL_COMPLETE"

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
        self.core.display.update_status("TRENCH RUN", f"VIEW: {self.perspective}")
        self.core.display.update_footer("B1: TOGGLE VIEW")
        asyncio.create_task(self.core.synth.play_sequence(tones.POWER_UP, patch="SCANNER"))
        await asyncio.sleep(2.0)

        self.core.hid.reset_encoder(0)
        self.score = 0
        self.level = 1
        self.walls.clear()
        self.drone_freq = 80.0 + (self.level * 2.0)  # Cache drone frequency

        # Spawn the first wall off-screen
        self.spawn_wall(y_start=-1.0)

        last_tick = ticks_ms()
        game_running = True

        while game_running:
            now = ticks_ms()
            delta_ms = ticks_diff(now, last_tick)

            if delta_ms >= 16:  # ~60 FPS Target

                # --- NEW: Perspective Toggle via Button 1 (B1) ---
                if self.core.hid.is_button_pressed(0, action="tap"):
                    # Toggle the state
                    self.perspective = "1ST_PERSON" if self.perspective == "3RD_PERSON" else "3RD_PERSON"

                    # Persist the setting so it remembers their preference next time
                    self.core.data.set_setting("TRENCH_RUN", "perspective", self.perspective)

                    # Update the variant so high scores are tracked for the view they finish in
                    self.variant = f"{self.perspective}_{self.difficulty}"

                    # Give audio/visual feedback of the change
                    self.core.display.update_status("TRENCH RUN", f"VIEW: {self.perspective}")
                    self.core.buzzer.play_sequence(tones.UI_TICK)
                # -------------------------------------------------

                self.update_player()
                crashed = self.update_walls()

                if crashed:
                    # Explode and end game
                    self.core.matrix.fill(Palette.WHITE)
                    asyncio.create_task(self.core.synth.play_sequence(tones.GAME_OVER))
                    await asyncio.sleep(0.1)
                    return await self.game_over()

                self.core.display.update_status(f"SCORE: {self.score}", f"SPEED: {self.level}")
                self.render()

                # Engine drone that pitches up slightly as you speed up
                self.core.synth.play_note(self.drone_freq, "ENGINE_HUM", duration=0.05)

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

            collision_row = self.MATRIX_HEIGHT - 2
            if old_y_int < collision_row and new_y_int >= collision_row:
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
                        self.drone_freq = 80.0 + (self.level * 2.0)  # Update drone frequency when level changes
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
                    render_gap = (wall['gap_x'] - self.player_pos + self.MATRIX_WIDTH // 2) % self.MATRIX_WIDTH

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
            # Ship is anchored in the center
            self.core.matrix.draw_pixel(self.MATRIX_WIDTH // 2, self.MATRIX_HEIGHT - 1, Palette.CYAN)
