#!/usr/bin/env python3
"""Test satellite hotplug behavior (topology change detection without mode abortion).

This test validates that the satellite network manager and main menu handle
satellite topology changes (connect/disconnect) without aborting running modes.

Test Strategy:
- Source code inspection (regex/string search) to verify behavior
- No CircuitPython dependencies required
- Tests are standalone and can run with python3

Background:
Prior to this change, satellite topology changes would trigger `abort_event.set()`,
which would forcefully terminate running game modes. This was problematic for
hot-pluggable satellite scenarios. The new behavior maintains the abort_event
for backward compatibility but no longer sets it on topology changes.
"""

import sys
import os
import re
import pytest


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def satellite_network_manager_path():
    """Fixture providing path to satellite_network_manager.py."""
    file_path = os.path.join(
        os.path.dirname(__file__), '..', 'src', 'managers', 'satellite_network_manager.py'
    )
    assert os.path.exists(file_path), "satellite_network_manager.py should exist"
    return file_path


@pytest.fixture
def satellite_network_manager_content(satellite_network_manager_path):
    """Fixture providing content of satellite_network_manager.py."""
    with open(satellite_network_manager_path, 'r') as f:
        return f.read()


@pytest.fixture
def main_menu_path():
    """Fixture providing path to main_menu.py."""
    file_path = os.path.join(
        os.path.dirname(__file__), '..', 'src', 'modes', 'main_menu.py'
    )
    assert os.path.exists(file_path), "main_menu.py should exist"
    return file_path


@pytest.fixture
def main_menu_content(main_menu_path):
    """Fixture providing content of main_menu.py."""
    with open(main_menu_path, 'r') as f:
        return f.read()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def extract_method(content, method_name, is_async=False):
    """Extract a method from source code content.
    
    Args:
        content: Source code content as string
        method_name: Name of the method to extract
        is_async: Whether the method is async (default: False)
    
    Returns:
        Method body as string, or None if not found
    """
    async_kw = "async " if is_async else ""
    # Match method definition and capture until next method at same or less indentation
    pattern = rf'{async_kw}def {method_name}\(self.*?\n(?=    (?:async )?def |class |\Z)'
    match = re.search(pattern, content, re.DOTALL)
    return match.group(0) if match else None


def extract_topology_change_block(loop_body):
    """Extract the topology change detection block from main loop.
    
    Args:
        loop_body: Content of the while True loop
    
    Returns:
        Topology change block as string, or None if not found
    """
    # Find the topology change detection block
    topology_check_match = re.search(
        r'if curr_sat_keys != last_sat_keys:',
        loop_body
    )
    
    if not topology_check_match:
        return None
    
    # Extract from the if statement to next line with equal or lesser indentation
    # Calculate indentation of the if statement
    line_start = loop_body.rfind('\n', 0, topology_check_match.start()) + 1
    if_line = loop_body[line_start:topology_check_match.end()]
    indent = len(if_line) - len(if_line.lstrip())
    
    # Find end of block by looking for a line with same or less indentation
    block_start = topology_check_match.start()
    block_end = len(loop_body)
    
    # Search for next line with same or less indentation
    lines_after = loop_body[block_start:].split('\n')
    accumulated = lines_after[0]  # Start with the if line
    
    for i, line in enumerate(lines_after[1:], 1):
        if line.strip() == '':  # Skip blank lines
            accumulated += '\n' + line
            continue
        line_indent = len(line) - len(line.lstrip())
        if line_indent <= indent:  # Found end of block
            break
        accumulated += '\n' + line
    
    return accumulated


# ============================================================================
# TEST 1: SATELLITE NETWORK MANAGER HOTPLUG BEHAVIOR
# ============================================================================

def test_satellite_network_manager_no_abort_on_hello(satellite_network_manager_content):
    """Test that _handle_hello_command does NOT call abort_event.set().
    
    New satellite connections should not abort running modes.
    """
    print("\nTesting _handle_hello_command does NOT abort modes...")
    
    # Extract the _handle_hello_command method
    hello_method_body = extract_method(
        satellite_network_manager_content,
        '_handle_hello_command',
        is_async=True
    )
    
    assert hello_method_body, "_handle_hello_command method should exist"
    
    # Verify abort_event.set() is NOT in the method
    assert 'abort_event.set()' not in hello_method_body, \
        "_handle_hello_command should NOT call abort_event.set() (new sat connect should not abort modes)"
    
    print("  ✓ _handle_hello_command does NOT call abort_event.set()")
    
    # Verify the method still populates the satellite dictionary
    assert 'self.satellites[sid]' in hello_method_body, \
        "_handle_hello_command should still populate satellites dict"
    
    print("  ✓ _handle_hello_command still populates satellites dict")
    
    # Verify display feedback for new satellite
    assert 'NEW SAT' in hello_method_body, \
        "_handle_hello_command should show 'NEW SAT' status to user"
    
    print("  ✓ _handle_hello_command shows 'NEW SAT' status feedback")
    print("✓ Test passed: New satellite connection does not abort modes")


