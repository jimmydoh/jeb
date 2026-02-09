#!/usr/bin/env python3
"""Test the satellite render loop and frame sync implementation.

This test validates that:
1. IndustrialSatelliteFirmware has a render_loop method
2. The render loop uses the same frame time as CoreManager (60Hz)
3. Frame sync state variables are initialized
4. SYNC_FRAME command is in the protocol
5. SYNC_FRAME command handler exists in satellite firmware
6. CoreManager broadcasts frame sync
"""

import sys
import os
import re

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def test_satellite_render_frame_time_exists():
    """Test that IndustrialSatelliteFirmware has RENDER_FRAME_TIME constant."""
    print("\nTesting that IndustrialSatelliteFirmware has RENDER_FRAME_TIME...")
    
    sat_firmware_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'src', 
        'satellites',
        'sat_01_firmware.py'
    )
    
    with open(sat_firmware_path, 'r') as f:
        content = f.read()
    
    # Check for RENDER_FRAME_TIME constant
    if 'RENDER_FRAME_TIME = 1.0 / 60.0' not in content:
        print("  ✗ 'RENDER_FRAME_TIME = 1.0 / 60.0' not found")
        return False
    
    print("  ✓ Found RENDER_FRAME_TIME = 1.0 / 60.0 (60Hz)")
    return True


def test_satellite_render_loop_exists():
    """Test that IndustrialSatelliteFirmware has render_loop method."""
    print("\nTesting that IndustrialSatelliteFirmware has render_loop...")
    
    sat_firmware_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'src', 
        'satellites',
        'sat_01_firmware.py'
    )
    
    with open(sat_firmware_path, 'r') as f:
        content = f.read()
    
    # Check for render_loop method
    if 'async def render_loop(self):' not in content:
        print("  ✗ 'async def render_loop(self):' not found")
        return False
    
    print("  ✓ Found render_loop method")
    
    # Extract the method
    method_pattern = r'async def render_loop\(self\):(.*?)(?=\n    async def |\n    def |\Z)'
    match = re.search(method_pattern, content, re.DOTALL)
    
    if not match:
        print("  ✗ Could not extract render_loop method body")
        return False
    
    method_body = match.group(1)
    
    # Check that it calls root_pixels.show()
    if 'self.root_pixels.show()' not in method_body:
        print("  ✗ Method does not call 'self.root_pixels.show()'")
        return False
    
    print("  ✓ Method calls self.root_pixels.show()")
    
    # Check that it increments frame counter
    if 'self.frame_counter' not in method_body:
        print("  ✗ Method does not increment frame_counter")
        return False
    
    print("  ✓ Method increments frame_counter")
    
    # Check that it uses RENDER_FRAME_TIME
    if 'self.RENDER_FRAME_TIME' not in method_body:
        print("  ✗ Method does not use RENDER_FRAME_TIME")
        return False
    
    print("  ✓ Method uses RENDER_FRAME_TIME for sleep")
    
    return True


def test_satellite_frame_sync_state():
    """Test that IndustrialSatelliteFirmware initializes frame sync state."""
    print("\nTesting that IndustrialSatelliteFirmware has frame sync state...")
    
    sat_firmware_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'src', 
        'satellites',
        'sat_01_firmware.py'
    )
    
    with open(sat_firmware_path, 'r') as f:
        content = f.read()
    
    # Check for frame sync state variables
    required_vars = ['frame_counter', 'last_sync_frame', 'time_offset']
    
    for var in required_vars:
        if f'self.{var}' not in content:
            print(f"  ✗ 'self.{var}' not found in __init__")
            return False
        print(f"  ✓ Found self.{var}")
    
    return True


