# File: src/modes/manifest.py
"""Mode Registry Manifest.

This module provides a centralized registry of all available mode classes.
CoreManager uses this manifest to dynamically register modes without
direct imports, avoiding circular dependencies and tight coupling.

To add a new mode:
1. Create your mode class in a new file in the modes/ directory
2. Add its details to the MODE_REGISTRY dictionary below, following the existing structure.
"""

# Mode Registry
MODE_REGISTRY = {
    "MAINMENU": {
        "id": "MAINMENU",
        "name": "MAIN MENU",
        "module_path": "modes.main_menu",
        "class_name": "MainMenu",
        "icon": "DEFAULT",
        "order": 0,
        "requires": ["CORE"],
        "settings": []
    },
    "DASHBOARD": {
        "id": "DASHBOARD",
        "name": "DASHBOARD",
        "module_path": "modes.main_menu",
        "class_name": "MainMenu",
        "icon": "DEFAULT",
        "order": 0,
        "requires": ["CORE"],
        "settings": []
    },
    "ZERO_PLAYER_MENU": {
        "id": "ZERO_PLAYER_MENU",
        "name": "ZERO PLAYER",
        "module_path": "modes.zero_player",
        "class_name": "ZeroPlayerMode",
        "icon": "ZERO_PLAYER",
        "menu": "MAIN",
        "has_tutorial": True,
        "order": 500,
        "submenu": "ZERO_PLAYER",
        "requires": ["CORE"],
        "settings": []
    },
}

# Admin Menu Items
MODE_REGISTRY |= {
    "LAYOUT_CONFIGURATOR": {
        "id": "LAYOUT_CONFIGURATOR",
        "name": "LAYOUT CONFIG",
        "module_path": "modes.layout_configurator",
        "class_name": "LayoutConfigurator",
        "icon": "ADMIN",
        "menu": "ADMIN",
        "order": 1020,
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
        "order": 1030,
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
        "order": 1099,
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
        "order": 1015,
        "requires": ["CORE"],
        "settings": []
    },
}

