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
import storage
import time

import supervisor

from utilities.logger import JEBLogger, LogLevel

# Init logger at DEBUG for initial boot
JEBLogger.set_level(LogLevel.DEBUG)
JEBLogger.enable_file_logging(False)

# Check if SD card was mounted in boot.py
# Note: We cannot import boot.py as it will re-execute the script
# Instead, check if /sd directory exists in the filesystem
# TODO: Fix this - I believe the /sd dir will exist regardless
def is_sd_mounted():
    """Check if SD card is mounted by verifying the mount point."""
    try:
        # storage.getmount returns the filesystem object mounted at path
        # or None if nothing is mounted.
        mount = storage.getmount('/sd')
        return mount is not None
    except OSError:
        return False

SD_MOUNTED = is_sd_mounted()
ROOT_DATA_DIR = "/sd" if SD_MOUNTED else "/"

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
        "type_name": "CORE",  # Human-readable name
        "wifi_ssid": "",  # Wi-Fi SSID (empty by default)
        "wifi_password": "",  # Wi-Fi password (empty by default)
        "update_url": "",  # OTA update URL (empty by default)
        "uart_baudrate": 115200,  # Default UART baudrate
        "uart_buffer_size": 512,  # Default UART buffer size
        "mount_sd_card": False,  # Whether to initialize SD card
        "debug_mode": False,  # Debug mode off by default
        "test_mode": True,  # Test mode on by default (real hardware should set to False)
        "web_server_enabled": False,  # Web server disabled by default
        "web_server_port": 80  # Default HTTP port
    }
    try:
        if file_exists("config.json"):
            with open("config.json", "r", encoding="utf-8") as f:
                config_data = json.load(f)
                JEBLogger.info("CODE", "Configuration loaded from config.json")
                # Merge with defaults - MicroPython compatible
                merged_config = default_config.copy()
                merged_config.update(config_data)
                return merged_config
        else:
            JEBLogger.warning("CODE", "No config.json found. Using default configuration.")
            return default_config
    except Exception as e:
        JEBLogger.error("CODE", f"Error loading config.json: {e}")
        JEBLogger.warning("CODE", "Using default configuration.")
        return default_config

# --- ENTRY POINT ---

JEBLogger.info("CODE", "*** BOOTING JEB SYSTEM ***")
JEBLogger.info("CODE", f"SD Card mounted: {SD_MOUNTED}")
config = load_config()

# --- OTA UPDATE CHECK ---
# Check if we need to run the updater before starting the main application
try:
    # Check if SD Mounted - Updater requires SD for temporary storage
    if SD_MOUNTED:

        from updater import should_check_for_updates, Updater, clear_update_flag

        if should_check_for_updates():
            JEBLogger.info("CODE", "Update flag detected - starting OTA update process")

            # Check if Wi-Fi is configured
            if config.get("wifi_ssid") and config.get("update_url"):
                try:
                    updater = Updater(config, sd_mounted=SD_MOUNTED)
                    update_success = updater.run_update()

                    if update_success:
                        # Only clear flag on successful update
                        clear_update_flag()
                        JEBLogger.info("CODE", "\n✓ Update complete and installed - rebooting...")
                        updater.reboot()
                    else:
                        # Do NOT clear flag - preserve for retry on next boot
                        JEBLogger.warning("CODE", "\n⚠️ Update failed - flag preserved for retry")
                        JEBLogger.warning("CODE", "Device will attempt update again on next boot")

                except Exception as e:
                    # Do NOT clear flag on fatal error - preserve for retry
                    JEBLogger.error("CODE", f"\n❌ Updater fatal error: {e}")
                    JEBLogger.warning("CODE", "Flag preserved - device will retry update on next boot")
                    JEBLogger.warning("CODE", "Continuing with existing firmware")
            else:
                JEBLogger.warning("CODE", "⚠️ Wi-Fi not configured - skipping update")
                JEBLogger.warning("CODE", "Configure wifi_ssid and update_url in config.json")
                clear_update_flag()  # Clear flag since config is missing

    else:
        from updater import clear_update_flag

        JEBLogger.warning("CODE", "⚠️ SD card not mounted - OTA updates require SD card")
        JEBLogger.warning("CODE", "Skipping update")
        clear_update_flag()

