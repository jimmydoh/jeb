#!/usr/bin/env python3
"""Unit tests for AudioManager file handle management."""

import sys
import os
import tempfile
import asyncio

# Mock audiocore and related modules since they're CircuitPython specific
class MockRawSample:
    """Mock RawSample for testing."""
    def __init__(self, file_or_data, channel_count=1, sample_rate=22050, bits_per_sample=16):
        # Support both constructor signatures
        if isinstance(file_or_data, (bytes, bytearray)):
            self.audio_data = file_or_data
        else:
            # It's a file-like object, just store reference
            self.audio_data = b'\x00' * 100  # Mock data
        self.channel_count = channel_count
        self.sample_rate = sample_rate
        self.bits_per_sample = bits_per_sample


class MockWaveFile:
    """Mock WaveFile for testing.

    The preload() path calls WaveFile(io.BytesIO(...)) with no buffer, while the
    streaming path calls WaveFile(file_handle, stream_buffer).  Making buffer
    optional handles both call signatures.
    """
    def __init__(self, f, buffer=None):
        self.sample_rate = 22050
        self.channel_count = 1
        self.bits_per_sample = 16
        self._position = 0
        self._data_size = 100  # Simulate small audio data
        self.file = f  # Keep reference to file for testing

    def readinto(self, samples):
        """Simulate reading audio data."""
        if self._position >= self._data_size:
            return 0
        chunk_size = min(len(samples), self._data_size - self._position)
        for i in range(chunk_size):
            samples[i] = i % 256
        self._position += chunk_size
        return chunk_size


class MockVoice:
    """Mock voice channel."""
    def __init__(self):
        self.playing = False
        self.level = 1.0
        self.current_source = None

    def play(self, source, loop=False):
        self.playing = True
        self.current_source = source

    def stop(self):
        self.playing = False
        self.current_source = None


class MockMixer:
    """Mock audiomixer.Mixer."""
    def __init__(self, voice_count, sample_rate, channel_count, bits_per_sample, samples_signed):
        self.voice_count = voice_count
        self.voice = [MockVoice() for _ in range(voice_count)]


class MockI2SOut:
    """Mock I2SOut."""
    def __init__(self, sck, ws, sd):
        pass

    def play(self, mixer):
        pass


class MockAudioCore:
    """Mock audiocore module."""
    RawSample = MockRawSample
    WaveFile = MockWaveFile


class MockAudioBusIO:
    """Mock audiobusio module."""
    I2SOut = MockI2SOut


class MockAudioMixer:
    """Mock audiomixer module."""
    Mixer = MockMixer


# Mock more modules
class MockModule:
    """Mock module that allows any attribute access."""
    def __getattr__(self, name):
        return lambda *args, **kwargs: None

sys.modules['digitalio'] = MockModule()
sys.modules['board'] = MockModule()
sys.modules['busio'] = MockModule()
sys.modules['adafruit_mcp230xx'] = MockModule()
sys.modules['adafruit_mcp230xx.mcp23017'] = MockModule()
sys.modules['adafruit_ticks'] = MockModule()
sys.modules['microcontroller'] = MockModule()
sys.modules['neopixel'] = MockModule()
sys.modules['displayio'] = MockModule()
sys.modules['usb_hid'] = MockModule()
sys.modules['adafruit_display_text'] = MockModule()
sys.modules['adafruit_display_text.label'] = MockModule()
sys.modules['adafruit_ssd1306'] = MockModule()
sys.modules['terminalio'] = MockModule()
sys.modules['adafruit_hid'] = MockModule()
sys.modules['adafruit_hid.keyboard'] = MockModule()
sys.modules['adafruit_hid.keycode'] = MockModule()
sys.modules['adafruit_hid.consumer_control'] = MockModule()
sys.modules['adafruit_hid.consumer_control_code'] = MockModule()
sys.modules['pwmio'] = MockModule()
sys.modules['analogio'] = MockModule()
sys.modules['synthio'] = MockModule()
sys.modules['adafruit_led_animation'] = MockModule()
sys.modules['adafruit_led_animation.animation'] = MockModule()
sys.modules['adafruit_led_animation.animation.solid'] = MockModule()

# Replace the imports
sys.modules['audiobusio'] = MockAudioBusIO
sys.modules['audiocore'] = MockAudioCore
sys.modules['audiomixer'] = MockAudioMixer

# Now import the AudioManager
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'managers'))
from audio_manager import AudioManager


def create_test_file(directory, filename, size):
    """Create a test WAV file with the specified size."""
    filepath = os.path.join(directory, filename)
    with open(filepath, 'wb') as f:
        f.write(b'\x00' * size)
    return filepath


