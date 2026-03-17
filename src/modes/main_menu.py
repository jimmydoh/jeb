#File: src/core/modes/main_menu.py
"""Main Menu Mode for Jeb Core."""

import asyncio

from utilities.palette import Palette
from utilities import tones
from utilities.logger import JEBLogger

from .utility_mode import UtilityMode

class MainMenu(UtilityMode):
    """Main Menu for selecting modes."""
    def __init__(self, core):
        """Initialize Main Menu mode."""
        JEBLogger.info("MENU", "[INIT] MainMenu")
        super().__init__(core, name="MAIN MENU", description="Select a mode to begin", exitable=False, timeout=10)
        self.state = "DASHBOARD"

    async def enter(self):
        """Override base setup to prevent clearing the boot logo."""
        self.core.audio.stop_all()
        self.core.hid.flush()
        # We explicitly omit self.core.matrix.clear() here to keep the boot logo!
        self.core.display.update_status("MAIN MENU", "LOADING...")
        await asyncio.sleep(0.1)

    _CATEGORY_TITLES = {
        "CORE": "[ CORE GAMES ]",
        "EXP1": "[ EXPANSION 1 ]",
        "ZERO": "[ ZERO PLAYER ]",
    }

    def _build_menu_items(self, menu="CORE"):
        """Dynamically build menu based on mode registry and connected hardware.

        This method accesses self.core.mode_registry which is a Dict[str, dict]
        mapping mode IDs to metadata dictionaries. Each metadata dict contains
        module_path, class_name, requirements, settings, and other configuration.
        Mode classes are lazily loaded via _load_mode_class() when needed.

        Orders the list by the "order" field in metadata if present, otherwise
        defaults to alphabetical by the mode name.

        Returns:
            List[str]: List of mode_id strings for modes that have their requirements met.
        """
        JEBLogger.info("MENU",f"Building menu items for menu '{menu}'...")
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
                items.sort(key=lambda mid: (self.core.mode_registry[mid].get("order", 9999), self.core.mode_registry[mid]["name"]))

        JEBLogger.debug("MENU", f"Built menu items: {items}")
        return items

    def _set_state(self, new_state):
        """Helper to switch states and update UI accordingly."""
        JEBLogger.info("MENU", f"Transitioning to state: {new_state}")

        self.state = new_state

        if new_state == "DASHBOARD":
            self.set_timeout(None)
            self.core.display.update_status("SYSTEM READY", "AWAITING INPUT")
            #self.core.matrix.show_icon("DEFAULT")

        elif new_state == "MENU":
            self.set_timeout(30)

        elif new_state == "ADMIN":
            self.set_timeout(30)
            self.core.display.update_status("ADMIN CONSOLE", "AUTHORIZED ACCESS")
            self.core.matrix.show_icon("ADMIN")

        elif new_state == "ZERO_PLAYER":
            self.set_timeout(30)
            self.core.display.update_status("ZERO PLAYER", "SELECT A SIMULATION")
            self.core.matrix.show_icon("ZERO_PLAYER")

    async def run(self):
        """Main Menu for selecting modes."""
        self.core.hid.flush() # Ensure no ghost inputs from previous modes
        self.core.hid.reset_encoder(0)

        # Set all Satellites to idle state (if applicable)
        for sat in self.core.satellites.values():
            sat.send("MODE", "IDLE")

        # UI State Variables
        start_state = getattr(self.core, "_menu_return_state", "DASHBOARD")
        self._set_state(start_state)

        focus_mode = "GAME" # "GAME" or "SETTINGS"

        # Category Variables
        current_category = getattr(self.core, "_last_menu_category", "CORE")

        # Data Variables
        core_items = self._build_menu_items("CORE")
        exp1_items = self._build_menu_items("EXP1")
        admin_items = self._build_menu_items("ADMIN")
        zero_player_items = self._build_menu_items("ZERO_PLAYER")

        def _items_for_category(cat):
            if cat == "CORE":
                return core_items
            if cat == "EXP1":
                return exp1_items
            return zero_player_items  # "ZERO"

        def _get_valid_categories():
            cats = ["CORE"]
            if exp1_items:
                cats.append("EXP1")
            cats.append("ZERO")
            return cats

        # Validate restored category is still available (e.g. satellite may have been removed)
        valid_cats = _get_valid_categories()
        if current_category not in valid_cats:
            current_category = "CORE"

        menu_items = _items_for_category(current_category)

        selected_game_idx = getattr(self.core, "_last_menu_idx", 0)

        if menu_items and selected_game_idx >= len(menu_items):
            selected_game_idx = len(menu_items) - 1

        selected_setting_idx = 0
        admin_idx = 0
        zero_player_idx = 0

        # Satellite topology tracking for hot-plug detection
        last_sat_keys = frozenset(self.core.satellites.keys())

        # Render Tracking (Prevents unnecessary screen updates)
        self.core.display.use_standard_layout()
        needs_render = True
        last_rendered_game = -1
        last_rendered_setting = -1
        last_rendered_admin = -1
        last_rendered_zero_player = -1
        last_rendered_state = None
        last_rendered_focus = None
        last_rendered_category = None
        slide_direction = "SLIDE_LEFT"

        # Turn off all button LEDs
        self.core.leds.off_led(-1)

        last_pos = self.core.hid.encoder_position()

        while True:
            # --- CONSOLE INTERRUPT CHECK ---
            if getattr(self, "_exit_requested", False):
                JEBLogger.info("MENU", "Exit requested by external manager.")
                return "EXIT"

            # =========================================
            # 1. GATHER INPUTS
            # =========================================
            curr_pos = self.core.hid.encoder_position()
            encoder_diff = curr_pos - last_pos
            encoder_pressed = self.core.hid.is_encoder_button_pressed(action="tap")
            b1_pressed = self.core.hid.is_button_pressed(0, action="tap")
            b2_pressed = self.core.hid.is_button_pressed(1, action="tap")
            b3_pressed = self.core.hid.is_button_pressed(2, action="tap")
            b4_pressed = self.core.hid.is_button_pressed(3, action="tap")
            b1_long = self.core.hid.is_button_pressed(0, long=True, duration=2000)
            b2_long = self.core.hid.is_button_pressed(1, long=True, duration=2000)
            b3_long = self.core.hid.is_button_pressed(2, long=True, duration=2000)
            b4_long = self.core.hid.is_button_pressed(3, long=True, duration=2000)

            # --- GLOBAL TIMEOUT CHECK ---
            if self.is_timed_out and self.state != "DASHBOARD":
                self.core.leds.off_led(-1)
                self.core.buzzer.play_sequence(tones.MENU_CLOSE)
                self._set_state("DASHBOARD")
                focus_mode = "GAME"
                needs_render = True

            # --- SATELLITE TOPOLOGY CHECK ---
            # Detect hot-plugged satellites and refresh menu items in-place
            curr_sat_keys = frozenset(self.core.satellites.keys())
            if curr_sat_keys != last_sat_keys:
                last_sat_keys = curr_sat_keys

                # Rebuild all lists
                core_items = self._build_menu_items("CORE")
                exp1_items = self._build_menu_items("EXP1")
                admin_items = self._build_menu_items("ADMIN")
                zero_player_items = self._build_menu_items("ZERO_PLAYER")

                # If current category is no longer valid (e.g. satellite removed), fall back to CORE
                valid_cats = _get_valid_categories()
                if current_category not in valid_cats:
                    current_category = "CORE"
                    selected_game_idx = 0  # Safe reset since the whole category vanished

                menu_items = _items_for_category(current_category)

                # SAFEGUARDS: Bound all relative indices to prevent IndexError in the render loop
                if menu_items and selected_game_idx >= len(menu_items):
                    selected_game_idx = len(menu_items) - 1
                elif not menu_items:
                    selected_game_idx = 0

                if admin_items and admin_idx >= len(admin_items):
                    admin_idx = len(admin_items) - 1
                elif not admin_items:
                    admin_idx = 0

                if zero_player_items and zero_player_idx >= len(zero_player_items):
                    zero_player_idx = len(zero_player_items) - 1
                elif not zero_player_items:
                    zero_player_idx = 0

                # Safely bound settings index if a satellite drop altered the current game
                if focus_mode == "SETTINGS":
                    if menu_items:
                        mode_meta = self.core.mode_registry[menu_items[selected_game_idx]]
                        mode_settings = mode_meta.get("settings", [])
                        if mode_settings and selected_setting_idx >= len(mode_settings):
                            selected_setting_idx = len(mode_settings) - 1
                        elif not mode_settings:
                            selected_setting_idx = 0
                    else:
                        selected_setting_idx = 0

                needs_render = True

            # =========================================
            # 2. PROCESS STATE & LOGIC
            # =========================================

            # --- DASHBOARD STATE ---
            if self.state == "DASHBOARD":
                any_button_pressed = (
                    encoder_pressed or
                    b1_pressed or b2_pressed or b3_pressed or b4_pressed or
                    b1_long or b2_long or b3_long or b4_long
                )

                if encoder_diff != 0 or any_button_pressed:
                    JEBLogger.info("MENU", f"Waking up from DASHBOARD")
                    self.touch()
                    core_items = self._build_menu_items("CORE")
                    exp1_items = self._build_menu_items("EXP1")
                    admin_items = self._build_menu_items("ADMIN")
                    zero_player_items = self._build_menu_items("ZERO_PLAYER")
                    menu_items = _items_for_category(current_category)
                    self._set_state("MENU")
                    needs_render = True
                    self.core.buzzer.play_sequence(tones.MENU_OPEN)

            # --- ADMIN STATE ---
            elif self.state == "ADMIN":
                if encoder_diff != 0:
                    JEBLogger.info("MENU", f"Encoder activity detected in ADMIN: diff={encoder_diff}")
                    self.touch()
                    slide_direction = "SLIDE_LEFT" if encoder_diff > 0 else "SLIDE_RIGHT"
                    if admin_items:
                        admin_idx = (admin_idx + encoder_diff) % len(admin_items)
                    self.core.buzzer.play_sequence(tones.UI_TICK)
                    needs_render = True

                if encoder_pressed and admin_items:
                    JEBLogger.info("MENU", f"Encoder button pressed in ADMIN: selected_idx={admin_idx}, mode_id={admin_items[admin_idx]}")
                    self.touch()
                    self.core.buzzer.play_sequence(tones.UI_CONFIRM)
                    self.core._menu_return_state = "ADMIN"
                    self.core.mode = admin_items[admin_idx]
                    return "ADMIN_CHOICE"

                if b4_pressed and not b4_long:
                    JEBLogger.info("MENU", "Exiting ADMIN, returning to MENU")
                    self.touch()
                    self.core.buzzer.play_sequence(tones.MENU_CLOSE)
                    self._set_state("MENU")
                    self.core.leds.stop_cylon()
                    self.core.leds.off_led(-1)
                    needs_render = True

            # --- ZERO PLAYER STATE ---
            elif self.state == "ZERO_PLAYER":
                if encoder_diff != 0:
                    JEBLogger.info("MENU", f"Encoder activity detected in ZERO_PLAYER: diff={encoder_diff}")
                    self.touch()
                    slide_direction = "SLIDE_LEFT" if encoder_diff > 0 else "SLIDE_RIGHT"
                    if zero_player_items:
                        zero_player_idx = (zero_player_idx + encoder_diff) % len(zero_player_items)
                    self.core.buzzer.play_sequence(tones.UI_TICK)
                    needs_render = True

                if encoder_pressed and zero_player_items:
                    JEBLogger.info("MENU", f"Encoder button pressed in ZERO_PLAYER: selected_idx={zero_player_idx}, mode_id={zero_player_items[zero_player_idx]}")
                    self.touch()
                    self.core.buzzer.play_sequence(tones.MENU_LAUNCH)
                    self.core._menu_return_state = "ZERO_PLAYER"
                    self.core.mode = zero_player_items[zero_player_idx]
                    return "ZERO_CHOICE"

                if b4_pressed and not b4_long:
                    JEBLogger.info("MENU", "Exiting ZERO_PLAYER, returning to MENU")
                    self.touch()
                    self.core.buzzer.play_sequence(tones.MENU_CLOSE)
                    self._set_state("MENU")
                    needs_render = True

            # --- MENU STATE ---
            elif self.state == "MENU":
                # Check for Admin transition
                if focus_mode == "GAME" and b1_long and b2_long:
                    JEBLogger.info("MENU", "Admin access granted via long press on B1 and B2")
                    self.touch()
                    self.core.buzzer.play_sequence(tones.SECRET_FOUND)
                    self._set_state("ADMIN")
                    JEBLogger.info("MENU", "Entering Admin Menu")
                    self.core.leds.off_led(-1)
                    self.core.leds.start_cylon(Palette.RED, speed=0.05)
                    self.core.leds.set_led(1, color=Palette.ORANGE, anim_mode="FLASH", speed=2.0)
                    needs_render = True
                    continue

                # Handle Category Cycle (B1 tap)
                if focus_mode == "GAME" and b1_pressed and not b1_long:
                    JEBLogger.info("MENU", f"B1 pressed, cycling category from {current_category}")
                    self.touch()
                    valid_cats = _get_valid_categories()
                    cat_idx = valid_cats.index(current_category) if current_category in valid_cats else 0
                    current_category = valid_cats[(cat_idx + 1) % len(valid_cats)]
                    menu_items = _items_for_category(current_category)
                    selected_game_idx = 0
                    self.core.buzzer.play_sequence(tones.MENU_OPEN)
                    needs_render = True
                    last_rendered_game = -1
                    last_rendered_category = None
                    JEBLogger.info("MENU", f"Switched to category: {current_category}, items: {menu_items}")

                # Handle Focus Toggle / Settings Entry
                if focus_mode == "GAME" and b2_pressed and not b2_long:
                    JEBLogger.info("MENU", f"B2 pressed, entering SETTINGS")
                    self.touch()
                    # Only enter settings if the current game HAS settings
                    current_game = menu_items[selected_game_idx]
                    if len(self.core.mode_registry[current_game].get("settings", [])) > 0:
                        JEBLogger.info("MENU", f"Entering SETTINGS focus for game '{current_game}'")
                        focus_mode = "SETTINGS"
                        selected_setting_idx = 0
                        self.core.buzzer.play_sequence(tones.MENU_OPEN)
                        needs_render = True

                # Handle GAME Focus Logic
                if focus_mode == "GAME":
                    if encoder_diff != 0:
                        JEBLogger.info("MENU", f"Encoder activity detected in GAME focus: diff={encoder_diff}")
                        self.touch()
                        slide_direction = "SLIDE_LEFT" if encoder_diff > 0 else "SLIDE_RIGHT"
                        #selected_game_idx = curr_pos % len(menu_items)
                        selected_game_idx = (selected_game_idx + encoder_diff) % len(menu_items)
                        JEBLogger.info("MENU", f"Encoder moved: diff={encoder_diff}, selected_game_idx={selected_game_idx}, menu_length={len(menu_items)}")
                        self.core.buzzer.play_sequence(tones.UI_TICK)
                        needs_render = True

                    if b3_pressed and not b3_long:
                        mode_id = menu_items[selected_game_idx]
                        mode_meta = self.core.mode_registry[mode_id]
                        self.touch() # Reset menu timeout

                        # Check the manifest BEFORE loading the class!
                        if mode_meta.get("has_tutorial", False):
                            JEBLogger.info("MENU", f"Starting tutorial for {mode_id}")
                            mode_id = menu_items[selected_game_idx]
                            mode_meta = self.core.mode_registry[mode_id]
                            self.core.buzzer.play_sequence(tones.MENU_LAUNCH)
                            self.core._menu_return_state = "MENU"
                            self.core._last_menu_idx = selected_game_idx
                            self.core._last_menu_category = current_category
                            self.core.mode = mode_id
                            self.core._pending_mode_variant = "TUTORIAL"
                            return "MENU_CHOICE"
                        else:
                            # Catch-all just in case they press it on a mode without one
                            JEBLogger.info("MENU", f"No tutorial available for {mode_id}")
                            self.core.buzzer.play_sequence(tones.ERROR)
                            self.core.display.update_footer("NO TUTORIAL")
                            needs_render = True

                    if encoder_pressed:
                        mode_id = menu_items[selected_game_idx]
                        mode_meta = self.core.mode_registry[mode_id]
                        JEBLogger.info("MENU", f"Encoder button pressed in GAME focus: selected_idx={selected_game_idx}, mode_id={mode_id}")
                        self.touch()
                        if mode_meta.get("submenu") == "ZERO_PLAYER":
                            JEBLogger.info("MENU", "Opening Zero Player submenu")
                            self.core.buzzer.play_sequence(tones.MENU_OPEN)
                            self._set_state("ZERO_PLAYER")
                            needs_render = True
                        else:
                            self.core.buzzer.play_sequence(tones.MENU_LAUNCH)

                            self.core._menu_return_state = "MENU"
                            self.core._last_menu_idx = selected_game_idx
                            self.core._last_menu_category = current_category

                            self.core.mode = mode_id
                            return "MENU_CHOICE"

                # Handle SETTINGS Focus Logic
                elif focus_mode == "SETTINGS":
                    current_game = menu_items[selected_game_idx]
                    mode_meta = self.core.mode_registry[current_game]
                    mode_settings = mode_meta.get("settings", [])

                    if len(mode_settings) > 0:
                        if encoder_diff != 0:
                            JEBLogger.info("MENU", f"Encoder activity detected in SETTINGS focus: diff={encoder_diff}")
                            self.touch()
                            #selected_setting_idx = curr_pos % len(mode_settings)
                            selected_setting_idx = (selected_setting_idx + encoder_diff) % len(mode_settings)
                            self.core.buzzer.play_sequence(tones.UI_TICK)
                            JEBLogger.info("MENU", f"Setting selected: {mode_settings[selected_setting_idx]['label']} (idx={selected_setting_idx})  of {len(mode_settings)}")
                            needs_render = True

                        if encoder_pressed:
                            JEBLogger.info("MENU", f"Encoder button pressed in SETTINGS focus: selected_setting_idx={selected_setting_idx}")
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
                            JEBLogger.info("MENU", f"Toggling setting '{setting['label']}' from '{current_val}' to '{new_value}'")
                            self.core.data.set_setting(mode_meta["id"], setting["key"], new_value)
                            self.core.buzzer.play_sequence(tones.UI_CONFIRM)
                            needs_render = True

                        if b4_pressed and not b4_long:
                            JEBLogger.info("MENU", "Exiting SETTINGS")
                            focus_mode = "GAME"
                            self.core.buzzer.play_sequence(tones.MENU_CLOSE)
                            needs_render = True

                    else:
                        JEBLogger.warning("MENU", "No settings found, exiting SETTINGS")
                        focus_mode = "GAME"
                        self.core.buzzer.play_sequence(tones.MENU_CLOSE)
                        needs_render = True

            # =========================================
            # 3. RENDER STAGE
            # =========================================
            # Only push updates to hardware if something visually changed!
            if needs_render or self.state != last_rendered_state or focus_mode != last_rendered_focus or selected_setting_idx != last_rendered_setting or current_category != last_rendered_category:
                JEBLogger.debug("MENU", f"Rendering... needs={needs_render}, state={self.state}, focus={focus_mode}, sett={selected_setting_idx}")
                JEBLogger.debug("MENU", f"Last - state={last_rendered_state}, focus={last_rendered_focus}, sett={last_rendered_setting}")
                if self.state == "DASHBOARD":
                    self.core.display.use_standard_layout()
                    self.core.display.update_header("JEB OS")
                    self.core.display.update_status("SYSTEM READY", "AWAITING INPUT")
                    self.core.display.update_footer("")
                    #self.core.matrix.clear()

                    if last_rendered_state is not None and last_rendered_state != "DASHBOARD":
                        self.core.matrix.show_icon("DEFAULT", anim_mode="FADE_IN", speed=1.0)

                elif self.state == "ADMIN":
                    #admin_idx = curr_pos % len(admin_items) if admin_items else 0

                    self.core.display.use_standard_layout()
                    self.core.display.update_header("- ADMIN MODE -")

                    if admin_items:
                        mode_id = admin_items[admin_idx]
                        mode_meta = self.core.mode_registry[mode_id]
                        self.core.display.update_status(f"> {mode_meta['name']} <", "Push to Select")
                        self.core.display.update_footer("B4:EXIT")

                        # Only re-trigger the slide animation if the admin mode actually changed
                        if admin_idx != last_rendered_admin:
                            self.core.matrix.show_icon(mode_meta["icon"], anim_mode=slide_direction, speed=2.0)
                        last_rendered_admin = admin_idx
                    else:
                        self.core.display.update_status("NO ADMIN MODES", "")
                        self.core.display.update_footer("B4:EXIT")
                        self.core.matrix.show_icon("WARNING")

                elif self.state == "ZERO_PLAYER":
                    #zero_player_idx = curr_pos % len(zero_player_items) if zero_player_items else 0

                    self.core.display.use_standard_layout()
                    self.core.display.update_header("- ZERO PLAYER -")

                    if zero_player_items:
                        mode_id = zero_player_items[zero_player_idx]
                        mode_meta = self.core.mode_registry[mode_id]
                        self.core.display.update_status(f"> {mode_meta['name']} <", "Push to Select")
                        self.core.display.update_footer("B4:EXIT")

                        # Only re-trigger the slide animation if the selection actually changed
                        if zero_player_idx != last_rendered_zero_player:
                            self.core.matrix.show_icon(mode_meta["icon"], anim_mode=slide_direction, speed=2.0)
                        last_rendered_zero_player = zero_player_idx
                    else:
                        self.core.display.update_status("NO ZERO PLAYER MODES", "")
                        self.core.display.update_footer("B4:EXIT")
                        self.core.matrix.show_icon("DEFAULT")

                elif self.state == "MENU":
                    category_title = self._CATEGORY_TITLES.get(current_category, f"[ {current_category} ]")

                    if focus_mode == "GAME":
                        if menu_items:
                            mode_id = menu_items[selected_game_idx]
                            mode_meta = self.core.mode_registry[mode_id]

                            self.core.display.update_header(category_title)
                            if mode_meta.get("submenu"):
                                self.core.display.update_status(f"> {mode_meta['name']} <", "Push to Open")
                            else:
                                high_score = self.core.data.get_high_score(mode_id)
                                self.core.display.update_status(f"> {mode_meta['name']} <", f"Hi: {high_score}")
                            hints = ["B1:NEXT"]
                            if len(mode_meta.get("settings", [])) > 0:
                                hints.append("B2:SETT")
                            if mode_meta.get("has_tutorial", False):
                                hints.append("B3:TUTE")
                            self.core.display.update_footer(" ".join(hints))
                            self.core.display.show_settings_menu(False)

                            # Only re-trigger the slide animation if the game or category changed
                            if selected_game_idx != last_rendered_game or current_category != last_rendered_category:
                                self.core.matrix.show_icon(mode_meta["icon"], anim_mode=slide_direction, speed=2.0)

                            last_rendered_game = selected_game_idx
                        else:
                            self.core.display.update_header(category_title)
                            self.core.display.update_status("NO MODES AVAILABLE", "")
                            self.core.display.update_footer("B1:NEXT")
                            self.core.matrix.show_icon("DEFAULT")

                    elif focus_mode == "SETTINGS":
                        mode_id = menu_items[selected_game_idx]
                        mode_meta = self.core.mode_registry[mode_id]
                        mode_settings = mode_meta.get("settings", [])
                        settings_strings = []
                        for s in mode_settings:
                            val = self.core.data.get_setting(mode_meta["id"], s["key"], s["default"])
                            settings_strings.append(f"{s['label']}: {val}")

                        self.core.display.update_header(f"-{mode_meta['name']}- SETTINGS")
                        self.core.display.update_settings_menu(settings_strings, selected_setting_idx)
                        self.core.display.update_footer("B4:EXIT")

                # Update tracking variables
                needs_render = False
                last_rendered_state = self.state
                last_rendered_focus = focus_mode
                last_rendered_setting = selected_setting_idx
                last_rendered_category = current_category

            last_pos = curr_pos

            await asyncio.sleep(0.01)
