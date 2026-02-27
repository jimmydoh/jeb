# File: src/core/managers/data_manager.py
"""Manages persistence for game scores and settings."""

import json
import os

from utilities.logger import JEBLogger

class DataManager:
    """Handles loading and saving game data to JSON on the SD card."""
    def __init__(self, root_dir="/"):
        JEBLogger.info("DATA", f"[INIT] DataManager - root_dir: {root_dir}")
        self.file_path = f"{root_dir}data/game_data.json"
        self.data = {}
        self._ensure_dir(f"{root_dir}data")
        self.load()

    def _ensure_dir(self, path):
        """Ensure the directory exists."""
        try:
            JEBLogger.debug("DATA", f"Ensuring data directory exists at: {path}")
            os.stat(path)
        except OSError:
            try:
                JEBLogger.debug("DATA", f"Creating data directory at: {path}")
                os.mkdir(path)
            except Exception as e:
                JEBLogger.error("DATA", f"Error creating data directory at {path}")
                JEBLogger.error("DATA", f"Error details: {e}")

    def load(self):
        """Load data from disk."""
        try:
            JEBLogger.debug("DATA", f"Loading game data from: {self.file_path}")
            with open(self.file_path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        except (OSError, ValueError):
            JEBLogger.debug("DATA", f"No game data found, creating new state values.")
            self.data = {}

    def save(self):
        """Save data to disk."""
        try:
            JEBLogger.debug("DATA", f"Saving game data to: {self.file_path}")
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f)
        except OSError as e:
            JEBLogger.error("DATA", f"Error saving game data to {self.file_path}")
            JEBLogger.error("DATA", f"Error details: {e}")

    def get_high_score(self, mode_name, variant=None):
        """Get high score for a game."""
        JEBLogger.debug("DATA", f"Retrieving high score for mode: {mode_name}, variant: {variant}")
        # If variant is None, try and return the first available variant's high score, otherwise return 0
        if mode_name in self.data:
            if variant and variant in self.data[mode_name]:
                return self.data[mode_name][variant].get("high_score", 0)
            elif not variant:
                # Return the high score of the first variant found
                for var_data in self.data[mode_name].values():
                    if "high_score" in var_data:
                        return var_data["high_score"]

    def save_high_score(self, mode_name, variant, score):
        """Set high score if higher than current."""
        JEBLogger.debug("DATA", f"Attempting to save high score for mode: {mode_name}, variant: {variant}, score: {score}")
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
        JEBLogger.debug("DATA", f"Retrieving setting '{setting_key}' for mode: {mode_name} with default: {default}")
        return self.data.get(mode_name, {}).get("CONFIG", {}).get(setting_key, default)

    def set_setting(self, mode_name, setting_key, value):
        """Update a specific setting."""
        JEBLogger.debug("DATA", f"Setting '{setting_key}' for mode: {mode_name} to value: {value}")
        # Ensure mode and CONFIG exist in data structure
        if mode_name not in self.data:
            self.data[mode_name] = {}
        if "CONFIG" not in self.data[mode_name]:
            self.data[mode_name]["CONFIG"] = {}
        self.data[mode_name]["CONFIG"][setting_key] = value
        self.save()
