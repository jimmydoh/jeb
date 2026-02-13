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

from .industrial_startup import IndustrialStartup
from .jebris import JEBris
from .main_menu import MainMenu
from .safe_cracker import SafeCracker
from .simon import Simon

# Registry of all available mode classes
# Each entry should be a mode class (not an instance)
AVAILABLE_MODES = [
    IndustrialStartup,
    JEBris,
    MainMenu,
    SafeCracker,
    Simon,
]

DEFAULT_METADATA = {
    "id": "UNKNOWN",
    "name": "Unknown Mode",
    "icon": "DEFAULT",
    "requires": ["CORE"],
    "settings": []
}

__all__ = ["AVAILABLE_MODES", "DEFAULT_METADATA"]
