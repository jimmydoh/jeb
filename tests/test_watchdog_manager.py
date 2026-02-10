#!/usr/bin/env python3
"""Unit tests for WatchdogManager.

Tests the WatchdogManager class which implements the 'Flag Pattern' for
watchdog feeding. The manager requires all registered tasks to check in
before feeding the watchdog, preventing blind feeding if a task crashes.
"""

import sys
import os

# Mock the microcontroller module BEFORE importing WatchdogManager
class MockWatchDogMode:
    """Mock WatchDogMode enum."""
    RESET = "RESET"


class MockWatchdog:
    """Mock watchdog timer for testing."""
    WatchDogMode = MockWatchDogMode
    
    def __init__(self):
        self.timeout = None
        self.mode = None
        self.feed_count = 0
        self.enabled = False
    
    def feed(self):
        """Mock feed method."""
        self.feed_count += 1
    
    def reset(self):
        """Reset the mock for a new test."""
        self.timeout = None
        self.mode = None
        self.feed_count = 0
        self.enabled = False


class MockMicrocontroller:
    """Mock microcontroller module."""
    watchdog = MockWatchdog()


# Install the mock before importing WatchdogManager
sys.modules['microcontroller'] = MockMicrocontroller()

# Add src to path for direct module import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'managers'))

# Import WatchdogManager after mocking
from watchdog_manager import WatchdogManager


def test_initialization_without_timeout():
    """Test WatchdogManager initialization without timeout."""
    print("Testing initialization without timeout...")
    
    # Reset the mock
    MockMicrocontroller.watchdog.reset()
    
    # Initialize without timeout
    task_names = ["task1", "task2", "task3"]
    manager = WatchdogManager(task_names, timeout=None)
    
    # Verify flags are initialized
    assert hasattr(manager, '_flags'), "Manager should have _flags attribute"
    assert len(manager._flags) == 3, "Should have 3 flags"
    assert "task1" in manager._flags, "task1 should be in flags"
    assert "task2" in manager._flags, "task2 should be in flags"
    assert "task3" in manager._flags, "task3 should be in flags"
    
    # All flags should start as False
    assert not manager._flags["task1"], "task1 flag should start False"
    assert not manager._flags["task2"], "task2 flag should start False"
    assert not manager._flags["task3"], "task3 flag should start False"
    
    # Watchdog should not be enabled
    assert MockMicrocontroller.watchdog.timeout is None, "Watchdog should not be configured"
    
    print("✓ Initialization without timeout test passed")


def test_initialization_with_timeout():
    """Test WatchdogManager initialization with timeout."""
    print("\nTesting initialization with timeout...")
    
    # Reset the mock
    MockMicrocontroller.watchdog.reset()
    
    # Initialize with timeout
    task_names = ["task1", "task2"]
    manager = WatchdogManager(task_names, timeout=5.0)
    
    # Verify flags are initialized
    assert len(manager._flags) == 2, "Should have 2 flags"
    assert all(not flag for flag in manager._flags.values()), "All flags should start False"
    
    # Watchdog should be enabled with correct settings
    assert MockMicrocontroller.watchdog.timeout == 5.0, "Watchdog timeout should be 5.0"
    assert MockMicrocontroller.watchdog.mode == "RESET", "Watchdog mode should be RESET"
    assert MockMicrocontroller.watchdog.feed_count == 1, "Watchdog should be fed once during init"
    
    print("✓ Initialization with timeout test passed")


def test_check_in_valid_task():
    """Test checking in a valid task."""
    print("\nTesting check_in with valid task...")
    
    # Reset the mock
    MockMicrocontroller.watchdog.reset()
    
    task_names = ["task_a", "task_b", "task_c"]
    manager = WatchdogManager(task_names, timeout=None)
    
    # Check in task_a
    manager.check_in("task_a")
    assert manager._flags["task_a"], "task_a flag should be True"
    assert not manager._flags["task_b"], "task_b flag should still be False"
    assert not manager._flags["task_c"], "task_c flag should still be False"
    
    # Check in task_b
    manager.check_in("task_b")
    assert manager._flags["task_a"], "task_a flag should still be True"
    assert manager._flags["task_b"], "task_b flag should be True"
    assert not manager._flags["task_c"], "task_c flag should still be False"
    
    print("✓ Check-in with valid task test passed")


