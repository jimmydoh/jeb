"""
boot.py - Hardware Safety Initialization and Update Mode Detection
Runs before code.py to ensure safe hardware state during startup
and to configure filesystem permissions for OTA updates.
"""

import board
import digitalio
import storage
import os

# CRITICAL: Set MOSFET_CONTROL (GP14) to OUTPUT and LOW immediately
# This prevents floating pin states during boot that could cause
# MOSFETs to enter an undefined state and create unsafe power conditions.
mosfet_control = digitalio.DigitalInOut(getattr(board, "GP14"))
mosfet_control.direction = digitalio.Direction.OUTPUT
mosfet_control.value = False  # LOW = MOSFETs OFF (Safe State)

print("boot.py: MOSFET_CONTROL (GP14) initialized to LOW (Safe State)")

# --- OTA UPDATE MODE DETECTION ---
# Check if we need to enable filesystem writes for OTA updates

def file_exists(filepath):
    """Check if a file exists."""
    try:
        os.stat(filepath)
        return True
    except OSError:
        return False

def needs_update():
    """
    Determine if system needs to enter update mode.
    
    Returns True if:
    - Update flag file exists (.update_flag)
    - version.json is missing (first boot)
    """
    # Check for update flag
    if file_exists(".update_flag"):
        print("boot.py: Update flag detected")
        return True
    
    # Check for missing version.json (first boot)
    if not file_exists("version.json"):
        print("boot.py: version.json missing - first boot detected")
        return True
    
    return False

# Determine boot mode
update_mode = needs_update()

if update_mode:
    print("boot.py: ⚡ UPDATE MODE - Filesystem writeable by code")
    print("boot.py: USB mass storage DISABLED during update")
    # Make filesystem writeable by CircuitPython code
    # Disable USB mass storage during update for safety
    storage.remount("/", readonly=False)
    storage.disable_usb_drive()
else:
    print("boot.py: 🔒 NORMAL MODE - Filesystem read-only")
    print("boot.py: USB mass storage ENABLED")
    # Normal boot: filesystem read-only, USB mass storage enabled
    # This is the default, but we make it explicit
    storage.remount("/", readonly=True)
    # USB mass storage is enabled by default

print("boot.py: Initialization complete")
