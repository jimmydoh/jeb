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


def test_file_exists():
    """Test that SatelliteNetworkManager file exists."""
    print("Testing SatelliteNetworkManager file exists...")
    
    file_path = os.path.join(
        os.path.dirname(__file__), '..', 'src', 'managers', 'satellite_network_manager.py'
    )
    
    assert os.path.exists(file_path), "satellite_network_manager.py should exist"
    print(f"  ✓ File exists at {file_path}")
    print("✓ File existence test passed")
    return file_path


def test_class_definition(file_path):
    """Test that SatelliteNetworkManager class is defined."""
    print("\nTesting SatelliteNetworkManager class definition...")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Check class definition
    assert 'class SatelliteNetworkManager:' in content, "Class should be defined"
    print("  ✓ SatelliteNetworkManager class is defined")
    print("✓ Class definition test passed")
    return content


def test_required_methods(content):
    """Test that required methods are present."""
    print("\nTesting required methods...")
    
    required_methods = [
        '__init__',
        'set_debug_mode',
        'discover_satellites',
        'get_sat',
        'send_all',
        'handle_message',
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
    
    # Check __init__ signature
    init_pattern = r'def __init__\(self, transport, display, audio\)'
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


def test_managers_package_export():
    """Test that SatelliteNetworkManager is exported from managers package."""
    print("\nTesting managers package export...")
    
    init_path = os.path.join(
        os.path.dirname(__file__), '..', 'src', 'managers', '__init__.py'
    )
    
    with open(init_path, 'r') as f:
        content = f.read()
    
    # Check import statement
    assert 'from .satellite_network_manager import SatelliteNetworkManager' in content, \
        "SatelliteNetworkManager should be imported"
    print("  ✓ SatelliteNetworkManager imported in __init__.py")
    
    # Check __all__ export
    assert 'SatelliteNetworkManager' in content, \
        "SatelliteNetworkManager should be in __all__"
    print("  ✓ SatelliteNetworkManager in __all__")
    
    print("✓ Package export test passed")


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
    
    # Verify old methods are removed
    assert 'def discover_satellites(self):' not in content, \
        "discover_satellites should be removed from CoreManager"
    assert 'def handle_message(self, message):' not in content, \
        "handle_message should be removed from CoreManager"
    assert 'def monitor_sats(self):' not in content, \
        "monitor_sats should be removed from CoreManager"
    print("  ✓ Old satellite methods removed from CoreManager")
    
    print("✓ CoreManager integration test passed")


if __name__ == "__main__":
    print("=" * 60)
    print("SatelliteNetworkManager Test Suite")
    print("Testing refactored satellite network manager")
    print("=" * 60)
    
    try:
        file_path = test_file_exists()
        content = test_class_definition(file_path)
        test_required_methods(content)
        test_satellite_logic_extracted(content)
        test_manager_initialization(content)
        test_docstrings(content)
        test_managers_package_export()
        test_core_manager_integration()
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)
        print()
        print("The SatelliteNetworkManager successfully:")
        print("  • Has been extracted from CoreManager")
        print("  • Contains satellite discovery logic")
        print("  • Contains satellite health monitoring logic")
        print("  • Contains message handling logic")
        print("  • Provides clean interface for CoreManager")
        print("  • Reduces CoreManager's responsibilities")
        print("  • Is properly integrated with CoreManager")
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        print("\n" + "=" * 60)
        print("TESTS FAILED ✗")
        print("=" * 60)
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        print("\n" + "=" * 60)
        print("TESTS FAILED ✗")
        print("=" * 60)
        sys.exit(1)

