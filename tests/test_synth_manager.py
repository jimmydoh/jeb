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
        # Expose named attributes to match the real synthio.Envelope interface.
        self.attack_time   = kwargs.get('attack_time', 0.001)
        self.decay_time    = kwargs.get('decay_time', 0.0)
        self.release_time  = kwargs.get('release_time', 0.1)
        self.attack_level  = kwargs.get('attack_level', 1.0)
        self.sustain_level = kwargs.get('sustain_level', 1.0)


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


# ---------------------------------------------------------------------------
# JSEQ v2 tests
# ---------------------------------------------------------------------------

def _build_jseq_v2(bpm, channels):
    """Helper: build a minimal JSEQ v2 binary buffer.

    Args:
        bpm (int): Global BPM.
        channels (list): List of channel spec dicts, each with keys:
            * ``track_type`` (int, 0=audio / 1=automation)
            * ``patch_idx``  (int)
            * ``override``   (tuple of 4 ints, or None)
            * ``steps``      (list of (byte0, byte1) tuples)

    Returns:
        bytes: The encoded .jseq v2 binary.
    """
    import struct
    out = bytearray(b'JSEQ')
    out.append(2)
    out.extend(struct.pack('<H', bpm))
    out.append(len(channels))

    for ch in channels:
        out.append(ch['patch_idx'])
        out.append(ch['track_type'])
        if ch.get('override'):
            out.append(1)  # override_flag
            out.extend(ch['override'])
        else:
            out.append(0)  # override_flag
        steps = ch['steps']
        out.extend(struct.pack('<H', len(steps)))
        for b0, b1 in steps:
            out.append(b0)
            out.append(b1)
    return bytes(out)


def test_load_jseq_v1_backwards_compatible():
    """JSEQ v1 files must still parse correctly after the v2 upgrade."""
    print("\nTesting v1 backwards compatibility...")

    import io
    import struct
    import builtins

    synth = SynthManager()

    bpm = 90
    header = b'JSEQ' + bytes([1]) + struct.pack('<H', bpm) + bytes([1])
    channel = bytes([0]) + struct.pack('<H', 1) + bytes([61, 32])  # patch=0, 1 note
    data = header + channel

    original_open = builtins.open
    builtins.open = lambda path, mode='r', *a, **kw: io.BytesIO(data)
    try:
        channels = synth.load_jseq('/sd/test.jseq')
    finally:
        builtins.open = original_open

    assert len(channels) == 1
    assert channels[0]['bpm'] == bpm
    assert channels[0].get('type') == 'audio'
    print("✓ v1 backwards compatibility test passed")


def test_load_jseq_v2_audio_channel():
    """JSEQ v2 basic audio channel parses correctly."""
    print("\nTesting v2 audio channel parsing...")

    import io
    import builtins

    synth = SynthManager()

    # note_idx=61 → MIDI 60 → C4, dur=32 → 1.0 beat
    data = _build_jseq_v2(120, [{'patch_idx': 0, 'track_type': 0, 'override': None,
                                   'steps': [(61, 32), (0, 8)]}])

    original_open = builtins.open
    builtins.open = lambda path, mode='r', *a, **kw: io.BytesIO(data)
    try:
        channels = synth.load_jseq('/sd/test.jseq')
    finally:
        builtins.open = original_open

    assert len(channels) == 1
    ch = channels[0]
    assert ch.get('type') == 'audio'
    assert ch['bpm'] == 120
    assert len(ch['sequence']) == 2

    # First step: MIDI 60 (note_idx=61 → midi=60 → C4)
    expected_freq = 440.0 * (2.0 ** ((60 - 69) / 12.0))
    assert abs(ch['sequence'][0][0] - expected_freq) < 0.01, "Frequency mismatch"
    assert abs(ch['sequence'][0][1] - 1.0) < 0.01, "Duration mismatch"

    # Second step: rest
    assert ch['sequence'][1][0] == 0, "Rest should have freq 0"
    print("✓ v2 audio channel test passed")


def test_load_jseq_v2_adsr_override():
    """JSEQ v2 inline ADSR override creates a modified envelope."""
    print("\nTesting v2 ADSR override...")

    import io
    import builtins

    synth = SynthManager()

    # Attack ×2.0 (200), Decay ×1.0 (100), Sustain ×0.5 (50), Release ×1.0 (100)
    data = _build_jseq_v2(120, [{'patch_idx': 5, 'track_type': 0,
                                   'override': (200, 100, 50, 100),
                                   'steps': [(61, 32)]}])

    original_open = builtins.open
    builtins.open = lambda path, mode='r', *a, **kw: io.BytesIO(data)
    try:
        channels = synth.load_jseq('/sd/test.jseq')
    finally:
        builtins.open = original_open

    assert len(channels) == 1
    ch = channels[0]
    assert ch.get('type') == 'audio'
    assert 'envelope_override' in ch, "envelope_override should be present"

    env = ch['envelope_override']
    assert env is not None, "envelope_override should not be None"

    # PAD patch: attack_time=0.5 → ×2.0 = 1.0
    assert abs(env.attack_time - 1.0) < 0.001, f"attack_time mismatch: {env.attack_time}"
    # PAD decay_time=0.2 → ×1.0 = 0.2 (unchanged)
    assert abs(env.decay_time - 0.2) < 0.001, f"decay_time mismatch: {env.decay_time}"
    # PAD sustain_level=0.8 → ×0.5 = 0.4
    assert abs(env.sustain_level - 0.4) < 0.001, f"sustain_level mismatch: {env.sustain_level}"
    # PAD release_time=0.5 → ×1.0 = 0.5 (unchanged)
    assert abs(env.release_time - 0.5) < 0.001, f"release_time mismatch: {env.release_time}"
    print("✓ v2 ADSR override test passed")