# CORE Game Modes
MODE_REGISTRY |= {
    "SIMON": {
        "id": "SIMON",
        "name": "SIMON SAYS",
        "module_path": "modes.simon",
        "class_name": "Simon",
        "icon": "SIMON",
        "menu": "MAIN",
        "has_tutorial": True,
        "order": 10,
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
            },
            {
                "key": "audio_engine",
                "label": "AUDIO",
                "options": ["MODERN", "CLASSIC"],
                "default": "MODERN"
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
        "has_tutorial": True,
        "order": 20,
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
        "has_tutorial": True,
        "order": 30,
        "requires": ["CORE"],
        "settings": []
    },
    "PONG": {
        "id": "PONG",
        "name": "MINI PONG",
        "module_path": "modes.pong",
        "class_name": "Pong",
        "icon": "PONG",
        "menu": "MAIN",
        "has_tutorial": True,
        "order": 40,
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
    "SNAKE": {
        "id": "SNAKE",
        "name": "CYBER SNAKE",
        "module_path": "modes.cyber_snake",
        "class_name": "CyberSnakeMode",
        "icon": "SNAKE",
        "menu": "MAIN",
        "has_tutorial": True,
        "order": 80,
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
    "ASTRO_BREAKER": {
        "id": "ASTRO_BREAKER",
        "name": "ASTRO BREAKER",
        "module_path": "modes.astro_breaker",
        "class_name": "AstroBreaker",
        "icon": "ASTRO_BREAKER",
        "menu": "MAIN",
        "has_tutorial": True,
        "order": 50,
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
        "has_tutorial": True,
        "order": 60,
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
    "LUNAR_SALVAGE": {
        "id": "LUNAR_SALVAGE",
        "name": "LUNAR SALVAGE",
        "module_path": "modes.lunar_salvage",
        "class_name": "LunarSalvage",
        "icon": "LUNAR_SALVAGE",
        "menu": "MAIN",
        "has_tutorial": True,
        "order": 65,
        "requires": ["CORE"],
        "settings": [
            {
                "key": "difficulty",
                "label": "DIFF",
                "options": ["EASY", "NORMAL", "HARD", "INSANE"],
                "default": "NORMAL"
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
        "has_tutorial": True,
        "order": 70,
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
    "VIRTUAL_PET": {
        "id": "VIRTUAL_PET",
        "name": "VIRTUAL PET",
        "module_path": "modes.virtual_pet",
        "class_name": "VirtualPet",
        "icon": "VIRTUAL_PET",
        "menu": "MAIN",
        "has_tutorial": True,
        "order": 110,
        "requires": ["CORE"],
        "settings": []
    },
    "RHYTHM": {
        "id": "RHYTHM",
        "name": "NEON BEATS",
        "module_path": "modes.rhythm_mode",
        "class_name": "RhythmMode",
        "icon": "RHYTHM",
        "menu": "MAIN",
        "has_tutorial": True,
        "order": 999,
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
        "has_tutorial": True,
        "order": 90,
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
        "has_tutorial": True,
        "order": 100,
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
}

# Zero Player Game Modes
MODE_REGISTRY |= {
    "CONWAYS_LIFE": {
        "id": "CONWAYS_LIFE",
        "name": "GAME OF LIFE",
        "module_path": "modes.conways_life",
        "class_name": "ConwaysLife",
        "icon": "CONWAYS_LIFE",
        "menu": "ZERO_PLAYER",
        "order": 510,
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
        "order": 520,
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
        "order": 530,
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
        "order": 540,
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
        "order": 550,
        "requires": ["CORE"],
        "settings": []
    },
    "PLASMA": {
        "id": "PLASMA",
        "name": "PLASMA",
        "module_path": "modes.plasma",
        "class_name": "PlasmaMode",
        "icon": "PLASMA",
        "menu": "ZERO_PLAYER",
        "order": 560,
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
        "order": 570,
        "requires": ["CORE"],
        "settings": []
    },
    "BOUNCING_SPRITE": {
        "id": "BOUNCING_SPRITE",
        "name": "BOUNCING SPRITE",
        "module_path": "modes.bouncing_sprite",
        "class_name": "BouncingSprite",
        "icon": "BOUNCING_SPRITE",
        "menu": "ZERO_PLAYER",
        "order": 580,
        "requires": ["CORE"],
        "settings": []
    },
    "WIREWORLD": {
        "id": "WIREWORLD",
        "name": "WIREWORLD",
        "module_path": "modes.wireworld",
        "class_name": "Wireworld",
        "icon": "WIREWORLD",
        "menu": "ZERO_PLAYER",
        "order": 590,
        "requires": ["CORE"],
        "settings": []
    },
    "STARFIELD": {
        "id": "STARFIELD",
        "name": "STARFIELD",
        "module_path": "modes.starfield",
        "class_name": "StarfieldMode",
        "icon": "STARFIELD",
        "menu": "ZERO_PLAYER",
        "order": 600,
        "requires": ["CORE"],
        "settings": [
            {
                "key": "warp",
                "label": "WARP",
                "options": ["1", "2", "3", "4", "5", "MAX"],
                "default": "3"
            }
        ]
    },
}

# Sat Type 01 INDUSTRIAL Game Modes
MODE_REGISTRY |= {
    "IND_START": {
        "id": "IND_START",
        "name": "INDUSTRIAL STARTUP",
        "module_path": "modes.industrial_startup",
        "class_name": "IndustrialStartup",
        "icon": "IND",
        "menu": "MAIN",
        "has_tutorial": True,
        "order": 1,
        "requires": ["INDUSTRIAL"],
        "settings": []
    },
    "ABYSSAL_ROVER": {
        "id": "ABYSSAL_ROVER",
        "name": "ABYSSAL ROVER",
        "module_path": "modes.abyssal_rover",
        "class_name": "AbyssalRover",
        "icon": "ABYSSAL_ROVER",
        "menu": "MAIN",
        "has_tutorial": True,
        "order": 85,
        "requires": ["CORE"],
        "optional": ["INDUSTRIAL"],
        "settings": [
            {
                "key": "difficulty",
                "label": "DIFF",
                "options": ["NORMAL", "HARD", "INSANE"],
                "default": "NORMAL"
            }
        ]
    },
    "ABYSSAL_PING": {
        "id": "ABYSSAL_PING",
        "name": "ABYSSAL PING",
        "module_path": "modes.abyssal_ping",
        "class_name": "AbyssalPing",
        "icon": "ABYSSAL_PING",
        "menu": "MAIN",
        "has_tutorial": True,
        "order": 2,
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
    "ORBITAL_STRIKE": {
        "id": "ORBITAL_STRIKE",
        "name": "ORBITAL STRIKE",
        "module_path": "modes.orbital_strike",
        "class_name": "OrbitalStrike",
        "icon": "ORBITAL_STRIKE",
        "menu": "MAIN",
        "has_tutorial": True,
        "order": 3,
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
        "has_tutorial": True,
        "order": 4,
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
    "DEFCON_COMMANDER": {
        "id": "DEFCON_COMMANDER",
        "name": "DEFCON CMDR",
        "module_path": "modes.defcon_commander",
        "class_name": "DefconCommander",
        "icon": "DEFCON_COMMANDER",
        "menu": "MAIN",
        "has_tutorial": True,
        "order": 5,
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
    "ARTILLERY_COMMAND": {
        "id": "ARTILLERY_COMMAND",
        "name": "ARTY COMMAND",
        "module_path": "modes.artillery_command",
        "class_name": "ArtilleryCommand",
        "icon": "ARTILLERY_COMMAND",
        "menu": "MAIN",
        "has_tutorial": True,
        "order": 6,
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
    "ENIGMA_BYTE": {
        "id": "ENIGMA_BYTE",
        "name": "ENIGMA BYTE",
        "module_path": "modes.enigma_byte",
        "class_name": "EnigmaByte",
        "icon": "ENIGMA_BYTE",
        "menu": "MAIN",
        "has_tutorial": True,
        "order": 7,
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
    "BUNKER_DEFUSE": {
        "id": "BUNKER_DEFUSE",
        "name": "BUNKER DEFUSE",
        "module_path": "modes.bunker_defuse",
        "class_name": "BunkerDefuse",
        "icon": "BUNKER_DEFUSE",
        "menu": "MAIN",
        "has_tutorial": True,
        "order": 8,
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
    "SEISMIC_STABILIZER": {
        "id": "SEISMIC_STABILIZER",
        "name": "SEISMIC STAB",
        "module_path": "modes.seismic_stabilizer",
        "class_name": "SeismicStabilizer",
        "icon": "SEISMIC_STABILIZER",
        "menu": "MAIN",
        "has_tutorial": True,
        "order": 8,
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
}

__all__ = ["MODE_REGISTRY"]
