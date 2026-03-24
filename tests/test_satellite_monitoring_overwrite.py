#!/usr/bin/env python3
"""Test that the satellite monitoring overwrite bug is fixed in CoreManager.

This test validates the fix for the bug where iterating over multiple required
satellites would overwrite the `target_sat` variable each loop iteration,
leaving only the last matched satellite monitored. The fix collects all
required satellites into a `target_sats` list and spawns a `monitor_satellite`
task for each one.
"""

import sys
import os
import re

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

CORE_MANAGER_PATH = os.path.join(
    os.path.dirname(__file__),
    '..',
    'src',
    'core',
    'core_manager.py'
)


def get_core_manager_source():
    with open(CORE_MANAGER_PATH, 'r') as f:
        return f.read()


def test_target_sats_list_initialized():
    """Test that the dependency-check loop initializes target_sats as a list."""
    print("\nTesting target_sats list initialization...")
    source = get_core_manager_source()
    assert 'target_sats = []' in source, \
        "start() should initialize target_sats as an empty list, not a single variable"
    print("  ✓ target_sats = [] found")


def test_target_sat_single_variable_not_used():
    """Test that the old overwriting single variable is gone from start()."""
    print("\nTesting that the overwriting 'target_sat = sat' pattern is removed...")
    source = get_core_manager_source()
    # The old pattern assigned a single variable inside the satellite-finding loop.
    # It should no longer appear; append() should be used instead.
    assert 'target_sat = sat' not in source, \
        "start() must not overwrite a single target_sat variable in the satellite loop"
    print("  ✓ Overwriting target_sat = sat pattern is absent")


def test_target_sats_append_used():
    """Test that each matched satellite is appended to target_sats."""
    print("\nTesting that target_sats.append(sat) is used...")
    source = get_core_manager_source()
    assert 'target_sats.append(sat)' in source, \
        "start() should append each matched satellite to target_sats"
    print("  ✓ target_sats.append(sat) found")


def test_run_mode_with_safety_accepts_list():
    """Test that run_mode_with_safety accepts target_sats (list) parameter."""
    print("\nTesting run_mode_with_safety signature accepts target_sats...")
    source = get_core_manager_source()
    assert 'async def run_mode_with_safety(self, mode_instance, target_sats=None)' in source, \
        "run_mode_with_safety must accept target_sats=None, not target_sat=None"
    print("  ✓ run_mode_with_safety(self, mode_instance, target_sats=None) found")


def test_run_mode_with_safety_no_single_sat_parameter():
    """Test that the old single-satellite parameter is gone from the signature."""
    print("\nTesting old target_sat parameter is removed from run_mode_with_safety...")
    source = get_core_manager_source()
    # The signature should not use the old single-variable form
    assert 'run_mode_with_safety(self, mode_instance, target_sat=None)' not in source, \
        "run_mode_with_safety must not still use the old target_sat=None parameter"
    print("  ✓ Old target_sat=None parameter is absent from signature")


def test_monitor_satellite_spawned_per_sat():
    """Test that run_mode_with_safety spawns a monitor task for each satellite."""
    print("\nTesting that a monitor_satellite task is spawned per satellite...")
    source = get_core_manager_source()

    # Extract run_mode_with_safety body
    method_pattern = r'async def run_mode_with_safety\(self.*?\n(.*?)(?=\n    async def|\n    def|\Z)'
    match = re.search(method_pattern, source, re.DOTALL)
    assert match, "Could not find run_mode_with_safety method"
    method_body = match.group(1)

    # Verify a loop iterates over target_sats and creates tasks
    assert 'for sat in target_sats' in method_body, \
        "run_mode_with_safety should iterate over target_sats to spawn monitor tasks"
    assert 'monitor_satellite(sat)' in method_body, \
        "run_mode_with_safety should call monitor_satellite(sat) for each sat"
    print("  ✓ for sat in target_sats / monitor_satellite(sat) found in method body")


def test_all_monitor_tasks_cancelled_on_exit():
    """Test that ALL satellite monitor tasks are cancelled in the cleanup block."""
    print("\nTesting that all sat monitor tasks are cancelled on exit...")
    source = get_core_manager_source()

    method_pattern = r'async def run_mode_with_safety\(self.*?\n(.*?)(?=\n    async def|\n    def|\Z)'
    match = re.search(method_pattern, source, re.DOTALL)
    assert match, "Could not find run_mode_with_safety method"
    method_body = match.group(1)

    # A loop should cancel all tasks in the list
    assert 'for task in sat_monitor_tasks' in method_body, \
        "Cleanup block must iterate over sat_monitor_tasks to cancel each one"
    assert 'task.cancel()' in method_body, \
        "Cleanup block must call task.cancel()"
    print("  ✓ Loop cancels all sat monitor tasks found in cleanup block")


