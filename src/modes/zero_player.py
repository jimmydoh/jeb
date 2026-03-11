"""Lightweight wrapper for holding the Zero Player mode's tutorial"""

import asyncio
import random

from utilities.palette import Palette
from utilities import tones
from .game_mode import GameMode

class ZeroPlayerMode(GameMode):
    def __init__(self, core):
        super().__init__(core, "ZERO PLAYER", "Zero Player Menu Item")

    async def run_tutorial(self):
        """
        A guided demonstration of universal Zero Player mode controls.

        The Voiceover Script (audio/tutes/zero_tute.wav) ~ 31 seconds:
            [0:00] "Welcome to the Zero Player collection."
            [0:04] "These modes are passive visualizers, perfect for leaving on your desk."
            [0:09] "While they run, you can turn the dial to adjust the simulation speed."
            [0:15] "Keep an eye on the screen footer. Physical buttons can be used to change colors or patterns."
            [0:22] "When you are ready to return to the main menu, simply press and hold the dial."
            [0:28] "Sit back, relax, and enjoy the show!"
            [0:31] (End of file)
        """
        await self.core.clean_slate()
        self.game_state = "TUTORIAL"

        # 1. Start the voiceover track
        self.core.audio.play("audio/tutes/zero_tute.wav", bus_id=self.core.audio.CH_VOICE)

        # Setup a simple mock particle system (Starfield-lite)
        particles = [
            [random.uniform(0, 15), random.uniform(0, 15),
             random.choice([-1, 1]) * random.uniform(0.2, 0.5),
             random.choice([-1, 1]) * random.uniform(0.2, 0.5)]
            for _ in range(12)
        ]

        async def render_particles(duration, speed_mult=1.0, color=Palette.CYAN):
            """Helper to run the mock visualizer for a set duration."""
            frames = int(duration / 0.05)
            for _ in range(frames):
                self.core.matrix.clear()
                for p in particles:
                    p[0] = (p[0] + p[2] * speed_mult) % 16
                    p[1] = (p[1] + p[3] * speed_mult) % 16
                    self.core.matrix.draw_pixel(int(p[0]), int(p[1]), color, show=False)
                self.core.matrix.show_frame()
                await asyncio.sleep(0.05)

        # [0:00 - 0:04] "Welcome to the Zero Player collection."
        self.core.display.update_header("-ZERO PLAYER-")
        self.core.display.update_status("PASSIVE VISUALIZERS", "")
        await render_particles(4.0, speed_mult=1.0)

        # [0:04 - 0:09] "These modes are passive visualizers..."
        self.core.display.update_status("SIT BACK & RELAX", "NO INPUT REQUIRED")
        await render_particles(5.0, speed_mult=1.0)

        # [0:09 - 0:15] "While they run, you can turn the dial to adjust the simulation speed."
        self.core.display.update_status("SIMULATION SPEED", "TURN DIAL TO ADJUST")

        # Puppeteer the speed increasing, complete with UI tick sounds
        for speed_step in range(1, 5):
            self.core.display.update_footer(f"SPEED: {speed_step}x")
            self.core.buzzer.play_sequence(tones.UI_TICK)
            await render_particles(1.5, speed_mult=speed_step)

        # [0:15 - 0:22] "Keep an eye on the screen footer. Physical buttons can be used..."
        self.core.display.update_status("MODE SETTINGS", "PRESS BUTTONS")
        self.core.display.update_footer("B1: PALETTE | B2: SHAPE")

        # Flash B1 LED to guide the player's eye
        if hasattr(self.core.leds, 'flash_led'):
            self.core.leds.flash_led(0, Palette.MAGENTA, duration=2.0, speed=0.2)

        await render_particles(2.0, speed_mult=2.0)

        # Simulate pressing B1 to change the palette
        self.core.buzzer.play_sequence(tones.UI_CONFIRM)
        self.core.display.update_footer("PALETTE: MAGENTA")
        await render_particles(4.0, speed_mult=2.0, color=Palette.MAGENTA)

        # [0:22 - 0:28] "When you are ready to return to the main menu, simply press and hold..."
        self.core.display.update_status("EXIT VISUALIZER", "HOLD DIAL TO EXIT")
        self.core.display.update_footer("")

        # Simulate the "Hold to Exit" progress bar filling up
        await render_particles(2.0, speed_mult=1.0, color=Palette.MAGENTA)
        self.core.buzzer.play_sequence(tones.UI_TICK)
        self.core.display.update_footer("EXITING.  ")
        await render_particles(1.0, speed_mult=0.5, color=Palette.MAGENTA)

        self.core.buzzer.play_sequence(tones.UI_TICK)
        self.core.display.update_footer("EXITING.. ")
        await render_particles(1.0, speed_mult=0.2, color=Palette.MAGENTA)

        self.core.buzzer.play_sequence(tones.UI_CONFIRM)
        self.core.display.update_footer("EXITING...")
        await render_particles(2.0, speed_mult=0.0, color=Palette.MAGENTA) # Freeze frame

        # [0:28 - 0:31] "Sit back, relax, and enjoy the show!"
        self.core.display.update_status("ENJOY THE SHOW", "")
        self.core.display.update_footer("")

        # Clean up and return to the menu
        await self.core.clean_slate()
        return "TUTORIAL_COMPLETE"

    async def run(self):
        """This will never be called natively, as the menu traps the encoder press."""
        pass
