#!/usr/bin/env python3
"""Unit tests for WatchdogManager.

Tests the WatchdogManager class which implements the 'Flag Pattern' for
watchdog feeding. The manager requires all registered tasks to check in
before feeding the watchdog, preventing blind feeding if a task crashes.
"""

import sys
import os
import asyncio
import time
from unittest.mock import patch

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

# Also mock the watchdog module so WatchDogMode.RESET resolves to "RESET"
class MockWatchModule:
    """Mock watchdog library module."""
    class WatchDogMode:
        RESET = "RESET"
        RAISE = "RAISE"

sys.modules['watchdog'] = MockWatchModule()

# Add src to path for direct module import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'managers'))

# Import WatchdogManager after mocking
import watchdog_manager as wdm
from watchdog_manager import WatchdogManager, WatchDogTimeout


class MockWatchdogRaisesOnRAISE(MockWatchdog):
    """Mock watchdog that raises NotImplementedError when mode is set to RAISE."""

    @property
    def mode(self):
        return self._mode_value

    @mode.setter
    def mode(self, value):
        if value == "RAISE":
            raise NotImplementedError("RAISE mode not supported on this platform")
        self._mode_value = value

    def reset(self):
        super().reset()
        self._mode_value = None


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
    
    # Initialize with timeout in RESET mode
    task_names = ["task1", "task2"]
    manager = WatchdogManager(task_names, timeout=5.0, mode="RESET")
    
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


def test_software_fallback_on_not_implemented_error():
    """Test that NotImplementedError on RAISE mode activates software fallback."""
    print("\nTesting software fallback when RAISE mode raises NotImplementedError...")

    raise_watchdog = MockWatchdogRaisesOnRAISE()
    raise_watchdog._mode_value = None

    with patch.object(wdm, 'w', raise_watchdog), \
         patch('asyncio.create_task') as mock_create_task:

        manager = WatchdogManager(["task1"], timeout=5.0, mode="RAISE")

        assert manager._software_mode is True, "_software_mode should be True"
        assert mock_create_task.called, "asyncio.create_task should be called"
        # Hardware feed should NOT be called when in software fallback mode
        assert raise_watchdog.feed_count == 0, "Hardware feed should not be called in software mode"

    print("✓ Software fallback on NotImplementedError test passed")


def test_safe_feed_updates_last_fed_time_in_software_mode():
    """Test that safe_feed() updates _last_fed_time in software mode."""
    print("\nTesting safe_feed() updates _last_fed_time in software mode...")

    MockMicrocontroller.watchdog.reset()

    task_names = ["task1", "task2"]
    manager = WatchdogManager(task_names, timeout=None)

    # Manually enable software mode
    manager._software_mode = True
    before = time.monotonic()

    manager.check_in("task1")
    manager.check_in("task2")
    result = manager.safe_feed()

    assert result is True, "safe_feed should return True"
    assert manager._last_fed_time >= before, "_last_fed_time should be updated"
    # Hardware watchdog should NOT be fed
    assert MockMicrocontroller.watchdog.feed_count == 0, "Hardware watchdog should not be fed"

    print("✓ safe_feed() updates _last_fed_time in software mode test passed")


def test_watchdog_timeout_exception_exists():
    """Test that WatchDogTimeout exception is importable and is a RuntimeError."""
    print("\nTesting WatchDogTimeout exception...")

    assert issubclass(WatchDogTimeout, RuntimeError), "WatchDogTimeout should inherit from RuntimeError"

    try:
        raise WatchDogTimeout("test timeout")
    except WatchDogTimeout as e:
        assert str(e) == "test timeout", "Exception message should match"
    except Exception:
        assert False, "Should have caught WatchDogTimeout"

    print("✓ WatchDogTimeout exception test passed")


def test_software_watchdog_monitor_raises_on_timeout():
    """Test that _software_watchdog_monitor raises WatchDogTimeout when feed is late."""
    print("\nTesting _software_watchdog_monitor raises WatchDogTimeout on timeout...")

    MockMicrocontroller.watchdog.reset()

    manager = WatchdogManager(["task1"], timeout=0.2)
    manager._software_mode = True
    # Set last_fed_time in the past (simulate timeout)
    manager._last_fed_time = time.monotonic() - 1.0

    async def run_monitor_once():
        """Run the monitor briefly to trigger the timeout."""
        try:
            await asyncio.wait_for(manager._software_watchdog_monitor(), timeout=1.0)
        except WatchDogTimeout:
            return True  # Expected
        return False

    raised = asyncio.run(run_monitor_once())
    assert raised is True, "_software_watchdog_monitor should raise WatchDogTimeout"

    print("✓ Software watchdog monitor raises WatchDogTimeout on timeout test passed")


def test_software_watchdog_monitor_does_not_raise_when_fed():
    """Test that _software_watchdog_monitor does NOT raise when safe_feed is called."""
    print("\nTesting _software_watchdog_monitor does not raise when kept fed...")

    MockMicrocontroller.watchdog.reset()

    manager = WatchdogManager(["task1"], timeout=5.0)
    manager._software_mode = True

    manager._last_fed_time = time.monotonic()  # Just fed

    async def run_monitor_briefly():
        """Run the monitor for a short time; it should NOT raise."""
        try:
            await asyncio.wait_for(manager._software_watchdog_monitor(), timeout=0.3)
        except WatchDogTimeout:
            return False  # Not expected
        except asyncio.TimeoutError:
            return True  # Expected - monitor ran without raising
        return False

    ok = asyncio.run(run_monitor_briefly())
    assert ok is True, "_software_watchdog_monitor should not raise when regularly fed"

    print("✓ Software watchdog monitor does not raise when kept fed test passed")


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
        test_software_fallback_on_not_implemented_error,
        test_safe_feed_updates_last_fed_time_in_software_mode,
        test_watchdog_timeout_exception_exists,
        test_software_watchdog_monitor_raises_on_timeout,
        test_software_watchdog_monitor_does_not_raise_when_fed,
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
        print("  • Falls back to software watchdog when RAISE mode is unsupported")
        print("  • Raises WatchDogTimeout when loop is starved in software mode")
    else:
        print("\n✗ SOME TESTS FAILED")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
