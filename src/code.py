# File: src/code.py
"""
PROJECT: JEB - JADNET Electronics Box
"""

import asyncio
import json
import os
import time

import storage
import supervisor

from utilities.logger import JEBLogger, LogLevel

# Init logger at DEBUG for initial boot
JEBLogger.set_level(LogLevel.DEBUG)
JEBLogger.enable_file_logging(False)

# Check if SD card was mounted in boot.py
def is_sd_mounted():
    """Check if SD card is mounted by verifying the mount point."""
    try:
        mount = storage.getmount('/sd')
        return mount is not None
    except OSError:
        return False

def is_wifi_available():
    """Check if Wi-Fi module is available by attempting to import wifi."""
    try:
        import wifi
        import socketpool
        return True
    except ImportError:
        return False

SD_MOUNTED = is_sd_mounted()
ROOT_DATA_DIR = "/sd" if SD_MOUNTED else "/"
WEB_SERVER = None

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
        "web_server_port": 80,  # Default HTTP port
        "hardware_features": {}  # Empty dict means all hardware enabled
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

# --- HARDWARE DUMMY INJECTION ---

def _inject_hardware_dummies(features):
    """Replace disabled hardware manager modules with lightweight dummy classes.

    Called immediately after config loading and strictly before CoreManager is
    imported, so that all subsequent ``from managers.x import Y`` statements
    transparently receive the dummy implementation.

    Args:
        features: dict mapping feature name -> bool (True = real hardware,
                  False = inject dummy).  Unknown keys are silently ignored.
    """
    import sys

    # Maps each feature flag to the real manager module(s) it controls
    feature_map = {
        "audio":   ["managers.audio_manager", "managers.synth_manager"],
        "display": ["managers.display_manager"],
        "matrix":  ["managers.matrix_manager"],
        "leds":    ["managers.led_manager"],
        "buzzer":  ["managers.buzzer_manager"],
        "power":   ["managers.power_manager", "managers.adc_manager"],
        "segment": ["managers.segment_manager"],
    }

    # Maps each real manager module to its dummy counterpart
    dummy_map = {
        "managers.audio_manager":   "dummies.audio_manager",
        "managers.synth_manager":   "dummies.synth_manager",
        "managers.display_manager": "dummies.display_manager",
        "managers.matrix_manager":  "dummies.matrix_manager",
        "managers.led_manager":     "dummies.led_manager",
        "managers.buzzer_manager":  "dummies.buzzer_manager",
        "managers.power_manager":   "dummies.power_manager",
        "managers.adc_manager":     "dummies.adc_manager",
        "managers.segment_manager": "dummies.segment_manager",
    }

    for feature, enabled in features.items():
        if enabled or feature not in feature_map:
            continue
        for manager_module in feature_map[feature]:
            dummy_module_name = dummy_map.get(manager_module)
            if dummy_module_name is None:
                continue
            try:
                __import__(dummy_module_name)
                sys.modules[manager_module] = sys.modules[dummy_module_name]
                JEBLogger.info("CODE", f"Dummy injected: {manager_module}")
            except ImportError as e:
                JEBLogger.warning("CODE", f"Could not load dummy for {manager_module}: {e}")


# --- ENTRY POINT ---
JEBLogger.info("CODE", "*** BOOTING JEB SYSTEM ***")
JEBLogger.info("CODE", f"SD Card mounted: {SD_MOUNTED}")
config = load_config()

# Visual indicator: rapidly flash the onboard LED when test_mode is active
if config.get("test_mode", False):
    try:
        import digitalio
        import board as _board
        _led = digitalio.DigitalInOut(_board.LED)
        _led.direction = digitalio.Direction.OUTPUT
        for _ in range(10):
            _led.value = True
            time.sleep(0.05)
            _led.value = False
            time.sleep(0.05)
        _led.deinit()
    except Exception:
        pass  # Silently skip if onboard LED is unavailable

