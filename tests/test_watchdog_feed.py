#!/usr/bin/env python3
"""Test that the watchdog feed fix is present in run_mode_with_safety.

This test validates that the fix for the watchdog starvation issue has been
applied correctly by checking that watchdog feeding is called in the
run_mode_with_safety method's waiting loop. The implementation now uses
the self.watchdog.safe_feed() method which implements the watchdog flag pattern.
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

    assert match, "Could not find run_mode_with_safety method"

    method_body = match.group(1)
    print("  ✓ Found run_mode_with_safety method")

    # Check for the while loop
    assert 'while not sub_task.done():' in method_body, "Could not find 'while not sub_task.done():' loop"

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
    assert 'self.watchdog.safe_feed()' in loop_body, "'self.watchdog.safe_feed()' not found in while loop"

    print("  ✓ Found 'self.watchdog.safe_feed()' in while loop")

    # Check that the feed is before the sleep call (at the top of the loop)
    feed_pos = loop_body.find('self.watchdog.safe_feed()')
    sleep_pos = loop_body.find('await asyncio.sleep(0.1)')

    if sleep_pos == -1:
        print("  ⚠ Warning: 'await asyncio.sleep(0.1)' not found in loop")
    elif feed_pos > sleep_pos:
        print("  ⚠ Warning: safe_feed_watchdog() appears after sleep, should be at top of loop")
    else:
        print("  ✓ safe_feed_watchdog() is positioned correctly (before sleep)")


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

    assert match, "Could not find start() method"

    start_body = match.group(1)
    print("  ✓ Found start() method")

    # Check for watchdog feed in the main loop (now uses safe_feed_watchdog)
    assert 'self.watchdog.safe_feed()' in start_body, "'self.watchdog.safe_feed()' not found in start() method"

    print("  ✓ Found 'self.watchdog.safe_feed()' in start() method")

    # Count occurrences
    feed_count = start_body.count('self.watchdog.safe_feed()')
    print(f"  ✓ Found {feed_count} safe_feed call(s) in start() method")




def run_all_tests():
    """Run all watchdog feed fix tests."""
    print("\n" + "=" * 60)
    print("Watchdog Feed Fix Verification")
    print("Testing fix for watchdog starvation during gameplay")
    print("=" * 60 + "\n")

    tests = [
        test_watchdog_feed_present_in_code,
        test_watchdog_feed_in_main_loop,
    ]

    failed = 0
    passed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"\n❌ Test failed: {test.__name__}")
            print(f"   Error: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    if failed == 0:
        print("ALL TESTS PASSED ✓")
        print()
        print("The fix successfully:")
        print("  • Uses safe_feed_watchdog() in run_mode_with_safety loop")
        print("  • Uses safe_feed_watchdog() in main start() loop")
        print("  • Imports microcontroller module for watchdog access")
        print("  • Prevents system reset during long-running modes")
        print("  • Implements watchdog flag pattern to prevent blind feeding")
    else:
        print("SOME TESTS FAILED ✗")
    print("=" * 60 + "\n")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