def test_check_in_invalid_task():
    """Test checking in an invalid task name."""
    print("\nTesting check_in with invalid task...")
    
    # Reset the mock
    MockMicrocontroller.watchdog.reset()
    
    task_names = ["task1", "task2"]
    manager = WatchdogManager(task_names, timeout=None)
    
    # Check in invalid task (should be silently ignored)
    manager.check_in("invalid_task")
    
    # Valid tasks should still be False
    assert not manager._flags["task1"], "task1 flag should still be False"
    assert not manager._flags["task2"], "task2 flag should still be False"
    
    # No error should be raised
    print("✓ Check-in with invalid task test passed (silently ignored)")


def test_safe_feed_all_tasks_checked_in():
    """Test safe_feed when all tasks have checked in."""
    print("\nTesting safe_feed when all tasks checked in...")
    
    # Reset the mock
    MockMicrocontroller.watchdog.reset()
    
    task_names = ["task1", "task2", "task3"]
    manager = WatchdogManager(task_names, timeout=5.0)
    
    # Reset feed count after initialization
    initial_feed_count = MockMicrocontroller.watchdog.feed_count
    
    # Check in all tasks
    manager.check_in("task1")
    manager.check_in("task2")
    manager.check_in("task3")
    
    # Verify all flags are True
    assert all(manager._flags.values()), "All flags should be True"
    
    # Call safe_feed
    result = manager.safe_feed()
    
    # Should return True
    assert result is True, "safe_feed should return True when all tasks checked in"
    
    # Watchdog should be fed
    assert MockMicrocontroller.watchdog.feed_count == initial_feed_count + 1, \
        "Watchdog should be fed once"
    
    # All flags should be reset to False
    assert not any(manager._flags.values()), "All flags should be reset to False after feeding"
    
    print("✓ Safe feed with all tasks checked in test passed")


def test_safe_feed_not_all_tasks_checked_in():
    """Test safe_feed when not all tasks have checked in."""
    print("\nTesting safe_feed when not all tasks checked in...")
    
    # Reset the mock
    MockMicrocontroller.watchdog.reset()
    
    task_names = ["task1", "task2", "task3"]
    manager = WatchdogManager(task_names, timeout=5.0)
    
    # Reset feed count after initialization
    initial_feed_count = MockMicrocontroller.watchdog.feed_count
    
    # Check in only some tasks
    manager.check_in("task1")
    manager.check_in("task2")
    # task3 is not checked in
    
    # Call safe_feed
    result = manager.safe_feed()
    
    # Should return False
    assert result is False, "safe_feed should return False when not all tasks checked in"
    
    # Watchdog should NOT be fed
    assert MockMicrocontroller.watchdog.feed_count == initial_feed_count, \
        "Watchdog should not be fed"
    
    # Flags should NOT be reset
    assert manager._flags["task1"], "task1 flag should still be True"
    assert manager._flags["task2"], "task2 flag should still be True"
    assert not manager._flags["task3"], "task3 flag should still be False"
    
    print("✓ Safe feed with not all tasks checked in test passed")


def test_safe_feed_no_tasks_checked_in():
    """Test safe_feed when no tasks have checked in."""
    print("\nTesting safe_feed when no tasks checked in...")
    
    # Reset the mock
    MockMicrocontroller.watchdog.reset()
    
    task_names = ["task1", "task2"]
    manager = WatchdogManager(task_names, timeout=5.0)
    
    # Reset feed count after initialization
    initial_feed_count = MockMicrocontroller.watchdog.feed_count
    
    # Don't check in any tasks
    
    # Call safe_feed
    result = manager.safe_feed()
    
    # Should return False
    assert result is False, "safe_feed should return False when no tasks checked in"
    
    # Watchdog should NOT be fed
    assert MockMicrocontroller.watchdog.feed_count == initial_feed_count, \
        "Watchdog should not be fed"
    
    print("✓ Safe feed with no tasks checked in test passed")


