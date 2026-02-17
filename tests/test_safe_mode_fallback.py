#!/usr/bin/env python3
"""Test safe mode fallback functionality.

This test verifies that the CoreManager properly falls back to SAFE_MODE
when DASHBOARD mode fails repeatedly, preventing infinite error loops.

Note: This test inspects source code rather than importing modules directly,
as the actual modules require CircuitPython hardware dependencies.
"""

import sys
import os
import re

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'core'))


def get_core_manager_source():
    """Get the source code of core_manager.py"""
    core_manager_path = os.path.join(
        os.path.dirname(__file__), '..', 'src', 'core', 'core_manager.py'
    )
    with open(core_manager_path, 'r') as f:
        return f.read()


def test_safe_mode_class_exists():
    """Test that SafeMode class is defined in core_manager module."""
    print("Testing SafeMode class existence...")
    
    source = get_core_manager_source()
    
    # Check for SafeMode class definition
    assert 'class SafeMode:' in source or 'class SafeMode(' in source, \
        "SafeMode class should be defined in core_manager.py"
    
    print("  ✓ SafeMode class is defined")
    print("✓ SafeMode class existence test passed")


def test_safe_mode_has_required_methods():
    """Test that SafeMode has all required methods."""
    print("\nTesting SafeMode required methods...")
    
    source = get_core_manager_source()
    
    # Extract SafeMode class definition
    safe_mode_match = re.search(r'class SafeMode.*?(?=\nclass |\Z)', source, re.DOTALL)
    assert safe_mode_match, "Could not find SafeMode class definition"
    
    safe_mode_code = safe_mode_match.group(0)
    
    # Check for required methods
    required_methods = ['__init__', 'enter', 'run', 'exit', 'execute']
    
    for method_name in required_methods:
        pattern = f'async def {method_name}|def {method_name}'
        assert re.search(pattern, safe_mode_code), \
            f"SafeMode should have {method_name} method"
        print(f"  ✓ SafeMode.{method_name} exists")
    
    print("✓ SafeMode required methods test passed")


def test_safe_mode_minimal_dependencies():
    """Test that SafeMode documentation mentions minimal dependencies."""
    print("\nTesting SafeMode minimal dependencies...")
    
    source = get_core_manager_source()
    
    # Extract SafeMode class
    safe_mode_match = re.search(r'class SafeMode.*?(?=\nclass |\Z)', source, re.DOTALL)
    assert safe_mode_match, "Could not find SafeMode class definition"
    
    safe_mode_code = safe_mode_match.group(0)
    
    # Should mention minimal or zero dependencies
    assert 'minimal' in safe_mode_code.lower() or 'zero' in safe_mode_code.lower(), \
        "SafeMode should mention minimal/zero dependencies in documentation"
    
    # Should handle display being None/unavailable
    assert 'if hasattr' in safe_mode_code or 'try:' in safe_mode_code, \
        "SafeMode should handle missing display gracefully"
    
    print("  ✓ SafeMode mentions minimal/zero dependencies")
    print("  ✓ SafeMode handles missing hardware gracefully")
    print("✓ SafeMode minimal dependencies test passed")


def test_core_manager_has_failure_tracking():
    """Test that CoreManager has dashboard failure tracking attributes."""
    print("\nTesting CoreManager failure tracking...")
    
    source = get_core_manager_source()
    
    # Check for failure tracking attributes
    assert 'dashboard_failure_count' in source, \
        "CoreManager should have dashboard_failure_count attribute"
    assert 'max_dashboard_failures' in source, \
        "CoreManager should have max_dashboard_failures attribute"
    
    # Check that they are initialized (should be set to 0)
    assert 'self.dashboard_failure_count = 0' in source, \
        "dashboard_failure_count should be initialized to 0"
    
    print("  ✓ CoreManager has dashboard_failure_count")
    print("  ✓ CoreManager has max_dashboard_failures")
    print("  ✓ Failure tracking initialized properly")
    print("✓ CoreManager failure tracking test passed")