def test_satellite_network_manager_no_abort_on_link_restored(satellite_network_manager_content):
    """Test that monitor_satellites link-restored section does NOT call abort_event.set().
    
    Satellite reconnection should not abort running modes.
    """
    print("\nTesting monitor_satellites link-restored section does NOT abort modes...")
    
    # Extract the monitor_satellites method
    monitor_method_body = extract_method(
        satellite_network_manager_content,
        'monitor_satellites',
        is_async=True
    )
    
    assert monitor_method_body, "monitor_satellites method should exist"
    
    # Find the link-restored section (where was_offline is set to False)
    link_restored_match = re.search(
        r'if sat\.was_offline:.*?sat\.was_offline = False',
        monitor_method_body,
        re.DOTALL
    )
    
    assert link_restored_match, "Link-restored logic should exist in monitor_satellites"
    link_restored_section = link_restored_match.group(0)
    
    # Verify abort_event.set() is NOT in the link-restored section
    assert 'abort_event.set()' not in link_restored_section, \
        "Link-restored section should NOT call abort_event.set() (reconnection should not abort modes)"
    
    print("  ✓ Link-restored section does NOT call abort_event.set()")
    
    # Verify display feedback for link restored
    assert 'LINK RESTORED' in link_restored_section, \
        "Link-restored section should show 'LINK RESTORED' status to user"
    
    print("  ✓ Link-restored section shows 'LINK RESTORED' status feedback")
    print("✓ Test passed: Satellite reconnection does not abort modes")


def test_satellite_network_manager_no_abort_on_link_lost(satellite_network_manager_content):
    """Test that monitor_satellites link-lost section does NOT call abort_event.set().
    
    Satellite disconnection should not abort running modes (mode should handle gracefully).
    """
    print("\nTesting monitor_satellites link-lost section does NOT abort modes...")
    
    # Extract the monitor_satellites method
    monitor_method_body = extract_method(
        satellite_network_manager_content,
        'monitor_satellites',
        is_async=True
    )
    
    assert monitor_method_body, "monitor_satellites method should exist"
    
    # Find the link-lost section (from ticks_diff check through display update)
    # Captures the entire link-lost handling block
    link_lost_match = re.search(
        r'if ticks_diff.*?>.*?5000:.*?self\.display\.update_status\([^)]*LINK[^)]*\)',
        monitor_method_body,
        re.DOTALL
    )
    
    assert link_lost_match, "Link-lost logic should exist in monitor_satellites"
    link_lost_section = link_lost_match.group(0)
    
    # Verify abort_event.set() is NOT in the link-lost section
    assert 'abort_event.set()' not in link_lost_section, \
        "Link-lost section should NOT call abort_event.set() (disconnection should not abort modes)"
    
    print("  ✓ Link-lost section does NOT call abort_event.set()")
    
    # Verify display feedback for link lost
    assert 'LINK LOST' in link_lost_section, \
        "Link-lost section should show 'LINK LOST' status to user"
    
    print("  ✓ Link-lost section shows 'LINK LOST' status feedback")
    print("✓ Test passed: Satellite disconnection does not abort modes")


def test_satellite_network_manager_abort_event_stored(satellite_network_manager_content):
    """Test that abort_event is still stored for backward compatibility.
    
    Even though abort_event.set() is no longer called for topology changes,
    the abort_event should still be stored so modes can manually abort if needed.
    """
    print("\nTesting abort_event is stored for backward compatibility...")
    
    # Find the __init__ method
    init_method_match = re.search(
        r'def __init__\(self.*?\n(?=\s*async def|\s*def)',
        satellite_network_manager_content,
        re.DOTALL
    )
    
    assert init_method_match, "__init__ method should exist"
    init_method_body = init_method_match.group(0)
    
    # Verify abort_event parameter is accepted
    assert 'abort_event' in init_method_body, \
        "__init__ should accept abort_event parameter"
    
    print("  ✓ __init__ accepts abort_event parameter")
    
    # Verify abort_event is stored
    assert 'self.abort_event = abort_event' in init_method_body, \
        "__init__ should store abort_event for backward compatibility"
    
    print("  ✓ abort_event is stored (self.abort_event = abort_event)")
    print("✓ Test passed: abort_event stored for backward compatibility")


