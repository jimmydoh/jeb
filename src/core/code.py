"""
PROJECT: JEB - JADNET Electronics Box - CORE COMMAND UNIT (MASTER)
VERSION: 0.1 - 2024-06-05

--- TODO LIST ---
Implement advanced error logging for satellite communications.
Add Matrix animations, non blocking for individual pixels and fill modes.
Replace neobar progress with matrix-based version.
Victory animation on matrix.
Boot animation on matrix.
Check power integrity during various load conditions.
boot.py for file handling.
calibration.json for voltage calibration values.
"""
import asyncio

from managers import JEBManager

jeb = JEBManager()

asyncio.run(jeb.start())