def test_load_jseq_v2_automation_channel():
    """JSEQ v2 automation channel parses steps as (param_id, value) pairs."""
    print("\nTesting v2 automation channel parsing...")

    import io
    import builtins

    synth = SynthManager()

    PARAM_LPF = synth_manager_module.JSEQ_PARAM_LPF_CUTOFF
    PARAM_AMP = synth_manager_module.JSEQ_PARAM_AMPLITUDE

    # 3 automation steps: LPF at 64, LPF at 128, amplitude at 200
    steps = [(PARAM_LPF, 64), (PARAM_LPF, 128), (PARAM_AMP, 200)]
    data = _build_jseq_v2(120, [{'patch_idx': 0, 'track_type': 1, 'override': None,
                                   'steps': steps}])

    original_open = builtins.open
    builtins.open = lambda path, mode='r', *a, **kw: io.BytesIO(data)
    try:
        channels = synth.load_jseq('/sd/test.jseq')
    finally:
        builtins.open = original_open

    assert len(channels) == 1
    ch = channels[0]
    assert ch.get('type') == 'automation', f"Expected 'automation', got '{ch.get('type')}'"
    assert len(ch['steps']) == 3
    assert ch['steps'][0] == (PARAM_LPF, 64)
    assert ch['steps'][1] == (PARAM_LPF, 128)
    assert ch['steps'][2] == (PARAM_AMP, 200)
    print("✓ v2 automation channel test passed")


def test_load_jseq_v2_meta_event():
    """JSEQ v2 pitch_idx 255 produces a (None, new_bpm) meta-event tuple."""
    print("\nTesting v2 BPM meta-event...")

    import io
    import builtins

    synth = SynthManager()

    # One normal note, then a BPM meta-event (new BPM = 140), then another note
    steps = [(61, 32), (255, 140), (64, 16)]
    data = _build_jseq_v2(120, [{'patch_idx': 0, 'track_type': 0, 'override': None,
                                   'steps': steps}])

    original_open = builtins.open
    builtins.open = lambda path, mode='r', *a, **kw: io.BytesIO(data)
    try:
        channels = synth.load_jseq('/sd/test.jseq')
    finally:
        builtins.open = original_open

    assert len(channels) == 1
    seq = channels[0]['sequence']
    assert len(seq) == 3

    # Second item is the meta-event
    assert seq[1][0] is None, "Meta-event should have None as first element"
    assert seq[1][1] == 140, f"Meta-event BPM should be 140, got {seq[1][1]}"
    print("✓ v2 BPM meta-event test passed")


def test_load_jseq_v2_mixed_channels():
    """JSEQ v2 file with one audio channel and one automation channel."""
    print("\nTesting v2 mixed audio + automation channels...")

    import io
    import builtins

    synth = SynthManager()

    data = _build_jseq_v2(100, [
        {'patch_idx': 0, 'track_type': 0, 'override': None, 'steps': [(61, 32)]},
        {'patch_idx': 0, 'track_type': 1, 'override': None, 'steps': [(0x00, 200), (0x00, 50)]},
    ])

    original_open = builtins.open
    builtins.open = lambda path, mode='r', *a, **kw: io.BytesIO(data)
    try:
        channels = synth.load_jseq('/sd/test.jseq')
    finally:
        builtins.open = original_open

    assert len(channels) == 2
    assert channels[0].get('type') == 'audio'
    assert channels[1].get('type') == 'automation'
    assert len(channels[1]['steps']) == 2
    print("✓ v2 mixed channels test passed")


def test_load_jseq_unknown_version_raises():
    """An unsupported version byte must raise ValueError."""
    print("\nTesting unknown version raises ValueError...")

    import io
    import struct
    import builtins

    synth = SynthManager()

    bad_data = b'JSEQ' + bytes([99]) + struct.pack('<H', 120) + bytes([1]) + bytes(10)

    original_open = builtins.open
    builtins.open = lambda path, mode='r', *a, **kw: io.BytesIO(bad_data)
    try:
        raised = False
        try:
            synth.load_jseq('/sd/test.jseq')
        except ValueError:
            raised = True
        assert raised, "load_jseq should raise ValueError for unknown version"
    finally:
        builtins.open = original_open

    print("✓ unknown version raises ValueError test passed")


