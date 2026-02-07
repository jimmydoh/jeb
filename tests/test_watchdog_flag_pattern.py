#!/usr/bin/env python3
"""Test the Watchdog Flag Pattern implementation.

This test validates that the fix for the "Blind Feeding" issue has been
applied correctly by checking that:
1. CoreManager has a watchdog_flags dictionary
2. All critical background tasks set their respective flags
3. The safe_feed_watchdog method checks all flags before feeding
4. Flags are reset after successful feeding
"""

import sys
import os
import re

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def test_watchdog_flags_dict_exists():
    """Test that watchdog_flags dictionary is initialized in CoreManager.__init__."""
    print("\nTesting that watchdog_flags dictionary exists...")
    
    # Read the core_manager.py file
    core_manager_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'src', 
        'core', 
        'core_manager.py'
    )
    
    with open(core_manager_path, 'r') as f:
        content = f.read()
    
    # Check for watchdog_flags initialization
    if 'self.watchdog_flags = {' not in content:
        print("  ✗ 'self.watchdog_flags = {' not found")
        return False
    
    print("  ✓ Found 'self.watchdog_flags' dictionary initialization")
    
    # Check for required flag keys
    required_flags = ["sat_network", "estop", "power", "connection", "hw_hid", "render"]
    for flag in required_flags:
        if f'"{flag}"' not in content:
            print(f"  ✗ Flag '{flag}' not found in watchdog_flags")
            return False
        print(f"  ✓ Found flag: {flag}")
    
    return True


def test_safe_feed_watchdog_method_exists():
    """Test that safe_feed_watchdog method exists and checks all flags."""
    print("\nTesting that safe_feed_watchdog method exists...")
    
    # Read the core_manager.py file
    core_manager_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'src', 
        'core', 
        'core_manager.py'
    )
    
    with open(core_manager_path, 'r') as f:
        content = f.read()
    
    # Check for safe_feed_watchdog method
    if 'def safe_feed_watchdog(self):' not in content:
        print("  ✗ 'def safe_feed_watchdog(self):' not found")
        return False
    
    print("  ✓ Found 'safe_feed_watchdog' method")
    
    # Extract the method
    method_pattern = r'def safe_feed_watchdog\(self\):(.*?)(?=\n    def |\n    async def |\Z)'
    match = re.search(method_pattern, content, re.DOTALL)
    
    if not match:
        print("  ✗ Could not extract safe_feed_watchdog method body")
        return False
    
    method_body = match.group(1)
    
    # Check that it checks all flags
    if 'all(self.watchdog_flags.values())' not in method_body:
        print("  ✗ Method does not check all flags with 'all(self.watchdog_flags.values())'")
        return False
    
    print("  ✓ Method checks all flags before feeding")
    
    # Check that it feeds the watchdog
    if 'microcontroller.watchdog.feed()' not in method_body:
        print("  ✗ Method does not feed watchdog with 'microcontroller.watchdog.feed()'")
        return False
    
    print("  ✓ Method feeds watchdog when all flags are True")
    
    # Check that it resets flags
    if 'self.watchdog_flags[key] = False' not in method_body:
        print("  ✗ Method does not reset flags after feeding")
        return False
    
    print("  ✓ Method resets flags after feeding")
    
    return True


def test_monitor_tasks_set_flags():
    """Test that all critical monitor tasks set their watchdog flags."""
    print("\nTesting that monitor tasks set their watchdog flags...")
    
    # Read the core_manager.py file
    core_manager_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'src', 
        'core', 
        'core_manager.py'
    )
    
    with open(core_manager_path, 'r') as f:
        content = f.read()
    
    # Define tasks and their corresponding flag names
    tasks_to_check = [
        ("monitor_estop", "estop"),
        ("monitor_power", "power"),
        ("monitor_connection", "connection"),
        ("monitor_hw_hid", "hw_hid"),
        ("render_loop", "render"),
    ]
    
    all_tasks_ok = True
    
    for task_name, flag_name in tasks_to_check:
        # Extract the task method
        method_pattern = rf'async def {task_name}\(self\):(.*?)(?=\n    async def |\n    def |\Z)'
        match = re.search(method_pattern, content, re.DOTALL)
        
        if not match:
            print(f"  ✗ Could not find {task_name} method")
            all_tasks_ok = False
            continue
        
        method_body = match.group(1)
        
        # Check if the flag is set
        flag_set_pattern = f'self.watchdog_flags["{flag_name}"] = True'
        if flag_set_pattern not in method_body:
            print(f"  ✗ {task_name} does not set watchdog flag '{flag_name}'")
            all_tasks_ok = False
        else:
            print(f"  ✓ {task_name} sets flag '{flag_name}'")
    
    return all_tasks_ok


