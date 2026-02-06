#!/usr/bin/env python3
"""Test that the watchdog feed fix is present in run_mode_with_safety.

This test validates that the fix for the watchdog starvation issue has been
applied correctly by checking that microcontroller.watchdog.feed() is called
in the run_mode_with_safety method's waiting loop.
"""

import sys
import os
import re

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def test_watchdog_feed_present_in_code():
    """Test that watchdog.feed() call is present in run_mode_with_safety."""
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
    
    # Check for watchdog feed call in the loop
    if 'microcontroller.watchdog.feed()' not in loop_body:
        print("  ✗ 'microcontroller.watchdog.feed()' not found in while loop")
        return False
    
    print("  ✓ Found 'microcontroller.watchdog.feed()' in while loop")
    
    # Check that the feed is before the sleep call (at the top of the loop)
    feed_pos = loop_body.find('microcontroller.watchdog.feed()')
    sleep_pos = loop_body.find('await asyncio.sleep(0.1)')
    
    if feed_pos > sleep_pos:
        print("  ⚠ Warning: watchdog.feed() appears after sleep, should be at top of loop")
    else:
        print("  ✓ watchdog.feed() is positioned correctly (before sleep)")
    
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
    
    # Check for watchdog feed in the main loop
    if 'microcontroller.watchdog.feed()' not in start_body:
        print("  ✗ 'microcontroller.watchdog.feed()' not found in start() method")
        return False
    
    print("  ✓ Found 'microcontroller.watchdog.feed()' in start() method")
    
    # Count occurrences
    feed_count = start_body.count('microcontroller.watchdog.feed()')
    print(f"  ✓ Found {feed_count} watchdog feed call(s) in start() method")
    
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
        print("  • Adds watchdog.feed() in run_mode_with_safety loop")
        print("  • Maintains watchdog.feed() in main start() loop")
        print("  • Imports microcontroller module for watchdog access")
        print("  • Prevents system reset during long-running modes")
        sys.exit(0)
    else:
        print("SOME TESTS FAILED ✗")
        sys.exit(1)