def test_stream_file_tracking():
    """Test that streaming files are tracked in _stream_files."""
    print("Testing stream file tracking...")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a large file that will be streamed (not cached)
        create_test_file(tmpdir, "stream.wav", 30720)

        # Create AudioManager
        manager = AudioManager(None, None, None, root_data_dir=tmpdir + "/")

        # Play the file on CH_SFX (bus_id=1), which maps to pool [4, 5, 6]; first free = voice 4
        asyncio.run(manager.play("stream.wav", bus_id=1))

        # Verify file handle is tracked at the physical voice index (4)
        assert 4 in manager._stream_files, "File handle should be tracked for physical voice 4 (CH_SFX pool)"
        assert not manager._stream_files[4].closed, "File handle should be open"

        print("  ✓ Stream file tracked in _stream_files")
        print(f"  ✓ File handle for physical voice 4 (CH_SFX) is open")

        manager.stop_all()  # Clean up file handles after test

    print("✓ Stream file tracking test passed")


def test_close_on_new_stream():
    """Test that old file handles are closed when playing new files on the same bus."""
    print("\nTesting file handle closure on new stream...")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create two large files
        create_test_file(tmpdir, "stream1.wav", 30720)
        create_test_file(tmpdir, "stream2.wav", 30720)

        # Create AudioManager
        manager = AudioManager(None, None, None, root_data_dir=tmpdir + "/")

        # Use CH_VOICE (bus_id=2), which has a single-voice pool [2].
        # Both plays will reuse the same physical voice (2).
        asyncio.run(manager.play("stream1.wav", bus_id=2))
        first_handle = manager._stream_files[2]

        # Play second file on same bus — pool [2] is fully occupied, round-robin returns voice 2
        asyncio.run(manager.play("stream2.wav", bus_id=2))
        second_handle = manager._stream_files[2]

        # Verify first handle was closed
        assert first_handle.closed, "First file handle should be closed"
        assert not second_handle.closed, "Second file handle should be open"
        assert first_handle != second_handle, "Should be different file handles"

        print("  ✓ First file handle closed when second file played on same bus")
        print("  ✓ Second file handle is open")

        manager.stop_all()  # Clean up file handles after test

    print("✓ File handle closure test passed")


def test_close_on_stop():
    """Test that file handles are closed when stop() is called."""
    print("\nTesting file handle closure on stop()...")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a large file
        create_test_file(tmpdir, "stream.wav", 30720)

        # Create AudioManager
        manager = AudioManager(None, None, None, root_data_dir=tmpdir + "/")

        # Play file on CH_SFX (bus_id=1), pool [4, 5, 6]; first free = voice 4
        asyncio.run(manager.play("stream.wav", bus_id=1))
        file_handle = manager._stream_files[4]

        # Stop the CH_SFX bus
        manager.stop(1)

        # Verify file handle was closed and removed from tracking
        assert file_handle.closed, "File handle should be closed after stop()"
        assert 4 not in manager._stream_files, "File handle should be removed from tracking"

        print("  ✓ File handle closed on stop()")
        print("  ✓ File handle removed from tracking")

    print("✓ Stop() test passed")


def test_close_on_stop_all():
    """Test that all file handles are closed when stop_all() is called."""
    print("\nTesting file handle closure on stop_all()...")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create multiple large files
        create_test_file(tmpdir, "stream1.wav", 30720)
        create_test_file(tmpdir, "stream2.wav", 30720)
        create_test_file(tmpdir, "stream3.wav", 30720)

        # Create AudioManager
        manager = AudioManager(None, None, None, root_data_dir=tmpdir + "/")

        # Play files on different buses with predictable single-voice pools:
        # CH_ATMO (bus_id=0) -> pool [0, 1], first free = voice 0
        # CH_VOICE (bus_id=2) -> pool [2]  -> voice 2
        # CH_SYNTH (bus_id=3) -> pool [3]  -> voice 3
        asyncio.run(manager.play("stream1.wav", bus_id=0))
        asyncio.run(manager.play("stream2.wav", bus_id=2))
        asyncio.run(manager.play("stream3.wav", bus_id=3))

        handle1 = manager._stream_files[0]
        handle2 = manager._stream_files[2]
        handle3 = manager._stream_files[3]

        # Stop all playback
        manager.stop_all()

        # Verify all file handles were closed
        assert handle1.closed, "Voice 0 (CH_ATMO) file handle should be closed"
        assert handle2.closed, "Voice 2 (CH_VOICE) file handle should be closed"
        assert handle3.closed, "Voice 3 (CH_SYNTH) file handle should be closed"
        assert len(manager._stream_files) == 0, "All file handles should be removed from tracking"

        print("  ✓ All file handles closed on stop_all()")
        print("  ✓ All file handles removed from tracking")

    print("✓ Stop_all() test passed")


