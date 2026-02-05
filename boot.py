"""
boot.py - Hardware Safety Initialization
Runs before code.py to ensure safe hardware state during startup.
"""

import board
import digitalio

# CRITICAL: Set MOSFET_CONTROL (GP14) to OUTPUT and LOW immediately
# This prevents floating pin states during boot that could cause
# MOSFETs to enter an undefined state and create unsafe power conditions.
mosfet_control = digitalio.DigitalInOut(board.GP14)
mosfet_control.direction = digitalio.Direction.OUTPUT
mosfet_control.value = False  # LOW = MOSFETs OFF (Safe State)

print("boot.py: MOSFET_CONTROL (GP14) initialized to LOW (Safe State)")
