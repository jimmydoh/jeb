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
import digitalio
import supervisor

# --- CONFIGURATION ---
TEST_TRIGGER_FILE = "jeb_test.txt"

def file_exists(filename):
    try:
        os.stat(filename)
        return True
    except OSError:
        return False

# --- ENTRY POINT ---
print(f"Checking for {TEST_TRIGGER_FILE}...")

if file_exists(TEST_TRIGGER_FILE):
    print("⚠️ TEST MODE TRIGGERED ⚠️")
    print("Loading Test Runner...")
    print("Connect to Serial Console NOW.")
    
    # Import and run the test harness
    import test_runner
    asyncio.run(test_runner.run())

else:
    app = None

    # 1. Load Configuration
    try:
        with open("/config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
    except OSError:
        print("CRITICAL ERROR: config.json missing!")
        # Fallback or halt
        config = {"role": "UNKNOWN"}

    print(f"BOOTING JEB SYSTEM... ROLE: {config.get('role')}")

    # 2. Conditional Loading
    if config["role"] == "CORE":
        from core.core_manager import CoreManager
        app = CoreManager()

    elif config["role"] == "SAT":
        from satellites import IndustrialSatellite
        # Pass the specific ID or Type if needed
        app = IndustrialSatellite(active=True, uart=None)

    else:
        print("UNKNOWN ROLE. HALTING.")
        while True:
            time.sleep(1)

    # 3. Main Execution
    if __name__ == "__main__":
        try:
            if app is None:
                print("No application configured; aborting.")
            else:
                asyncio.run(app.start())
        except Exception as e:
            print(f"CRITICAL CRASH: {e}")
            import traceback
            traceback.print_exception(e)
            time.sleep(5)
            supervisor.reload()
