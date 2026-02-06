#!/usr/bin/env python3
"""Unit tests for BaseMode class."""

import sys
import os
import asyncio
import pytest

# Add src to path for direct module import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'modes'))

# Import BaseMode
from base import BaseMode


class MockManager:
    """Mock manager object for testing."""
    def __init__(self):
        self.cleared = False
        self.stopped = False
        self.flushed = False
        self.status_text = ""
        self.sub_status_text = ""
        self.current_mode_step = 0
    
    def clear(self):
        """Mock clear."""
        self.cleared = True
    
    def stop_all(self):
        """Mock stop_all."""
        self.stopped = True
    
    def flush(self):
        """Mock flush."""
        self.flushed = True
    
    def update_status(self, text, sub_text=""):
        """Mock update_status."""
        self.status_text = text
        self.sub_status_text = sub_text


class MockCore:
    """Mock core manager for testing."""
    def __init__(self):
        self.matrix = MockManager()
        self.audio = MockManager()
        self.hid = MockManager()
        self.display = MockManager()
        self.current_mode_step = 0


def test_basemode_initialization():
    """Test BaseMode initialization."""
    print("Testing BaseMode initialization...")
    
    core = MockCore()
    mode = BaseMode(core, name="TEST_MODE", description="Test Mode Description")
    
    assert mode.core == core, "Core should be stored"
    assert mode.name == "TEST_MODE", "Name should be stored"
    assert mode.description == "Test Mode Description", "Description should be stored"
    assert mode.variant == "DEFAULT", "Variant should default to DEFAULT"
    
    print("✓ BaseMode initialization test passed")


def test_basemode_default_variant():
    """Test that variant defaults to DEFAULT."""
    print("\nTesting BaseMode default variant...")
    
    core = MockCore()
    mode = BaseMode(core, name="MODE")
    
    assert mode.variant == "DEFAULT", "Variant should default to DEFAULT"
    
    print("✓ Default variant test passed")


@pytest.mark.asyncio
async def test_basemode_enter():
    """Test BaseMode enter method."""
    print("\nTesting BaseMode enter...")
    
    core = MockCore()
    mode = BaseMode(core, name="TEST_MODE")
    
    # Enter should reset hardware and update display
    await mode.enter()
    
    assert core.matrix.cleared, "Matrix should be cleared on enter"
    assert core.audio.stopped, "Audio should be stopped on enter"
    assert core.hid.flushed, "HID should be flushed on enter"
    assert core.display.status_text == "TEST_MODE", "Display should show mode name"
    assert core.display.sub_status_text == "LOADING...", "Display should show loading"
    
    print("✓ BaseMode enter test passed")


@pytest.mark.asyncio
async def test_basemode_exit():
    """Test BaseMode exit method."""
    print("\nTesting BaseMode exit...")
    
    core = MockCore()
    mode = BaseMode(core, name="TEST_MODE")
    
    # Set some state
    core.current_mode_step = 5
    
    # Exit should cleanup
    await mode.exit()
    
    assert core.matrix.cleared, "Matrix should be cleared on exit"
    assert core.audio.stopped, "Audio should be stopped on exit"
    assert core.current_mode_step == 0, "Mode step should be reset on exit"
    
    print("✓ BaseMode exit test passed")


@pytest.mark.asyncio
async def test_basemode_run_not_implemented():
    """Test that run method raises NotImplementedError."""
    print("\nTesting BaseMode run raises NotImplementedError...")
    
    core = MockCore()
    mode = BaseMode(core, name="TEST_MODE")
    
    try:
        await mode.run()
        assert False, "run() should raise NotImplementedError"
    except NotImplementedError as e:
        assert "Subclasses must implement the run() method" in str(e)
    
    print("✓ run() NotImplementedError test passed")


