#File: src/core/modes/main_menu.py
"""Main Menu Mode for Jeb Core."""

import asyncio

from utilities import Palette,tones

from .utility_mode import UtilityMode

class MainMenu(UtilityMode):
    """Main Menu for selecting modes."""
    METADATA = {
        "id": "MAIN_MENU",
        "name": "MAIN MENU",
        "icon": "DEFAULT",
        "requires": ["CORE"],
        "settings": []
    }
    def __init__(self, core):
        super().__init__(core, name="MAIN MENU", description="Select a mode to begin", timeout=10)
        self.state = "DASHBOARD"

    def _build_menu_items(self):
        """Dynamically build menu based on AVAILABLE_MODES and connected hardware.
        
        This method accesses self.core.modes which is a Dict[str, Type[BaseMode]]
        mapping mode IDs to mode classes. Each mode class has a METADATA attribute
        describing its requirements and configuration.
        
        Returns:
            List[Tuple[str, dict]]: List of (mode_id, metadata) tuples for modes
                                     that have their requirements met.
        """
        items = []

        # Sort by name or predefined order if you wish
        # self.core.modes is Dict[mode_id: str, mode_class: Type[BaseMode]]
        for mode_id, mode_class in self.core.modes.items():
            # Access the mode's METADATA class attribute
            # Expected structure documented in BaseMode class
            meta = mode_class.METADATA

            # Skip system modes (like Main Menu itself, or Debug if not needed)
            if mode_id in ["MAIN_MENU", "DASHBOARD"]:
                continue

            # Check requirements
            # meta["requires"] is List[str] of hardware dependencies
            requirements_met = True
            for req in meta.get("requires", []):
                if req == "CORE":
                    continue
                # Check for specific satellite type presence
                # self.core.satellites is Dict[slot_id: int, Satellite]
                # Each Satellite has: sat_type_name (str), is_active (bool), slot_id (int)
                has_sat = any(s.sat_type_name == req for s in self.core.satellites.values())
                if not has_sat:
                    requirements_met = False
                    break

            if requirements_met:
                items.append((mode_id, meta))

        return items

    def _set_state(self, new_state):
        """Helper to switch states and update UI accordingly."""
        self.state = new_state

        if new_state == "DASHBOARD":
            self.set_timeout(None)
            self.core.display.load_view("dashboard")
            self.core.display.update_status("SYSTEM READY", "AWAITING INPUT")
            asyncio.create_task(self.core.matrix.show_icon("DEFAULT", anim="PULSE", speed=3.0))

        elif new_state == "MENU":
            self.set_timeout(30)
            self.core.display.load_view("game_info")
            asyncio.create_task(self.core.matrix.show_icon("MENU", anim="SLIDE_LEFT", speed=2.0))

        elif new_state == "ADMIN":
            self.set_timeout(30)
            self.core.display.load_view("admin")
            self.core.display.update_status("ADMIN CONSOLE", "AUTHORIZED ACCESS")
            asyncio.create_task(self.core.matrix.show_icon("ADMIN", anim="PULSE", speed=2.0))
            self.core.hid.reset_encoder(0)

    async def run(self):
        """Main Menu for selecting modes."""
        self.core.hid.reset_encoder(0)
        last_pos = self.core.hid.encoder_pos
        self._set_state("DASHBOARD")

        # Menu Logic Variables
        menu_items = self._build_menu_items()
        selected_game_idx = 0
        focus_mode = "GAME" # "GAME" (Matrix Select) or "SETTINGS" (OLED Select)
        selected_setting_idx = 0

        while True:
            curr_pos = self.core.hid.encoder_pos

            # --- GLOBAL TIMEOUT CHECK ---
            if self.is_timed_out:
                if self.state != "DASHBOARD":
                    self.core.audio.play(
                        "audio/menu/close.wav",
                        self.core.audio.CH_SFX,
                        level=0.8
                    )
                    self._set_state("DASHBOARD")
                    focus_mode = "GAME"

            # --- INPUT WAKEUP ---
            if curr_pos != last_pos:
                self.touch()

            # =========================================
            # STATE: DASHBOARD (Idle)
            # =========================================
            if self.state == "DASHBOARD":

                # Turn off all button LEDs
                self.core.led.off_led(-1)

                if curr_pos != last_pos or self.core.hid.dial_pressed:
                    menu_items = self._build_menu_items()
                    self._set_state("MENU")
                    last_pos = curr_pos
                    self.core.audio.play(
                        "audio/menu/open.wav",
                        self.core.audio.CH_SFX,
                        level=0.8
                    )
                    continue

            # =========================================
            # STATE: MENU (Game Select & Settings)
            # =========================================
            elif self.state == "MENU":

                # Turn off all button LEDs
                self.core.led.off_led(-1)

                # Add breath effect to 'D' button to indicate it can be used to enter settings
                self.core.led.set_led(
                    index=3,
                    color=Palette.CYAN,
                    anim="BREATH",
                    speed=2.0
                )

                meta = menu_items[selected_game_idx]

                # --- UPDATE DISPLAY ---
                display_settings = []
                for s in meta["settings"]:
                    current_value = self.core.data.get_setting(meta["id"], s["key"], s["default"])
                    display_settings.append({
                        "label": s["label"],
                        "value": str(current_value)
                    })

                # Get High Score
                high_score = self.core.data.get_score(meta["id"])

                self.core.display.update_game_menu(
                    title=meta["name"],
                    score=high_score,
                    settings=display_settings,
                    selected_idx=selected_setting_idx,
                    has_focus=(focus_mode == "SETTINGS")
                )

                # --- INPUT HANDLING ---

                # ENCODER TURN
                if curr_pos != last_pos:

                    # Menu Tick
                    self.core.audio.play(
                        "audio/menu/tick.wav",
                        self.core.audio.CH_SFX,
                        level=0.8
                    )

                    if focus_mode == "GAME":

                        # Cycle Games
                        selected_game_idx = self.core.hid.get_scaled_encoder_pos(
                            multiplier=1.0,
                            wrap=len(menu_items)
                        )

                        # Update Icon
                        asyncio.create_task(
                            self.core.matrix.show_icon(
                                menu_items[selected_game_idx]["icon"],
                                anim="SLIDE_LEFT",
                                speed=2.0
                            )
                        )

                    elif focus_mode == "SETTINGS":

                        # Cycle Settings Row
                        if len(meta["settings"]) > 0:
                            delta = curr_pos - last_pos
                            selected_setting_idx = (selected_setting_idx + delta) % len(meta["settings"])

                    last_pos = curr_pos

                # ENCODER PRESS
                if self.core.hid.dial_pressed:
                    self.touch()

                    if focus_mode == "GAME":
                        # START GAME
                        self.core.audio.play(
                            "audio/menu/power.wav",
                            self.core.audio.CH_SFX,
                            level=0.8
                        )
                        return meta["id"]

                    elif focus_mode == "SETTINGS":
                        # TOGGLE SETTING OPTION
                        self.core.audio.play(
                            "audio/menu/select.wav",
                            self.core.audio.CH_SFX,
                            level=0.8
                        )

                        # Cycle through options for the selected setting
                        if len(meta["settings"]) > 0:
                            setting = meta["settings"][selected_setting_idx]
                            current_value = self.core.data.get_setting(
                                meta["id"],
                                setting["key"],
                                setting["default"]
                            )
                            # Find current index in options and increment
                            try:
                                opt_idx = setting["options"].index(current_value)
                            except ValueError:
                                opt_idx = 0
                            new_idx = (opt_idx + 1) % len(setting["options"])
                            new_value = setting["options"][new_idx]

                            # Save immediately
                            self.core.data.set_setting(meta["id"], setting["key"], new_value)

                # 'D' BUTTON to toggle focus
                if self.core.hid.is_pressed(3, action="tap"):
                    self.touch()
                    if focus_mode == "GAME":
                        if len(meta["settings"]) > 0:
                            focus_mode = "SETTINGS"
                            selected_setting_idx = 0
                            self.core.audio.play(
                                "audio/menu/open.wav",
                                self.core.audio.CH_SFX,
                                level=0.8
                            )
                    elif focus_mode == "SETTINGS":
                        focus_mode = "GAME"
                        self.core.hid.reset_encoder(selected_game_idx)
                        last_pos = selected_game_idx
                        self.core.audio.play(
                            "audio/menu/close.wav",
                            self.core.audio.CH_SFX,
                            level=0.8
                        )

                # Secret Admin Trigger (A + D hold)
                if focus_mode == "GAME" and self.core.hid.is_pressed(0,long=True) and self.core.hid.is_pressed(3,long=True):
                    self.touch()
                    self.core.buzzer.play_song(tones.SECRET_FOUND)
                    self._set_state("ADMIN")

            # =========================================
            # STATE: ADMIN MENU (Work in progress)
            # =========================================
            elif self.state == "ADMIN":

                # Turn off all button LEDs
                self.core.led.off_led(-1)

                # Start a Cylon strobe
                self.core.led.start_cylon(Palette.RED, speed=0.05)

                # Add breath effect to 'B' button to indicate it can be used to exit admin menu
                self.core.led.set_led(
                    index=1,
                    color=Palette.ORANGE,
                    anim="FLASH",
                    speed=2.0
                )

                menu_items = ["Settings", "Debug Dash", "Calibration", "UART Logs", "Reset"]
                menu_keys = ["SETTINGS", "DEBUG", "CALIB", "UARTLOG", "RESET"]

                # Navigation
                if curr_pos != last_pos:
                    admin_idx = self.core.hid.get_scaled_encoder_pos(
                        multiplier=1.0,
                        wrap=len(menu_items)
                    )

                    self.core.display.update_admin_menu(menu_items, admin_idx)
                    self.core.audio.play("audio/menu/tick.wav", self.core.audio.CH_SFX, level=0.8)
                    last_pos = curr_pos

                # Selection
                if self.core.hid.dial_pressed:
                    self.touch()
                    admin_idx = self.core.hid.get_scaled_encoder_pos(
                        multiplier=1.0,
                        wrap=len(menu_items)
                    )
                    self.core.audio.play("audio/menu/select.wav", self.core.audio.CH_SFX, level=0.8)
                    return menu_keys[admin_idx]

                # Back Button (B Button)
                if self.core.hid.is_pressed(1,long=True,duration=2000):
                    self.touch()
                    self.core.audio.play("audio/menu/close.wav", self.core.audio.CH_SFX, level=0.8)
                    self._set_state("DASHBOARD")

            await asyncio.sleep(0.01)
