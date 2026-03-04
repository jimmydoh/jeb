#!/usr/bin/env python3
"""Unit tests for SynthManager (synthio-based implementation)."""

import sys
import os
import asyncio
import pytest
from unittest import mock

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
sys.modules['pwmio'] = MockModule()


# --- Mock synthio module with specific classes ---

class MockEnvelope:
    """Mock for synthio.Envelope."""
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class MockNote:
    """Mock for synthio.Note."""
    def __init__(self, frequency, waveform=None, envelope=None):
        self.frequency = frequency
        self.waveform = waveform
        self.envelope = envelope
        self.released = False


class MockSynthesizer:
    """Mock for synthio.Synthesizer."""
    def __init__(self, sample_rate=22050, channel_count=1):
        self.sample_rate = sample_rate
        self.channel_count = channel_count
        self.pressed_notes = []
        self.released_notes = []

    def press(self, note):
        self.pressed_notes.append(note)

    def release(self, note):
        self.released_notes.append(note)
        note.released = True

    def release_all(self):
        self.pressed_notes.clear()


class MockSynthio:
    """Mock for the synthio module."""
    Note = MockNote
    Synthesizer = MockSynthesizer
    Envelope = MockEnvelope


sys.modules['synthio'] = MockSynthio()

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import packages first to establish them as packages
import utilities
import utilities.synth_registry
import managers

# Import SynthManager directly using importlib to bypass managers/__init__.py
import importlib.util
spec = importlib.util.spec_from_file_location(
    "synth_manager",
    os.path.join(os.path.dirname(__file__), '..', 'src', 'managers', 'synth_manager.py')
)
synth_manager_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(synth_manager_module)
SynthManager = synth_manager_module.SynthManager


# ---------------------------------------------------------------------------
# Sync Tests
# ---------------------------------------------------------------------------

def test_synth_initialization():
    """Test SynthManager initialization with default params."""
    print("Testing SynthManager initialization...")

    synth = SynthManager()

    assert synth.synth is not None, "Synthesizer should be initialized"
    assert isinstance(synth.synth, MockSynthesizer), "synth should be a MockSynthesizer"
    assert synth.synth.sample_rate == 22050, "Default sample_rate should be 22050"
    assert synth.synth.channel_count == 1, "Default channel_count should be 1"
    assert synth._chiptune_task is None, "_chiptune_task should be None after init"
    assert synth.override is None, "override should be None by default"

    print("✓ SynthManager initialization test passed")


def test_synth_initialization_custom_params():
    """Test SynthManager initialization with custom params."""
    print("\nTesting SynthManager initialization with custom params...")

    fake_waveform = [0, 1, 2, 3]
    synth = SynthManager(sample_rate=44100, channel_count=2, waveform_override=fake_waveform)

    assert synth.synth.sample_rate == 44100, "sample_rate should be 44100"
    assert synth.synth.channel_count == 2, "channel_count should be 2"
    assert synth.override == fake_waveform, "override should match provided waveform"
    assert synth._chiptune_task is None, "_chiptune_task should be None after init"

    print("✓ Custom params initialization test passed")


def test_synth_source_property():
    """Test that source property returns the synth object."""
    print("\nTesting source property...")

    synth = SynthManager()
    assert synth.source is synth.synth, "source property should return synth object"

    print("✓ Source property test passed")


def test_play_note_returns_note_object():
    """Test that play_note returns a note object."""
    print("\nTesting play_note returns a note object...")

    synth = SynthManager()
    n = synth.play_note(440.0)

    assert n is not None, "play_note should return a note object"
    assert isinstance(n, MockNote), "returned note should be a MockNote"
    assert n.frequency == 440.0, "note frequency should match"

    print("✓ play_note returns note object test passed")


def test_play_note_uses_select_patch_as_fallback():
    """Test that play_note uses Patches.SELECT as fallback when patch=None."""
    print("\nTesting play_note uses Patches.SELECT as fallback...")

    from utilities.synth_registry import Patches

    synth = SynthManager()
    n = synth.play_note(440.0, patch=None)

    # The note should have been created with Patches.SELECT's wave and envelope
    assert n.waveform == Patches.SELECT["wave"], "should use SELECT patch's waveform"
    assert n.envelope == Patches.SELECT["envelope"], "should use SELECT patch's envelope"

    print("✓ play_note fallback to Patches.SELECT test passed")