def test_satellite_network_manager_display_updates_present(satellite_network_manager_content):
    """Test that display updates are still present for user feedback.
    
    Even though modes are not aborted, users should still see topology changes.
    """
    print("\nTesting display updates for satellite topology changes...")
    
    # Verify "NEW SAT" display update
    assert 'NEW SAT' in satellite_network_manager_content, \
        "Display should show 'NEW SAT' for new satellite connections"
    print("  ✓ 'NEW SAT' display update present")
    
    # Verify "LINK RESTORED" display update
    assert 'LINK RESTORED' in satellite_network_manager_content, \
        "Display should show 'LINK RESTORED' for satellite reconnections"
    print("  ✓ 'LINK RESTORED' display update present")
    
    # Verify "LINK LOST" display update
    assert 'LINK LOST' in satellite_network_manager_content, \
        "Display should show 'LINK LOST' for satellite disconnections"
    print("  ✓ 'LINK LOST' display update present")
    
    print("✓ Test passed: Display updates present for all topology changes")


# ============================================================================
# TEST 2: MAIN MENU IN-LOOP SATELLITE TOPOLOGY DETECTION
# ============================================================================

def test_main_menu_last_sat_keys_initialization(main_menu_content):
    """Test that last_sat_keys is initialized before the main loop.
    
    For topology change detection, we need to track the previous satellite set.
    """
    print("\nTesting last_sat_keys initialization...")
    
    # Find the run method
    run_method_match = re.search(
        r'async def run\(self\):.*?(?=\n    async def |\n    def |\Z)',
        main_menu_content,
        re.DOTALL
    )
    
    assert run_method_match, "run method should exist in MainMenu"
    run_method_body = run_method_match.group(0)
    
    # Find the while True loop
    while_loop_match = re.search(
        r'while True:',
        run_method_body
    )
    
    assert while_loop_match, "run method should have 'while True:' loop"
    
    # Extract code before the while loop
    code_before_loop = run_method_body[:while_loop_match.start()]
    
    # Verify last_sat_keys is initialized before the loop
    assert 'last_sat_keys' in code_before_loop, \
        "last_sat_keys should be initialized before 'while True:' loop"
    
    print("  ✓ last_sat_keys variable is initialized before while True loop")
    
    # Verify it uses frozenset for immutable comparison
    assert 'frozenset' in code_before_loop and 'satellites.keys()' in code_before_loop, \
        "last_sat_keys should be initialized with frozenset(self.core.satellites.keys())"
    
    print("  ✓ last_sat_keys uses frozenset(self.core.satellites.keys())")
    print("✓ Test passed: last_sat_keys properly initialized")


def test_main_menu_curr_sat_keys_computation(main_menu_content):
    """Test that curr_sat_keys is computed inside the main loop.
    
    For real-time topology detection, curr_sat_keys must be computed each iteration.
    """
    print("\nTesting curr_sat_keys computation inside loop...")
    
    # Find the run method
    run_method_match = re.search(
        r'async def run\(self\):.*?(?=\n    async def |\n    def |\Z)',
        main_menu_content,
        re.DOTALL
    )
    
    assert run_method_match, "run method should exist in MainMenu"
    run_method_body = run_method_match.group(0)
    
    # Find the while True loop
    while_loop_match = re.search(
        r'while True:(.*?)(?=\n    async def |\n    def |\Z)',
        run_method_body,
        re.DOTALL
    )
    
    assert while_loop_match, "run method should have 'while True:' loop"
    loop_body = while_loop_match.group(1)
    
    # Verify curr_sat_keys is computed inside the loop
    assert 'curr_sat_keys' in loop_body, \
        "curr_sat_keys should be computed inside 'while True:' loop"
    
    print("  ✓ curr_sat_keys variable is computed inside while True loop")
    
    # Verify it uses frozenset for comparison
    assert 'frozenset' in loop_body and 'satellites.keys()' in loop_body, \
        "curr_sat_keys should use frozenset(self.core.satellites.keys())"
    
    print("  ✓ curr_sat_keys uses frozenset(self.core.satellites.keys())")
    print("✓ Test passed: curr_sat_keys properly computed in loop")


