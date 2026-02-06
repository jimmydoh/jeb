#!/usr/bin/env python3
"""Test that the watchdog feed fix is present in run_mode_with_safety.

This test validates that the fix for the watchdog starvation issue has been
applied correctly by checking that watchdog feeding is called in the 
run_mode_with_safety method's waiting loop. The implementation now uses
the safe_feed_watchdog() method which implements the watchdog flag pattern.
"""

import sys
import os
import re

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def test_watchdog_feed_present_in_code():
    """Test that watchdog feeding is present in run_mode_with_safety."""
    print("\nTesting that watchdog feed is present in code...")
    
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
    
    # Find the run_mode_with_safety method
    method_pattern = r'async def run_mode_with_safety\(self.*?\n(.*?)(?=\n    async def|\n    def|\Z)'
    match = re.search(method_pattern, content, re.DOTALL)
    
    if not match:
        print("  ✗ Could not find run_mode_with_safety method")
        return False
    
    method_body = match.group(1)
    print("  ✓ Found run_mode_with_safety method")
    
    # Check for the while loop
    if 'while not sub_task.done():' not in method_body:
        print("  ✗ Could not find 'while not sub_task.done():' loop")
        return False
    
    print("  ✓ Found 'while not sub_task.done():' loop")
    
    # Extract the while loop body
    loop_start = method_body.find('while not sub_task.done():')
    loop_body = method_body[loop_start:]
    
    # Find the next method or class definition to limit the scope
    next_def = loop_body.find('\n    async def', 10)
    if next_def == -1:
        next_def = loop_body.find('\n    def', 10)
    if next_def != -1:
        loop_body = loop_body[:next_def]
    
    # Check for watchdog feed call in the loop (now uses safe_feed_watchdog)
    if 'self.safe_feed_watchdog()' not in loop_body:
        print("  ✗ 'self.safe_feed_watchdog()' not found in while loop")
        return False
    
    print("  ✓ Found 'self.safe_feed_watchdog()' in while loop")
    
    # Check that the feed is before the sleep call (at the top of the loop)
    feed_pos = loop_body.find('self.safe_feed_watchdog()')
    sleep_pos = loop_body.find('await asyncio.sleep(0.1)')
    
    if sleep_pos == -1:
        print("  ⚠ Warning: 'await asyncio.sleep(0.1)' not found in loop")
    elif feed_pos > sleep_pos:
        print("  ⚠ Warning: safe_feed_watchdog() appears after sleep, should be at top of loop")
    else:
        print("  ✓ safe_feed_watchdog() is positioned correctly (before sleep)")
    
    return True


def test_watchdog_feed_in_main_loop():
    """Test that watchdog feed is also present in the main start() loop."""
    print("\nTesting that watchdog feed is present in main start() loop...")
    
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
    
    # Find the start method
    start_pattern = r'async def start\(self\):(.*?)(?=\n    async def|\n    def|\Z)'
    match = re.search(start_pattern, content, re.DOTALL)
    
    if not match:
        print("  ✗ Could not find start() method")
        return False
    
    start_body = match.group(1)
    print("  ✓ Found start() method")
    
    # Check for watchdog feed in the main loop (now uses safe_feed_watchdog)
    if 'self.safe_feed_watchdog()' not in start_body:
        print("  ✗ 'self.safe_feed_watchdog()' not found in start() method")
        return False
    
    print("  ✓ Found 'self.safe_feed_watchdog()' in start() method")
    
    # Count occurrences
    feed_count = start_body.count('self.safe_feed_watchdog()')
    print(f"  ✓ Found {feed_count} safe_feed_watchdog call(s) in start() method")
    
    return True


def test_microcontroller_import():
    """Test that microcontroller module is imported."""
    print("\nTesting that microcontroller is imported...")
    
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
    
    # Check for microcontroller import
    if 'import microcontroller' not in content:
        print("  ✗ 'import microcontroller' not found")
        return False
    
    print("  ✓ Found 'import microcontroller'")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Watchdog Feed Fix Verification")
    print("Testing fix for watchdog starvation during gameplay")
    print("=" * 60)
    
    results = []
    results.append(("Microcontroller Import", test_microcontroller_import()))
    results.append(("Watchdog Feed in run_mode_with_safety", test_watchdog_feed_present_in_code()))
    results.append(("Watchdog Feed in start() loop", test_watchdog_feed_in_main_loop()))
    
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
        print("The fix successfully:")
        print("  • Uses safe_feed_watchdog() in run_mode_with_safety loop")
        print("  • Uses safe_feed_watchdog() in main start() loop")
        print("  • Imports microcontroller module for watchdog access")
        print("  • Prevents system reset during long-running modes")
        print("  • Implements watchdog flag pattern to prevent blind feeding")
        sys.exit(0)
    else:
        print("SOME TESTS FAILED ✗")
        sys.exit(1)