def test_multiple_cycles():
    """Test multiple check-in and feed cycles."""
    print("\nTesting multiple check-in and feed cycles...")
    
    # Reset the mock
    MockMicrocontroller.watchdog.reset()
    
    task_names = ["task1", "task2"]
    manager = WatchdogManager(task_names, timeout=5.0)
    
    # Reset feed count after initialization
    initial_feed_count = MockMicrocontroller.watchdog.feed_count
    
    # Cycle 1: All tasks check in
    manager.check_in("task1")
    manager.check_in("task2")
    result1 = manager.safe_feed()
    assert result1 is True, "Cycle 1: should feed"
    assert MockMicrocontroller.watchdog.feed_count == initial_feed_count + 1
    
    # Cycle 2: Only task1 checks in
    manager.check_in("task1")
    result2 = manager.safe_feed()
    assert result2 is False, "Cycle 2: should not feed"
    assert MockMicrocontroller.watchdog.feed_count == initial_feed_count + 1  # No additional feed
    
    # Cycle 3: task2 checks in now (task1 still True from cycle 2)
    manager.check_in("task2")
    result3 = manager.safe_feed()
    assert result3 is True, "Cycle 3: should feed (both tasks checked in over time)"
    assert MockMicrocontroller.watchdog.feed_count == initial_feed_count + 2
    
    # Cycle 4: All tasks check in again
    manager.check_in("task1")
    manager.check_in("task2")
    result4 = manager.safe_feed()
    assert result4 is True, "Cycle 4: should feed"
    assert MockMicrocontroller.watchdog.feed_count == initial_feed_count + 3
    
    print("✓ Multiple cycles test passed")


def test_single_task():
    """Test WatchdogManager with a single task."""
    print("\nTesting with single task...")
    
    # Reset the mock
    MockMicrocontroller.watchdog.reset()
    
    task_names = ["only_task"]
    manager = WatchdogManager(task_names, timeout=None)
    
    # Check in the only task
    manager.check_in("only_task")
    
    # Should be able to feed
    result = manager.safe_feed()
    assert result is True, "Should feed when the only task checks in"
    
    # Flag should be reset
    assert not manager._flags["only_task"], "Flag should be reset"
    
    print("✓ Single task test passed")


def test_empty_task_list():
    """Test WatchdogManager with empty task list."""
    print("\nTesting with empty task list...")
    
    # Reset the mock
    MockMicrocontroller.watchdog.reset()
    
    task_names = []
    manager = WatchdogManager(task_names, timeout=None)
    
    # With no tasks, safe_feed should always succeed
    result = manager.safe_feed()
    assert result is True, "Should feed when no tasks are registered (all([]) is True)"
    
    print("✓ Empty task list test passed")


def run_all_tests():
    """Run all WatchdogManager unit tests."""
    print("=" * 60)
    print("WatchdogManager Unit Tests")
    print("=" * 60)
    
    tests = [
        test_initialization_without_timeout,
        test_initialization_with_timeout,
        test_check_in_valid_task,
        test_check_in_invalid_task,
        test_safe_feed_all_tasks_checked_in,
        test_safe_feed_not_all_tasks_checked_in,
        test_safe_feed_no_tasks_checked_in,
        test_multiple_cycles,
        test_single_task,
        test_empty_task_list,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"\n✗ {test.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"\n✗ {test.__name__} ERROR: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    if failed == 0:
        print("\n✓ ALL WATCHDOG MANAGER TESTS PASSED")
        print("\nThe WatchdogManager class correctly:")
        print("  • Initializes task flags")
        print("  • Configures hardware watchdog when timeout is provided")
        print("  • Tracks task check-ins")
        print("  • Only feeds watchdog when all tasks check in")
        print("  • Resets flags after successful feeding")
        print("  • Handles invalid task names gracefully")
        print("  • Supports multiple check-in/feed cycles")
    else:
        print("\n✗ SOME TESTS FAILED")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