def test_play_note_with_explicit_patch():
    """Test that play_note uses provided patch."""
    print("\nTesting play_note with explicit patch...")

    from utilities.synth_registry import Patches

    synth = SynthManager()
    n = synth.play_note(880.0, patch=Patches.BEEP)

    assert n.waveform == Patches.BEEP["wave"], "should use BEEP patch's waveform"
    assert n.envelope == Patches.BEEP["envelope"], "should use BEEP patch's envelope"

    print("✓ play_note with explicit patch test passed")


def test_play_note_presses_synth():
    """Test that play_note presses the note on the synthesizer."""
    print("\nTesting play_note presses note on synth...")

    synth = SynthManager()
    n = synth.play_note(440.0)

    assert n in synth.synth.pressed_notes, "note should be in pressed_notes after play_note"

    print("✓ play_note presses synth test passed")


def test_stop_note():
    """Test that stop_note releases a pressed note."""
    print("\nTesting stop_note...")

    synth = SynthManager()
    n = synth.play_note(440.0)
    assert n in synth.synth.pressed_notes, "note should be pressed"

    synth.stop_note(n)
    assert n in synth.synth.released_notes, "note should appear in released_notes after stop_note"

    print("✓ stop_note test passed")


def test_release_all():
    """Test that release_all stops all notes."""
    print("\nTesting release_all...")

    synth = SynthManager()
    synth.play_note(261.63)  # C4
    synth.play_note(329.63)  # E4
    synth.play_note(392.00)  # G4

    assert len(synth.synth.pressed_notes) == 3, "Three notes should be pressed"

    synth.release_all()

    assert len(synth.synth.pressed_notes) == 0, "All notes should be released after release_all"

    print("✓ release_all test passed")


# ---------------------------------------------------------------------------
# Async Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_chiptune_sequencer_returns_task():
    """Test that start_chiptune_sequencer returns a running asyncio Task."""
    print("\nTesting start_chiptune_sequencer returns task...")

    synth = SynthManager()
    channels = {
        'melody': {
            'bpm': 240,
            'sequence': [('C4', 1)]
        }
    }

    task = synth.start_chiptune_sequencer(channels)

    assert task is not None, "start_chiptune_sequencer should return a task"
    assert isinstance(task, asyncio.Task), "returned value should be an asyncio.Task"
    assert not task.done(), "task should be running"

    # Clean up
    synth.stop_chiptune()
    await asyncio.sleep(0)  # Let cancellation process

    print("✓ start_chiptune_sequencer returns task test passed")


@pytest.mark.asyncio
async def test_start_chiptune_sequencer_sets_task_attribute():
    """Test that start_chiptune_sequencer sets _chiptune_task attribute."""
    print("\nTesting start_chiptune_sequencer sets _chiptune_task...")

    synth = SynthManager()
    assert synth._chiptune_task is None, "_chiptune_task should start as None"

    channels = {
        'bass': {
            'bpm': 240,
            'sequence': [('C3', 1)]
        }
    }

    task = synth.start_chiptune_sequencer(channels)
    assert synth._chiptune_task is task, "_chiptune_task should be set to the returned task"

    # Clean up
    synth.stop_chiptune()
    await asyncio.sleep(0)

    print("✓ start_chiptune_sequencer sets _chiptune_task test passed")


@pytest.mark.asyncio
async def test_start_chiptune_sequencer_accepts_all_channels():
    """Test start_chiptune_sequencer with melody, bass, and noise channels."""
    print("\nTesting start_chiptune_sequencer with all channels...")

    synth = SynthManager()
    channels = {
        'melody': {
            'bpm': 240,
            'sequence': [('C4', 1)]
        },
        'bass': {
            'bpm': 240,
            'sequence': [('C3', 1)]
        },
        'noise': {
            'bpm': 240,
            'sequence': [('C4', 1)]
        }
    }

    task = synth.start_chiptune_sequencer(channels)

    assert task is not None, "Task should be created"
    assert isinstance(task, asyncio.Task), "Should be an asyncio.Task"
    assert not task.done(), "Task should be running"

    # Clean up
    synth.stop_chiptune()
    await asyncio.sleep(0)

    print("✓ start_chiptune_sequencer with all channels test passed")


