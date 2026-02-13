# filepath: jeb-core\src\core\managers\__init__.py
"""Top-level package for manager classes."""

from .power_manager import PowerManager
from .watchdog_manager import WatchdogManager

__all__ = [
    "PowerManager",
    "WatchdogManager"
]
