#!/usr/bin/env python3
"""Test _spawn_status_task coroutine factory pattern to avoid coroutine leaks.

This test validates that the _spawn_status_task method accepts a coroutine
factory (callable + args) instead of a coroutine object, which prevents
'coroutine was never awaited' warnings when throttling skips task creation.

Note: This test verifies the source code structure without full module import
to avoid CircuitPython dependencies.
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


def test_spawn_status_task_signature(content):
    """Test that _spawn_status_task accepts a coroutine factory."""
    print("Testing _spawn_status_task signature...")
    
    # Check that the signature accepts coro_func and *args, **kwargs
    pattern = r'def _spawn_status_task\(self,\s*coro_func,\s*\*args,\s*\*\*kwargs\):'
    assert re.search(pattern, content), \
        "_spawn_status_task should accept coro_func, *args, **kwargs"
    print("  ✓ _spawn_status_task accepts coroutine factory pattern")
    
    print("✓ Signature test passed")


def test_spawn_status_task_implementation(content):
    """Test that _spawn_status_task calls the factory function."""
    print("\nTesting _spawn_status_task implementation...")
    
    # Check that it calls coro_func(*args, **kwargs)
    pattern = r'coro_func\(\*args,\s*\*\*kwargs\)'
    assert re.search(pattern, content), \
        "_spawn_status_task should call coro_func(*args, **kwargs)"
    print("  ✓ _spawn_status_task calls factory function with args/kwargs")
    
    # Check that it creates a task from the result
    pattern = r'asyncio\.create_task\(coro_func\(\*args,\s*\*\*kwargs\)\)'
    assert re.search(pattern, content), \
        "_spawn_status_task should create task from factory result"
    print("  ✓ Task created from factory function result")
    
    print("✓ Implementation test passed")


def test_spawn_status_task_docstring(content):
    """Test that _spawn_status_task has updated documentation."""
    print("\nTesting _spawn_status_task documentation...")
    
    # Find the _spawn_status_task method and its docstring
    method_start = content.find('def _spawn_status_task(')
    assert method_start != -1, "_spawn_status_task method should exist"
    
    # Get a section of text after the method definition
    section = content[method_start:method_start+1500]
    
    # Check that there is a docstring
    assert '"""' in section, "_spawn_status_task should have a docstring"
    
    # Extract docstring content (simplified - just get text between triple quotes)
    first_quotes = section.find('"""')
    if first_quotes != -1:
        second_quotes = section.find('"""', first_quotes + 3)
        if second_quotes != -1:
            docstring = section[first_quotes:second_quotes+3].lower()
            
            # Check for key documentation points
            assert 'factory' in docstring or 'callable' in docstring, \
                "Docstring should mention factory or callable"
            print("  ✓ Docstring mentions factory/callable pattern")
            
            assert 'coroutine was never awaited' in docstring or \
                   ('avoid' in docstring and 'warning' in docstring), \
                "Docstring should explain the motivation"
            print("  ✓ Docstring explains motivation for the pattern")
    
    print("✓ Documentation test passed")


def test_call_sites_use_factory_pattern(content):
    """Test that all _spawn_status_task call sites use the factory pattern."""
    print("\nTesting _spawn_status_task call sites...")
    
    # Find all calls to _spawn_status_task
    call_pattern = r'self\._spawn_status_task\('
    calls = list(re.finditer(call_pattern, content))
    
    assert len(calls) > 0, "Should have at least one call to _spawn_status_task"
    print(f"  ✓ Found {len(calls)} calls to _spawn_status_task")
    
    # Check that calls don't have parentheses after the first argument
    # (which would indicate passing a coroutine object instead of a factory)
    bad_pattern = r'self\._spawn_status_task\(\s*self\.display\.update_status\([^)]+\)\s*\)'
    bad_calls = list(re.finditer(bad_pattern, content))
    
    assert len(bad_calls) == 0, \
        f"Found {len(bad_calls)} calls passing coroutine objects instead of factory"
    print("  ✓ No calls pass coroutine objects (all use factory pattern)")
    
    # Check that calls pass the method reference without calling it
    good_pattern = r'self\._spawn_status_task\(\s*self\.display\.update_status,\s*["\']'
    good_calls = list(re.finditer(good_pattern, content))
    
    assert len(good_calls) > 0, \
        "Should have calls using factory pattern (method, args)"
    print(f"  ✓ Found {len(good_calls)} calls using proper factory pattern")
    
    print("✓ Call sites test passed")


def test_throttling_logic_preserved(content):
    """Test that the throttling logic is still present."""
    print("\nTesting throttling logic...")
    
    # Check that throttling condition is still there
    pattern = r'if self\._current_status_task is None or self\._current_status_task\.done\(\):'
    assert re.search(pattern, content), \
        "Throttling logic should check if task is None or done"
    print("  ✓ Throttling condition preserved")
    
    # Check that _current_status_task is still assigned
    pattern = r'self\._current_status_task = asyncio\.create_task'
    assert re.search(pattern, content), \
        "Should assign to _current_status_task"
    print("  ✓ Task assignment preserved")
    
    print("✓ Throttling logic test passed")


if __name__ == "__main__":
    # Run tests with pytest when executed as a script
    import subprocess
    result = subprocess.run([sys.executable, "-m", "pytest", __file__, "-v"])
    sys.exit(result.returncode)