def test_apply_adsr_multipliers():
    """_apply_adsr_multipliers creates a correctly scaled envelope."""
    print("\nTesting _apply_adsr_multipliers...")

    synth = SynthManager()

    from utilities.synth_registry import Envelopes
    base = Envelopes.PAD  # attack=0.5, decay=0.2, sustain=0.8, release=0.5

    # Double attack (200), halve sustain (50), no change elsewhere (100)
    result = synth._apply_adsr_multipliers(base, (200, 100, 50, 100))

    assert abs(result.attack_time - 1.0) < 0.001,   f"attack_time: {result.attack_time}"
    assert abs(result.decay_time - 0.2) < 0.001,    f"decay_time: {result.decay_time}"
    assert abs(result.sustain_level - 0.4) < 0.001, f"sustain_level: {result.sustain_level}"
    assert abs(result.release_time - 0.5) < 0.001,  f"release_time: {result.release_time}"
    print("✓ _apply_adsr_multipliers test passed")


def test_apply_adsr_multipliers_sustain_clamped():
    """Sustain level must not exceed 1.0 even with a large multiplier."""
    print("\nTesting ADSR multiplier sustain clamping...")

    synth = SynthManager()

    from utilities.synth_registry import Envelopes
    base = Envelopes.PAD  # sustain=0.8

    # 200 × 0.8 = 1.6 → should clamp to 1.0
    result = synth._apply_adsr_multipliers(base, (100, 100, 200, 100))
    assert result.sustain_level <= 1.0, "sustain_level must not exceed 1.0"
    assert abs(result.sustain_level - 1.0) < 0.001
    print("✓ ADSR multiplier sustain clamping test passed")


@pytest.mark.asyncio
async def test_play_sequence_bpm_meta_event():
    """play_sequence honours dynamic BPM meta-events embedded in the sequence."""
    print("\nTesting play_sequence BPM meta-event handling...")

    synth = SynthManager()
    sleep_calls = []

    original_sleep = asyncio.sleep

    async def spy_sleep(t):
        sleep_calls.append(t)

    asyncio.sleep = spy_sleep
    try:
        # One rest at 120 BPM, then BPM meta-event → 240 BPM, then another rest
        # At 120 BPM: beat_duration=0.5s, rest=1.0 beat → 0.5s sleep
        # At 240 BPM: beat_duration=0.25s, rest=1.0 beat → 0.25s sleep
        sequence_data = {
            'bpm': 120,
            'patch': 'SELECT',
            'sequence': [
                (0, 1.0),      # rest at 120 BPM → 0.5s
                (None, 240),   # meta-event: new BPM = 240
                (0, 1.0),      # rest at 240 BPM → 0.25s
            ]
        }
        await synth.play_sequence(sequence_data)
    finally:
        asyncio.sleep = original_sleep

    # The first rest is 0.5s (120 BPM, 1 beat), the third is 0.25s (240 BPM, 1 beat)
    assert any(abs(t - 0.5) < 0.001 for t in sleep_calls), f"Expected 0.5s sleep, got: {sleep_calls}"
    assert any(abs(t - 0.25) < 0.001 for t in sleep_calls), f"Expected 0.25s sleep, got: {sleep_calls}"
    print("✓ play_sequence BPM meta-event test passed")


@pytest.mark.asyncio
async def test_play_sequence_uses_envelope_override():
    """play_sequence uses envelope_override from channel dict when present."""
    print("\nTesting play_sequence envelope_override...")

    synth = SynthManager()
    used_envelopes = []

    original_note_cls = synth.synth.__class__

    class CapturingNote:
        def __init__(self, frequency, waveform=None, envelope=None):
            self.frequency = frequency
            self.waveform = waveform
            self.envelope = envelope
            used_envelopes.append(envelope)

    import synthio as mock_synthio
    original_note = mock_synthio.Note
    mock_synthio.Note = CapturingNote

    try:
        override_env = mock_synthio.Envelope(attack_time=9.9)
        sequence_data = {
            'bpm': 120,
            'patch': 'BEEP',
            'envelope_override': override_env,
            'sequence': [(440.0, 0.01)]
        }
        await synth.play_sequence(sequence_data)
    finally:
        mock_synthio.Note = original_note

    assert len(used_envelopes) == 1
    assert used_envelopes[0] is override_env, "envelope_override should be used"
    print("✓ play_sequence envelope_override test passed")


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
        # v2 tests
        test_load_jseq_v1_backwards_compatible,
        test_load_jseq_v2_audio_channel,
        test_load_jseq_v2_adsr_override,
        test_load_jseq_v2_automation_channel,
        test_load_jseq_v2_meta_event,
        test_load_jseq_v2_mixed_channels,
        test_load_jseq_unknown_version_raises,
        test_apply_adsr_multipliers,
        test_apply_adsr_multipliers_sustain_clamped,
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
        # v2 async tests
        test_play_sequence_bpm_meta_event,
        test_play_sequence_uses_envelope_override,
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