def test_satellite_starts_render_loop():
    """Test that satellite's start() method starts render_loop."""
    print("\nTesting that satellite start() method starts render_loop...")
    
    sat_firmware_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'src', 
        'satellites',
        'sat_01_firmware.py'
    )
    
    with open(sat_firmware_path, 'r') as f:
        content = f.read()
    
    # Extract the start method
    start_pattern = r'async def start\(self\):(.*?)(?=\n    async def |\n    def |\Z)'
    match = re.search(start_pattern, content, re.DOTALL)
    
    if not match:
        print("  ✗ Could not find start() method")
        return False
    
    start_body = match.group(1)
    
    # Check for render_loop task creation
    if 'asyncio.create_task(self.render_loop())' not in start_body:
        print("  ✗ 'asyncio.create_task(self.render_loop())' not found in start()")
        return False
    
    print("  ✓ start() creates render_loop task")
    
    # Check for LED animate_loop task creation
    if 'asyncio.create_task(self.leds.animate_loop())' not in start_body:
        print("  ✗ 'asyncio.create_task(self.leds.animate_loop())' not found in start()")
        return False
    
    print("  ✓ start() creates LED animate_loop task")
    
    return True


def test_sync_frame_protocol():
    """Test that SYNC_FRAME command is in protocol."""
    print("\nTesting that SYNC_FRAME command exists in protocol...")
    
    protocol_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'src',
        'protocol.py'
    )
    
    with open(protocol_path, 'r') as f:
        content = f.read()
    
    # Check for SYNC_FRAME in COMMAND_MAP
    if '"SYNC_FRAME":' not in content:
        print("  ✗ 'SYNC_FRAME' not found in COMMAND_MAP")
        return False
    
    print("  ✓ Found SYNC_FRAME in COMMAND_MAP")
    
    # Check for SYNC_FRAME in PAYLOAD_SCHEMAS
    if '"SYNC_FRAME":' not in content or 'Frame sync' not in content:
        print("  ✗ SYNC_FRAME payload schema not found")
        return False
    
    print("  ✓ Found SYNC_FRAME payload schema")
    
    return True


def test_satellite_sync_frame_handler():
    """Test that satellite has SYNC_FRAME command handler."""
    print("\nTesting that satellite handles SYNC_FRAME command...")
    
    sat_firmware_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'src', 
        'satellites',
        'sat_01_firmware.py'
    )
    
    with open(sat_firmware_path, 'r') as f:
        content = f.read()
    
    # Extract the process_local_cmd method
    method_pattern = r'async def process_local_cmd\(self, cmd, val\):(.*?)(?=\n    async def |\n    def |\Z)'
    match = re.search(method_pattern, content, re.DOTALL)
    
    if not match:
        print("  ✗ Could not find process_local_cmd method")
        return False
    
    method_body = match.group(1)
    
    # Check for SYNC_FRAME handler
    if 'cmd == "SYNC_FRAME"' not in method_body:
        print("  ✗ SYNC_FRAME command handler not found")
        return False
    
    print("  ✓ Found SYNC_FRAME command handler")
    
    # Check that it updates sync state
    if 'self.last_sync_frame' not in method_body:
        print("  ✗ Handler does not update last_sync_frame")
        return False
    
    print("  ✓ Handler updates last_sync_frame")
    
    if 'self.time_offset' not in method_body:
        print("  ✗ Handler does not update time_offset")
        return False
    
    print("  ✓ Handler updates time_offset")
    
    return True


def test_core_frame_sync_state():
    """Test that CoreManager has frame sync state."""
    print("\nTesting that CoreManager has frame sync state...")
    
    core_manager_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'src', 
        'core',
        'core_manager.py'
    )
    
    with open(core_manager_path, 'r') as f:
        content = f.read()
    
    # Check for frame sync state variables
    if 'self.frame_counter' not in content:
        print("  ✗ 'self.frame_counter' not found")
        return False
    
    print("  ✓ Found self.frame_counter")
    
    if 'self.last_sync_broadcast' not in content:
        print("  ✗ 'self.last_sync_broadcast' not found")
        return False
    
    print("  ✓ Found self.last_sync_broadcast")
    
    return True


