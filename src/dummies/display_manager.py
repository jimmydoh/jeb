# File: src/dummies/display_manager.py
"""Dummy DisplayManager - no-op replacement for isolated hardware testing."""

import asyncio

class DummyStatus:
    """Simple class to mimic the status property of the real DisplayManager."""
    def __init__(self):
        self._value = "Dummy DisplayManager - no status available"

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, new_value):
        self._value = new_value

    @property
    def y(self):
        return 0
    
    @y.setter
    def y(self, new_y):
        pass

class DisplayManager:
    """Drop-in dummy for DisplayManager. All methods are no-ops."""

    def __init__(self, *args, **kwargs):
        self.status = DummyStatus()

    def use_standard_layout(self):
        pass

    def use_custom_layout(self):
        pass

    def set_custom_content(self, content_group):
        pass

    def update_header(self, text):
        pass

    def update_footer(self, text):
        pass

    def update_status(self, main_text, sub_text=None):
        pass

    async def scroll_loop(self):
        while True:
            await asyncio.sleep(0.1)

    async def animate_slide_in(self, main_text, sub_text=None, direction="left", delay=0.02):
        pass

    async def animate_typewriter(self, main_text, sub_text=None, char_delay=0.05):
        pass

    async def animate_blink(self, main_text, sub_text=None, times=3,
                             on_duration=0.3, off_duration=0.2):
        pass

    def show_waveform(self, samples):
        pass

    def show_eq_bands(self, band_heights, num_bands=16):
        pass

    def show_settings_menu(self, show=None):
        pass

    def update_settings_menu(self, menu_items, selected_index):
        pass

    def cleanup(self):
        pass