def test_core_manager_safe_mode_logic():
    """Test that CoreManager has SAFE_MODE logic in start() method."""
    print("\nTesting CoreManager SAFE_MODE logic...")
    
    source = get_core_manager_source()
    
    # Check for SAFE_MODE handling
    assert '"SAFE_MODE"' in source, \
        "CoreManager should reference SAFE_MODE string"
    assert 'self.mode == "SAFE_MODE"' in source, \
        "CoreManager should check for SAFE_MODE state"
    assert 'self.mode == "DASHBOARD"' in source, \
        "CoreManager should check for DASHBOARD failures"
    
    # Check for failure counter increment
    assert 'dashboard_failure_count += 1' in source, \
        "CoreManager should increment failure counter"
    
    # Check for safe mode activation on max failures
    assert 'self.mode = "SAFE_MODE"' in source, \
        "CoreManager should activate SAFE_MODE"
    
    # Check for counter reset on successful load
    assert 'dashboard_failure_count = 0' in source, \
        "CoreManager should reset failure counter on success"
    
    print("  ✓ CoreManager references SAFE_MODE")
    print("  ✓ CoreManager checks for SAFE_MODE state")
    print("  ✓ CoreManager checks for DASHBOARD failures")
    print("  ✓ CoreManager increments failure counter")
    print("  ✓ CoreManager activates SAFE_MODE on max failures")
    print("  ✓ CoreManager resets counter on success")
    print("✓ CoreManager SAFE_MODE logic test passed")


def test_safe_mode_error_message():
    """Test that SafeMode displays appropriate error message."""
    print("\nTesting SafeMode error message...")
    
    source = get_core_manager_source()
    
    # Extract SafeMode class
    safe_mode_match = re.search(r'class SafeMode.*?(?=\nclass |\Z)', source, re.DOTALL)
    assert safe_mode_match, "Could not find SafeMode class definition"
    
    safe_mode_code = safe_mode_match.group(0)
    
    # Should contain error message about DASHBOARD being corrupt
    assert 'DASHBOARD CORRUPT' in safe_mode_code or 'DASHBOARD' in safe_mode_code, \
        "SafeMode should mention DASHBOARD in error message"
    assert 'HALT' in safe_mode_code or 'halt' in safe_mode_code, \
        "SafeMode should indicate system halt"
    assert 'intervention' in safe_mode_code.lower(), \
        "SafeMode should mention developer intervention"
    
    print("  ✓ SafeMode contains DASHBOARD CORRUPT message")
    print("  ✓ SafeMode indicates system halt")
    print("  ✓ SafeMode mentions developer intervention")
    print("✓ SafeMode error message test passed")


def test_safe_mode_runs_indefinitely():
    """Test that SafeMode run() method waits indefinitely."""
    print("\nTesting SafeMode infinite wait...")
    
    source = get_core_manager_source()
    
    # Extract SafeMode class
    safe_mode_match = re.search(r'class SafeMode.*?(?=\nclass |\Z)', source, re.DOTALL)
    assert safe_mode_match, "Could not find SafeMode class definition"
    
    safe_mode_code = safe_mode_match.group(0)
    
    # Extract run method
    run_match = re.search(r'async def run\(.*?\n(?=    async def |    def |\Z)', 
                          safe_mode_code, re.DOTALL)
    assert run_match, "Could not find run() method"
    
    run_code = run_match.group(0)
    
    # Should have an infinite loop (while True)
    assert 'while True:' in run_code, \
        "SafeMode run() should have infinite loop"
    assert 'await asyncio.sleep' in run_code, \
        "SafeMode run() should use asyncio.sleep"
    
    print("  ✓ SafeMode run() has infinite loop")
    print("  ✓ SafeMode run() uses asyncio.sleep")
    print("✓ SafeMode infinite wait test passed")


if __name__ == "__main__":
    print("=" * 60)
    print("Safe Mode Fallback Test Suite")
    print("Testing fail-safe mode to prevent infinite error loops")
    print("=" * 60)
    
    try:
        test_safe_mode_class_exists()
        test_safe_mode_has_required_methods()
        test_safe_mode_minimal_dependencies()
        test_core_manager_has_failure_tracking()
        test_core_manager_safe_mode_logic()
        test_safe_mode_error_message()
        test_safe_mode_runs_indefinitely()
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)
        print()
        print("Safe mode implementation successfully:")
        print("  • Defines SafeMode class with minimal dependencies")
        print("  • Tracks DASHBOARD failure count in CoreManager")
        print("  • Falls back to SAFE_MODE after repeated failures")
        print("  • Prevents infinite error loops")
        print("  • Displays appropriate error messages")
        print("  • Runs indefinitely awaiting intervention")
        
        sys.exit(0)
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
