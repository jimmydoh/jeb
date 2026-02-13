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
sys.modules['watchdog'] = MockModule()
sys.modules['storage'] = MockModule()

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# Mock synthio module with actual implementation for testing
class MockNote:
    """Mock synthio.Note."""
    def __init__(self, frequency, waveform=None, envelope=None):
        self.frequency = frequency
        self.waveform = waveform
        self.envelope = envelope


class MockEnvelope:
    """Mock synthio.Envelope."""
    def __init__(self, attack_time=0, decay_time=0, release_time=0, 
                 attack_level=1.0, sustain_level=1.0):
        self.attack_time = attack_time
        self.decay_time = decay_time
        self.release_time = release_time
        self.attack_level = attack_level
        self.sustain_level = sustain_level


class MockSynthesizer:
    """Mock synthio.Synthesizer."""
    def __init__(self, sample_rate=22050, channel_count=None):
        self.sample_rate = sample_rate
        self.channel_count = channel_count
        self.pressed_notes = []
        self.released_notes = []
    
    def press(self, note):
        """Mock press."""
        self.pressed_notes.append(note)
    
    def release(self, note):
        """Mock release."""
        self.released_notes.append(note)
    
    def release_all(self):
        """Mock release_all."""
        self.pressed_notes.clear()
        self.released_notes.clear()


class MockSynthio:
    """Mock synthio module."""
    Note = MockNote
    Envelope = MockEnvelope
    Synthesizer = MockSynthesizer


sys.modules['synthio'] = MockSynthio()


# Mock audiopwmio module
class MockPWMAudioOut:
    """Mock audiopwmio.PWMAudioOut."""
    def __init__(self, pin):
        self.pin = pin
        self.playing_source = None
    
    def play(self, source):
        """Mock play."""
        self.playing_source = source


class MockAudiopwmio:
    """Mock audiopwmio module."""
    PWMAudioOut = MockPWMAudioOut


sys.modules['audiopwmio'] = MockAudiopwmio()


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
    
    assert buzzer.audio is not None, "Audio output should be initialized"
    assert buzzer.engine is not None, "Synth engine should be initialized"
    assert buzzer.audio.playing_source == buzzer.engine.source, "Audio should be playing synth source"
    
    print("✓ Buzzer initialization test passed")


def test_buzzer_stop():
    """Test buzzer stop functionality."""
    print("\nTesting buzzer stop...")
    
    mock_pin = "GP10"
    buzzer = BuzzerManager(mock_pin)
    
    # Simulate some notes playing
    buzzer.engine.synth.press(MockNote(440))
    buzzer.engine.synth.press(MockNote(880))
    
    assert len(buzzer.engine.synth.pressed_notes) == 2, "Should have 2 pressed notes"
    
    # Stop should release all notes
    buzzer.stop()
    
    assert len(buzzer.engine.synth.pressed_notes) == 0, "Stop should clear all pressed notes"
    
    print("✓ Buzzer stop test passed")


def test_play_note_without_duration():
    """Test playing a continuous note without duration."""
    print("\nTesting play_note without duration...")
    
    mock_pin = "GP10"
    buzzer = BuzzerManager(mock_pin)
    
    # Play a note without duration (continuous)
    buzzer.play_note(440, duration=None)
    
    # Verify note was pressed in the synth engine
    assert len(buzzer.engine.synth.pressed_notes) == 1, "Should have 1 pressed note"
    assert buzzer.engine.synth.pressed_notes[0].frequency == 440, "Note frequency should be 440"
    
    print("✓ Play note without duration test passed")


@pytest.mark.asyncio
async def test_play_note_with_duration():
    """Test playing a note with auto-release duration."""
    print("\nTesting play_note with duration...")
    
    mock_pin = "GP10"
    buzzer = BuzzerManager(mock_pin)
    
    # Play a note with duration (auto-release)
    buzzer.play_note(880, duration=0.05)
    
    # Verify note was pressed
    assert len(buzzer.engine.synth.pressed_notes) == 1, "Should have 1 pressed note"
    
    # Wait for auto-release
    await asyncio.sleep(0.1)
    
    assert len(buzzer.engine.synth.released_notes) == 1, "Note should be auto-released"
    
    print("✓ Play note with duration test passed")


@pytest.mark.asyncio
async def test_play_sequence():
    """Test playing a sequence of notes."""
    print("\nTesting play_sequence...")
    
    mock_pin = "GP10"
    buzzer = BuzzerManager(mock_pin)
    
    # Create a simple sequence
    sequence_data = {
        'bpm': 240,  # Fast tempo for testing
        'sequence': [
            ('C4', 0.1),
            ('D4', 0.1),
            ('E4', 0.1)
        ]
    }
    
    # Note: BuzzerManager.play_sequence doesn't await, so we call the engine directly
    # This is testing the underlying implementation
    await buzzer.engine.play_sequence(sequence_data)
    
    # Should have pressed notes
    assert len(buzzer.engine.synth.pressed_notes) > 0, "Should have pressed notes during sequence"
    
    # Should have released notes
    assert len(buzzer.engine.synth.released_notes) > 0, "Should have released notes after sequence"
    
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
            (0, 0.1),  # Rest
            ('E4', 0.1)
        ]
    }
    
    # Call the engine directly since BuzzerManager.play_sequence doesn't await
    await buzzer.engine.play_sequence(sequence_data)
    
    # Should have played and released notes (but not the rest)
    assert len(buzzer.engine.synth.pressed_notes) == 2, "Should have pressed 2 notes (skipping rest)"
    assert len(buzzer.engine.synth.released_notes) == 2, "Should have released 2 notes"
    
    print("✓ Sequence with rest test passed")


@pytest.mark.asyncio
async def test_multiple_notes_overlap():
    """Test that multiple notes can be played simultaneously."""
    print("\nTesting multiple overlapping notes...")
    
    mock_pin = "GP10"
    buzzer = BuzzerManager(mock_pin)
    
    # Play multiple notes with long duration
    buzzer.play_note(440, duration=1.0)
    buzzer.play_note(554, duration=1.0)
    buzzer.play_note(659, duration=1.0)
    
    # Give them time to start
    await asyncio.sleep(0.05)
    
    assert len(buzzer.engine.synth.pressed_notes) == 3, "Should have 3 simultaneous notes"
    
    # Clean up
    buzzer.stop()
    
    print("✓ Multiple overlapping notes test passed")


def test_stop_clears_all_notes():
    """Test that stop() releases all playing notes."""
    print("\nTesting stop clears all notes...")
    
    mock_pin = "GP10"
    buzzer = BuzzerManager(mock_pin)
    
    # Play multiple notes
    buzzer.play_note(440)
    buzzer.play_note(554)
    buzzer.play_note(659)
    
    assert len(buzzer.engine.synth.pressed_notes) == 3, "Should have 3 pressed notes"
    
    # Stop should clear everything
    buzzer.stop()
    
    assert len(buzzer.engine.synth.pressed_notes) == 0, "Stop should clear all pressed notes"
    assert len(buzzer.engine.synth.released_notes) == 0, "Stop should clear released notes tracking"
    
    print("✓ Stop clears all notes test passed")


def run_all_tests():
    """Run all buzzer manager tests."""
    print("="*60)
    print("Running BuzzerManager Tests (synthio-based)")
    print("="*60)
    
    sync_tests = [
        test_buzzer_initialization,
        test_buzzer_stop,
        test_play_note_without_duration,
        test_stop_clears_all_notes,
    ]
    
    async_tests = [
        test_play_note_with_duration,
        test_play_sequence,
        test_play_sequence_with_rest,
        test_multiple_notes_overlap,
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
