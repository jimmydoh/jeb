"""Manages displayio objects and hardware for the JEB Master OLED."""

import gc
import displayio
import terminalio
import adafruit_displayio_ssd1306
from adafruit_display_text import label

class DisplayManager:
    """Manages displayio objects and hardware for the JEB Master OLED.
    
    Display Layout System:
    ----------------------
    The display supports three layout modes:
    
    1. LEGACY LAYOUT (default on initialization): Backward compatible
       - Preserves original behavior with status labels and viewport
       - Ensures existing modes work without modification
    
    2. STANDARD LAYOUT (recommended for new modes): Three-zone design
       - Header (top ~15px): System stats, mode indicators
       - Main/Central (middle ~35px): Mode content, status messages
       - Footer (bottom ~14px): Logs, console messages
       
    3. CUSTOM LAYOUT: Full display control for modes requiring bespoke UI
       - Modes can overlay or completely replace the standard layout
       - Useful for games or utilities with specific display needs
    
    Usage:
    ------
    Legacy layout (automatic for existing modes):
        display.update_status("Message", "Sub message")
        display.load_view("dashboard")
    
    Standard layout (recommended for new modes):
        display.use_standard_layout()
        display.update_status("Main message", "Sub message")
        display.update_header("CPU: 45%")
        display.update_footer("Log message")
        
    Custom layout (for specialized modes):
        display.use_custom_layout()
        custom_group = displayio.Group()
        # Add custom displayio elements to custom_group
        display.set_custom_content(custom_group)
    """
    def __init__(self, i2c_bus, device_address=0x3C):
        displayio.release_displays()
        self.display_bus = displayio.I2CDisplay(i2c_bus, device_address=device_address)
        self.hw = adafruit_displayio_ssd1306.SSD1306(self.display_bus, width=128, height=64)

        # Root group for all UI layers
        self.root = displayio.Group()
        self.hw.root_group = self.root

        # Track current layout mode
        self._layout_mode = None  # "legacy", "standard", or "custom"
        
        # ===== STANDARD LAYOUT COMPONENTS =====
        # Header zone (top, ~15px height): System stats, mode indicators
        self.header_group = displayio.Group()
        self.header_label = label.Label(terminalio.FONT, text="", x=2, y=5)
        self.header_group.append(self.header_label)
        
        # Main/Central zone (middle, ~35px height): Primary content
        self.main_group = displayio.Group()
        self.status = label.Label(terminalio.FONT, text="", x=5, y=30)
        self.sub_status = label.Label(terminalio.FONT, text="", x=5, y=45)
        self.main_group.append(self.status)
        self.main_group.append(self.sub_status)
        
        # Footer zone (bottom, ~14px height): Logs, console messages
        self.footer_group = displayio.Group()
        self.footer_label = label.Label(terminalio.FONT, text="", x=2, y=60)
        self.footer_group.append(self.footer_label)
        
        # ===== CUSTOM LAYOUT COMPONENTS =====
        # Custom viewport for modes that need full control
        self.custom_group = displayio.Group()
        
        # ===== BACKWARD COMPATIBILITY =====
        # Legacy viewport layer for existing modes
        self.viewport = displayio.Group()
        
        # ===== PRE-BUILT MODE GROUPS (LEGACY) =====
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
        
        # Initialize with legacy mode for backward compatibility
        # This ensures existing modes work without modification
        self._setup_legacy_layout()

    # ===== LAYOUT MODE METHODS =====
    
    def use_standard_layout(self):
        """Switch to standard three-zone layout (Header/Main/Footer).
        
        This is the recommended layout for most modes. It provides:
        - Header zone for system stats and mode indicators
        - Main zone for primary mode content
        - Footer zone for logs and console messages
        
        Example:
            display.use_standard_layout()
            display.update_status("Ready", "Press button")
            display.update_header("Mode: GAME")
            display.update_footer("Score saved")
        """
        if self._layout_mode == "standard":
            return  # Already in standard mode
        
        # Clear root and rebuild with standard layout
        while len(self.root) > 0:
            self.root.pop()
        
        # Add zones in order: header, main, footer
        self.root.append(self.header_group)
        self.root.append(self.main_group)
        self.root.append(self.footer_group)
        
        self._layout_mode = "standard"
    
    def use_custom_layout(self):
        """Switch to custom layout mode for full display control.
        
        Use this when a mode needs complete control over the display,
        such as games with bespoke UI or specialized utilities.
        
        After calling this, use set_custom_content() to display your content.
        
        Example:
            display.use_custom_layout()
            my_group = displayio.Group()
            # Add custom elements to my_group
            display.set_custom_content(my_group)
        """
        if self._layout_mode == "custom":
            return  # Already in custom mode
        
        # Clear root and add custom group
        while len(self.root) > 0:
            self.root.pop()
        
        self.root.append(self.custom_group)
        self._layout_mode = "custom"
    
    def set_custom_content(self, content_group):
        """Set the content for custom layout mode.
        
        Args:
            content_group: A displayio.Group containing your custom UI elements
        
        Note: Call use_custom_layout() first to switch to custom mode.
        """
        # Clear custom group and add new content
        while len(self.custom_group) > 0:
            self.custom_group.pop()
        
        if content_group is not None:
            self.custom_group.append(content_group)
    
    def _setup_legacy_layout(self):
        """Set up the legacy layout for backward compatibility.
        
        This preserves the original display behavior where status labels
        and viewport are directly added to root.
        """
        # Clear root
        while len(self.root) > 0:
            self.root.pop()
        
        # Add legacy components: status labels + viewport
        self.root.append(self.status)
        self.root.append(self.sub_status)
        self.root.append(self.viewport)
        
        self._layout_mode = "legacy"
    
    # ===== STANDARD LAYOUT UPDATE METHODS =====
    
    def update_header(self, text):
        """Update the header zone text (system stats, mode indicator).
        
        Args:
            text: String to display in header (e.g., "CPU: 45% | RAM: 120KB")
        """
        self.header_label.text = text
    
    def update_footer(self, text):
        """Update the footer zone text (logs, console messages).
        
        Args:
            text: String to display in footer (e.g., "Config saved")
        """
        self.footer_label.text = text
    
    # ===== LEGACY/COMMON METHODS =====

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
        """Primary method for updating game and system messages.
        
        Works in both legacy and standard layout modes.
        In standard mode, updates the main zone content.
        """
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
