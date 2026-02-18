#!/usr/bin/env python3
"""Unit tests for AudioManager preload functionality."""

import sys
import os
import tempfile

# Mock CircuitPython modules BEFORE any imports
class MockModule:
    """Generic mock module."""
    def __getattr__(self, name):
        return MockModule()
    
    def __call__(self, *args, **kwargs):
        return MockModule()

# Mock audiocore module with necessary classes
class MockRawSample:
    """Mock RawSample for testing."""
    def __init__(self, *args, **kwargs):
        # Accept various argument patterns
        if len(args) > 0:
            # Could be (file) or (audio_data, channel_count, sample_rate, bits_per_sample)
            if hasattr(args[0], 'read'):
                # File-like object
                self.file = args[0]
            else:
                # Audio data
                self.audio_data = args[0]
                if len(args) >= 4:
                    self.channel_count = args[1] if len(args) > 1 else kwargs.get('channel_count', 1)
                    self.sample_rate = args[2] if len(args) > 2 else kwargs.get('sample_rate', 22050)
                    self.bits_per_sample = args[3] if len(args) > 3 else kwargs.get('bits_per_sample', 16)

class MockWaveFile:
    """Mock WaveFile for testing."""
    def __init__(self, f, buffer):
        self.sample_rate = 22050
        self.channel_count = 1
        self.bits_per_sample = 16

class MockAudioCore:
    """Mock audiocore module."""
    RawSample = MockRawSample
    WaveFile = MockWaveFile

class MockAudioBusIO:
    """Mock audiobusio module."""
    class I2SOut:
        def __init__(self, sck, ws, sd):
            pass
        def play(self, mixer):
            pass

class MockAudioMixer:
    """Mock audiomixer module."""
    class Mixer:
        def __init__(self, voice_count, sample_rate, channel_count, bits_per_sample, samples_signed):
            self.voice_count = voice_count
            self.voice = [None] * voice_count

# Mock all CircuitPython dependencies
sys.modules['audiobusio'] = MockAudioBusIO
sys.modules['audiocore'] = MockAudioCore
sys.modules['audiomixer'] = MockAudioMixer
sys.modules['adafruit_ticks'] = MockModule()
sys.modules['digitalio'] = MockModule()
sys.modules['busio'] = MockModule()
sys.modules['board'] = MockModule()
sys.modules['neopixel'] = MockModule()
sys.modules['microcontroller'] = MockModule()
sys.modules['watchdog'] = MockModule()
sys.modules['analogio'] = MockModule()
sys.modules['audiopwmio'] = MockModule()
sys.modules['synthio'] = MockModule()
sys.modules['ulab'] = MockModule()
sys.modules['adafruit_mcp230xx'] = MockModule()
sys.modules['adafruit_mcp230xx.mcp23017'] = MockModule()
sys.modules['adafruit_displayio_ssd1306'] = MockModule()
sys.modules['adafruit_display_text'] = MockModule()
sys.modules['displayio'] = MockModule()
sys.modules['terminalio'] = MockModule()
sys.modules['adafruit_httpserver'] = MockModule()

# Add src directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

# Import the REAL AudioManager from production code
from managers.audio_manager import AudioManager, MAX_PRELOAD_SIZE_BYTES


def create_test_file(directory, filename, size):
    """Create a test WAV file with the specified size."""
    filepath = os.path.join(directory, filename)
    with open(filepath, 'wb') as f:
        f.write(b'\x00' * size)
    return filepath


# Mock pin objects for AudioManager initialization
class MockPin:
    """Mock pin object for testing."""
    pass


