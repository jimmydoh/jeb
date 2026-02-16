#!/usr/bin/env python3
"""Unit tests for BuzzerManager (pwmio-based implementation)."""

import sys
import os
import asyncio
import pytest

# Mock CircuitPython modules BEFORE any imports
class MockModule:
    """Generic mock module."""
    def __getattr__(self, name):
        return MockModule()
    
    def __call__(self, *args, **kwargs):
        return MockModule()


sys.modules['digitalio'] = MockModule()
sys.modules['busio'] = MockModule()
sys.modules['board'] = MockModule()
sys.modules['adafruit_mcp230xx'] = MockModule()
sys.modules['adafruit_mcp230xx.mcp23017'] = MockModule()
sys.modules['adafruit_ticks'] = MockModule()
sys.modules['audiobusio'] = MockModule()
sys.modules['audiocore'] = MockModule()
sys.modules['audiomixer'] = MockModule()
sys.modules['audiopwmio'] = MockModule()
sys.modules['analogio'] = MockModule()
sys.modules['microcontroller'] = MockModule()
sys.modules['watchdog'] = MockModule()
sys.modules['storage'] = MockModule()
sys.modules['synthio'] = MockModule()

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# Mock pwmio module
class MockPWMOut:
    """Mock pwmio.PWMOut."""
    def __init__(self, pin, duty_cycle=0, frequency=440, variable_frequency=False):
        self.pin = pin
        self.duty_cycle = duty_cycle
        self.frequency = frequency
        self.variable_frequency = variable_frequency
        self.history = []  # Track state changes for testing
    
    def __setattr__(self, name, value):
        if name != 'history' and hasattr(self, 'history'):
            self.history.append((name, value))
        super().__setattr__(name, value)


class MockPwmio:
    """Mock pwmio module."""
    PWMOut = MockPWMOut


sys.modules['pwmio'] = MockPwmio()


# Import packages first to establish them as packages
import utilities
import utilities.synth_registry
import managers

# Import BuzzerManager directly using importlib to bypass managers/__init__.py
import importlib.util
spec = importlib.util.spec_from_file_location(
    "buzzer_manager",
    os.path.join(os.path.dirname(__file__), '..', 'src', 'managers', 'buzzer_manager.py')
)
buzzer_manager_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(buzzer_manager_module)
BuzzerManager = buzzer_manager_module.BuzzerManager


def test_buzzer_initialization():
    """Test BuzzerManager initialization."""
    print("Testing buzzer initialization...")
    
    mock_pin = "GP10"
    buzzer = BuzzerManager(mock_pin)
    
    assert buzzer.buzzer is not None, "PWM buzzer should be initialized"
    assert buzzer.buzzer.duty_cycle == 0, "Initial duty cycle should be 0 (silent)"
    assert buzzer.buzzer.frequency == 440, "Initial frequency should be 440Hz"
    assert buzzer.buzzer.variable_frequency == True, "Variable frequency should be enabled"
    assert buzzer._current_task is None, "No task should be running initially"
    
    # Test volume calculation (default 0.5)
    expected_volume = int(0.5 * (2**16 - 1))
    assert buzzer.VOLUME_ON == expected_volume, f"Volume should be {expected_volume}"
    assert buzzer.VOLUME_OFF == 0, "VOLUME_OFF should be 0"
    
    print("✓ Buzzer initialization test passed")


def test_buzzer_volume_validation():
    """Test volume validation."""
    print("\nTesting volume validation...")
    
    mock_pin = "GP10"
    
    # Valid volumes
    buzzer1 = BuzzerManager(mock_pin, volume=0.0)
    assert buzzer1.VOLUME_ON == 0
    
    buzzer2 = BuzzerManager(mock_pin, volume=1.0)
    assert buzzer2.VOLUME_ON == 65535
    
    # Invalid volumes
    try:
        BuzzerManager(mock_pin, volume=-0.1)
        assert False, "Should raise ValueError for volume < 0"
    except ValueError as e:
        assert "between 0.0 and 1.0" in str(e)
    
    try:
        BuzzerManager(mock_pin, volume=1.1)
        assert False, "Should raise ValueError for volume > 1"
    except ValueError as e:
        assert "between 0.0 and 1.0" in str(e)
    
    print("✓ Volume validation test passed")


@pytest.mark.asyncio
async def test_buzzer_stop():
    """Test buzzer stop functionality."""
    print("\nTesting buzzer stop...")
    
    mock_pin = "GP10"
    buzzer = BuzzerManager(mock_pin)
    
    # Create a long-running task
    buzzer._current_task = asyncio.create_task(asyncio.sleep(10))
    
    # Stop should cancel the task
    await buzzer.stop()
    
    assert buzzer._current_task.done(), "Task should be cancelled"
    assert buzzer._current_task.cancelled(), "Task should be marked as cancelled"
    assert buzzer.buzzer.duty_cycle == 0, "Duty cycle should be 0 after stop"
    
    print("✓ Buzzer stop test passed")


@pytest.mark.asyncio
async def test_play_note_with_duration():
    """Test playing a note with duration."""
    print("\nTesting play_note with duration...")
    
    mock_pin = "GP10"
    buzzer = BuzzerManager(mock_pin, testing=True)
    
    # Play a short note
    buzzer.play_note(440, duration=0.1)
    
    # Give the task time to start and run
    await asyncio.sleep(0.05)
    
    # Verify buzzer is playing
    assert buzzer.buzzer.frequency == 440, "Frequency should be set to 440Hz"
    assert buzzer.buzzer.duty_cycle == buzzer.VOLUME_ON, "Duty cycle should be on"
    
    # Wait for note to complete
    await asyncio.sleep(0.1)
    
    # Verify buzzer stopped
    assert buzzer.buzzer.duty_cycle == buzzer.VOLUME_OFF, "Duty cycle should be off after duration"
    
    print("✓ Play note with duration test passed")


