"""
core.satellites package

Exports package version and prepares public API surface.
"""

from .base import Satellite
from .industrial import IndustrialSatellite

__all__ = [
    "Satellite",
    "IndustrialSatellite"
]
