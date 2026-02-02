#File: src/core/modes/main_menu.py
"""Main Menu Mode for Jeb Core."""

import asyncio

from .utility_mode import UtilityMode

class MainMenu(UtilityMode):
    """Main Menu for selecting modes."""

    def __init__(self, jeb):
        super().__init__(jeb, name="MAIN MENU", description="Select a mode to begin", timeout=10)
        self.state = "DASHBOARD"

    def _set_state(self, new_state):
        """Helper to switch states and update UI accordingly."""
        self.state = new_state

        if new_state == "DASHBOARD":
            self.set_timeout(None)
            self.jeb.display.load_view("dashboard")
            self.jeb.display.update_status("SYSTEM READY", "AWAITING INPUT")
            asyncio.create_task(self.jeb.matrix.show_icon("DEFAULT", anim="PULSE", speed=3.0))

        elif new_state == "MENU":
            self.set_timeout(10)
            self.jeb.display.load_view("menu")
            self.jeb.display.update_status("MAIN MENU", "TURN DIAL TO SELECT")
            asyncio.create_task(self.jeb.matrix.show_icon("MENU", anim="SLIDE_LEFT", speed=2.0))

        elif new_state == "ADMIN":
            self.set_timeout(30)
            self.jeb.display.load_view("admin")
            self.jeb.display.update_status("ADMIN CONSOLE", "AUTHORIZED ACCESS")
            asyncio.create_task(self.jeb.matrix.show_icon("ADMIN", anim="PULSE", speed=2.0))
            self.jeb.hid.reset_encoder(0)

    async def run(self):
        """Main Menu for selecting modes."""

        self.jeb.hid.reset_encoder(0)
        last_pos = self.jeb.hid.encoder_pos

        self._set_state("DASHBOARD")

        while True:
            curr_pos = self.jeb.hid.encoder_pos

            # --- GLOBAL TIMEOUT CHECK ---
            if self.is_timed_out:
                if self.state in ["MENU", "ADMIN"]:
                    self.jeb.audio.play("audio/menu/close.wav", self.jeb.audio.CH_SFX, level=0.8)
                    self._set_state("DASHBOARD")

            # --- INPUT HANDLING ---
            # Any movement or button press resets the timer via self.touch()
            if curr_pos != last_pos:
                self.touch()

            # --- STATE LOGIC ---
            if self.state == "DASHBOARD":
                if curr_pos != last_pos or self.jeb.hid.dial_pressed:
                    self.touch()
                    last_pos = curr_pos
                    self._set_state("MENU")
                    self.jeb.audio.play("audio/menu/open.wav", self.jeb.audio.CH_SFX, level=0.8)
                    continue

            elif self.state == "MENU":
                # Core module modes
                modes = [
                    ["SIMON", "SIMON"],
                    ["SAFE CRACKER", "SAFE"]
                ]

                # Dynamically add modes based on what is actually plugged in
                for sid, sat in self.jeb.satellites.items():
                    if sat.type == "INDUSTRIAL":
                        if not any(m[1] == "IND" for m in modes):
                            modes.append(["INDUSTRIAL STARTUP", "IND"])

                # Navigation
                if curr_pos != last_pos:
                    menu_idx = self.jeb.hid.get_scaled_pos(multiplier=1.0, wrap=len(modes))

                    self.jeb.display.update_status(f"{modes[menu_idx][0]}","PRESS TO SELECT")
                    await self.jeb.matrix.show_icon(modes[menu_idx][1], anim="SLIDE_LEFT", speed=2.0)

                    self.jeb.audio.play("audio/menu/tick.wav", self.jeb.audio.CH_SFX, level=0.8)
                    last_pos = curr_pos

                # Selection
                if self.jeb.hid.dial_pressed:
                    self.touch()
                    menu_idx = self.jeb.hid.get_scaled_encoder_pos(multiplier=1.0, wrap=len(modes))
                    self.jeb.audio.play("audio/menu/power.wav", self.jeb.audio.CH_SFX, level=0.8)
                    # TODO Play Selection animation
                    return modes[menu_idx][1]

                # Secret Admin Trigger (A + D hold)
                if self.jeb.hid.is_pressed(0,long=True) and self.jeb.hid.is_pressed(3,long=True):
                    self.touch()
                    self.jeb.audio.play("audio/menu/open.wav", self.jeb.audio.CH_SFX, level=0.8)
                    self._set_state("ADMIN")

            # Menu State - ADMIN
            elif self.state == "ADMIN":
                menu_items = ["Settings", "Debug Dash", "Calibration", "UART Logs", "Reset"]
                menu_keys = ["SETTINGS", "DEBUG", "CALIB", "UARTLOG", "RESET"]

                # Navigation
                if curr_pos != last_pos:
                    admin_idx = self.jeb.hid.get_scaled_encoder_pos(multiplier=1.0, wrap=len(menu_items))

                    self.jeb.display.update_admin_menu(menu_items, admin_idx)
                    self.jeb.audio.play("audio/menu/tick.wav", self.jeb.audio.CH_SFX, level=0.8)
                    last_pos = curr_pos

                # Selection
                if self.jeb.hid.dial_pressed:
                    self.touch()
                    admin_idx = self.jeb.hid.get_scaled_encoder_pos(multiplier=1.0, wrap=len(menu_items))
                    self.jeb.audio.play("audio/menu/select.wav", self.jeb.audio.CH_SFX, level=0.8)
                    return menu_keys[admin_idx]

                # Back Button (B Button)
                if self.jeb.hid.is_pressed(1,long=True,duration=2000):
                    self.touch()
                    self.jeb.audio.play("audio/menu/close.wav", self.jeb.audio.CH_SFX, level=0.8)
                    self._set_state("DASHBOARD")

            await asyncio.sleep(0.01)
