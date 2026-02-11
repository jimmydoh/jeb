"""
core.satellites package

Exports package version and prepares public API surface.
"""

from .sat_01_driver import IndustrialSatelliteDriver
from .sat_01_firmware import IndustrialSatelliteFirmware

__all__ = [
    "IndustrialSatelliteDriver",
    "IndustrialSatelliteFirmware"
]
