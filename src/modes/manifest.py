# File: src/modes/manifest.py
"""Mode Registry Manifest.

This module provides a centralized registry of all available mode classes.
CoreManager uses this manifest to dynamically register modes without
direct imports, avoiding circular dependencies and tight coupling.

To add a new mode:
1. Create your mode class in a new file in the modes/ directory
2. Import it in this file
3. Add it to the AVAILABLE_MODES list
"""

# Mode Registry
MODE_REGISTRY = {
    "MAINMENU": {
        "id": "MAINMENU",
        "name": "MAIN MENU",
        "module_path": "modes.main_menu",
        "class_name": "MainMenu",
        "icon": "home",
        "requires": ["CORE"],
        "settings": []
    },
    "DASHBOARD": {
        "id": "DASHBOARD",
        "name": "DASHBOARD",
        "module_path": "modes.main_menu",
        "class_name": "MainMenu",
        "icon": "home",
        "requires": ["CORE"],
        "settings": []
    },
    "SIMON": {
        "id": "SIMON",
        "name": "SIMON SAYS",
        "module_path": "modes.simon",
        "class_name": "SimonMode",
        "icon": "simon",
        "requires": ["CORE"],
        "settings": [
            {
                "key": "mode",
                "label": "MODE",
                "options": ["CLASSIC", "REVERSE", "BLIND"],
                "default": "CLASSIC"
            },
            {
                "key": "difficulty",
                "label": "DIFF",
                "options": ["EASY","NORMAL", "HARD", "INSANE"],
                "default": "NORMAL"
            }
        ]
    },
    "JEBRIS": {
        "id": "JEBRIS",
        "name": "JEBRIS",
        "module_path": "modes.jebris",
        "class_name": "JebrisMode",
        "icon": "tetris",
        "requires": ["CORE"],
        "settings": [
            {
                "key": "difficulty",
                "label": "SPEED",
                "options": ["EASY", "NORMAL", "HARD", "INSANE"],
                "default": "NORMAL"
            },
            {
                "key": "music",
                "label": "MUSIC",
                "options": ["ON", "OFF"],
                "default": "ON"
            }
        ]
    },
    "SAFE": {
        "id": "SAFE",
        "name": "SAFE CRACKER",
        "module_path": "modes.safe_cracker",
        "class_name": "SafeCrackerMode",
        "icon": "dial",
        "requires": ["CORE"],
        "settings": []
    },
    "IND_START": {
        "id": "IND_START",
        "name": "INDUSTRIAL STARTUP",
        "module_path": "modes.industrial_startup",
        "class_name": "IndustrialStartupMode",
        "icon": "factory",
        "requires": ["INDUSTRIAL"],
        "settings": []
    }
}

__all__ = ["MODE_REGISTRY"]
