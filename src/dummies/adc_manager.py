# File: src/dummies/adc_manager.py
"""Dummy ADCManager - no-op replacement for isolated hardware testing."""


class ADCManager:
    """Drop-in dummy for ADCManager. All reads return 0.0."""

    def __init__(self, *args, **kwargs):
        pass

    def add_channel(self, name, pin_or_index, divider_multiplier=1.0):
        pass

    def read(self, name):
        return 0.0

    def read_all(self):
        return {}
