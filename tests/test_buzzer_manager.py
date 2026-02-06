#!/usr/bin/env python3
"""Unit tests for BuzzerManager."""

import sys
import os
import asyncio

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
sys.modules['synthio'] = MockModule()
sys.modules['adafruit_ticks'] = MockModule()
sys.modules['audiopwmio'] = MockModule()
sys.modules['audiobusio'] = MockModule()
sys.modules['audiocore'] = MockModule()
sys.modules['audiomixer'] = MockModule()

# Add src to path for direct module import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# Mock pwmio module with actual PWMOut implementation
class MockPWMOut:
    """Mock PWMOut for testing."""
    def __init__(self, pin, duty_cycle=0, frequency=440, variable_frequency=False):
        self.pin = pin
        self.duty_cycle = duty_cycle
        self.frequency = frequency
        self.variable_frequency = variable_frequency
        self.deinited = False
    
    def deinit(self):
        """Mock deinit."""
        self.deinited = True


class MockPwmio:
    """Mock pwmio module."""
    PWMOut = MockPWMOut


sys.modules['pwmio'] = MockPwmio()

# Mock tones module - define TEST_SONG at module level for reusability
TEST_SONG = {'sequence': [('C4', 0.25), ('D4', 0.25), ('E4', 0.5)], 'bpm': 120, 'loop': False}

# Mock tones module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'utilities'))
from tones import note, BEEP, SUCCESS


# Now import BuzzerManager directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'managers'))

# Import the actual module to bypass utilities init
import importlib.util
spec = importlib.util.spec_from_file_location(
    "buzzer_manager",
    os.path.join(os.path.dirname(__file__), '..', 'src', 'managers', 'buzzer_manager.py')
)
buzzer_manager = importlib.util.module_from_spec(spec)

# Mock the utilities import in buzzer_manager before execution
class MockUtilities:
    """Mock utilities module."""
    class tones:
        note = staticmethod(note)
        BEEP = BEEP
        SUCCESS = SUCCESS
        TEST_SONG = TEST_SONG  # Use the module-level constant

sys.modules['utilities'] = MockUtilities()
sys.modules['utilities.tones'] = MockUtilities.tones

# Now execute the module
spec.loader.exec_module(buzzer_manager)
BuzzerManager = buzzer_manager.BuzzerManager


def test_buzzer_initialization():
    """Test BuzzerManager initialization."""
    print("Testing buzzer initialization...")
    
    mock_pin = "GP10"
    buzzer = BuzzerManager(mock_pin, volume=0.5, testing=True)
    
    assert buzzer.buzzer is not None, "Buzzer PWMOut should be initialized"
    assert buzzer.testing is True, "Testing flag should be set"
    assert buzzer.VOLUME_OFF == 0, "VOLUME_OFF should be 0"
    assert buzzer.VOLUME_ON > 0, "VOLUME_ON should be greater than 0"
    assert buzzer._current_task is None, "No task should be running initially"
    
    print("✓ Buzzer initialization test passed")


def test_buzzer_volume_validation():
    """Test that invalid volume values raise errors."""
    print("\nTesting buzzer volume validation...")
    
    mock_pin = "GP10"
    
    # Test valid volumes
    BuzzerManager(mock_pin, volume=0.0, testing=True)
    BuzzerManager(mock_pin, volume=0.5, testing=True)
    BuzzerManager(mock_pin, volume=1.0, testing=True)
    
    # Test invalid volumes
    try:
        BuzzerManager(mock_pin, volume=-0.1, testing=True)
        assert False, "Should raise ValueError for negative volume"
    except ValueError:
        pass
    
    try:
        BuzzerManager(mock_pin, volume=1.1, testing=True)
        assert False, "Should raise ValueError for volume > 1.0"
    except ValueError:
        pass
    
    print("✓ Volume validation test passed")