def test_main_menu_topology_change_detection(main_menu_content):
    """Test that topology changes trigger menu rebuild.
    
    When curr_sat_keys != last_sat_keys, menu_items should be rebuilt.
    """
    print("\nTesting topology change detection and menu rebuild...")
    
    # Extract the run method
    run_method_body = extract_method(main_menu_content, 'run', is_async=True)
    assert run_method_body, "run method should exist in MainMenu"
    
    # Find the while True loop
    while_loop_match = re.search(
        r'while True:(.*?)(?=\n    async def |\n    def |\Z)',
        run_method_body,
        re.DOTALL
    )
    
    assert while_loop_match, "run method should have 'while True:' loop"
    loop_body = while_loop_match.group(1)
    
    # Extract topology change block using helper
    topology_block = extract_topology_change_block(loop_body)
    assert topology_block, \
        "Loop should check 'if curr_sat_keys != last_sat_keys:' for topology changes"
    
    print("  ✓ Topology change detection present (curr_sat_keys != last_sat_keys)")
    
    # Verify last_sat_keys is updated
    assert 'last_sat_keys = curr_sat_keys' in topology_block, \
        "Topology change block should update last_sat_keys = curr_sat_keys"
    
    print("  ✓ last_sat_keys is updated on topology change")
    
    # Verify menu_items is rebuilt
    assert 'menu_items = self._build_menu_items()' in topology_block or \
           '_build_menu_items()' in topology_block, \
        "Topology change block should rebuild menu_items via _build_menu_items()"
    
    print("  ✓ menu_items rebuilt via _build_menu_items() on topology change")
    print("✓ Test passed: Topology changes trigger menu rebuild")


def test_main_menu_selected_game_idx_clamping(main_menu_content):
    """Test that selected_game_idx is clamped when topology changes.
    
    If menu shrinks (satellite disconnects), selected index must be clamped to prevent IndexError.
    """
    print("\nTesting selected_game_idx clamping on topology change...")
    
    # Extract the run method
    run_method_body = extract_method(main_menu_content, 'run', is_async=True)
    assert run_method_body, "run method should exist in MainMenu"
    
    # Find the while True loop
    while_loop_match = re.search(
        r'while True:(.*?)(?=\n    async def |\n    def |\Z)',
        run_method_body,
        re.DOTALL
    )
    
    assert while_loop_match, "run method should have 'while True:' loop"
    loop_body = while_loop_match.group(1)
    
    # Extract topology change block using helper
    topology_block = extract_topology_change_block(loop_body)
    assert topology_block, "Topology change detection should exist"
    
    # Verify selected_game_idx is clamped when menu shrinks
    # Look for pattern like: if selected_game_idx >= len(menu_items)
    clamping_pattern = r'selected_game_idx\s*>=\s*len\(menu_items\)'
    assert re.search(clamping_pattern, topology_block), \
        "Topology change block should clamp selected_game_idx when >= len(menu_items)"
    
    print("  ✓ selected_game_idx is checked against len(menu_items)")
    
    # Verify it's set to a valid value (len(menu_items) - 1)
    assert 'selected_game_idx = len(menu_items) - 1' in topology_block, \
        "selected_game_idx should be clamped to len(menu_items) - 1"
    
    print("  ✓ selected_game_idx clamped to len(menu_items) - 1 when out of bounds")
    print("✓ Test passed: selected_game_idx properly clamped on topology change")


def test_main_menu_needs_render_flag(main_menu_content):
    """Test that needs_render flag is set on topology change.
    
    UI should update when topology changes to show new menu items.
    """
    print("\nTesting needs_render flag set on topology change...")
    
    # Extract the run method
    run_method_body = extract_method(main_menu_content, 'run', is_async=True)
    assert run_method_body, "run method should exist in MainMenu"
    
    # Find the while True loop
    while_loop_match = re.search(
        r'while True:(.*?)(?=\n    async def |\n    def |\Z)',
        run_method_body,
        re.DOTALL
    )
    
    assert while_loop_match, "run method should have 'while True:' loop"
    loop_body = while_loop_match.group(1)
    
    # Extract topology change block using helper
    topology_block = extract_topology_change_block(loop_body)
    assert topology_block, "Topology change detection should exist"
    
    # Verify needs_render is set to True
    assert 'needs_render = True' in topology_block, \
        "Topology change block should set needs_render = True to trigger UI update"
    
    print("  ✓ needs_render = True on topology change")
    print("✓ Test passed: UI updates triggered on topology change")


# ============================================================================
# MAIN RUNNER
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("SATELLITE HOTPLUG BEHAVIOR TEST SUITE")
    print("=" * 70)
    print("\nValidating that satellite topology changes no longer abort modes")
    print("and that main menu detects topology changes in real-time.\n")
    
    # Run tests with pytest when executed as a script
    result = pytest.main([__file__, "-v", "--tb=short"])
    
    print("\n" + "=" * 70)
    if result == 0:
        print("✓ ALL TESTS PASSED")
    else:
        print("✗ SOME TESTS FAILED")
    print("=" * 70)
    
    sys.exit(result)
