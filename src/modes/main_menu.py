#File: src/core/modes/main_menu.py
"""Main Menu Mode for Jeb Core."""

import asyncio

from utilities.palette import Palette
from utilities import tones

from .utility_mode import UtilityMode

class MainMenu(UtilityMode):
    """Main Menu for selecting modes."""
    def __init__(self, core):
        super().__init__(core, name="MAIN MENU", description="Select a mode to begin", timeout=10)
        self.state = "DASHBOARD"

    def _build_menu_items(self, menu="MAIN"):
        """Dynamically build menu based on mode registry and connected hardware.

        This method accesses self.core.mode_registry which is a Dict[str, dict]
        mapping mode IDs to metadata dictionaries. Each metadata dict contains
        module_path, class_name, requirements, settings, and other configuration.
        Mode classes are lazily loaded via _load_mode_class() when needed.

        Returns:
            List[str]: List of mode_id strings for modes that have their requirements met.
        """
        items = []

        # Sort by name or predefined order if you wish
        # self.core.mode_registry is Dict[mode_id: str, metadata: dict]
        for mode_id, meta in self.core.mode_registry.items():

            # Skip modes that don't belong to the current menu context (if using menu categories)
            if "menu" not in meta or meta["menu"] != menu:
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
                items.append(mode_id)

        return items

    def _set_state(self, new_state):
        """Helper to switch states and update UI accordingly."""
        self.state = new_state

        if new_state == "DASHBOARD":
            self.set_timeout(None)
            self.core.display.update_status("SYSTEM READY", "AWAITING INPUT")
            self.core.matrix.show_icon("DEFAULT")

        elif new_state == "MENU":
            self.set_timeout(30)

        elif new_state == "ADMIN":
            self.set_timeout(30)
            self.core.display.update_status("ADMIN CONSOLE", "AUTHORIZED ACCESS")
            self.core.matrix.show_icon("ADMIN")
            self.core.hid.reset_encoder(0)

    async def run(self):
        """Main Menu for selecting modes."""
        self.core.hid.flush() # Ensure no ghost inputs from previous modes
        self.core.hid.reset_encoder(0)

        # Set all Satellites to idle state (if applicable)
        for sat in self.core.satellites.values():
            sat.send("MODE", "IDLE")

        # UI State Variables
        self._set_state("DASHBOARD")
        focus_mode = "GAME" # "GAME" or "SETTINGS"

        # Data Variables
        menu_items = self._build_menu_items()
        admin_items = self._build_menu_items("ADMIN")
        selected_game_idx = 0
        selected_setting_idx = 0

        # Satellite topology tracking for hot-plug detection
        last_sat_keys = frozenset(self.core.satellites.keys())

        # Render Tracking (Prevents unnecessary screen updates)
        self.core.display.use_standard_layout()
        needs_render = True
        last_rendered_game = -1
        last_rendered_setting = -1
        last_rendered_admin = -1
        last_rendered_state = None
        last_rendered_focus = None
        slide_direction = "SLIDE_LEFT"

        # Turn off all button LEDs
        self.core.leds.off_led(-1)

        last_pos = 0

        while True:
            # =========================================
            # 1. GATHER INPUTS
            # =========================================
            curr_pos = self.core.hid.encoder_position()
            encoder_diff = curr_pos - last_pos
            encoder_pressed = self.core.hid.is_encoder_button_pressed(action="tap")
            btn_d_pressed = self.core.hid.is_button_pressed(3, action="tap")
            btn_a_long = self.core.hid.is_button_pressed(0, long=True)
            btn_d_long = self.core.hid.is_button_pressed(3, long=True)
            btn_b_long = self.core.hid.is_button_pressed(1, long=True, duration=2000)

            # --- GLOBAL TIMEOUT CHECK ---
            if self.is_timed_out and self.state != "DASHBOARD":
                self.core.leds.off_led(-1)
                await self.core.audio.play("audio/menu/close.wav", self.core.audio.CH_SFX, level=0.8)
                self._set_state("DASHBOARD")
                focus_mode = "GAME"
                needs_render = True

            # --- SATELLITE TOPOLOGY CHECK ---
            # Detect hot-plugged satellites and refresh menu items in-place
            curr_sat_keys = frozenset(self.core.satellites.keys())
            if curr_sat_keys != last_sat_keys:
                last_sat_keys = curr_sat_keys
                menu_items = self._build_menu_items()
                admin_items = self._build_menu_items("ADMIN")
                if menu_items and selected_game_idx >= len(menu_items):
                    selected_game_idx = len(menu_items) - 1
                needs_render = True

            # =========================================
            # 2. PROCESS STATE & LOGIC
            # =========================================

            # --- DASHBOARD STATE ---
            if self.state == "DASHBOARD":
                if encoder_diff != 0 or encoder_pressed:
                    self.touch()
                    menu_items = self._build_menu_items()
                    self._set_state("MENU")
                    needs_render = True
                    await self.core.audio.play("audio/menu/open.wav", self.core.audio.CH_SFX, level=0.8)

                    # Prepare hardware for MENU state
                    self.core.hid.reset_encoder(selected_game_idx)
                    curr_pos = selected_game_idx
                    self.core.leds.set_led(3, color=Palette.CYAN, anim="BREATH", speed=0.5)

            # --- ADMIN STATE ---
            elif self.state == "ADMIN":
                admin_idx = curr_pos % len(admin_items) if admin_items else 0

                if encoder_diff != 0:
                    self.touch()
                    slide_direction = "SLIDE_LEFT" if encoder_diff > 0 else "SLIDE_RIGHT"
                    await self.core.audio.play("audio/menu/tick.wav", self.core.audio.CH_SFX, level=0.8)
                    needs_render = True

                if encoder_pressed and admin_items:
                    self.touch()
                    await self.core.audio.play("audio/menu/select.wav", self.core.audio.CH_SFX, level=0.8)
                    self.core.mode = admin_items[admin_idx]
                    return "SUCCESS"

                if btn_b_long:
                    self.touch()
                    await self.core.audio.play("audio/menu/close.wav", self.core.audio.CH_SFX, level=0.8)
                    self._set_state("DASHBOARD")
                    self.core.leds.stop_cylon()
                    self.core.leds.off_led(-1)
                    needs_render = True

            # --- MENU STATE ---
            elif self.state == "MENU":
                # Check for Admin transition
                if focus_mode == "GAME" and btn_a_long and btn_d_long:
                    self.touch()
                    self.core.buzzer.play_sequence(tones.SECRET_FOUND)
                    self._set_state("ADMIN")
                    print("DEBUG: Entering Admin Menu")
                    self.core.leds.off_led(-1)
                    self.core.leds.start_cylon(Palette.RED, speed=0.05)
                    self.core.leds.set_led(1, color=Palette.ORANGE, anim="FLASH", speed=2.0)
                    needs_render = True
                    continue

                # Handle Focus Toggle ('D' Button)
                if btn_d_pressed:
                    self.touch()
                    if focus_mode == "GAME":
                        # Only enter settings if the current game HAS settings
                        current_game = menu_items[selected_game_idx]
                        if len(self.core.mode_registry[current_game].get("settings", [])) > 0:
                            focus_mode = "SETTINGS"
                            selected_setting_idx = 0
                            self.core.hid.reset_encoder(0)
                            curr_pos = 0
                            await self.core.audio.play("audio/menu/open.wav", self.core.audio.CH_SFX, level=0.8)
                            needs_render = True
                    else: # Exiting Settings
                        focus_mode = "GAME"
                        self.core.hid.reset_encoder(selected_game_idx)
                        curr_pos = selected_game_idx
                        await self.core.audio.play("audio/menu/close.wav", self.core.audio.CH_SFX, level=0.8)
                        needs_render = True

                # Handle GAME Focus Logic
                if focus_mode == "GAME":
                    if encoder_diff != 0:
                        self.touch()
                        slide_direction = "SLIDE_LEFT" if encoder_diff > 0 else "SLIDE_RIGHT"
                        selected_game_idx = curr_pos % len(menu_items)
                        await self.core.audio.play("audio/menu/tick.wav", self.core.audio.CH_SFX, level=0.8)
                        needs_render = True

                    if encoder_pressed:
                        self.touch()
                        await self.core.audio.play("audio/menu/power.wav", self.core.audio.CH_SFX, level=0.8)
                        self.core.mode = menu_items[selected_game_idx]
                        return "SUCCESS"

                # Handle SETTINGS Focus Logic
                elif focus_mode == "SETTINGS":
                    current_game = menu_items[selected_game_idx]
                    mode_meta = self.core.mode_registry[current_game]
                    mode_settings = mode_meta.get("settings", [])

                    if len(mode_settings) > 0:
                        if encoder_diff != 0:
                            self.touch()
                            selected_setting_idx = curr_pos % len(mode_settings)
                            await self.core.audio.play("audio/menu/tick.wav", self.core.audio.CH_SFX, level=0.8)
                            needs_render = True

                        if encoder_pressed:
                            self.touch()
                            setting = mode_settings[selected_setting_idx]
                            # Toggle Logic
                            current_val = self.core.data.get_setting(mode_meta["id"], setting["key"], setting["default"])
                            try:
                                opt_idx = setting["options"].index(current_val)
                            except ValueError:
                                opt_idx = 0
                            new_idx = (opt_idx + 1) % len(setting["options"])
                            new_value = setting["options"][new_idx]

                            self.core.data.set_setting(mode_meta["id"], setting["key"], new_value)
                            await self.core.audio.play("audio/menu/select.wav", self.core.audio.CH_SFX, level=0.8)
                            needs_render = True

            # =========================================
            # 3. RENDER STAGE
            # =========================================
            # Only push updates to hardware if something visually changed!
            if needs_render or self.state != last_rendered_state or focus_mode != last_rendered_focus:

                if self.state == "DASHBOARD":
                    self.core.display.use_standard_layout()
                    self.core.display.update_header("JADNET Electronics Box")
                    self.core.display.update_status("SYSTEM READY", "Push encoder to begin")
                    self.core.display.update_footer("")
                    self.core.matrix.clear()

                elif self.state == "ADMIN":
                    admin_idx = curr_pos % len(admin_items) if admin_items else 0

                    self.core.display.use_standard_layout()
                    self.core.display.update_header("- ADMIN MODE -")

                    if admin_items:
                        mode_id = admin_items[admin_idx]
                        mode_meta = self.core.mode_registry[mode_id]
                        self.core.display.update_status(f"> {mode_meta['name']} <", "Push to Select")
                        self.core.display.update_footer("Hold 'W' to Exit")

                        # Only re-trigger the slide animation if the admin mode actually changed
                        if admin_idx != last_rendered_admin:
                            self.core.matrix.show_icon(mode_meta["icon"], anim_mode=slide_direction, speed=2.0)
                        last_rendered_admin = admin_idx
                    else:
                        self.core.display.update_status("NO ADMIN MODES", "Hold 'W' to Exit")
                        self.core.display.update_footer("WARNING: System Override")
                        self.core.matrix.show_icon("WARNING")

                elif self.state == "MENU":
                    mode_id = menu_items[selected_game_idx]
                    mode_meta = self.core.mode_registry[mode_id]

                    if focus_mode == "GAME":
                        self.core.display.update_header(f"-{mode_meta['name']}-")
                        high_score = self.core.data.get_high_score(mode_id)
                        self.core.display.update_status(f"HIGH SCORE: {high_score}", "Push to Select")
                        self.core.display.show_settings_menu(False)
                        settings_hint = "Press 'D' for Settings" if len(mode_meta.get("settings", [])) > 0 else ""
                        self.core.display.update_footer(settings_hint)

                        # Only re-trigger the slide animation if the game actually changed
                        if selected_game_idx != last_rendered_game:
                            self.core.matrix.show_icon(mode_meta["icon"], anim_mode=slide_direction, speed=2.0)

                        last_rendered_game = selected_game_idx

                    elif focus_mode == "SETTINGS":
                        mode_settings = mode_meta.get("settings", [])
                        settings_strings = []
                        for s in mode_settings:
                            val = self.core.data.get_setting(mode_meta["id"], s["key"], s["default"])
                            settings_strings.append(f"{s['label']}: {val}")

                        self.core.display.update_header(f"-{mode_meta['name']}- SETTINGS")
                        self.core.display.update_settings_menu(settings_strings, selected_setting_idx)
                        self.core.display.update_footer("Press 'D' to Exit")

                        last_rendered_setting = selected_setting_idx

                    last_rendered_focus = focus_mode

                # Update tracking variables
                needs_render = False
                last_rendered_state = self.state

            last_pos = curr_pos

            await asyncio.sleep(0.01)
