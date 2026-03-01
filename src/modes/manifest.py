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
    "POWER_TELEMETRY": {
        "id": "POWER_TELEMETRY",
        "name": "PWR TELEMETRY",
        "module_path": "modes.power_telemetry",
        "class_name": "PowerTelemetryMode",
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
    },
    "EMOJI_REVEAL": {
        "id": "EMOJI_REVEAL",
        "name": "EMOJI REVEAL",
        "module_path": "modes.emoji_reveal",
        "class_name": "EmojiRevealMode",
        "icon": "EMOJI_REVEAL",
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
                "key": "rounds",
                "label": "ROUNDS",
                "options": ["3", "5", "10"],
                "default": "5"
            }
        ]
    },
    "FREQ_HUNTER": {
        "id": "FREQ_HUNTER",
        "name": "FREQ HUNTER",
        "module_path": "modes.frequency_hunter",
        "class_name": "FrequencyHunterMode",
        "icon": "FREQ_HUNTER",
        "menu": "MAIN",
        "requires": ["CORE"],
        "settings": [
            {
                "key": "difficulty",
                "label": "DIFF",
                "options": ["NORMAL", "HARD"],
                "default": "NORMAL"
            },
            {
                "key": "time_limit",
                "label": "TIME",
                "options": ["30", "60", "90"],
                "default": "60"
            }
        ]
    },
    "ZERO_PLAYER_MENU": {
        "id": "ZERO_PLAYER_MENU",
        "name": "ZERO PLAYER",
        "module_path": "",
        "class_name": "",
        "icon": "ZERO_PLAYER",
        "menu": "MAIN",
        "submenu": "ZERO_PLAYER",
        "requires": ["CORE"],
        "settings": []
    },
    "CONWAYS_LIFE": {
        "id": "CONWAYS_LIFE",
        "name": "GAME OF LIFE",
        "module_path": "modes.conways_life",
        "class_name": "ConwaysLife",
        "icon": "CONWAYS_LIFE",
        "menu": "ZERO_PLAYER",
        "requires": ["CORE"],
        "settings": []
    },
    "LANGTONS_ANT": {
        "id": "LANGTONS_ANT",
        "name": "LANGTON'S ANT",
        "module_path": "modes.langtons_ant",
        "class_name": "LangtonsAnt",
        "icon": "LANGTONS_ANT",
        "menu": "ZERO_PLAYER",
        "requires": ["CORE"],
        "settings": [
            {
                "key": "ants",
                "label": "ANTS",
                "options": ["1", "2", "4"],
                "default": "1"
            }
        ]
    },
    "WOLFRAM_AUTOMATA": {
        "id": "WOLFRAM_AUTOMATA",
        "name": "WOLFRAM 1D",
        "module_path": "modes.wolfram_automata",
        "class_name": "WolframAutomata",
        "icon": "WOLFRAM_AUTOMATA",
        "menu": "ZERO_PLAYER",
        "requires": ["CORE"],
        "settings": [
            {
                "key": "rule",
                "label": "RULE",
                "options": ["30", "90", "110", "184"],
                "default": "90"
            }
        ]
    },
    "LISSAJOUS": {
        "id": "LISSAJOUS",
        "name": "LISSAJOUS",
        "module_path": "modes.lissajous",
        "class_name": "LissajousMode",
        "icon": "LISSAJOUS",
        "menu": "ZERO_PLAYER",
        "requires": ["CORE"],
        "settings": []
    },
    "BOIDS": {
        "id": "BOIDS",
        "name": "BOIDS",
        "module_path": "modes.boids",
        "class_name": "BoidsMode",
        "icon": "BOIDS",
        "menu": "ZERO_PLAYER",
        "requires": ["CORE"],
        "settings": []
    },
    "FALLING_SAND": {
        "id": "FALLING_SAND",
        "name": "FALLING SAND",
        "module_path": "modes.falling_sand",
        "class_name": "FallingSandMode",
        "icon": "FALLING_SAND",
        "menu": "ZERO_PLAYER",
        "requires": ["CORE"],
        "settings": []
    },
    "ORBITAL_STRIKE": {
        "id": "ORBITAL_STRIKE",
        "name": "ORBITAL STRIKE",
        "module_path": "modes.orbital_strike",
        "class_name": "OrbitalStrike",
        "icon": "ORBITAL_STRIKE",
        "menu": "MAIN",
        "requires": ["CORE", "INDUSTRIAL"],
        "settings": [
            {
                "key": "difficulty",
                "label": "DIFF",
                "options": ["NORMAL", "HARD", "INSANE"],
                "default": "NORMAL"
            }
        ]
    },
    "IRON_CANOPY": {
        "id": "IRON_CANOPY",
        "name": "IRON CANOPY",
        "module_path": "modes.iron_canopy",
        "class_name": "IronCanopy",
        "icon": "IRON_CANOPY",
        "menu": "MAIN",
        "requires": ["CORE", "INDUSTRIAL"],
        "settings": [
            {
                "key": "difficulty",
                "label": "DIFF",
                "options": ["NORMAL", "HARD", "INSANE"],
                "default": "NORMAL"
            }
        ]
    }
}

__all__ = ["MODE_REGISTRY"]