def test_link_lost_check_uses_list():
    """Test that the LINK_LOST check in run_mode_with_safety uses the list."""
    print("\nTesting that LINK_LOST check references target_sats not target_sat...")
    source = get_core_manager_source()

    method_pattern = r'async def run_mode_with_safety\(self.*?\n(.*?)(?=\n    async def|\n    def|\Z)'
    match = re.search(method_pattern, source, re.DOTALL)
    assert match, "Could not find run_mode_with_safety method"
    method_body = match.group(1)

    # Old single-variable guard must be gone
    assert 'if target_sat and self.target_sat_event.is_set()' not in method_body, \
        "LINK_LOST guard must not reference the old single target_sat variable"

    # New guard uses the list
    assert 'if target_sats and self.target_sat_event.is_set()' in method_body, \
        "LINK_LOST guard must check target_sats (the list)"
    print("  ✓ LINK_LOST guard correctly uses target_sats list")


def test_reconnect_waits_for_all_sats():
    """Test that the reconnect countdown waits for ALL sats to come back."""
    print("\nTesting that reconnect loop checks all satellites...")
    source = get_core_manager_source()

    # The reconnect countdown should use any() to wait for all sats
    assert 'any(not s.is_active for s in target_sats)' in source, \
        "Reconnect countdown must use any(not s.is_active for s in target_sats)"
    print("  ✓ Reconnect countdown uses any(not s.is_active for s in target_sats)")


def test_link_restored_checks_all_sats():
    """Test that the LINK RESTORED path requires ALL sats to be active."""
    print("\nTesting that LINK RESTORED requires all satellites active...")
    source = get_core_manager_source()

    assert 'all(s.is_active for s in target_sats)' in source, \
        "LINK RESTORED must use all(s.is_active for s in target_sats)"
    print("  ✓ LINK RESTORED uses all(s.is_active for s in target_sats)")


def test_target_sat_event_cleared_before_monitors_spawned():
    """Test that target_sat_event is cleared before new monitor tasks are spawned."""
    print("\nTesting that target_sat_event is cleared before spawning monitor tasks...")
    source = get_core_manager_source()

    method_pattern = r'async def run_mode_with_safety\(self.*?\n(.*?)(?=\n    async def|\n    def|\Z)'
    match = re.search(method_pattern, source, re.DOTALL)
    assert match, "Could not find run_mode_with_safety method"
    method_body = match.group(1)

    # Both the clear and the task list should be present
    assert 'target_sat_event.clear()' in method_body, \
        "run_mode_with_safety must clear target_sat_event before spawning monitor tasks"
    clear_pos = method_body.find('target_sat_event.clear()')
    tasks_pos = method_body.find('sat_monitor_tasks')
    assert clear_pos < tasks_pos, \
        "target_sat_event.clear() must appear before sat_monitor_tasks in method body"
    print("  ✓ target_sat_event.clear() appears before sat_monitor_tasks")


def run_all_tests():
    """Run all satellite monitoring overwrite fix tests."""
    print("\n" + "=" * 60)
    print("Satellite Monitoring Overwrite Fix Verification")
    print("Testing fix for multi-satellite monitoring bug")
    print("=" * 60 + "\n")

    tests = [
        test_target_sats_list_initialized,
        test_target_sat_single_variable_not_used,
        test_target_sats_append_used,
        test_run_mode_with_safety_accepts_list,
        test_run_mode_with_safety_no_single_sat_parameter,
        test_monitor_satellite_spawned_per_sat,
        test_all_monitor_tasks_cancelled_on_exit,
        test_link_lost_check_uses_list,
        test_reconnect_waits_for_all_sats,
        test_link_restored_checks_all_sats,
        test_target_sat_event_cleared_before_monitors_spawned,
    ]

    failed = 0
    passed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"\n❌ FAILED: {test.__name__}")
            print(f"   {e}")
            failed += 1
        except Exception as e:
            print(f"\n❌ ERROR: {test.__name__}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    if failed == 0:
        print(f"ALL {passed} TESTS PASSED ✓")
        print()
        print("The fix successfully:")
        print("  - Collects all required satellites into target_sats list")
        print("  - Spawns a monitor_satellite task for each satellite")
        print("  - Cancels all monitor tasks on mode exit")
        print("  - Aborts mode if ANY required satellite disconnects")
        print("  - Waits for ALL satellites to reconnect before resuming")
    else:
        print(f"{failed} TEST(S) FAILED, {passed} passed ✗")
    print("=" * 60 + "\n")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
