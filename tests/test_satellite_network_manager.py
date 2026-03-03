#!/usr/bin/env python3
"""Test SatelliteNetworkManager functionality.

This test validates the refactored satellite network manager that was
extracted from CoreManager to address the "God Object" anti-pattern.

Note: This test verifies the source code structure and content without
full module import to avoid CircuitPython dependencies.
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


def test_file_exists(file_path):
    """Test that SatelliteNetworkManager file exists."""
    print("Testing SatelliteNetworkManager file exists...")
    assert os.path.exists(file_path), "satellite_network_manager.py should exist"
    print(f"  ✓ File exists at {file_path}")
    print("✓ File existence test passed")


def test_class_definition(content):
    """Test that SatelliteNetworkManager class is defined."""
    print("\nTesting SatelliteNetworkManager class definition...")

    # Check class definition
    assert 'class SatelliteNetworkManager:' in content, "Class should be defined"
    print("  ✓ SatelliteNetworkManager class is defined")
    print("✓ Class definition test passed")


def test_required_methods(content):
    """Test that required methods are present."""
    print("\nTesting required methods...")

    required_methods = [
        '__init__',
        'set_debug_mode',
        'discover_satellites',
        'get_sat',
        'send_all',
        'monitor_messages',  # Changed from handle_message to monitor_messages
        'monitor_satellites',
    ]

    for method in required_methods:
        pattern = f'def {method}\\('
        assert re.search(pattern, content), f"Method {method} should exist"
        print(f"  ✓ Method '{method}' exists")

    print("✓ Required methods test passed")


def test_satellite_logic_extracted(content):
    """Test that satellite-related logic was extracted from CoreManager."""
    print("\nTesting satellite logic extraction...")

    # Check for satellite discovery logic
    assert 'ID_ASSIGN' in content, "ID assignment logic should be present"
    print("  ✓ ID assignment logic present")

    # Check for message handling
    assert 'STATUS' in content and 'POWER' in content and 'HELLO' in content, \
        "Message handling logic should be present"
    print("  ✓ Message handling logic present (STATUS, POWER, HELLO)")

    # Check for health monitoring
    assert 'ticks_diff' in content or 'last_seen' in content, \
        "Health monitoring logic should be present"
    print("  ✓ Health monitoring logic present")

    # Check for satellite registry
    assert 'self.satellites' in content, "Satellite registry should be managed"
    print("  ✓ Satellite registry managed")

    # Check for telemetry
    assert 'self.sat_telemetry' in content, "Satellite telemetry should be managed"
    print("  ✓ Satellite telemetry managed")

    print("✓ Satellite logic extraction test passed")


def test_manager_initialization(content):
    """Test that manager accepts required dependencies."""
    print("\nTesting manager initialization...")

    # Check __init__ signature (allow optional parameters)
    init_pattern = (
        r'def __init__\(\s*self\s*,\s*transport\s*,\s*display\s*,\s*audio'
        r'(?:\s*:[^,)]*)?\s*(?:,|\))'
    )
    assert re.search(init_pattern, content), "__init__ should accept transport, display, audio"
    print("  ✓ __init__ accepts transport, display, audio parameters")

    # Check dependencies are stored
    assert 'self.transport = transport' in content, "Transport should be stored"
    assert 'self.display = display' in content, "Display should be stored"
    assert 'self.audio = audio' in content, "Audio should be stored"
    print("  ✓ Dependencies are stored correctly")

    print("✓ Manager initialization test passed")


def test_docstrings(content):
    """Test that class and methods have documentation."""
    print("\nTesting documentation...")

    # Check class docstring
    assert '"""' in content, "Class should have docstring"
    assert 'satellite' in content.lower(), "Documentation should mention satellites"
    print("  ✓ Class has documentation")

    # Check method docstrings
    docstring_methods = [
        'discover_satellites',
        'get_sat',
        'send_all',
        'handle_message',
        'monitor_satellites',
    ]

    for method in docstring_methods:
        # Find method definition and check for docstring nearby
        method_pattern = f'def {method}\\('
        if re.search(method_pattern, content):
            # Simple check: method definition should have """ somewhere after it
            method_pos = content.find(f'def {method}(')
            next_content = content[method_pos:method_pos+500]
            assert '"""' in next_content, f"Method {method} should have docstring"
            print(f"  ✓ Method '{method}' has documentation")

    print("✓ Documentation test passed")


def test_core_manager_integration():
    """Test that CoreManager uses the new manager."""
    print("\nTesting CoreManager integration...")

    core_path = os.path.join(
        os.path.dirname(__file__), '..', 'src', 'core', 'core_manager.py'
    )

    with open(core_path, 'r') as f:
        content = f.read()

    # Check SatelliteNetworkManager import
    assert 'SatelliteNetworkManager' in content, \
        "CoreManager should import SatelliteNetworkManager"
    print("  ✓ CoreManager imports SatelliteNetworkManager")

    # Check sat_network initialization
    assert 'self.sat_network = SatelliteNetworkManager' in content, \
        "CoreManager should initialize sat_network"
    print("  ✓ CoreManager initializes sat_network")

    # Check delegation via properties or direct calls
    assert 'sat_network' in content, \
        "CoreManager should use sat_network"
    print("  ✓ CoreManager uses sat_network")

    # Verify old methods are removed from CoreManager (they're now in SatelliteNetworkManager)
    # Neither the old synchronous versions nor the new async versions should be in CoreManager
    assert 'def discover_satellites(self):' not in content and 'async def discover_satellites(self):' not in content, \
        "discover_satellites (sync or async) should not be in CoreManager - it's in SatelliteNetworkManager"
    assert 'def handle_message(' not in content and 'def monitor_messages(' not in content, \
        "handle_message/monitor_messages should not be in CoreManager - they're in SatelliteNetworkManager"
    assert 'def monitor_sats(' not in content and 'def monitor_satellites(' not in content, \
        "monitor_sats/monitor_satellites should not be in CoreManager - they're in SatelliteNetworkManager"
    print("  ✓ Old satellite methods removed from CoreManager (moved to SatelliteNetworkManager)")

    print("✓ CoreManager integration test passed")


