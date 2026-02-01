"""Main Menu Mode for Jeb Core."""

import time
import asyncio

class MainMenu:
    """Main Menu for selecting modes."""

    def __init__(self, jeb):
        self.name = "MAIN MENU"
        self.description = "Select a mode to begin"
        self.jeb = jeb

    async def run(self):
        """Main Menu for selecting modes."""
        self.jeb.mode = "DASHBOARD"
        self.jeb.hid.reset_encoder(0)
        last_pos = self.jeb.hid.encoder_pos
        curr_pos = 0
        last_interaction = time.monotonic()

        while True:
            curr_pos = self.jeb.hid.encoder_pos
            now = time.monotonic()

            # Default State - DASHBOARD
            if self.jeb.mode == "DASHBOARD":
                self.jeb.display.load_view("dashboard")
                self.jeb.display.update_status("SYSTEM READY", "AWAITING INPUT")
                await self.jeb.matrix.show_icon("DEFAULT", anim="PULSE", speed=3.0)

                # If the user turns the dial or presses the button, switch to Menu layout
                if (curr_pos != last_pos or self.jeb.hid.dial_pressed):
                    last_interaction = now
                    last_pos = curr_pos
                    if not in_menu:
                        in_menu = True
                        self.jeb.mode = "MENU"
                        self.jeb.display.load_view("menu")
                        self.jeb.audio.play_sfx("menu_open.wav")
                        continue

            # Menu State - MENU
            elif self.jeb.mode == "MENU":
                # Core module modes
                modes = [
                    ["SIMON CORE", "SIMON"],
                    ["SAFE CRACKER", "SAFE"]
                ]
                # Dynamically add modes based on what is actually plugged in
                for sid, sat in self.jeb.satellites.items():
                    if sat.type == "INDUSTRIAL":
                        # Only add if not already in the list
                        if not any(m[1] == "IND" for m in modes):
                            modes.append(["INDUSTRIAL STARTUP", "IND"])

                # Handle Navigation (Rotation)
                if curr_pos != last_pos:
                    menu_idx = self.jeb.hid.get_scaled_pos(multiplier=1.0, wrap=len(modes))
                    self.jeb.display.update_status(f"{modes[menu_idx][0]}","PRESS TO SELECT")
                    await self.jeb.matrix.show_icon(modes[menu_idx][1], anim="SLIDE_LEFT", speed=2.0)
                    last_pos = curr_pos
                    last_interaction = now
                    self.jeb.audio.play_sfx("menu_tick.wav") # Feedback for movement
                    continue

                # Handle Selection (Button Press)
                if self.jeb.hid.is_pressed(4,long=True,duration=500):
                    self.jeb.audio.play_sfx("menu_power.wav")
                    # TODO Play Selection animation
                    return modes[curr_pos][1]

                # Handle Idle Timeout (10 Seconds)
                if now - last_interaction > 10.0:
                    self.jeb.mode = "DASHBOARD"
                    continue

                # Secret Admin Trigger (A + D hold)
                if self.jeb.hid.is_pressed(0,long=True,duration=2000) and self.jeb.hid.is_pressed(3,long=True,duration=2000):
                    self.jeb.mode = "ADMIN"
                    self.jeb.display.load_view("admin")
                    self.jeb.display.update_status("ADMIN CONSOLE", "AUTHORIZED ACCESS")
                    self.jeb.audio.play_sfx("menu_open.wav")
                    # TODO Pulsing Matrix animation for admin mode
                    continue

            # Menu State - ADMIN
            elif self.jeb.mode == "ADMIN":
                menu_items = ["Settings", "Debug Dash", "Calibration", "UART Logs", "Reset"]
                menu_keys = ["SETTINGS", "DEBUG", "CALIB", "UARTLOG", "RESET"]
                admin_idx = 0

                # Handle Admin Navigation (Rotation)
                if curr_pos != last_pos:
                    diff = curr_pos - last_pos
                    admin_idx = (admin_idx + diff) % len(menu_items)
                    last_pos = curr_pos
                    last_interaction = now
                    self.jeb.display.update_admin_menu(menu_items, admin_idx)
                    self.jeb.audio.play_sfx("menu_tick.wav")
                    continue

                # Handle Selection (Button Press)
                if self.jeb.hid.dial_pressed:
                    self.jeb.audio.play_sfx("menu_select.wav")
                    # TODO Play Selection animation
                    return menu_keys[admin_idx]

                # Handle Exit (Long Press B)
                if self.jeb.hid.is_pressed(1,long=True,duration=2000):
                    self.jeb.audio.play_sfx("menu_close.wav")
                    self.jeb.mode = "DASHBOARD"
                    self.jeb.display.load_view("dashboard")
                    continue

                # Handle Admin Idle Timeout (30 Seconds)
                if now - last_interaction > 30.0:
                    self.jeb.mode = "DASHBOARD"
                    self.jeb.display.load_view("dashboard")
                    continue

            await asyncio.sleep(0.01)
