"""Manages displayio objects and hardware for the JEB Master OLED."""

import asyncio
import displayio
import terminalio
import adafruit_displayio_ssd1306
from adafruit_display_text import label

class DisplayManager:
    """Manages displayio objects and hardware for the JEB Master OLED.

    Display Layout System:
    ----------------------
    The display supports two layout modes:

    1. STANDARD LAYOUT (recommended for new modes): Three-zone design
       - Header (top ~15px): System stats, mode indicators
       - Main/Central (middle ~35px): Mode content, status messages
       - Footer (bottom ~14px): Logs, console messages

    2. CUSTOM LAYOUT: Full display control for modes requiring bespoke UI
       - Modes can overlay or completely replace the standard layout
       - Useful for games or utilities with specific display needs

    DEPRECATED: Legacy Layout

    Usage:
    ------
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
        self._layout_mode = None  # "standard", or "custom"

        # ===== STANDARD LAYOUT COMPONENTS =====
        # Header zone (top, ~15px height): System stats, mode indicators
        self.header_group = displayio.Group()
        self.header_label = label.Label(terminalio.FONT, text="", x=2, y=4)
        self.header_group.append(self.header_label)

        # Main/Central zone (middle, ~35px height): Primary content
        self.main_group = displayio.Group()
        self.status = label.Label(terminalio.FONT, text="", x=2, y=24)
        self.sub_status = label.Label(terminalio.FONT, text="", x=2, y=40)
        self.main_group.append(self.status)
        self.main_group.append(self.sub_status)

        # Footer zone (bottom, ~14px height): Logs, console messages
        self.footer_group = displayio.Group()
        self.footer_label = label.Label(terminalio.FONT, text="", x=2, y=60)
        self.footer_group.append(self.footer_label)

        # Tracking for Synchronized Ping-Pong scrolling
        self._scroll_offset = 0
        self._scroll_dir = -1
        self._scroll_wait = 40
        self._scroll_max_distance = 0

        # Track which labels are eligible for scrolling
        self._scrollable_labels = {
            "status": {"label": self.status, "base_x": 2, "width": 0},
            "sub_status": {"label": self.sub_status, "base_x": 2, "width": 0}
        }

        # ===== SETTINGS MENU COMPONENTS =====
        # Swaps with main_group when in settings mode
        self.settings_group = displayio.Group()
        self.settings_labels = []

        # Create 3 lines for the scrollable list
        # Y-offsets 24, 34, 44 fit beautifully between Header (5) and Footer (60)
        for i in range(3):
            lbl = label.Label(terminalio.FONT, text="", x=2, y=24 + (i * 10))
            self.settings_labels.append(lbl)
            self.settings_group.append(lbl)

        self.settings_group.hidden = True # Hidden by default

        # ===== CUSTOM LAYOUT COMPONENTS =====
        # Custom viewport for modes that need full control
        self.custom_group = displayio.Group()

        self.use_standard_layout()  # Start in standard layout by default

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
        self.root.append(self.settings_group)  # Settings group swaps with main when active
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

    def update_status(self, main_text, sub_text=None):
        """Primary method for updating game and system messages.

        Works in both legacy and standard layout modes.
        In standard mode, updates the main zone content.
        """
        self._set_text_and_scroll_limits("status", main_text)

        if sub_text is not None:
            self._set_text_and_scroll_limits("sub_status", sub_text)

    def _set_text_and_scroll_limits(self, key, text):
        """Helper to calculate widths and trigger global scroll sync."""
        state = self._scrollable_labels[key]
        label_obj = state["label"]

        # Guard clause: Do nothing if the text hasn't changed
        if label_obj.text == text:
            return

        # Update text and calculate its specific pixel width
        label_obj.text = text
        state["width"] = len(text) * 6

        # Recalculate the GLOBAL maximum distance needed
        max_width = max(s["width"] for s in self._scrollable_labels.values())

        if max_width > 128:
            # 128 screen width - max text width - 10px padding margin
            self._scroll_max_distance = max_width - 128 + 10
        else:
            self._scroll_max_distance = 0

        # Reset the global camera so the new text is readable from the start
        self._scroll_offset = 0
        self._scroll_dir = -1
        self._scroll_wait = 40

        # Instantly snap all labels back to their default positions
        for s in self._scrollable_labels.values():
            s["label"].x = s["base_x"]

    async def scroll_loop(self):
        """Background task to smoothly pan long text back and forth in sync."""
        import asyncio
        while True:
            # Only animate if at least one line is longer than the screen
            if self._scroll_max_distance > 0:

                if self._scroll_wait > 0:
                    self._scroll_wait -= 1
                else:
                    # Move the global camera
                    self._scroll_offset += self._scroll_dir

                    # Check boundaries and reverse direction
                    if self._scroll_offset <= -self._scroll_max_distance:
                        self._scroll_offset = -self._scroll_max_distance
                        self._scroll_dir = 1     # Change direction to Right
                        self._scroll_wait = 20   # Pause at the end
                    elif self._scroll_offset >= 0:
                        self._scroll_offset = 0
                        self._scroll_dir = -1    # Change direction to Left
                        self._scroll_wait = 40   # Pause longer at the beginning

                    # Apply the global offset ONLY to lines that need it
                    for s in self._scrollable_labels.values():
                        if s["width"] > 128:
                            s["label"].x = s["base_x"] + self._scroll_offset

            # ~30 FPS scroll speed
            await asyncio.sleep(0.03)

    def show_settings_menu(self, show=None):
        """Choose visibility of the settings menu, which replaces the main zone."""
        if show:
            self.settings_group.hidden = False
            self.main_group.hidden = True
        else:
            self.settings_group.hidden = True
            self.main_group.hidden = False

    def update_settings_menu(self, menu_items, selected_index):
        """Renders a scrollable list with color-inversion highlighting.

        Args:
            menu_items (list): List of strings e.g., ["Sound: ON", "Diff: HARD", "Exit"]
            selected_index (int): The currently selected item index
        """
        self.show_settings_menu(True)  # Ensure settings menu is visible
        total_items = len(menu_items)
        if total_items == 0:
            return

        # --- SCROLLING CAMERA MATH ---
        # Show 3 items max. Keep the selected item centered if possible.
        if total_items <= 3:
            start_idx = 0
        else:
            start_idx = selected_index - 1
            # Clamp to top and bottom boundaries
            start_idx = max(0, min(start_idx, total_items - 3))

        # --- RENDER THE 3 LABELS ---
        for i in range(3):
            item_idx = start_idx + i
            lbl = self.settings_labels[i]

            if item_idx < total_items:
                text = menu_items[item_idx]

                if item_idx == selected_index:
                    # HIGHLIGHTED: Add caret, pad to 21 chars for a full-width bar
                    padded_text = f"> {text}".ljust(21)
                    lbl.text = padded_text
                    lbl.color = 0x000000          # Black text
                    lbl.background_color = 0xFFFFFF # White background block
                else:
                    # NORMAL: Add spacing to align with caret, no background
                    padded_text = f"  {text}".ljust(21)
                    lbl.text = padded_text
                    lbl.color = 0xFFFFFF          # White text
                    lbl.background_color = None   # Transparent background

                lbl.hidden = False
            else:
                # Hide unused labels if the list is shorter than 3 items
                lbl.hidden = True