@pytest.mark.asyncio
async def test_basemode_execute():
    """Test BaseMode execute wrapper."""
    print("\nTesting BaseMode execute wrapper...")
    
    core = MockCore()
    
    # Create a subclass that implements run
    class TestMode(BaseMode):
        def __init__(self, core):
            super().__init__(core, name="TEST_MODE")
            self.run_called = False
            self.enter_called = False
            self.exit_called = False
        
        async def enter(self):
            await super().enter()
            self.enter_called = True
        
        async def run(self):
            self.run_called = True
            return "TEST_RESULT"
        
        async def exit(self):
            await super().exit()
            self.exit_called = True
    
    mode = TestMode(core)
    result = await mode.execute()
    
    assert mode.enter_called, "enter() should be called"
    assert mode.run_called, "run() should be called"
    assert mode.exit_called, "exit() should be called"
    assert result == "TEST_RESULT", "execute() should return run() result"
    
    print("✓ execute() wrapper test passed")


@pytest.mark.asyncio
async def test_basemode_execute_ensures_exit():
    """Test that execute always calls exit, even on exception."""
    print("\nTesting BaseMode execute ensures exit on exception...")
    
    core = MockCore()
    
    # Create a subclass that raises an exception in run
    class FailingMode(BaseMode):
        def __init__(self, core):
            super().__init__(core, name="FAILING_MODE")
            self.exit_called = False
        
        async def run(self):
            raise ValueError("Test error")
        
        async def exit(self):
            await super().exit()
            self.exit_called = True
    
    mode = FailingMode(core)
    
    try:
        await mode.execute()
        assert False, "execute() should propagate the exception"
    except ValueError:
        pass
    
    assert mode.exit_called, "exit() should be called even when run() raises exception"
    
    print("✓ execute() ensures exit test passed")


@pytest.mark.asyncio
async def test_basemode_subclass_implementation():
    """Test that subclasses can properly implement run."""
    print("\nTesting BaseMode subclass implementation...")
    
    core = MockCore()
    
    # Create a proper subclass
    class GameMode(BaseMode):
        def __init__(self, core):
            super().__init__(core, name="GAME_MODE", description="A game mode")
            self.variant = "HARD"
        
        async def run(self):
            return "GAME_COMPLETE"
    
    mode = GameMode(core)
    
    assert mode.name == "GAME_MODE"
    assert mode.description == "A game mode"
    assert mode.variant == "HARD"
    
    result = await mode.execute()
    assert result == "GAME_COMPLETE"
    
    print("✓ Subclass implementation test passed")


@pytest.mark.asyncio
async def test_basemode_execute_return_none():
    """Test that execute handles run methods that return None."""
    print("\nTesting BaseMode execute with None return...")
    
    core = MockCore()
    
    class SimpleMode(BaseMode):
        async def run(self):
            pass  # Returns None implicitly
    
    mode = SimpleMode(core, name="SIMPLE")
    result = await mode.execute()
    
    assert result is None, "execute() should return None if run() returns None"
    
    print("✓ execute() with None return test passed")


def test_basemode_multiple_instances():
    """Test creating multiple BaseMode instances."""
    print("\nTesting multiple BaseMode instances...")
    
    core = MockCore()
    
    mode1 = BaseMode(core, name="MODE1", description="First mode")
    mode2 = BaseMode(core, name="MODE2", description="Second mode")
    
    assert mode1.name == "MODE1"
    assert mode2.name == "MODE2"
    assert mode1.core == core
    assert mode2.core == core
    assert mode1 != mode2
    
    print("✓ Multiple instances test passed")


def run_all_tests():
    """Run all BaseMode tests."""
    print("="*60)
    print("Running BaseMode Tests")
    print("="*60)
    
    sync_tests = [
        test_basemode_initialization,
        test_basemode_default_variant,
        test_basemode_multiple_instances,
    ]
    
    async_tests = [
        test_basemode_enter,
        test_basemode_exit,
        test_basemode_run_not_implemented,
        test_basemode_execute,
        test_basemode_execute_ensures_exit,
        test_basemode_subclass_implementation,
        test_basemode_execute_return_none,
    ]
    
    passed = 0
    failed = 0
    
    # Run synchronous tests
    for test in sync_tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"\n✗ {test.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"\n✗ {test.__name__} ERROR: {e}")
            failed += 1
    
    # Run asynchronous tests
    for test in async_tests:
        try:
            asyncio.run(test())
            passed += 1
        except AssertionError as e:
            print(f"\n✗ {test.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"\n✗ {test.__name__} ERROR: {e}")
            failed += 1
    
    print("\n" + "="*60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("="*60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
