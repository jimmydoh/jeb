# File: src/dummies/power_manager.py
"""Dummy PowerManager - no-op replacement for isolated hardware testing."""

import asyncio

class _SafeVoltageDict(dict):
    """Dict subclass that returns a safe non-alerting voltage for any missing key."""

    def __missing__(self, key):
        return 5.0


class PowerManager:
    """Drop-in dummy for PowerManager.

    check_power_integrity() always returns True so the CoreManager boot
    sequence proceeds normally. Voltage readings use safe placeholder values
    that will not trigger any brownout or failure alerts.
    """

    def __init__(self, *args, **kwargs):
        self.sat_pwr = type('sat_pwr', (), {'value': False})()
        self.sat_detect = type('sat_detect', (), {'value': False})()
        pass

    @property
    def status(self):
        return _SafeVoltageDict()

    @property
    def max(self):
        return _SafeVoltageDict()

    @property
    def min(self):
        return _SafeVoltageDict()

    @property
    def satbus_connected(self):
        return False

    @property
    def satbus_powered(self):
        return False

    async def soft_start_satellites(self):
        return True, "OK"

    def emergency_kill(self):
        pass

    async def check_power_integrity(self):
        return True