@pytest.mark.asyncio
async def test_stop_chiptune_cancels_task():
    """Test that stop_chiptune cancels the running task."""
    print("\nTesting stop_chiptune cancels task...")

    synth = SynthManager()
    channels = {
        'melody': {
            'bpm': 240,
            'sequence': [('C4', 1)]
        }
    }

    task = synth.start_chiptune_sequencer(channels)
    assert not task.done(), "Task should be running before stop"

    synth.stop_chiptune()

    # Allow event loop to process the cancellation
    await asyncio.sleep(0)

    assert task.cancelled() or task.done(), "Task should be cancelled after stop_chiptune"

    print("✓ stop_chiptune cancels task test passed")


@pytest.mark.asyncio
async def test_stop_chiptune_clears_task_attribute():
    """Test that stop_chiptune clears _chiptune_task to None."""
    print("\nTesting stop_chiptune clears _chiptune_task...")

    synth = SynthManager()
    channels = {
        'melody': {
            'bpm': 240,
            'sequence': [('C4', 1)]
        }
    }

    synth.start_chiptune_sequencer(channels)
    assert synth._chiptune_task is not None, "_chiptune_task should be set"

    synth.stop_chiptune()

    assert synth._chiptune_task is None, "_chiptune_task should be None after stop_chiptune"
    await asyncio.sleep(0)

    print("✓ stop_chiptune clears _chiptune_task test passed")


@pytest.mark.asyncio
async def test_stop_chiptune_calls_release_all():
    """Test that stop_chiptune calls release_all to silence all active notes."""
    print("\nTesting stop_chiptune calls release_all...")

    synth = SynthManager()

    # Manually press some notes
    synth.play_note(261.63)  # C4
    synth.play_note(329.63)  # E4
    assert len(synth.synth.pressed_notes) == 2, "Notes should be pressed before stop"

    # Start and immediately stop chiptune
    channels = {
        'melody': {
            'bpm': 240,
            'sequence': [('C4', 1)]
        }
    }
    synth.start_chiptune_sequencer(channels)
    synth.stop_chiptune()

    assert len(synth.synth.pressed_notes) == 0, "All notes should be released after stop_chiptune"
    await asyncio.sleep(0)

    print("✓ stop_chiptune calls release_all test passed")


@pytest.mark.asyncio
async def test_stop_chiptune_when_no_task():
    """Test that stop_chiptune handles gracefully when no task is running."""
    print("\nTesting stop_chiptune with no running task...")

    synth = SynthManager()
    assert synth._chiptune_task is None, "Should start with no task"

    # Should not raise any error
    synth.stop_chiptune()
    assert synth._chiptune_task is None, "_chiptune_task should remain None"
    await asyncio.sleep(0)

    print("✓ stop_chiptune with no task test passed")


@pytest.mark.asyncio
async def test_start_generative_drone_calls_play_note_with_dict_patch():
    """Test that start_generative_drone calls play_note with a dict patch (not a string).

    This validates the bug fix ensuring Patches.ENGINE_HUM (a dict) is passed
    to play_note rather than a plain string. The drone should always call
    play_note with a dict containing 'wave' and 'envelope' keys.
    """
    print("\nTesting start_generative_drone calls play_note with dict patch...")

    synth = SynthManager()
    play_note_calls = []

    # Spy on play_note to capture arguments without replacing its behavior
    original_play_note = synth.play_note

    def spy_play_note(frequency, patch=None, duration=None):
        play_note_calls.append({'frequency': frequency, 'patch': patch, 'duration': duration})
        return original_play_note(frequency, patch=patch, duration=duration)

    synth.play_note = spy_play_note

    # Start the infinite drone and let it run through at least one iteration.
    # The drone calls play_note *before* its first asyncio.sleep, so a single
    # yield to the event loop is enough to guarantee one call.
    # Note: behavior verified for both CPython and CircuitPython event loops.
    drone_task = asyncio.create_task(synth.start_generative_drone())
    await asyncio.sleep(0.01)  # Yield to event loop; drone runs to first await

    # Cancel the infinite loop
    drone_task.cancel()
    try:
        await drone_task
    except asyncio.CancelledError:
        pass

    assert len(play_note_calls) >= 1, "play_note should have been called at least once"

    for call in play_note_calls:
        patch_arg = call['patch']
        assert isinstance(patch_arg, dict), (
            f"play_note should be called with a dict patch, "
            f"got {type(patch_arg).__name__}: {patch_arg!r}"
        )
        assert "wave" in patch_arg, "patch dict should have a 'wave' key"
        assert "envelope" in patch_arg, "patch dict should have an 'envelope' key"

    print("✓ start_generative_drone uses dict patch test passed")


