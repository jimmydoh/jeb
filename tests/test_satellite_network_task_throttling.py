#!/usr/bin/env python3
"""Test task throttling in SatelliteNetworkManager.

This test validates that the satellite network manager properly throttles
task creation to prevent unbounded task spawning during satellite malfunctions.
"""

import sys
import os
import re
import pytest


@pytest.fixture
def file_path():
    """Fixture providing the path to satellite_network_manager.py."""
    file_path = os.path.join(
        os.path.dirname(__file__), '..', 'src', 'managers', 'satellite_network_manager.py'
    )
    assert os.path.exists(file_path), "satellite_network_manager.py should exist"
    return file_path


@pytest.fixture
def content(file_path):
    """Fixture providing the content of satellite_network_manager.py."""
    with open(file_path, 'r') as f:
        return f.read()


def test_task_tracking_attributes_exist(content):
    """Test that task tracking attributes are initialized."""
    print("\nTesting task tracking attributes...")
    
    # Check for status task tracking
    assert 'self._current_status_task' in content, \
        "Should have _current_status_task attribute"
    print("  ✓ _current_status_task attribute found")
    
    # Verify initialization to None
    assert 'self._current_status_task = None' in content, \
        "Should initialize _current_status_task to None"
    print("  ✓ Task attribute initialized to None")
    
    print("✓ Task tracking attributes test passed")


def test_spawn_status_task_method_exists(content):
    """Test that _spawn_status_task method exists and has proper implementation."""
    print("\nTesting _spawn_status_task method...")
    
    # Check method exists
    assert 'def _spawn_status_task(self' in content, \
        "Should have _spawn_status_task method"
    print("  ✓ _spawn_status_task method exists")
    
    # Check for throttling logic
    assert '_current_status_task.done()' in content, \
        "Should check if task is done before spawning new one"
    print("  ✓ Method checks if task is done")
    
    # Check that it creates task
    pattern = r'self\._current_status_task\s*=\s*asyncio\.create_task'
    assert re.search(pattern, content), \
        "Should create and store asyncio task"
    print("  ✓ Method creates and stores task")
    
    print("✓ _spawn_status_task method test passed")


def test_no_direct_asyncio_create_task_in_handle_message(content):
    """Test that handle_message uses throttled task spawning for status updates."""
    print("\nTesting handle_message uses throttled task spawning for status updates...")
    
    # Find handle_message method
    handle_message_start = content.find('def handle_message(self')
    assert handle_message_start != -1, "handle_message method should exist"
    
    # Find the next method after handle_message
    next_method_start = content.find('\n    def ', handle_message_start + 1)
    if next_method_start == -1:
        next_method_start = len(content)
    
    handle_message_body = content[handle_message_start:next_method_start]
    
    # Check that _spawn_status_task is used for status updates
    assert '_spawn_status_task' in handle_message_body, \
        "handle_message should use _spawn_status_task"
    print("  ✓ handle_message uses _spawn_status_task")
    
    # Verify status updates are throttled (not using direct asyncio.create_task for display.update_status)
    # Audio tasks are allowed to use asyncio.create_task directly
    status_update_pattern = r'asyncio\.create_task\s*\(\s*self\.display\.update_status'
    status_matches = re.findall(status_update_pattern, handle_message_body)
    
    assert len(status_matches) == 0, \
        f"Status updates should use _spawn_status_task, not direct asyncio.create_task (found {len(status_matches)} instances)"
    print("  ✓ Status updates use throttled spawning")
    
    print("✓ handle_message throttled task spawning test passed")


def test_no_direct_asyncio_create_task_in_monitor_satellites(content):
    """Test that monitor_satellites doesn't use direct asyncio.create_task calls."""
    print("\nTesting monitor_satellites uses throttled task spawning...")
    
    # Find monitor_satellites method
    monitor_start = content.find('async def monitor_satellites(self')
    assert monitor_start != -1, "monitor_satellites method should exist"
    
    # Get the method body (rest of file since it's likely the last method)
    monitor_body = content[monitor_start:]
    
    # Check that direct asyncio.create_task is not used
    direct_create_task_pattern = r'asyncio\.create_task\s*\('
    matches = re.findall(direct_create_task_pattern, monitor_body)
    
    assert len(matches) == 0, \
        f"monitor_satellites should not use direct asyncio.create_task (found {len(matches)} instances)"
    print("  ✓ monitor_satellites does not use direct asyncio.create_task")
    
    # Check that it uses the throttled method
    assert '_spawn_status_task' in monitor_body, \
        "monitor_satellites should use _spawn_status_task"
    print("  ✓ monitor_satellites uses _spawn_status_task")
    
    print("✓ monitor_satellites throttled task spawning test passed")


def test_error_command_handling_throttled(content):
    """Test that ERROR command uses throttled spawning for status updates."""
    print("\nTesting ERROR command uses throttled spawning for status updates...")
    
    # Find the ERROR command handling section
    error_section_pattern = r'elif cmd == "ERROR":.*?(?=elif|else:|except)'
    error_section_match = re.search(error_section_pattern, content, re.DOTALL)
    
    assert error_section_match, "ERROR command handling should exist"
    error_section = error_section_match.group(0)
    
    # Verify it uses _spawn_status_task for status updates
    assert '_spawn_status_task' in error_section, \
        "ERROR handling should use _spawn_status_task for status updates"
    print("  ✓ ERROR handling uses _spawn_status_task for status updates")
    
    # Verify status updates are not using direct asyncio.create_task
    status_update_pattern = r'asyncio\.create_task\s*\(\s*self\.display\.update_status'
    if re.search(status_update_pattern, error_section):
        assert False, "ERROR handling should not use direct asyncio.create_task for status updates"
    print("  ✓ ERROR status updates use throttled spawning")
    
    # Audio tasks are allowed to use asyncio.create_task directly
    print("  ✓ ERROR audio tasks can use direct asyncio.create_task")
    
    print("✓ ERROR command throttled spawning test passed")


def test_docstrings_for_new_methods(content):
    """Test that new throttling methods have documentation."""
    print("\nTesting documentation for new methods...")
    
    # Check _spawn_status_task docstring
    spawn_status_pos = content.find('def _spawn_status_task(')
    assert spawn_status_pos != -1
    next_content = content[spawn_status_pos:spawn_status_pos+500]
    assert '"""' in next_content, "_spawn_status_task should have docstring"
    assert 'throttl' in next_content.lower(), \
        "docstring should mention throttling"
    print("  ✓ _spawn_status_task has throttling documentation")
    
    print("✓ Documentation test passed")


if __name__ == "__main__":
    # Run tests with pytest when executed as a script
    import subprocess
    result = subprocess.run([sys.executable, "-m", "pytest", __file__, "-v"])
    sys.exit(result.returncode)
