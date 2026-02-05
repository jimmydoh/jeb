"""Manages displayio objects and hardware for the JEB Master OLED."""

import gc
import displayio
import terminalio
import adafruit_displayio_ssd1306
from adafruit_display_text import label

class DisplayManager:
    """Manages displayio objects and hardware for the JEB Master OLED."""
    def __init__(self, i2c_bus):
        displayio.release_displays()
        self.display_bus = displayio.I2CDisplay(i2c_bus, device_address=0x3C)
        self.hw = adafruit_displayio_ssd1306.SSD1306(self.display_bus, width=128, height=64)

        # Root group for all UI layers
        self.root = displayio.Group()
        self.hw.root_group = self.root

        # Persistant Layer: Common Status Labels
        # These are ALWAYS at index 0 and 1 of the root group
        self.status = label.Label(terminalio.FONT, text="", x=5, y=30)
        self.sub_status = label.Label(terminalio.FONT, text="", x=5, y=45)
        self.root.append(self.status)
        self.root.append(self.sub_status)

        # Viewport Layer: This is where mode-specific graphics go
        self.viewport = displayio.Group()
        self.root.append(self.viewport)

        # Separate Viewport Groups
        # ** DASHBOARD VIEW **
        self.dash_group = displayio.Group()
        self.dash_header = label.Label(terminalio.FONT, text="--- JADNET CORE ---", x=10, y=5)
        self.dash_group.append(self.dash_header)

        # ** GAME INFO / SETTINGS VIEW **
        self.game_info_group = displayio.Group()
        self.game_header = label.Label(terminalio.FONT, text="", x=5, y=5)
        self.game_score = label.Label(terminalio.FONT, text="", x=5, y=18)
        self.game_settings_lines = []
        for i in range(3): # Show 3 settings lines
            lbl = label.Label(terminalio.FONT, text="", x=15, y=32 + (i * 12))
            self.game_settings_lines.append(lbl)

        self.settings_cursor = label.Label(terminalio.FONT, text=">", x=5, y=32)
        self.game_info_group.append(self.game_header)
        self.game_info_group.append(self.game_score)
        self.game_info_group.append(self.settings_cursor)
        for line in self.game_settings_lines:
            self.game_info_group.append(line)

        # ** ADMIN MENU VIEW **
        self.admin_group = displayio.Group()
        self.admin_header = label.Label(terminalio.FONT, text="--- ADMIN MENU ---", x=10, y=5)
        self.admin_group.append(self.admin_header)
        self.admin_lines = [] # Menu Items (4 visible lines)
        for i in range(4):
            line = label.Label(terminalio.FONT, text="", x=12, y=10 + (i * 15))
            self.admin_lines.append(line)
        self.admin_group.append(self.admin_lines)
        self.admin_carat = label.Label(terminalio.FONT, text=">", x=2, y=10) # Carat Indicator
        self.admin_group.append(self.admin_carat)

        # ** DEBUG STATS VIEW **
        self.debug_group = displayio.Group()
        self.debug_header = label.Label(terminalio.FONT, text="--- DEBUG STATS ---", x=10, y=5)
        self.debug_group.append(self.debug_header)
        self.debug_ram = label.Label(terminalio.FONT, text="RAM: 000KB FREE", x=5, y=25) # RAM Label
        self.debug_group.append(self.debug_ram)
        self.debug_cpu = label.Label(terminalio.FONT, text="LOOP: 0.0ms", x=5, y=40) # CPU/Task Load Label
        self.debug_group.append(self.debug_cpu)
        self.debug_sat_count = label.Label(terminalio.FONT, text="SATS: 0 ACTIVE", x=5, y=55) # Satellite Count Label
        self.debug_group.append(self.debug_sat_count)

        # Storage for Viewport Layouts
        self.views = {
            "dashboard": self.dash_group,
            "menu": self.dash_group,
            "game_info": self.game_info_group,
            "admin_menu": self.admin_group,
            "debug_menu": self.debug_group
        }

        # Layout Dictionary: X, Y coordinates for status labels per mode
        self.layouts = {
            "default": {"status": (5, 30), "sub": (5, 45)}
        }

    def _set_layout(self, mode_name):
        """Reposition the 'common' labels based on the active mode."""
        if mode_name in self.layouts:
            coords = self.layouts[mode_name]
            self.status.x, self.status.y = coords["status"]
            self.sub_status.x, self.sub_status.y = coords["sub"]

    def load_view(self, view_name):
        """Change the viewport content for a specific mode.
            Move Persistent Labels as needed.
        """
        self._set_layout(view_name)
        while len(self.viewport) > 0:
            self.viewport.pop()
        if view_name in self.views:
            self.viewport.append(self.views[view_name])

    def update_status(self, main_text, sub_text=None):
        """Primary method for updating game and system messages."""
        self.status.text = main_text
        if sub_text is not None:
            self.sub_status.text = sub_text

    def update_game_menu(self, title, score, settings, selected_idx, has_focus):
        """Updates the Game Info / Settings screen.

        settings: list of dicts {'label': 'SPEED', 'value': 'FAST'}
        selected_idx: index of currently selected setting (if has_focus is True)
        has_focus: Boolean, if True, show cursor on settings.
        """
        self.game_header.text = f"-- {title} --"
        self.game_score.text = f"HIGH: {score}"

        # Display Cursor only if settings are focused
        if has_focus and len(settings) > 0:
            self.settings_cursor.hidden = False
            # Determine scroll offset if we have many settings
            # Simple version: fixed 3 lines
            start_idx = 0
            if selected_idx > 2:
                start_idx = selected_idx - 2

            self.settings_cursor.y = 32 + ((selected_idx - start_idx) * 12)
        else:
            self.settings_cursor.hidden = True
            start_idx = 0

        # Draw Settings Lines
        for i in range(3):
            data_idx = start_idx + i
            if data_idx < len(settings):
                item = settings[data_idx]
                self.game_settings_lines[i].text = f"{item['label']}: {item['value']}"
            else:
                self.game_settings_lines[i].text = ""

    def update_admin_menu(self, items, selected_idx):
        """Updates the text and carat position for the admin menu."""
        num_visible = 4
        # Calculate which slice of the list to show
        top_index = (selected_idx // num_visible) * num_visible

        for i in range(num_visible):
            item_idx = top_index + i
            if item_idx < len(items):
                self.admin_lines[i].text = items[item_idx]
            else:
                self.admin_lines[i].text = "" # Clear unused lines

        # Position the carat relative to the visible window
        local_idx = selected_idx % num_visible
        self.admin_carat.y = 10 + (local_idx * 15)

    def update_debug_stats(self, loop_time, sat_count):
        """Updates the debug labels with fresh data."""
        # Force a garbage collection to get an accurate 'Free' reading
        #gc.collect()
        if hasattr(gc, "mem_free"):
            free_ram = gc.mem_free() / 1024
        else:
            free_ram = 0.0

        self.debug_ram.text = f"RAM: {free_ram:.1f}KB FREE"
        self.debug_cpu.text = f"LOOP: {loop_time:.1f}ms"
        self.debug_sat_count.text = f"SATS: {sat_count} ACTIVE"