# ---------------------------------------------------------------------------
# JSEQ and preview_channels Tests
# ---------------------------------------------------------------------------

def test_jseq_patch_names_list():
    """Test that JSEQ_PATCH_NAMES is a non-empty list of valid Patches names."""
    print("\nTesting JSEQ_PATCH_NAMES list...")

    from utilities.synth_registry import Patches

    assert isinstance(synth_manager_module.JSEQ_PATCH_NAMES, list), "JSEQ_PATCH_NAMES should be a list"
    assert len(synth_manager_module.JSEQ_PATCH_NAMES) > 0, "JSEQ_PATCH_NAMES should not be empty"
    for name in synth_manager_module.JSEQ_PATCH_NAMES:
        assert hasattr(Patches, name), f"Patches should have attribute '{name}'"

    print("✓ JSEQ_PATCH_NAMES test passed")


def test_jseq_midi_to_freq():
    """Test _jseq_midi_to_freq converts MIDI note 69 to A4=440Hz."""
    print("\nTesting _jseq_midi_to_freq...")

    freq = synth_manager_module._jseq_midi_to_freq(69)
    assert abs(freq - 440.0) < 0.01, f"MIDI 69 should be 440 Hz, got {freq}"

    # C4 = MIDI 60
    freq_c4 = synth_manager_module._jseq_midi_to_freq(60)
    assert abs(freq_c4 - 261.63) < 0.5, f"MIDI 60 should be ~261.63 Hz, got {freq_c4}"

    print("✓ _jseq_midi_to_freq test passed")


def test_load_jseq_invalid_magic():
    """Test that load_jseq raises ValueError for invalid magic bytes."""
    print("\nTesting load_jseq with invalid magic bytes...")

    import io
    import builtins

    synth = SynthManager()

    invalid_data = b'NOPE\x01\x78\x00\x01' + b'\x00\x01\x00' + b'\x00\x08'

    original_open = builtins.open

    def mock_open(path, mode='r', *args, **kwargs):
        return io.BytesIO(invalid_data)

    builtins.open = mock_open
    try:
        raised = False
        try:
            synth.load_jseq('/sd/sequences/test.jseq')
        except ValueError:
            raised = True
        assert raised, "load_jseq should raise ValueError for invalid magic"
    finally:
        builtins.open = original_open

    print("✓ load_jseq invalid magic test passed")


def test_load_jseq_valid_file():
    """Test that load_jseq correctly parses a valid .jseq binary file."""
    print("\nTesting load_jseq with valid binary data...")

    import io
    import struct
    import builtins

    synth = SynthManager()

    # Build a minimal valid .jseq: 1 channel, 2 notes, BPM=120
    # Header: JSEQ + version + BPM LE + channel_count
    bpm = 120
    num_channels = 1
    patch_idx = 0   # RETRO_LEAD
    notes = [(62, 32), (0, 8)]  # note_idx 62 → MIDI 61 = C#4, quarter note; then rest, sixteenth

    header = b'JSEQ'
    header += bytes([1])               # version
    header += struct.pack('<H', bpm)   # BPM little-endian
    header += bytes([num_channels])

    channel_data = bytes([patch_idx])
    channel_data += struct.pack('<H', len(notes))
    for note_idx, dur_units in notes:
        channel_data += bytes([note_idx, dur_units])

    data = header + channel_data

    original_open = builtins.open

    def mock_open(path, mode='r', *args, **kwargs):
        return io.BytesIO(data)

    builtins.open = mock_open
    try:
        channels = synth.load_jseq('/sd/sequences/test.jseq')
    finally:
        builtins.open = original_open

    assert len(channels) == 1, f"Should have 1 channel, got {len(channels)}"
    ch = channels[0]
    assert ch['bpm'] == bpm, f"BPM should be {bpm}, got {ch['bpm']}"
    assert len(ch['sequence']) == len(notes), "Sequence length mismatch"

    # First note: note_idx 62 → MIDI note 61 (C#4) → freq = 440 * 2^((61-69)/12)
    expected_freq = 440.0 * (2.0 ** ((61 - 69) / 12.0))
    assert abs(ch['sequence'][0][0] - expected_freq) < 0.01, "Frequency mismatch for MIDI 61"

    # Second note: rest -> freq = 0
    assert ch['sequence'][1][0] == 0, "Rest should have frequency 0"

    # Duration: 32 units / 32 = 1.0 beats (quarter note)
    assert abs(ch['sequence'][0][1] - 1.0) < 0.01, "Duration of first note should be 1.0 beats"

    print("✓ load_jseq valid file test passed")


