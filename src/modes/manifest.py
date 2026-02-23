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
        "icon": "DEFAULT",
        "requires": ["CORE"],
        "settings": []
    },
    "DASHBOARD": {
        "id": "DASHBOARD",
        "name": "DASHBOARD",
        "module_path": "modes.main_menu",
        "class_name": "MainMenu",
        "icon": "DEFAULT",
        "requires": ["CORE"],
        "settings": []
    },
    "SIMON": {
        "id": "SIMON",
        "name": "SIMON SAYS",
        "module_path": "modes.simon",
        "class_name": "Simon",
        "icon": "SIMON",
        "menu": "MAIN",
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
        "class_name": "JEBris",
        "icon": "JEBRIS",
        "menu": "MAIN",
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
        "class_name": "SafeCracker",
        "icon": "SAFE",
        "menu": "MAIN",
        "requires": ["CORE"],
        "settings": []
    },
    "IND_START": {
        "id": "IND_START",
        "name": "INDUSTRIAL STARTUP",
        "module_path": "modes.industrial_startup",
        "class_name": "IndustrialStartup",
        "icon": "IND",
        "menu": "MAIN",
        "requires": ["INDUSTRIAL"],
        "settings": []
    },
    "PONG": {
        "id": "PONG",
        "name": "MINI PONG",
        "module_path": "modes.pong",
        "class_name": "Pong",
        "icon": "PONG",
        "menu": "MAIN",
        "requires": ["CORE"],
        "optional": ["INDUSTRIAL"],
        "settings": [
            {
                "key": "mode",
                "label": "MODE",
                "options": ["1P", "2P"],
                "default": "1P"
            },
            {
                "key": "difficulty",
                "label": "DIFF",
                "options": ["EASY", "NORMAL", "HARD", "INSANE"],
                "default": "NORMAL"
            }
        ]
    },
    "ASTRO_BREAKER": {
        "id": "ASTRO_BREAKER",
        "name": "ASTRO BREAKER",
        "module_path": "modes.astro_breaker",
        "class_name": "AstroBreaker",
        "icon": "ASTRO_BREAKER",
        "menu": "MAIN",
        "requires": ["CORE"],
        "settings": [
            {
                "key": "difficulty",
                "label": "DIFF",
                "options": ["NORMAL", "HARD", "INSANE"],
                "default": "NORMAL"
            }
        ]
    },
    "TRENCH_RUN": {
        "id": "TRENCH_RUN",
        "name": "TRENCH RUN",
        "module_path": "modes.trench_run",
        "class_name": "TrenchRun",
        "icon": "TRENCH_RUN",
        "menu": "MAIN",
        "requires": ["CORE"],
        "settings": [
            {
                "key": "difficulty",
                "label": "DIFF",
                "options": ["NORMAL", "HARD", "INSANE"],
                "default": "NORMAL"
            },
            {
                "key": "perspective",
                "label": "VIEW",
                "options": ["3RD_PERSON", "1ST_PERSON"],
                "default": "3RD_PERSON"
            }
        ]
    },
    "DATA_FLOW": {
        "id": "DATA_FLOW",
        "name": "DATA FLOW",
        "module_path": "modes.data_flow",
        "class_name": "DataFlowMode",
        "icon": "DATA_FLOW",
        "menu": "MAIN",
        "requires": ["CORE"],
        "settings": [
            {
                "key": "difficulty",
                "label": "DIFF",
                "options": ["NORMAL", "HARD"],
                "default": "NORMAL"
            }
        ]
    },
    "LAYOUT_CONFIGURATOR": {
        "id": "LAYOUT_CONFIGURATOR",
        "name": "LAYOUT CONFIG",
        "module_path": "modes.layout_configurator",
        "class_name": "LayoutConfigurator",
        "icon": "ADMIN",
        "menu": "ADMIN",
        "requires": ["CORE"],
        "settings": []
    },
    "GLOBAL_SETTINGS": {
        "id": "GLOBAL_SETTINGS",
        "name": "GLOBAL SETTINGS",
        "module_path": "modes.global_settings",
        "class_name": "GlobalSettings",
        "icon": "ADMIN",
        "menu": "ADMIN",
        "requires": ["CORE"],
        "settings": []
    },
    "DEBUG": {
        "id": "DEBUG",
        "name": "DEBUG DASH",
        "module_path": "modes.debug",
        "class_name": "DebugMode",
        "icon": "ADMIN",
        "menu": "ADMIN",
        "requires": ["CORE"],
        "settings": []
    },
    "SNAKE": {
        "id": "SNAKE",
        "name": "CYBER SNAKE",
        "module_path": "modes.cyber_snake",
        "class_name": "CyberSnakeMode",
        "icon": "SNAKE",
        "menu": "MAIN",
        "requires": ["CORE"],
        "settings": [
            {
                "key": "difficulty",
                "label": "DIFF",
                "options": ["NORMAL", "HARD", "INSANE"],
                "default": "NORMAL"
            },
            {
                "key": "edges",
                "label": "EDGES",
                "options": ["WRAP", "WALLS"],
                "default": "WRAP"
            }
        ]
    },
    "RHYTHM": {
        "id": "RHYTHM",
        "name": "NEON BEATS",
        "module_path": "modes.rhythm_mode",
        "class_name": "RhythmMode",
        "icon": "RHYTHM",
        "menu": "MAIN",
        "requires": ["CORE"],
        "settings": [
            {
                "key": "difficulty",
                "label": "DIFF",
                "options": ["EASY", "NORMAL", "HARD"],
                "default": "NORMAL"
            },
            {
                "key": "latency",
                "label": "LATENCY",
                "options": ["0", "20", "45", "70", "100"],
                "default": "45"
            }
        ]
    }
}

__all__ = ["MODE_REGISTRY"]
