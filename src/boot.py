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

# --- SD CARD INITIALIZATION ---
# Initialize SD card early for OTA updates (files downloaded to SD card)

SD_MOUNTED = False

def initialize_sd_card():
    """Initialize the SD card and mount it at /sd."""
    global SD_MOUNTED
    
    try:
        import busio
        import sdcardio
        
        print("boot.py: Initializing SPI for SD card", end="")
        spi_clock = getattr(board, "GP18")
        spi_mosi = getattr(board, "GP19")
        spi_miso = getattr(board, "GP16")
        sdcard_cs = getattr(board, "GP17")
        spi = busio.SPI(clock=spi_clock, MOSI=spi_mosi, MISO=spi_miso)
        print(" - ✅")
        
        print("boot.py: Initializing SD card", end="")
        sdcard = sdcardio.SDCard(spi, digitalio.DigitalInOut(sdcard_cs))
        print(" - ✅")
        
        print("boot.py: Mounting SD card at /sd", end="")
        vfs = storage.VfsFat(sdcard)
        storage.mount(vfs, "/sd")
        print(" - ✅")
        
        SD_MOUNTED = True
        return True
        
    except Exception as e:
        print(" - ❌")
        print(f"boot.py: SD card initialization failed: {e}")
        print("boot.py: OTA updates will not be available")
        return False

# Try to initialize SD card
initialize_sd_card()

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
    """
    # Check for update flag
    if file_exists(".update_flag"):
        print("boot.py: Update flag detected")
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
    # Normal boot: filesystem read-only for code, writable via USB mass storage
    # In CircuitPython, readonly=True means:
    #   - Running CircuitPython code CANNOT write to filesystem
    #   - USB mass storage (host computer) CAN still write to filesystem
    # This allows users to manually edit config.json or create .update_flag via USB
    # while preventing the running code from accidentally modifying files
    storage.remount("/", readonly=True)
    # USB mass storage is enabled by default

print("boot.py: Initialization complete")
