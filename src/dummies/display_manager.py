# File: src/dummies/display_manager.py
"""Dummy DisplayManager - no-op replacement for isolated hardware testing."""

import asyncio


class DisplayManager:
    """Drop-in dummy for DisplayManager. All methods are no-ops."""

    def __init__(self, *args, **kwargs):
        pass

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

    def show_waveform(self, samples):
        pass

    def show_eq_bands(self, band_heights, num_bands=16):
        pass

    def show_settings_menu(self, show=None):
        pass

    def update_settings_menu(self, menu_items, selected_index):
        pass
