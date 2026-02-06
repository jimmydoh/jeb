# filepath: jeb-core\src\core\modes\__init__.py
"""Top-level package for mode classes."""

# Import from manifest for centralized mode registry
from .manifest import AVAILABLE_MODES
from .base import BaseMode

__all__ = [
    "AVAILABLE_MODES",
    "BaseMode"
]