@pytest.mark.asyncio
async def test_preview_channels_creates_task():
    """Test that preview_channels creates and returns an asyncio Task."""
    print("\nTesting preview_channels creates task...")

    from utilities.synth_registry import Patches

    synth = SynthManager()

    channels_data = [
        {'bpm': 120, 'patch': 'RETRO_LEAD', 'sequence': [('C4', 0.25)]},
        {'bpm': 120, 'patch': Patches.BEEP, 'sequence': [('E4', 0.25)]},
    ]

    task = synth.preview_channels(channels_data)

    assert task is not None, "preview_channels should return a task"
    assert isinstance(task, asyncio.Task), "returned value should be an asyncio.Task"
    assert synth._chiptune_task is task, "_chiptune_task should be set to the returned task"

    synth.stop_chiptune()
    await asyncio.sleep(0)

    print("✓ preview_channels creates task test passed")


@pytest.mark.asyncio
async def test_preview_channels_resolves_string_patch():
    """Test that preview_channels resolves string patch names to Patches dicts."""
    print("\nTesting preview_channels resolves string patch names...")

    from utilities.synth_registry import Patches

    synth = SynthManager()
    pressed_patches = []

    original_play_sequence = synth.play_sequence

    async def spy_play_sequence(sequence_data, patch=None):
        pressed_patches.append(sequence_data.get('patch'))
        # Don't await the real sequence (takes time); just return
        return

    synth.play_sequence = spy_play_sequence

    channels_data = [
        {'bpm': 120, 'patch': 'BEEP', 'sequence': [('C4', 0.25)]},
    ]

    task = synth.preview_channels(channels_data)
    await asyncio.sleep(0.05)
    synth.stop_chiptune()
    await asyncio.sleep(0)

    # The patch should have been resolved from string 'BEEP' to Patches.BEEP dict
    assert len(pressed_patches) >= 1, "play_sequence should have been called"
    for p in pressed_patches:
        if p is not None:
            assert isinstance(p, dict), f"Patch should be resolved to dict, got {type(p)}"
            assert 'wave' in p, "Resolved patch should have 'wave' key"

    print("✓ preview_channels resolves string patch test passed")

def run_all_tests():
    """Run all SynthManager tests."""
    print("=" * 60)
    print("Running SynthManager Tests")
    print("=" * 60)

    sync_tests = [
        test_synth_initialization,
        test_synth_initialization_custom_params,
        test_synth_source_property,
        test_play_note_returns_note_object,
        test_play_note_uses_select_patch_as_fallback,
        test_play_note_with_explicit_patch,
        test_play_note_presses_synth,
        test_stop_note,
        test_release_all,
        test_jseq_patch_names_list,
        test_jseq_midi_to_freq,
        test_load_jseq_invalid_magic,
        test_load_jseq_valid_file,
    ]

    async_tests = [
        test_start_chiptune_sequencer_returns_task,
        test_start_chiptune_sequencer_sets_task_attribute,
        test_start_chiptune_sequencer_accepts_all_channels,
        test_stop_chiptune_cancels_task,
        test_stop_chiptune_clears_task_attribute,
        test_stop_chiptune_calls_release_all,
        test_stop_chiptune_when_no_task,
        test_start_generative_drone_calls_play_note_with_dict_patch,
        test_preview_channels_creates_task,
        test_preview_channels_resolves_string_patch,
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
            import traceback
            traceback.print_exc()
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
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