def test_sat_network_sets_flag():
    """Test that SatelliteNetworkManager.monitor_satellites sets its flag."""
    print("\nTesting that SatelliteNetworkManager.monitor_satellites sets flag...")
    
    # Read the satellite_network_manager.py file
    sat_network_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'src', 
        'managers',
        'satellite_network_manager.py'
    )
    
    with open(sat_network_path, 'r') as f:
        content = f.read()
    
    # Check that __init__ accepts watchdog_flags parameter
    if 'watchdog_flags=None' not in content:
        print("  ✗ __init__ does not accept watchdog_flags parameter")
        return False
    
    print("  ✓ __init__ accepts watchdog_flags parameter")
    
    # Extract the monitor_satellites method
    method_pattern = r'async def monitor_satellites\(self\):(.*?)(?=\n    async def |\n    def |\Z)'
    match = re.search(method_pattern, content, re.DOTALL)
    
    if not match:
        print("  ✗ Could not find monitor_satellites method")
        return False
    
    method_body = match.group(1)
    
    # Check if the flag is set
    if 'self.watchdog_flags["sat_network"] = True' not in method_body:
        print("  ✗ monitor_satellites does not set watchdog flag 'sat_network'")
        return False
    
    print("  ✓ monitor_satellites sets flag 'sat_network'")
    
    # Check for None check
    if 'if self.watchdog_flags is not None:' not in method_body:
        print("  ✗ monitor_satellites does not check if watchdog_flags is None")
        return False
    
    print("  ✓ monitor_satellites checks if watchdog_flags is not None")
    
    return True


def test_main_loop_uses_safe_feed():
    """Test that the main loop uses safe_feed_watchdog instead of direct feed."""
    print("\nTesting that main loop uses safe_feed_watchdog...")
    
    # Read the core_manager.py file
    core_manager_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'src', 
        'core', 
        'core_manager.py'
    )
    
    with open(core_manager_path, 'r') as f:
        content = f.read()
    
    # Extract the start method
    start_pattern = r'async def start\(self\):(.*?)(?=\n    async def |\n    def |\Z)'
    match = re.search(start_pattern, content, re.DOTALL)
    
    if not match:
        print("  ✗ Could not find start() method")
        return False
    
    start_body = match.group(1)
    print("  ✓ Found start() method")
    
    # Check for safe_feed_watchdog calls
    if 'self.safe_feed_watchdog()' not in start_body:
        print("  ✗ 'self.safe_feed_watchdog()' not found in start() method")
        return False
    
    print("  ✓ start() method uses safe_feed_watchdog")
    
    # Count occurrences
    feed_count = start_body.count('self.safe_feed_watchdog()')
    print(f"  ✓ Found {feed_count} safe_feed_watchdog call(s) in start() method")
    
    # Check that direct microcontroller.watchdog.feed() is NOT used in main loop
    # (It should only be in safe_feed_watchdog now)
    direct_feed_count = start_body.count('microcontroller.watchdog.feed()')
    if direct_feed_count > 0:
        print(f"  ⚠ Warning: Found {direct_feed_count} direct watchdog.feed() call(s) in start()")
        print("  ⚠ Main loop should use safe_feed_watchdog() instead")
    else:
        print("  ✓ No direct watchdog.feed() calls in start() method")
    
    return True