# Inject dummy modules for any disabled hardware features before any
# manager imports occur (including the CoreManager module-level imports).
_inject_hardware_dummies(config.get("hardware_features", {}))

# Do we have an SSID and Password
if config.get("wifi_ssid") and config.get("wifi_password"):
    JEBLogger.info("CODE", "Wi-Fi credentials provided in config")

    try:
        from managers.wifi_manager import WiFiManager
        wifi_manager = WiFiManager(config)
        JEBLogger.info("CODE", "WiFi Manager initialized")

        # OTA UPDATE CHECK
        if SD_MOUNTED and config.get("update_url", "") != "":
            try:
                from updater import should_check_for_updates, Updater, clear_update_flag

                if should_check_for_updates():
                    JEBLogger.info("CODE", "Update flag detected - starting OTA update process")

                    try:
                        updater = Updater(config, sd_mounted=SD_MOUNTED, wifi_manager=wifi_manager)
                        update_success = updater.run_update()

                        if update_success:
                            # Only clear flag on successful update
                            clear_update_flag()
                            JEBLogger.info("CODE", "✓ Update complete and installed - rebooting...")
                            updater.reboot()
                        else:
                            # Do NOT clear flag - preserve for retry on next boot
                            JEBLogger.warning("CODE", "⚠️ Update failed - flag preserved for retry")
                            JEBLogger.warning("CODE", "Device will attempt update again on next boot")

                    except Exception as e:
                        # Do NOT clear flag on fatal error - preserve for retry
                        JEBLogger.error("CODE", f"❌ Updater fatal error: {e}")
                        JEBLogger.warning("CODE", "Flag preserved - device will retry update on next boot")
                        JEBLogger.warning("CODE", "Continuing with existing firmware")
            except ImportError:
                JEBLogger.warning("CODE", "⚠️ Updater module not available")

        # WEB SERVER CHECK
        elif config.get("web_server_enabled", False):
            try:
                from managers.web_server_manager import WebServerManager
                JEBLogger.info("CODE", " --- WEB SERVER INITIALIZATION --- ")
                WEB_SERVER = WebServerManager(config, wifi_manager=wifi_manager)
                JEBLogger.info("CODE", "Web server manager initialized - will start with app")
            except ImportError:
                JEBLogger.warning("CODE", "⚠️ WebServerManager not available - check dependencies")
            except Exception as e:
                JEBLogger.error("CODE", f"⚠️ Web server initialization error: {e}")

    except ImportError:
        JEBLogger.warning("CODE", "⚠️ WiFiManager not available - skipping OTA update and web server")
else:
    JEBLogger.info("CODE", "No Wi-Fi credentials provided - skipping OTA update and web server initialization")


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

async def main():
    """Main asynchronous entry point for running the application and web server."""
    try:
        if app is None:
            JEBLogger.error("CODE", "‼️No application loaded.‼️")
            while True:
                time.sleep(1)
        else:
            JEBLogger.info("CODE", f"Starting main app loop for {type_name}")

            app_task = asyncio.create_task(app.start())

            coros = [app_task]

            if WEB_SERVER is not None:
                web_task = asyncio.create_task(WEB_SERVER.start())
                coros.append(web_task)

            done, pending = await asyncio.wait(coros, return_when=asyncio.FIRST_EXCEPTION)

            # Cancel any surviving background tasks before the supervisor reload
            for task in pending:
                task.cancel()

            # Log exceptions from completed tasks
            import traceback
            for task in done:
                exc = task.exception()
                if exc is not None:
                    JEBLogger.error("CODE", f"Task failed with error: {exc}")
                    traceback.print_exception(type(exc), exc, exc.__traceback__)
    except Exception as e:
        JEBLogger.error("CODE", f"🚨⛔ CRITICAL CRASH: {e}")
        import traceback
        traceback.print_exception(type(e), e, e.__traceback__)
        # Reduced sleep to maintain watchdog margin before reload
        time.sleep(2)
        supervisor.reload()

# 3. Main Execution
if __name__ == "__main__":
    asyncio.run(main())