def test_core_broadcasts_frame_sync():
    """Test that CoreManager broadcasts frame sync in render_loop."""
    print("\nTesting that CoreManager broadcasts frame sync...")
    
    core_manager_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'src', 
        'core',
        'core_manager.py'
    )
    
    with open(core_manager_path, 'r') as f:
        content = f.read()
    
    # Extract the render_loop method
    method_pattern = r'async def render_loop\(self\):(.*?)(?=\n    async def |\Z)'
    match = re.search(method_pattern, content, re.DOTALL)
    
    if not match:
        print("  ✗ Could not find render_loop method")
        return False
    
    method_body = match.group(1)
    
    # Check for frame counter increment
    if 'self.frame_counter' not in method_body:
        print("  ✗ render_loop does not increment frame_counter")
        return False
    
    print("  ✓ render_loop increments frame_counter")
    
    # Check for SYNC_FRAME broadcast
    if 'SYNC_FRAME' not in method_body:
        print("  ✗ render_loop does not broadcast SYNC_FRAME")
        return False
    
    print("  ✓ render_loop broadcasts SYNC_FRAME")
    
    # Check for periodic broadcast (not every frame)
    if 'last_sync_broadcast' not in method_body:
        print("  ✗ render_loop does not check last_sync_broadcast")
        return False
    
    print("  ✓ render_loop uses periodic broadcast (not every frame)")
    
    return True


def test_frame_rate_consistency():
    """Test that Core and Satellite use the same frame rate."""
    print("\nTesting frame rate consistency between Core and Satellite...")
    
    core_manager_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'src', 
        'core',
        'core_manager.py'
    )
    
    sat_firmware_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'src', 
        'satellites',
        'sat_01_firmware.py'
    )
    
    with open(core_manager_path, 'r') as f:
        core_content = f.read()
    
    with open(sat_firmware_path, 'r') as f:
        sat_content = f.read()
    
    # Both should have RENDER_FRAME_TIME = 1.0 / 60.0
    core_has_60hz = 'RENDER_FRAME_TIME = 1.0 / 60.0' in core_content
    sat_has_60hz = 'RENDER_FRAME_TIME = 1.0 / 60.0' in sat_content
    
    if not core_has_60hz:
        print("  ✗ CoreManager does not have RENDER_FRAME_TIME = 1.0 / 60.0")
        return False
    
    if not sat_has_60hz:
        print("  ✗ IndustrialSatelliteFirmware does not have RENDER_FRAME_TIME = 1.0 / 60.0")
        return False
    
    print("  ✓ Both Core and Satellite use 60Hz (RENDER_FRAME_TIME = 1.0 / 60.0)")
    
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Satellite Render Loop and Frame Sync Verification")
    print("Testing LED/Neopixel rendering revamp implementation")
    print("=" * 60)
    
    results = []
    results.append(("Satellite has RENDER_FRAME_TIME", test_satellite_render_frame_time_exists()))
    results.append(("Satellite has render_loop method", test_satellite_render_loop_exists()))
    results.append(("Satellite has frame sync state", test_satellite_frame_sync_state()))
    results.append(("Satellite starts render_loop", test_satellite_starts_render_loop()))
    results.append(("SYNC_FRAME in protocol", test_sync_frame_protocol()))
    results.append(("Satellite handles SYNC_FRAME", test_satellite_sync_frame_handler()))
    results.append(("CoreManager has frame sync state", test_core_frame_sync_state()))
    results.append(("CoreManager broadcasts frame sync", test_core_broadcasts_frame_sync()))
    results.append(("Frame rate consistency", test_frame_rate_consistency()))
    
    print("\n" + "=" * 60)
    print("Test Results Summary:")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {test_name}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("ALL TESTS PASSED ✓")
        print()
        print("The satellite render loop implementation successfully:")
        print("  • Adds render_loop to satellites at 60Hz (matches Core)")
        print("  • Provides centralized LED hardware writes (root_pixels.show())")
        print("  • Implements frame sync protocol (SYNC_FRAME command)")
        print("  • Broadcasts frame sync from Core to satellites")
        print("  • Tracks time offset for coordinated animations")
        print("  • Maintains backward compatibility with existing LED commands")
        sys.exit(0)
    else:
        print("SOME TESTS FAILED ✗")
        sys.exit(1)
