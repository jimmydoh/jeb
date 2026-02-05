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
            with open(self.file_path, "r") as f:
                self.data = json.load(f)
        except (OSError, ValueError):
            print("No game data found, creating new.")
            self.data = {}

    def save(self):
        """Save data to disk."""
        try:
            with open(self.file_path, "w") as f:
                json.dump(self.data, f)
        except OSError as e:
            print(f"Error saving game data: {e}")

    def get_score(self, game_key):
        """Get high score for a game."""
        return self.data.get(game_key, {}).get("high_score", 0)

    def set_score(self, game_key, score):
        """Set high score if higher than current."""
        current = self.get_score(game_key)
        if score > current:
            if game_key not in self.data:
                self.data[game_key] = {}
            self.data[game_key]["high_score"] = score
            self.save()
            return True
        return False

    def get_setting(self, game_key, setting_key, default=None):
        """Retrieve a specific setting."""
        return self.data.get(game_key, {}).get("settings", {}).get(setting_key, default)

    def set_setting(self, game_key, setting_key, value):
        """Update a specific setting."""
        if game_key not in self.data:
            self.data[game_key] = {}
        if "settings" not in self.data[game_key]:
            self.data[game_key]["settings"] = {}

        self.data[game_key]["settings"][setting_key] = value
        self.save()