def test_preload_small_file():
    """Test that small files (< 20KB) are preloaded successfully."""
    print("Testing small file preload...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a small test file (10KB)
        small_file = create_test_file(tmpdir, "small.wav", 10240)
        
        # Create AudioManager with temp directory as root (with mock pins)
        manager = AudioManager(
            sck=MockPin(),
            ws=MockPin(),
            sd=MockPin(),
            root_data_dir=tmpdir + "/"
        )
        
        # Preload the file
        manager.preload(["small.wav"])
        
        # Verify it was cached
        expected_key = tmpdir + "/small.wav"
        assert expected_key in manager._cache, "Small file should be in cache"
        assert isinstance(manager._cache[expected_key], MockRawSample), "Cached object should be RawSample"
        
        print("  ✓ Small file (10KB) preloaded successfully")
    
    print("✓ Small file preload test passed")


def test_preload_large_file():
    """Test that large files (> 20KB) are NOT preloaded."""
    print("\nTesting large file preload...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a large test file (30KB)
        large_file = create_test_file(tmpdir, "large.wav", 30720)
        
        # Create AudioManager with temp directory as root (with mock pins)
        manager = AudioManager(
            sck=MockPin(),
            ws=MockPin(),
            sd=MockPin(),
            root_data_dir=tmpdir + "/"
        )
        
        # Preload the file
        manager.preload(["large.wav"])
        
        # Verify it was NOT cached
        expected_key = tmpdir + "/large.wav"
        assert expected_key not in manager._cache, "Large file should NOT be in cache"
        
        print("  ✓ Large file (30KB) correctly skipped")
    
    print("✓ Large file preload test passed")


def test_preload_boundary():
    """Test the exact 20KB boundary."""
    print("\nTesting 20KB boundary...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create files at the boundary
        just_under = create_test_file(tmpdir, "just_under.wav", 20479)
        exactly_20kb = create_test_file(tmpdir, "exactly_20kb.wav", 20480)
        just_over = create_test_file(tmpdir, "just_over.wav", 20481)
        
        # Create AudioManager with temp directory as root (with mock pins)
        manager = AudioManager(
            sck=MockPin(),
            ws=MockPin(),
            sd=MockPin(),
            root_data_dir=tmpdir + "/"
        )
        
        # Preload all files
        manager.preload(["just_under.wav", "exactly_20kb.wav", "just_over.wav"])
        
        # Verify boundaries
        assert tmpdir + "/just_under.wav" in manager._cache, "File just under 20KB should be cached"
        assert tmpdir + "/exactly_20kb.wav" in manager._cache, "File exactly 20KB should be cached"
        assert tmpdir + "/just_over.wav" not in manager._cache, "File just over 20KB should NOT be cached"
        
        print("  ✓ File at 20479 bytes: preloaded")
        print("  ✓ File at 20480 bytes: preloaded")
        print("  ✓ File at 20481 bytes: skipped")
    
    print("✓ Boundary test passed")


def test_preload_multiple_files():
    """Test preloading multiple files with mixed sizes."""
    print("\nTesting multiple files with mixed sizes...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create multiple files
        file1 = create_test_file(tmpdir, "file1.wav", 5000)
        file2 = create_test_file(tmpdir, "file2.wav", 15000)
        file3 = create_test_file(tmpdir, "file3.wav", 25000)
        file4 = create_test_file(tmpdir, "file4.wav", 10000)
        
        # Create AudioManager with temp directory as root (with mock pins)
        manager = AudioManager(
            sck=MockPin(),
            ws=MockPin(),
            sd=MockPin(),
            root_data_dir=tmpdir + "/"
        )
        
        # Preload all files
        manager.preload(["file1.wav", "file2.wav", "file3.wav", "file4.wav"])
        
        # Verify cache contents
        assert tmpdir + "/file1.wav" in manager._cache, "file1.wav should be cached"
        assert tmpdir + "/file2.wav" in manager._cache, "file2.wav should be cached"
        assert tmpdir + "/file3.wav" not in manager._cache, "file3.wav should NOT be cached"
        assert tmpdir + "/file4.wav" in manager._cache, "file4.wav should be cached"
        assert len(manager._cache) == 3, "Should have exactly 3 files in cache"
        
        print("  ✓ file1.wav (5KB): preloaded")
        print("  ✓ file2.wav (15KB): preloaded")
        print("  ✓ file3.wav (25KB): skipped")
        print("  ✓ file4.wav (10KB): preloaded")
    
    print("✓ Multiple files test passed")


def test_preload_nonexistent_file():
    """Test handling of non-existent files."""
    print("\nTesting non-existent file handling...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create AudioManager with temp directory as root (with mock pins)
        manager = AudioManager(
            sck=MockPin(),
            ws=MockPin(),
            sd=MockPin(),
            root_data_dir=tmpdir + "/"
        )
        
        # Try to preload a non-existent file
        manager.preload(["nonexistent.wav"])
        
        # Verify cache is empty
        assert len(manager._cache) == 0, "Cache should be empty for non-existent file"
        
        print("  ✓ Non-existent file handled gracefully")
    
    print("✓ Non-existent file test passed")


if __name__ == "__main__":
    print("=" * 60)
    print("AudioManager Preload Test Suite")
    print("=" * 60)
    
    try:
        test_preload_small_file()
        test_preload_large_file()
        test_preload_boundary()
        test_preload_multiple_files()
        test_preload_nonexistent_file()
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