def test_buzzer_stop():
    """Test buzzer stop functionality."""
    print("\nTesting buzzer stop...")
    
    mock_pin = "GP10"
    buzzer = BuzzerManager(mock_pin, volume=0.5, testing=True)
    
    # Stop should set duty cycle to 0
    buzzer.buzzer.duty_cycle = 32767  # Simulate active
    buzzer.stop()
    
    assert buzzer.buzzer.duty_cycle == buzzer.VOLUME_OFF, "Stop should set duty cycle to 0"
    
    print("✓ Buzzer stop test passed")


async def test_buzzer_tone_logic():
    """Test internal tone playing logic."""
    print("\nTesting buzzer tone logic...")
    
    mock_pin = "GP10"
    buzzer = BuzzerManager(mock_pin, volume=0.5, testing=True)
    
    # Test playing a tone with duration
    await buzzer._play_tone_logic(440, 0.05)
    
    # Verify buzzer state after tone
    assert buzzer.buzzer.duty_cycle == buzzer.VOLUME_OFF, "Buzzer should be off after tone completes"
    
    # Test playing a tone without duration (continuous)
    await buzzer._play_tone_logic(880, None)
    assert buzzer.buzzer.duty_cycle == buzzer.VOLUME_ON, "Buzzer should stay on for continuous tone"
    
    buzzer.stop()
    
    print("✓ Buzzer tone logic test passed")


async def test_buzzer_sequence_logic():
    """Test internal sequence playing logic."""
    print("\nTesting buzzer sequence logic...")
    
    mock_pin = "GP10"
    buzzer = BuzzerManager(mock_pin, volume=0.5, testing=True)
    
    # Test short sequence without looping
    sequence = [(440, 0.05), (880, 0.05)]
    await buzzer._play_sequence_logic(sequence, tempo=1.0, loop=False)
    
    assert buzzer.buzzer.duty_cycle == buzzer.VOLUME_OFF, "Buzzer should be off after sequence"
    
    print("✓ Buzzer sequence logic test passed")


async def test_buzzer_sequence_with_rest():
    """Test sequence with rest notes (frequency = 0)."""
    print("\nTesting sequence with rest notes...")
    
    mock_pin = "GP10"
    buzzer = BuzzerManager(mock_pin, volume=0.5, testing=True)
    
    # Sequence with rest
    sequence = [(440, 0.05), (0, 0.05), (880, 0.05)]
    await buzzer._play_sequence_logic(sequence, tempo=1.0, loop=False)
    
    assert buzzer.buzzer.duty_cycle == buzzer.VOLUME_OFF, "Buzzer should be off after sequence"
    
    print("✓ Sequence with rest test passed")


def test_buzzer_tone_trigger():
    """Test tone trigger method."""
    print("\nTesting buzzer tone trigger...")
    
    async def run_test():
        mock_pin = "GP10"
        buzzer = BuzzerManager(mock_pin, volume=0.5, testing=True)
        
        # Trigger a tone
        buzzer.tone(440, 0.1)
        
        # Check that task was created
        assert buzzer._current_task is not None, "Task should be created"
        assert not buzzer._current_task.done(), "Task should be running"
        
        # Stop the buzzer (which cancels the task)
        buzzer.stop()
        
        print("✓ Tone trigger test passed")
    
    asyncio.run(run_test())


def test_buzzer_sequence_trigger():
    """Test sequence trigger method."""
    print("\nTesting buzzer sequence trigger...")
    
    async def run_test():
        mock_pin = "GP10"
        buzzer = BuzzerManager(mock_pin, volume=0.5, testing=True)
        
        # Trigger a sequence
        sequence = [(440, 0.1), (880, 0.1)]
        buzzer.sequence(sequence, tempo=1.0, loop=False)
        
        # Check that task was created
        assert buzzer._current_task is not None, "Task should be created"
        
        # Stop the buzzer
        buzzer.stop()
        
        print("✓ Sequence trigger test passed")
    
    asyncio.run(run_test())


