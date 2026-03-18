"""
boot.py - Hardware Safety Initialization and Update Mode Detection
Runs before code.py to ensure safe hardware state during startup
and to configure filesystem permissions for OTA updates.

Filesystem access policy:
  - USB connected (VBUS HIGH):  Readonly for code; USB mass storage enabled.
  - Sat Bus only  (VBUS LOW):   Writable for code; USB mass storage disabled.
                                Holding GP12 (encoder push) during boot forces
                                readonly for 'data-only USB' debugging.
"""

import board
import digitalio
import storage
import os

# CRITICAL: Set MOSFET_CONTROL (GP14) to OUTPUT and LOW immediately
mosfet_control = digitalio.DigitalInOut(getattr(board, "GP14"))
mosfet_control.direction = digitalio.Direction.OUTPUT
mosfet_control.value = False  # LOW = MOSFETs OFF (Safe State)

print("boot.py: MOSFET_CONTROL (GP14) initialized to LOW (Safe State)")

# --- VBUS SENSE DETECTION ---
vbus_sense = digitalio.DigitalInOut(getattr(board, "GP24"))
vbus_sense.direction = digitalio.Direction.INPUT
vbus_high = vbus_sense.value  # True = USB present, False = Sat Bus only

print(f"boot.py: VBUS sense (GP24) = {'HIGH (USB)' if vbus_high else 'LOW (Sat Bus)'}")

# --- BOOT OVERRIDE BUTTON (GP12 = Encoder Push) ---
override_pin = digitalio.DigitalInOut(getattr(board, "GP12"))
override_pin.direction = digitalio.Direction.INPUT
override_pin.pull = digitalio.Pull.UP
force_readonly = not override_pin.value  # Active-LOW: pressed → force readonly

if force_readonly:
    print("boot.py: Override button (GP12) held - forcing readonly mode")

# --- SD CARD INITIALIZATION ---
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
        return False

initialize_sd_card()

# --- HARDWARE-DRIVEN FILESYSTEM ROUTING ---
if not vbus_high and not force_readonly:
    # --- SATELLITE DEPLOYMENT MODE (OTA ENABLED) ---
    print("boot.py: 🛰️  SATELLITE MODE - Filesystem writeable by code")
    print("boot.py: USB mass storage DISABLED (no USB connection)")
    storage.remount("/", readonly=False)
    storage.disable_usb_drive()
else:
    # --- NORMAL / DEBUG MODE (OTA DISABLED) ---
    if force_readonly:
        print("boot.py: 🔒 FORCED READONLY MODE - Override button held")
    else:
        print("boot.py: 🔒 NORMAL MODE - Filesystem read-only (USB Connected)")
    print("boot.py: USB mass storage ENABLED")
    storage.remount("/", readonly=True)

print("boot.py: Initialization complete")
