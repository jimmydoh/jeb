# filepath: jeb-core\src\core\modes\__init__.py
"""Top-level package for mode classes."""

# Import from manifest for centralized mode registry
from .manifest import AVAILABLE_MODES

# For backward compatibility, also export individual mode classes
from .industrial_startup import IndustrialStartup
from .jebris import JEBris
from .main_menu import MainMenu
from .safe_cracker import SafeCracker
from .simon import Simon

__all__ = [
    "AVAILABLE_MODES",
    "IndustrialStartup",
    "JEBris",
    "MainMenu",
    "SafeCracker",
    "Simon",
]