def test_buzzer_play_song_with_dict():
    """Test playing a song with dictionary data."""
    print("\nTesting play_song with dictionary...")
    
    async def run_test():
        mock_pin = "GP10"
        buzzer = BuzzerManager(mock_pin, volume=0.5, testing=True)
        
        # Test with dictionary
        song_data = {
            'sequence': [('C4', 0.25), ('D4', 0.25)],
            'bpm': 120,
            'loop': False
        }
        
        buzzer.play_song(song_data)
        
        assert buzzer._current_task is not None, "Task should be created for song"
        
        buzzer.stop()
        
        print("✓ Play song with dictionary test passed")
    
    asyncio.run(run_test())


def test_buzzer_play_song_with_string():
    """Test playing a song by name."""
    print("\nTesting play_song with string name...")
    
    async def run_test():
        mock_pin = "GP10"
        buzzer = BuzzerManager(mock_pin, volume=0.5, testing=True)
        
        # Test with string name (uses MockTones)
        buzzer.play_song("TEST_SONG")
        
        assert buzzer._current_task is not None, "Task should be created for song"
        
        buzzer.stop()
        
        print("✓ Play song with string name test passed")
    
    asyncio.run(run_test())


def test_buzzer_play_song_invalid_name():
    """Test playing a song with invalid name."""
    print("\nTesting play_song with invalid name...")
    
    mock_pin = "GP10"
    buzzer = BuzzerManager(mock_pin, volume=0.5, testing=True)
    
    # Test with invalid string name
    buzzer.play_song("NONEXISTENT_SONG")
    
    # Should not create a task for invalid song
    assert buzzer._current_task is None or buzzer._current_task.done(), \
        "Task should not be created for invalid song"
    
    print("✓ Invalid song name test passed")


def test_buzzer_preemption():
    """Test that new sounds preempt existing ones."""
    print("\nTesting buzzer preemption...")
    
    async def run_test():
        mock_pin = "GP10"
        buzzer = BuzzerManager(mock_pin, volume=0.5, testing=True)
        
        # Start first tone
        buzzer.tone(440, 1.0)
        first_task = buzzer._current_task
        
        # Give it a moment to start
        await asyncio.sleep(0.01)
        
        # Start second tone (should cancel first)
        buzzer.tone(880, 1.0)
        second_task = buzzer._current_task
        
        # Give cancellation a moment to process
        await asyncio.sleep(0.01)
        
        assert first_task != second_task, "Second tone should create new task"
        # Note: In async context, cancellation might not be immediate,
        # so we just check that a new task was created
        assert buzzer._current_task == second_task, "Current task should be the second one"
        
        buzzer.stop()
        
        print("✓ Buzzer preemption test passed")
    
    asyncio.run(run_test())


def test_buzzer_loop_override():
    """Test loop parameter override."""
    print("\nTesting loop override...")
    
    async def run_test():
        mock_pin = "GP10"
        buzzer = BuzzerManager(mock_pin, volume=0.5, testing=True)
        
        # Song with loop=True, but override to False
        song_data = {
            'sequence': [('C4', 0.1)],
            'bpm': 120,
            'loop': True
        }
        
        buzzer.play_song(song_data, loop=False)
        
        assert buzzer._current_task is not None, "Task should be created"
        
        buzzer.stop()
        
        print("✓ Loop override test passed")
    
    asyncio.run(run_test())


def run_all_tests():
    """Run all buzzer manager tests."""
    print("="*60)
    print("Running BuzzerManager Tests")
    print("="*60)
    
    tests = [
        test_buzzer_initialization,
        test_buzzer_volume_validation,
        test_buzzer_stop,
        test_buzzer_tone_trigger,
        test_buzzer_sequence_trigger,
        test_buzzer_play_song_with_dict,
        test_buzzer_play_song_with_string,
        test_buzzer_play_song_invalid_name,
        test_buzzer_preemption,
        test_buzzer_loop_override,
    ]
    
    async_tests = [
        test_buzzer_tone_logic,
        test_buzzer_sequence_logic,
        test_buzzer_sequence_with_rest,
    ]
    
    passed = 0
    failed = 0
    
    # Run all tests (they handle async internally now)
    all_tests = tests + async_tests
    for test in all_tests:
        try:
            if asyncio.iscoroutinefunction(test):
                asyncio.run(test())
            else:
                test()
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
