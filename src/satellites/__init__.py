"""
core.satellites package

Exports package version and prepares public API surface.
"""

from .base import Satellite
from .sat_01_industrial import IndustrialSatellite  # Deprecated: For backwards compatibility
from .sat_01_driver import IndustrialSatelliteDriver
from .sat_01_firmware import IndustrialSatelliteFirmware

__all__ = [
    "Satellite",
    "IndustrialSatellite",  # Deprecated: Use IndustrialSatelliteDriver or IndustrialSatelliteFirmware
    "IndustrialSatelliteDriver",
    "IndustrialSatelliteFirmware"
]