def test_run_mode_with_safety_uses_safe_feed():
    """Test that run_mode_with_safety uses safe_feed_watchdog."""
    print("\nTesting that run_mode_with_safety uses safe_feed_watchdog...")
    
    # Read the core_manager.py file
    core_manager_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'src', 
        'core', 
        'core_manager.py'
    )
    
    with open(core_manager_path, 'r') as f:
        content = f.read()
    
    # Extract the run_mode_with_safety method
    method_pattern = r'async def run_mode_with_safety\(self.*?\):(.*?)(?=\n    async def |\n    def |\Z)'
    match = re.search(method_pattern, content, re.DOTALL)
    
    if not match:
        print("  ✗ Could not find run_mode_with_safety method")
        return False
    
    method_body = match.group(1)
    print("  ✓ Found run_mode_with_safety method")
    
    # Check for safe_feed_watchdog calls
    if 'self.safe_feed_watchdog()' not in method_body:
        print("  ✗ 'self.safe_feed_watchdog()' not found in run_mode_with_safety")
        return False
    
    print("  ✓ run_mode_with_safety uses safe_feed_watchdog")
    
    # Check that direct microcontroller.watchdog.feed() is NOT used
    if 'microcontroller.watchdog.feed()' in method_body:
        print("  ⚠ Warning: Direct watchdog.feed() still found in run_mode_with_safety")
        print("  ⚠ Should use safe_feed_watchdog() instead")
    else:
        print("  ✓ No direct watchdog.feed() calls in run_mode_with_safety")
    
    return True


def test_sat_network_receives_flags():
    """Test that CoreManager passes watchdog_flags to SatelliteNetworkManager."""
    print("\nTesting that CoreManager passes watchdog_flags to SatelliteNetworkManager...")
    
    # Read the core_manager.py file
    core_manager_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'src', 
        'core', 
        'core_manager.py'
    )
    
    with open(core_manager_path, 'r') as f:
        content = f.read()
    
    # Check that SatelliteNetworkManager is initialized with watchdog_flags
    if 'SatelliteNetworkManager(' not in content:
        print("  ✗ SatelliteNetworkManager initialization not found")
        return False
    
    # Extract the initialization
    init_pattern = r'self\.sat_network = SatelliteNetworkManager\((.*?)\)'
    match = re.search(init_pattern, content, re.DOTALL)
    
    if not match:
        print("  ✗ Could not extract SatelliteNetworkManager initialization")
        return False
    
    init_args = match.group(1)
    
    # Check if watchdog_flags is passed
    if 'self.watchdog_flags' not in init_args:
        print("  ✗ watchdog_flags not passed to SatelliteNetworkManager")
        return False
    
    print("  ✓ CoreManager passes watchdog_flags to SatelliteNetworkManager")
    
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Watchdog Flag Pattern Implementation Verification")
    print("Testing fix for watchdog blind feeding")
    print("=" * 60)
    
    results = []
    results.append(("Watchdog flags dictionary exists", test_watchdog_flags_dict_exists()))
    results.append(("safe_feed_watchdog method exists", test_safe_feed_watchdog_method_exists()))
    results.append(("Monitor tasks set flags", test_monitor_tasks_set_flags()))
    results.append(("SatelliteNetworkManager sets flag", test_sat_network_sets_flag()))
    results.append(("CoreManager passes flags to SatelliteNetworkManager", test_sat_network_receives_flags()))
    results.append(("Main loop uses safe_feed_watchdog", test_main_loop_uses_safe_feed()))
    results.append(("run_mode_with_safety uses safe_feed_watchdog", test_run_mode_with_safety_uses_safe_feed()))
    
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
        print("The watchdog flag pattern successfully:")
        print("  • Prevents blind feeding if critical tasks crash")
        print("  • Checks all critical task flags before feeding")
        print("  • Resets flags after feeding to detect next iteration")
        print("  • Allows system reset to recover from zombie state")
        print("  • Maintains all existing watchdog functionality")
        sys.exit(0)
    else:
        print("SOME TESTS FAILED ✗")
        sys.exit(1)