@pytest.mark.asyncio
async def test_play_note_without_duration():
    """Test playing a continuous note without duration."""
    print("\nTesting play_note without duration...")
    
    mock_pin = "GP10"
    buzzer = BuzzerManager(mock_pin)
    
    # Play a continuous note
    buzzer.play_note(880, duration=None)
    
    # Give the task time to start
    await asyncio.sleep(0.05)
    
    # Verify buzzer is playing
    assert buzzer.buzzer.frequency == 880, "Frequency should be set to 880Hz"
    assert buzzer.buzzer.duty_cycle == buzzer.VOLUME_ON, "Duty cycle should be on"
    
    # Stop manually
    await buzzer.stop()
    assert buzzer.buzzer.duty_cycle == buzzer.VOLUME_OFF, "Duty cycle should be off after stop"
    
    print("✓ Play note without duration test passed")


@pytest.mark.asyncio
async def test_play_sequence():
    """Test playing a sequence of notes."""
    print("\nTesting play_sequence...")
    
    mock_pin = "GP10"
    buzzer = BuzzerManager(mock_pin, testing=True)
    
    # Create a simple sequence
    sequence_data = {
        'bpm': 240,  # Fast tempo for testing
        'sequence': [
            ('C4', 0.1),
            ('D4', 0.1),
            ('E4', 0.1)
        ]
    }
    
    buzzer.play_sequence(sequence_data)
    
    # Give time for sequence to start and play
    await asyncio.sleep(0.4)
    
    # The sequence should have played
    assert buzzer._current_task is not None, "Task should exist"
    
    # Stop to clean up
    await buzzer.stop()
    
    print("✓ Play sequence test passed")


@pytest.mark.asyncio
async def test_play_sequence_with_rest():
    """Test sequence with rest notes (frequency = 0)."""
    print("\nTesting sequence with rest notes...")
    
    mock_pin = "GP10"
    buzzer = BuzzerManager(mock_pin)
    
    # Sequence with rest
    sequence_data = {
        'bpm': 240,  # Fast tempo
        'sequence': [
            ('C4', 0.1),
            ('-', 0.1),  # Rest
            ('E4', 0.1)
        ]
    }
    
    buzzer.play_sequence(sequence_data)
    
    # Give time for sequence to complete
    await asyncio.sleep(0.4)
    
    # Stop to clean up
    await buzzer.stop()
    
    print("✓ Sequence with rest test passed")


@pytest.mark.asyncio
async def test_play_sequence_by_name():
    """Test playing a named sequence from tones module."""
    print("\nTesting play_sequence by name...")
    
    mock_pin = "GP10"
    buzzer = BuzzerManager(mock_pin)
    
    # Play a named sequence (should exist in tones.py)
    buzzer.play_sequence('BEEP')
    
    # Give time for sequence to start
    await asyncio.sleep(0.1)
    
    # Stop to clean up
    await buzzer.stop()
    
    print("✓ Play sequence by name test passed")


@pytest.mark.asyncio
async def test_invalid_sequence_name():
    """Test handling of invalid sequence name."""
    print("\nTesting invalid sequence name...")
    
    mock_pin = "GP10"
    buzzer = BuzzerManager(mock_pin)
    
    # Play an invalid sequence name (should print warning and return)
    buzzer.play_sequence('NONEXISTENT_SEQUENCE')
    
    # Give time for any potential task
    await asyncio.sleep(0.05)
    
    # Task should not be created
    assert buzzer._current_task is None, "No task should be created for invalid sequence"
    
    print("✓ Invalid sequence name test passed")


@pytest.mark.asyncio
async def test_invalid_sequence_type():
    """Test handling of invalid sequence type."""
    print("\nTesting invalid sequence type...")
    
    mock_pin = "GP10"
    buzzer = BuzzerManager(mock_pin)
    
    # Try to play an invalid type
    buzzer.play_sequence(12345)  # Not a string or dict
    
    # Give time for any potential task
    await asyncio.sleep(0.05)
    
    # Task should not be created
    assert buzzer._current_task is None, "No task should be created for invalid type"
    
    print("✓ Invalid sequence type test passed")


@pytest.mark.asyncio
async def test_stop_clears_task():
    """Test that stop() properly cancels and clears the task."""
    print("\nTesting stop clears task...")
    
    mock_pin = "GP10"
    buzzer = BuzzerManager(mock_pin)
    
    # Play a note
    buzzer.play_note(440)
    
    # Give time for task to start
    await asyncio.sleep(0.05)
    
    assert buzzer._current_task is not None, "Task should exist"
    
    # Stop should cancel and wait for the task
    await buzzer.stop()
    
    assert buzzer._current_task.done(), "Task should be done after stop"
    assert buzzer.buzzer.duty_cycle == 0, "Buzzer should be silent"
    
    print("✓ Stop clears task test passed")


def run_all_tests():
    """Run all buzzer manager tests."""
    print("="*60)
    print("Running BuzzerManager Tests (pwmio-based)")
    print("="*60)
    
    sync_tests = [
        test_buzzer_initialization,
        test_buzzer_volume_validation,
    ]
    
    async_tests = [
        test_buzzer_stop,
        test_play_note_with_duration,
        test_play_note_without_duration,
        test_play_sequence,
        test_play_sequence_with_rest,
        test_play_sequence_by_name,
        test_invalid_sequence_name,
        test_invalid_sequence_type,
        test_stop_clears_task,
    ]
    
    passed = 0
    failed = 0
    
    # Run sync tests
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
    
    # Run async tests
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
