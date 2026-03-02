"""Manages displayio objects and hardware for the JEB Master OLED."""

import asyncio
import displayio
from utilities.logger import JEBLogger

try:
    # CircuitPython 9+ (Actual Hardware)
    import i2cdisplaybus
    I2CDisplayClass = i2cdisplaybus.I2CDisplayBus
except ImportError:
    # Blinka / Emulator / CircuitPython 8.x
    I2CDisplayClass = displayio.I2CDisplay

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
        JEBLogger.info("DISP", f"[INIT] DisplayManager - device_address: {hex(device_address)}")
        displayio.release_displays()
        self.display_bus = I2CDisplayClass(i2c_bus, device_address=device_address)
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

        # Tracking for Scrolling and Animations
        self._scroll_offset = 0
        self._scroll_dir = -1
        self._scroll_wait = 40
        self._scroll_max_distance = 0
        self._scrolling_labels = {}
        self._active_animations = {}

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

        # ===== AUDIO VISUALIZER COMPONENTS =====
        # Pre-allocated once to avoid heap fragmentation during fast render loops
        self._audio_bitmap = displayio.Bitmap(128, 64, 2)
        self._audio_palette = displayio.Palette(2)
        self._audio_palette[0] = 0x000000  # background
        self._audio_palette[1] = 0xFFFFFF  # foreground
        self._audio_grid = displayio.TileGrid(self._audio_bitmap, pixel_shader=self._audio_palette)
        self._audio_group = displayio.Group()
        self._audio_group.append(self._audio_grid)

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

        JEBLogger.info("DISP", "[LAYOUT] Switching to standard layout")

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

        JEBLogger.info("DISP", "[LAYOUT] Switching to custom layout")

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

    # ===== UNIVERSAL UPDATE METHODS =====

    def update(self, label_obj, text, scroll=False, base_x=5, anim=None, **kwargs):
        """Universal method to update any label with optional animation.

        Args:
            label_obj: The label to update (e.g., self.status, self.header_label)
            text: The new text to display
            animation: Optional animation type ("slide_in", "typewriter", "blink")
            kwargs: Additional parameters for the animation (e.g., direction, char_delay)
        """
        JEBLogger.debug("DISP", f"Update {self._get_label_name(label_obj)}: '{text}' ({scroll}|{anim})")

        if label_obj in self._active_animations:
            self._active_animations[label_obj].cancel()
            del self._active_animations[label_obj]

        if anim == "slide_in":
            self._active_animations[label_obj] = asyncio.create_task(
                self.animate_slide_in(
                    label_obj, text, scroll, scroll_base_x=base_x, **kwargs
                )
            )
        elif anim == "typewriter":
            self._active_animations[label_obj] = asyncio.create_task(
                self.animate_typewriter(
                    label_obj, text, scroll, scroll_base_x=base_x, **kwargs
                )
            )
        elif anim == "blink":
            self._active_animations[label_obj] = asyncio.create_task(
                self.animate_blink(
                    label_obj, text, scroll, scroll_base_x=base_x, **kwargs
                )
            )
        else:
            if scroll:
                self._set_text_and_scroll_limits(label_obj, text, base_x)
            else:
                label_obj.text = text
                # Reset scroll if not scrolling
                label_obj.x = base_x
                # Remove from scrolling labels if it was previously scrollable
                self._remove_scrolling_label(label_obj)


    # ===== STANDARD LAYOUT UPDATE METHODS =====

    def update_header(self, text, **kwargs):
        """Update the header zone text (system stats, mode indicator).

        Args:
            text: String to display in header (e.g., "CPU: 45% | RAM: 120KB")
        """
        self.update(self.header_label, text, scroll=True, base_x=2, **kwargs)

    def update_footer(self, text, **kwargs):
        """Update the footer zone text (logs, console messages).

        Args:
            text: String to display in footer (e.g., "Config saved")
        """
        self.update(self.footer_label, text, scroll=True, base_x=2, **kwargs)

    def update_status(self, main_text, sub_text=None, **kwargs):
        """Primary method for updating game and system messages.

        Works in both legacy and standard layout modes.
        In standard mode, updates the main zone content.
        """
        self.update(self.status, main_text, scroll=True, base_x=5, **kwargs)

        if sub_text is not None:
            self.update(self.sub_status, sub_text, scroll=True, base_x=5, **kwargs)

    def _get_label_name(self, label_obj):
        """Reverse-lookup the human-readable name of a label object."""
        if label_obj is self.status:
            return "MSTAT"
        if label_obj is self.sub_status:
            return "SSTAT"
        if label_obj is self.header_label:
            return "HEADR"
        if label_obj is self.footer_label:
            return "FOOTR"
        if label_obj in self.settings_labels:
            return f"SETTG {self.settings_labels.index(label_obj)}"
        return "CUSTM"

    def _add_scrolling_label(self, label_obj, base_x=5):
        """Helper to add a label to the scrolling system if not already tracked."""
        label_id = id(label_obj)
        if label_id not in self._scrolling_labels:
            self._scrolling_labels[label_id] = {
                "label": label_obj, 
                "base_x": base_x, 
                "width": len(label_obj.text) * 6
            }
        else:
            self._scrolling_labels[label_id]["width"] = len(label_obj.text) * 6
            self._scrolling_labels[label_id]["base_x"] = base_x

        # Recalculate the global maximum distance needed
        max_width = max(s["width"] for s in self._scrolling_labels.values())
        self._scroll_max_distance = max(0, max_width - 128 + 10)

    def _remove_scrolling_label(self, label_obj):
        """Helper to remove a label from the scrolling system."""
        label_id = id(label_obj)
        if label_id in self._scrolling_labels:
            del self._scrolling_labels[label_id]
            # Recalculate the global maximum distance needed
            if self._scrolling_labels:
                max_width = max(s["width"] for s in self._scrolling_labels.values())
                self._scroll_max_distance = max(0, max_width - 128 + 10)
            else:
                self._scroll_max_distance = 0

    def _set_text_and_scroll_limits(self, label_obj, text, base_x=5):
        """
        Helper to calculate widths and trigger global scroll sync.

        Args:
            label_obj: The label to update (e.g., self.status, self.header_label)
            text: The new text to display
            base_x: The base x position for the label
            width: The width of the label
        """
        # Guard clause: Do nothing if the text hasn't changed
        if label_obj.text == text:
            return

        # Update text and calculate its specific pixel width
        label_obj.text = text
        self._add_scrolling_label(label_obj, base_x)

        label_id = id(label_obj)
        s = self._scrolling_labels[label_id]
        
        if s["width"] > 128:
            s["label"].x = s["base_x"] + self._scroll_offset
        else:
            s["label"].x = s["base_x"]

    async def scroll_loop(self):
        """Background task to smoothly pan long text back and forth in sync."""
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
                    for s in self._scrolling_labels.values():
                        if s["width"] > 128:
                            s["label"].x = s["base_x"] + self._scroll_offset

            # ~30 FPS scroll speed
            await asyncio.sleep(0.033)

    # ===== ANIMATION TRANSITION METHODS =====

    async def animate_slide_in(self, label_obj, text, scroll=False, scroll_base_x=5, direction="left", delay=0.02):
        """Animate main zone text sliding in from a direction.

        Sets the text of the label and calculates its width,
        then overrides the x position to the off-screen start and smoothly
        slides the labels to their final resting position.

        Args:
            label_obj: The label to animate (e.g., self.status or self.sub_status).
            text:       The new text to display.
            direction:  "left" to enter from the right edge (default),
                        "right" to enter from the left edge.
            delay:      Seconds between animation frames (default 0.02).
        """
        # Set text and reset scroll limits to the final state first.
        label_obj.text = text

        display_width = 128
        base_x = 2
        step = -6 if direction == "left" else 6
        start_x = display_width if direction == "left" else -display_width

        # Override x to the off-screen start position.
        label_obj.x = start_x

        x = start_x
        while True:
            x += step
            if step < 0:
                x = max(x, base_x)
            else:
                x = min(x, base_x)
            label_obj.x = x
            await asyncio.sleep(delay)
            if x == base_x:
                break

        self.update(label_obj, text, scroll=scroll, base_x=scroll_base_x)

    async def animate_typewriter(self, label_obj, text, scroll=False, scroll_base_x=5, delay=0.05, direction="left"):
        """Animate text appearing one character at a time (typewriter effect).

        Args:
            label_obj: The label to animate (e.g., self.status or self.sub_status).
            text:       The new text to display.
            delay:      Seconds between each character (default 0.05 s).
            direction:  "left" (default) types normally. 
                        "right" types from the right edge, pushing text left (telegraph style).
        """
        # Start from blank so the typing animation is visible.
        label_obj.text = ""
        self._remove_scrolling_label(label_obj)  # Ensure it's not treated as scrollable during animation

        char_width = 6
        right_margin = 126  # 128 screen width - 2px padding

        for i in range(1, len(text) + 1):
            label_obj.text = text[:i]
            
            if direction == "right":
                # Pin the 'cursor' to the right edge and push the text leftwards
                label_obj.x = right_margin - (i * char_width)
            else:
                label_obj.x = scroll_base_x
                
            await asyncio.sleep(delay)

        # --- SEAMLESS TRANSITION ---
        # If it typed from the right, the text might be floating in the middle of the screen.
        # We rapidly slide it left to its final base_x position so it doesn't abruptly teleport.
        if direction == "right":
            while label_obj.x > scroll_base_x:
                label_obj.x = max(scroll_base_x, label_obj.x - 6)
                await asyncio.sleep(0.015)

        # Let the universal update take over for final state/scrolling
        self.update(label_obj, text, scroll=scroll, base_x=scroll_base_x)

    async def animate_blink(self, label_obj, text, scroll=False, scroll_base_x=5,
                            times=3, on_duration=0.3, off_duration=0.2):
        """Animate text blinking to draw attention.

        The main zone is shown and hidden for the specified number of cycles,
        ending in the visible state.

        Args:
            label_obj: The label to animate (e.g., self.status or self.sub_status).
            text:       The new text to display.
            times:        Number of blink cycles (default 3).
            on_duration:  Seconds the text is visible per cycle (default 0.3).
            off_duration: Seconds the text is hidden per cycle (default 0.2).
        """
        label_obj.text = text

        for _ in range(times):
            label_obj.hidden = False
            await asyncio.sleep(on_duration)
            label_obj.hidden = True
            await asyncio.sleep(off_duration)

        # Always leave the label visible when done.
        label_obj.hidden = False

        self.update(label_obj, text, scroll=scroll, base_x=scroll_base_x)

    # ===== AUDIO VISUALIZER METHODS =====

    def show_waveform(self, samples):
        """Render an audio waveform on the OLED display.

        Switches to custom layout and draws each sample as a pixel on its
        column, mapping amplitude 0.0 → bottom row and 1.0 → top row.

        Args:
            samples: Iterable of amplitude floats in [0.0, 1.0] where 0.5 = silence.
                     Up to 128 values are used (one per pixel column).
        """
        self.use_custom_layout()

        self._audio_bitmap.fill(0)  # Fast native clear

        width = min(len(samples), 128)
        for x in range(width):
            y = int((1.0 - float(samples[x])) * 63)
            y = max(0, min(63, y))
            self._audio_bitmap[x, y] = 1

        self.set_custom_content(self._audio_group)

    def show_eq_bands(self, band_heights, num_bands=16):
        """Render EQ frequency-band bars on the OLED display.

        Switches to custom layout and draws vertical bars rising from the
        bottom of the screen, scaled to the OLED dimensions (128×64 px).

        Args:
            band_heights: Iterable of bar heights (0 to num_bands) per band.
            num_bands:    Total number of bands expected (default: 16).
        """
        self.use_custom_layout()

        self._audio_bitmap.fill(0)  # Fast native clear

        band_count = min(len(band_heights), num_bands)
        bar_width = max(1, 128 // num_bands)

        for i in range(band_count):
            # Scale band height to OLED height; leave a 1 px gap between bars
            pixel_height = int(band_heights[i] * 64 / num_bands)
            pixel_height = max(0, min(64, pixel_height))

            bar_start_x = i * bar_width
            bar_end_x = min(bar_start_x + bar_width - 1, 127)

            for x in range(bar_start_x, bar_end_x + 1):
                for y in range(64 - pixel_height, 64):
                    self._audio_bitmap[x, y] = 1

        self.set_custom_content(self._audio_group)

    def show_settings_menu(self, show=None):
        """Choose visibility of the settings menu, which replaces the main zone."""
        if show:
            JEBLogger.info("DISP", "Showing settings menu")
            self.settings_group.hidden = False
            self.main_group.hidden = True
        else:
            JEBLogger.info("DISP", "Hiding settings menu")
            self.settings_group.hidden = True
            self.main_group.hidden = False

    def cleanup(self):
        """Release display hardware resources on application exit.

        Call this when the application is exiting (e.g., Ctrl+C or Ctrl+D)
        to prevent the display bus from remaining locked.  CircuitPython can
        then reclaim the OLED for its console, and a soft-reboot (Ctrl+D)
        will no longer error with "GP5 in use".
        """
        JEBLogger.info("DISP", "[CLEANUP] Releasing display hardware")
        try:
            displayio.release_displays()
        except Exception as e:  # pylint: disable=broad-except
            JEBLogger.warning("DISP", f"[CLEANUP] release_displays failed: {e}")

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