except ImportError:
    JEBLogger.warning("CODE", "⚠️ Updater module not available")


# --- WEB SERVER STARTUP (if enabled) ---
web_server = None
if config.get("web_server_enabled", False):
    try:
        from managers.web_server_manager import WebServerManager

        # Check if WiFi is configured
        if config.get("wifi_ssid") and config.get("wifi_password"):
            JEBLogger.info("CODE", " --- WEB SERVER INITIALIZATION --- ")
            web_server = WebServerManager(config)
            JEBLogger.info("CODE", "Web server manager initialized - will start with app")
        else:
            JEBLogger.warning("CODE", "⚠️ WiFi credentials not configured - web server disabled")
            JEBLogger.warning("CODE", "Configure wifi_ssid and wifi_password in config.json")
    except ImportError:
        JEBLogger.warning("CODE", "⚠️ WebServerManager not available - check dependencies")
    except Exception as e:
        JEBLogger.error("CODE", f"⚠️ Web server initialization error: {e}")


# --- APPLICATION RUN ---
app = None

role = config.get("role", "UNKNOWN")
type_id = config.get("type_id", "--")
type_name = config.get("type_name", "UNKNOWN")
debug_mode = config.get("debug_mode", False)
test_mode = config.get("test_mode", False)

JEBLogger.info("CODE", f"ROLE: {role}, ID: {type_id}, NAME: {type_name}")

# Add computed values to config for manager initialization
config["root_data_dir"] = ROOT_DATA_DIR

if test_mode:
    JEBLogger.warning("CODE", "⚠️ Running in TEST MODE. No main application will be loaded. ⚠️")
    from managers.console_manager import ConsoleManager
    app = ConsoleManager(role, type_id)
else:
    if role == "CORE" and type_id == "00":
        from core.core_manager import CoreManager
        app = CoreManager(config=config)

    elif role == "SAT" and type_id == "01":
        from satellites.sat_01_firmware import IndustrialSatelliteFirmware
        app = IndustrialSatelliteFirmware()

    else:
        JEBLogger.error("CODE", "❗Unknown role/type_id combination. No application loaded.❗")
        while True:
            time.sleep(1)

# 3. Main Execution
if __name__ == "__main__":
    try:
        if app is None:
            JEBLogger.error("CODE", "‼️No application loaded.‼️")
            while True:
                time.sleep(1)
        else:
            JEBLogger.info("CODE", f"Starting main app loop for {type_name} ")

            # If web server is enabled, run both app and web server concurrently
            if web_server is not None:
                async def run_both():
                    """Run both the main app and web server concurrently."""
                    app_task = asyncio.create_task(app.start())
                    web_task = asyncio.create_task(web_server.start())

                    # Use return_exceptions=True to capture errors without stopping other tasks
                    results = await asyncio.gather(app_task, web_task, return_exceptions=True)

                    # Check for exceptions in either task
                    for i, result in enumerate(results):
                        if isinstance(result, Exception):
                            task_name = "app" if i == 0 else "web_server"
                            JEBLogger.error("CODE", f"Task {task_name} failed with error: {result}")
                            import traceback
                            traceback.print_exception(type(result), result, result.__traceback__)

                asyncio.run(run_both())
            else:
                asyncio.run(app.start())
    except Exception as e:
        JEBLogger.error("CODE", f"🚨⛔ CRITICAL CRASH: {e}")
        import traceback
        traceback.print_exception(type(e), e, e.__traceback__)
        # Reduced sleep to maintain watchdog margin before reload
        time.sleep(2)
        supervisor.reload()
