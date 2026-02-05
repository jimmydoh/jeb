# File: src/core/managers/data_manager.py
"""Manages persistence for game scores and settings."""

import json
import os

class DataManager:
    """Handles loading and saving game data to JSON on the SD card."""
    def __init__(self, root_dir="/"):
        self.file_path = f"{root_dir}data/game_data.json"
        self.data = {}
        self._ensure_dir(f"{root_dir}data")
        self.load()

    def _ensure_dir(self, path):
        """Ensure the directory exists."""
        try:
            os.stat(path)
        except OSError:
            try:
                os.mkdir(path)
            except Exception as e:
                print(f"Error creating data dir: {e}")

    def load(self):
        """Load data from disk."""
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        except (OSError, ValueError):
            print("No game data found, creating new.")
            self.data = {}

    def save(self):
        """Save data to disk."""
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f)
        except OSError as e:
            print(f"Error saving game data: {e}")

    def get_high_score(self, mode_name, variant):
        """Get high score for a game."""
        return self.data.get(mode_name, {}).get(variant, {}).get("high_score", 0)

    def save_high_score(self, mode_name, variant, score):
        """Set high score if higher than current."""
        # Ensure mode and variant exist in data structure
        if mode_name not in self.data:
            self.data[mode_name] = {}
        if variant not in self.data[mode_name]:
            self.data[mode_name][variant] = {}
        current_high = self.data[mode_name][variant].get("high_score", 0)
        if score > current_high:
            self.data[mode_name][variant]["high_score"] = score
            self.save()
            return True
        return False

    def get_setting(self, mode_name, setting_key, default=None):
        """Retrieve a specific setting."""
        return self.data.get(mode_name, {}).get("CONFIG", {}).get(setting_key, default)

    def set_setting(self, mode_name, setting_key, value):
        """Update a specific setting."""
        # Ensure mode and CONFIG exist in data structure
        if mode_name not in self.data:
            self.data[mode_name] = {}
        if "CONFIG" not in self.data[mode_name]:
            self.data[mode_name]["CONFIG"] = {}
        self.data[mode_name]["CONFIG"][setting_key] = value
        self.save()