def test_cached_vs_streamed():
    """Test that cached files don't create file handles but streamed files do."""
    print("\nTesting cached vs streamed file handling...")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a small file (will be cached) and a large file (will be streamed)
        create_test_file(tmpdir, "small.wav", 10240)
        create_test_file(tmpdir, "large.wav", 30720)

        # Create AudioManager and preload small file
        manager = AudioManager(None, None, None, root_data_dir=tmpdir + "/")
        manager.preload(["small.wav"])

        try:
            # Use CH_VOICE (bus_id=2), pool [2] -> physical voice 2
            asyncio.run(manager.play("small.wav", bus_id=2))
            assert 2 not in manager._stream_files, "Cached file should not create stream file handle"

            # Play streamed file on the same bus
            asyncio.run(manager.play("large.wav", bus_id=2))
            assert 2 in manager._stream_files, "Streamed file should create stream file handle"
            assert not manager._stream_files[2].closed, "Streamed file handle should be open"

            print("  ✓ Cached file does not create stream file handle")
            print("  ✓ Streamed file creates stream file handle")
        finally:
            # Ensure any open stream file handles are closed before temp dir cleanup
            manager.stop_all()

    print("✓ Cached vs streamed test passed")


def test_close_stream_when_playing_cached():
    """Test that streaming file handles are closed when playing cached audio."""
    print("\nTesting stream closure when switching to cached audio...")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create files
        create_test_file(tmpdir, "small.wav", 10240)
        create_test_file(tmpdir, "large.wav", 30720)

        # Create AudioManager and preload small file
        manager = AudioManager(None, None, None, root_data_dir=tmpdir + "/")
        manager.preload(["small.wav"])

        # Use CH_VOICE (bus_id=2), pool [2] -> physical voice 2
        asyncio.run(manager.play("large.wav", bus_id=2))
        stream_handle = manager._stream_files[2]

        # Play cached file on same bus
        asyncio.run(manager.play("small.wav", bus_id=2))

        # Verify stream handle was closed
        assert stream_handle.closed, "Stream file handle should be closed when playing cached audio"
        assert 2 not in manager._stream_files, "Stream file handle should be removed from tracking"

        print("  ✓ Stream file handle closed when switching to cached audio")

    print("✓ Stream-to-cached switch test passed")


def test_multiple_channels():
    """Test that file handles are managed independently per bus."""
    print("\nTesting independent bus management...")

    with tempfile.TemporaryDirectory() as tmpdir:
        manager = None
        try:
            # Create multiple files
            create_test_file(tmpdir, "stream1.wav", 30720)
            create_test_file(tmpdir, "stream2.wav", 30720)
            create_test_file(tmpdir, "stream3.wav", 30720)

            # Create AudioManager
            manager = AudioManager(None, None, None, root_data_dir=tmpdir + "/")

            # Play different files on different buses with predictable single-voice pools:
            # CH_ATMO (bus_id=0) -> pool [0, 1], first free = voice 0
            # CH_VOICE (bus_id=2) -> pool [2]  -> voice 2
            # CH_SYNTH (bus_id=3) -> pool [3]  -> voice 3
            asyncio.run(manager.play("stream1.wav", bus_id=0))
            asyncio.run(manager.play("stream2.wav", bus_id=2))
            asyncio.run(manager.play("stream3.wav", bus_id=3))

            handle1 = manager._stream_files[0]
            handle2 = manager._stream_files[2]
            handle3 = manager._stream_files[3]

            # Stop CH_VOICE bus only
            manager.stop(2)

            # Verify only CH_VOICE was closed
            assert not handle1.closed, "Voice 0 (CH_ATMO) should still be open"
            assert handle2.closed, "Voice 2 (CH_VOICE) should be closed"
            assert not handle3.closed, "Voice 3 (CH_SYNTH) should still be open"

            assert 0 in manager._stream_files, "Voice 0 (CH_ATMO) should still be tracked"
            assert 2 not in manager._stream_files, "Voice 2 (CH_VOICE) should not be tracked"
            assert 3 in manager._stream_files, "Voice 3 (CH_SYNTH) should still be tracked"

            print("  ✓ File handles managed independently per bus")
            print("  ✓ Stopping one bus doesn't affect others")
        finally:
            if manager is not None:
                manager.stop_all()

    print("✓ Multiple buses test passed")


if __name__ == "__main__":
    print("=" * 60)
    print("AudioManager File Handle Management Test Suite")
    print("=" * 60)

    try:
        test_stream_file_tracking()
        test_close_on_new_stream()
        test_close_on_stop()
        test_close_on_stop_all()
        test_cached_vs_streamed()
        test_close_stream_when_playing_cached()
        test_multiple_channels()

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