_POWER_CMD_BODY_PATTERN = re.compile(
    r'async def _handle_power_command\(.*?(?=\n    (?:async )?def |\Z)',
    re.DOTALL,
)
"""Pre-compiled regex that extracts the _handle_power_command method body."""


@pytest.fixture
def power_cmd_body(content):
    """Fixture that extracts the _handle_power_command method body from the source file."""
    method_match = _POWER_CMD_BODY_PATTERN.search(content)
    assert method_match, "_handle_power_command method body should be extractable"
    return method_match.group(0)


def test_handle_power_command_is_async(content):
    """Test that _handle_power_command is defined as an async method."""
    print("\nTesting _handle_power_command is an async method...")

    assert re.search(r'async def _handle_power_command\(', content), \
        "_handle_power_command should be defined as an async method"
    print("  ✓ _handle_power_command is defined as async")

    print("✓ _handle_power_command async method test passed")


def test_handle_power_command_stores_telemetry(content, power_cmd_body):
    """Test that _handle_power_command stores parsed voltages in sat_telemetry."""
    print("\nTesting _handle_power_command telemetry storage...")

    # Verify the assignment target is keyed by satellite ID
    assert 'self.sat_telemetry[sid]' in content, \
        "_handle_power_command should store telemetry in self.sat_telemetry[sid]"
    print("  ✓ self.sat_telemetry[sid] assignment is present")

    # All three telemetry keys must appear in the dict literal inside the method.
    # Accept both single- and double-quoted forms (Python allows either).
    for key in ('in', 'bus', 'logic'):
        pattern = rf'''["']{re.escape(key)}["']'''
        assert re.search(pattern, power_cmd_body), \
            f"Telemetry dict should contain key '{key}' in _handle_power_command"
    print("  ✓ Telemetry dict contains 'in', 'bus', and 'logic' keys")

    print("✓ _handle_power_command telemetry storage test passed")


def test_handle_power_command_uses_get_float(content, power_cmd_body):
    """Test that get_float is imported from payload_parser and called in _handle_power_command."""
    print("\nTesting _handle_power_command uses get_float...")

    # Verify the import at module level
    assert re.search(
        r'from utilities\.payload_parser import.*get_float',
        content,
    ), "get_float should be imported from utilities.payload_parser"
    print("  ✓ get_float is imported from utilities.payload_parser")

    # Verify get_float is actually called inside the method body
    assert re.search(r'get_float\(', power_cmd_body), \
        "get_float should be called inside _handle_power_command"
    print("  ✓ get_float is called inside _handle_power_command")

    print("✓ _handle_power_command get_float usage test passed")


def test_handle_power_command_uvlo_threshold(content, power_cmd_body):
    """Test that SAT_UVLO_THRESHOLD constant is defined and used in the UVLO guard."""
    print("\nTesting _handle_power_command UVLO threshold constant and condition...")

    # Constant must be declared on the class with the expected value
    assert re.search(r'SAT_UVLO_THRESHOLD\s*=\s*18\.0', content), \
        "SAT_UVLO_THRESHOLD should be defined as 18.0"
    print("  ✓ SAT_UVLO_THRESHOLD = 18.0 constant is defined")

    # Condition must reference the constant (not a bare literal)
    assert re.search(r'v_in\s*<\s*self\.SAT_UVLO_THRESHOLD', power_cmd_body), \
        "UVLO check should compare v_in against self.SAT_UVLO_THRESHOLD"
    print("  ✓ UVLO condition uses self.SAT_UVLO_THRESHOLD")

    # Guard against zero/negative v_in must also be present
    assert re.search(r'v_in\s*>\s*0', power_cmd_body), \
        "UVLO check should also guard with v_in > 0"
    print("  ✓ UVLO guard includes v_in > 0")

    print("✓ _handle_power_command UVLO threshold test passed")


def test_handle_power_command_uvlo_triggers_display_and_audio(power_cmd_body):
    """Test that a UVLO condition triggers a display status update and an audio alarm task."""
    print("\nTesting _handle_power_command UVLO display and audio response...")

    # Display alert must be raised with the SAT UVLO ALERT message
    assert re.search(r'self\.display\.update_status\(', power_cmd_body), \
        "_handle_power_command should call self.display.update_status"
    assert 'SAT UVLO ALERT' in power_cmd_body, \
        "_handle_power_command should pass 'SAT UVLO ALERT' to update_status"
    print("  ✓ self.display.update_status called with 'SAT UVLO ALERT'")

    # Audio alarm task must be spawned inside the method
    assert re.search(r'self\._spawn_audio_task\(', power_cmd_body), \
        "_handle_power_command should spawn an audio task via self._spawn_audio_task"
    print("  ✓ self._spawn_audio_task is called inside _handle_power_command")

    print("✓ _handle_power_command UVLO display and audio trigger test passed")


if __name__ == "__main__":
    # Run tests with pytest when executed as a script
    import subprocess
    result = subprocess.run([sys.executable, "-m", "pytest", __file__, "-v"])
    sys.exit(result.returncode)
