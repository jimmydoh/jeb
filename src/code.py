# File: src/code.py
"""
PROJECT: JEB - JADNET Electronics Box

--- TODO LIST ---
CORE:
Implement advanced error logging for satellite communications.
Add Matrix animations, non blocking for individual pixels and fill modes.
Replace neobar progress with matrix-based version.
Victory animation on matrix.
Boot animation on matrix.
Check power integrity during various load conditions.
boot.py for file handling.
calibration.json for voltage calibration values.

SAT 01:
Implement power monitoring via ADC.
Implement power protection for downstream satellites.
Optimize async tasks for responsiveness.
Implement configuration commands from Master.
UART Buffering and flow control.
Test with multiple chained satellites.
"""

import asyncio
import json
import os
import time

import board
import busio
import digitalio
import sdcardio
import storage
import supervisor

ROOT_DATA_DIR = "/"

def file_exists(filename):
    """Check if a file exists on the filesystem."""
    try:
        os.stat(filename)
        return True
    except OSError:
        return False

def load_config():
    """Load configuration from config.json if it exists, otherwise return defaults."""
    default_config = {
        "role": "CORE",  # Default role
        "type_id": "00",  # Satellite ID (00 for core)
        "uart_baudrate": 115200,  # Default UART baudrate
        "mount_sd_card": False,  # Whether to initialize SD card
        "debug_mode": False,  # Debug mode off by default
        "test_mode": True  # Test mode on by default (real hardware should set to False)
    }
    try:
        if file_exists("config.json"):
            with open("config.json", "r", encoding="utf-8") as f:
                config_data = json.load(f)
                print("Configuration loaded from config.json")
                return {**default_config, **config_data}  # Merge with defaults
        else:
            print("No config.json found. Using default configuration.")
            return default_config
    except Exception as e:
        print(f"Error loading config.json: {e}")
        print("Using default configuration.")
        return default_config

def initialize_sd_card():
    """Initialize the SD card and mount it."""
    # SD Card Setup
    # SPI Pin Setup for Pico 2
    # SCK=GP18, MOSI=GP19, MISO=GP16, CS=GP17
    try:
        print("Initializing SPI interface", end="")
        spi_clock = getattr(board, "GP18")
        spi_mosi = getattr(board, "GP19")
        spi_miso = getattr(board, "GP16")
        sdcard_cs = getattr(board, "GP17")
        spi = busio.SPI(clock=spi_clock, MOSI=spi_mosi, MISO=spi_miso)
        print(" - ✅")
    except Exception as e:
        print(" - ❌")
        print(f"SPI initialization failed: {e}")
        return False

    try:
        print("Initializing SD card", end="")
        sdcard = sdcardio.SDCard(spi, digitalio.DigitalInOut(sdcard_cs))
        print(" - ✅")
    except Exception as e:
        print(" - ❌")
        print(f"SD Card initialization failed: {e}")
        return False

    try:
        print("Mounting SD card", end="")
        vfs = storage.VfsFat(sdcard)
        storage.mount(vfs, "/sd")
        print(" - ✅")
    except Exception as e:
        print(" - ❌")
        print(f"SD Card mounting failed: {e}")
        return False

    return True

# --- ENTRY POINT ---

print("*** BOOTING JEB SYSTEM ***")
config = load_config()

if config.get("mount_sd_card"):
    if initialize_sd_card():
        ROOT_DATA_DIR = "/sd"
    else:
        ROOT_DATA_DIR = "/"

app = None

role = config.get("role", "UNKNOWN")
type_id = config.get("type_id", "--")
type_name = config.get("type_name", "UNKNOWN")
debug_mode = config.get("debug_mode", False)
test_mode = config.get("test_mode", False)

print(f"ROLE: {role}, ID: {type_id}, NAME: {type_name}")

if test_mode:
    print("⚠️ Running in TEST MODE. No main application will be loaded. ⚠️")
    from testing import TestManager
    app = TestManager(role, type_id)
else:
    if role == "CORE" and type_id == "00":
        from core.core_manager import CoreManager
        app = CoreManager()

    elif role == "SAT" and type_id == "01":
        from satellites import IndustrialSatellite
        app = IndustrialSatellite(active=True, uart=None)

    else:
        print("❗Unknown role/type_id combination. No application loaded.❗")
        while True:
            time.sleep(1)

# 3. Main Execution
if __name__ == "__main__":
    try:
        if app is None:
            print("‼️No application loaded.‼️")
        else:
            print(f"Starting main app loop for {type_name} ")
            asyncio.run(app.start())
    except Exception as e:
        print(f"🚨⛔ CRITICAL CRASH: {e}")
        import traceback
        traceback.print_exception(e)
        time.sleep(5)
        supervisor.reload()
