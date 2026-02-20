# File: src/dummies/segment_manager.py
"""Dummy SegmentManager - no-op replacement for isolated hardware testing."""

import asyncio


class SegmentManager:
    """Drop-in dummy for SegmentManager. All methods are no-ops."""

    def __init__(self, *args, **kwargs):
        pass

    async def start_message(self, message, loop=False, speed=0.3, direction="L"):
        pass

    async def apply_command(self, cmd, val):
        pass

    async def start_corruption(self, duration=None):
        pass

    async def start_matrix(self, duration=None):
        pass
