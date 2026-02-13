#!/usr/bin/env python3
"""Unit tests for BuzzerManager (synthio-based implementation)."""

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
sys.modules['analogio'] = MockModule()
sys.modules['microcontroller'] = MockModule()
sys.modules['storage'] = MockModule()
sys.modules['supervisor'] = MockModule()

# Add src to path for direct module import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# Mock synthio with tracking
class MockNote:
    """Mock synthio.Note object."""
    def __init__(self, frequency, waveform=None, envelope=None):
        self.frequency = frequency
        self.waveform = waveform
        self.envelope = envelope


class MockSynthesizer:
    """Mock synthio.Synthesizer."""
    def __init__(self, sample_rate=22050, channel_count=1):
        self.sample_rate = sample_rate
        self.channel_count = channel_count
        self.pressed_notes = []
        self.released_notes = []
    
    def press(self, note):
        """Track pressed notes."""
        self.pressed_notes.append(note)
    
    def release(self, note):
        """Track released notes."""
        self.released_notes.append(note)
    
    def release_all(self):
        """Release all notes."""
        self.released_notes.extend(self.pressed_notes)
        self.pressed_notes.clear()


class MockSynthio:
    """Mock synthio module."""
    Note = MockNote
    Synthesizer = MockSynthesizer
    
    class Envelope:
        """Mock synthio.Envelope."""
        def __init__(self, attack_time=0, decay_time=0, release_time=0,
                     attack_level=1, sustain_level=1):
            self.attack_time = attack_time
            self.decay_time = decay_time
            self.release_time = release_time
            self.attack_level = attack_level
            self.sustain_level = sustain_level


sys.modules['synthio'] = MockSynthio()


# Mock audiopwmio
class MockPWMAudioOut:
    """Mock PWMAudioOut."""
    def __init__(self, pin):
        self.pin = pin
        self.playing = None
    
    def play(self, source):
        """Mock play method."""
        self.playing = source


class MockAudioPwmio:
    """Mock audiopwmio module."""
    PWMAudioOut = MockPWMAudioOut


sys.modules['audiopwmio'] = MockAudioPwmio()

# Now import the modules we need to test - use direct import to avoid managers.__init__.py
import importlib.util

# Import synth_manager directly
synth_spec = importlib.util.spec_from_file_location(
    "synth_manager",
    os.path.join(os.path.dirname(__file__), '..', 'src', 'managers', 'synth_manager.py')
)
synth_manager_module = importlib.util.module_from_spec(synth_spec)
sys.modules['managers.synth_manager'] = synth_manager_module
synth_spec.loader.exec_module(synth_manager_module)
SynthManager = synth_manager_module.SynthManager

# Import buzzer_manager directly
buzzer_spec = importlib.util.spec_from_file_location(
    "buzzer_manager",
    os.path.join(os.path.dirname(__file__), '..', 'src', 'managers', 'buzzer_manager.py')
)
buzzer_manager_module = importlib.util.module_from_spec(buzzer_spec)
buzzer_spec.loader.exec_module(buzzer_manager_module)
BuzzerManager = buzzer_manager_module.BuzzerManager


def test_buzzer_initialization():
    """Test BuzzerManager initialization."""
    print("Testing buzzer initialization...")
    
    mock_pin = "GP10"
    buzzer = BuzzerManager(mock_pin)
    
    assert buzzer.audio is not None, "Audio output should be initialized"
    assert buzzer.engine is not None, "SynthManager should be initialized"
    assert isinstance(buzzer.engine, SynthManager), "Engine should be a SynthManager"
    
    print("✓ Buzzer initialization test passed")


def test_buzzer_stop():
    """Test buzzer stop functionality."""
    print("\nTesting buzzer stop...")
    
    async def run_test():
        mock_pin = "GP10"
        buzzer = BuzzerManager(mock_pin)
        
        # Play a note
        buzzer.play_note(440, duration=1.0)
        
        # Stop should release all notes
        await buzzer.stop()
        
        # Verify notes were released
        synth = buzzer.engine.synth
        assert len(synth.pressed_notes) == 0 or len(synth.released_notes) > 0, \
            "Stop should release notes"
        
        print("✓ Buzzer stop test passed")
    
    asyncio.run(run_test())


def test_play_note_basic():
    """Test playing a single note."""
    print("\nTesting play_note basic...")
    
    mock_pin = "GP10"
    buzzer = BuzzerManager(mock_pin)
    
    # Play a note (non-blocking)
    buzzer.play_note(440)
    
    # Verify a note was pressed
    synth = buzzer.engine.synth
    assert len(synth.pressed_notes) > 0, "Note should be pressed"
    assert synth.pressed_notes[0].frequency == 440, "Frequency should match"
    
    print("✓ Play note basic test passed")


def test_play_note_with_duration():
    """Test playing a note with auto-release duration."""
    print("\nTesting play_note with duration...")
    
    async def run_test():
        mock_pin = "GP10"
        buzzer = BuzzerManager(mock_pin)
        
        # Play a note with duration (creates async task)
        buzzer.play_note(880, duration=0.1)
        
        # Verify note was pressed
        synth = buzzer.engine.synth
        assert len(synth.pressed_notes) > 0, "Note should be pressed"
        
        # Wait for auto-release
        await asyncio.sleep(0.15)
        
        # Note should be released
        assert len(synth.released_notes) > 0, "Note should be auto-released"
        
        print("✓ Play note with duration test passed")
    
    asyncio.run(run_test())


@pytest.mark.asyncio
async def test_play_sequence():
    """Test playing a sequence of notes."""
    print("\nTesting play_sequence...")
    
    mock_pin = "GP10"
    buzzer = BuzzerManager(mock_pin)
    
    # Create a simple sequence
    sequence_data = {
        'bpm': 120,
        'sequence': [('C4', 0.1), ('D4', 0.1), ('E4', 0.1)]
    }
    
    # Play sequence (should be async)
    await buzzer.play_sequence(sequence_data)
    
    # Verify notes were played
    synth = buzzer.engine.synth
    # At least some notes should have been pressed and released
    assert len(synth.pressed_notes) > 0, "Notes should have been pressed"
    assert len(synth.released_notes) > 0, "Notes should have been released"
    
    print("✓ Play sequence test passed")


@pytest.mark.asyncio
async def test_stop_is_async():
    """Test that stop() can be awaited."""
    print("\nTesting stop is async...")
    
    mock_pin = "GP10"
    buzzer = BuzzerManager(mock_pin)
    
    # This should not raise an error
    await buzzer.stop()
    
    print("✓ Stop is async test passed")


def test_engine_uses_square_wave():
    """Test that buzzer uses square wave by default."""
    print("\nTesting engine uses square wave...")
    
    from utilities.synth_registry import Waveforms
    
    mock_pin = "GP10"
    buzzer = BuzzerManager(mock_pin)
    
    # Check that override was set to SQUARE
    assert buzzer.engine.override == Waveforms.SQUARE, \
        "Buzzer should use square wave"
    
    print("✓ Engine uses square wave test passed")


def run_all_tests():
    """Run all buzzer manager tests."""
    print("="*60)
    print("Running BuzzerManager Tests (synthio-based)")
    print("="*60)
    
    sync_tests = [
        test_buzzer_initialization,
        test_buzzer_stop,
        test_play_note_basic,
        test_play_note_with_duration,
        test_engine_uses_square_wave,
    ]
    
    async_tests = [
        test_play_sequence,
        test_stop_is_async,
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
