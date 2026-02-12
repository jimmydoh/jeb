#!/usr/bin/env python3
"""Unit tests for AudioManager voice_count validation."""

import sys
import os

# Mock the CircuitPython modules before importing AudioManager
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


class MockI2SOut:
    """Mock I2SOut."""
    def __init__(self, sck, ws, sd):
        pass
    
    def play(self, mixer):
        pass


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


class MockAudioBusIO:
    """Mock audiobusio module."""
    I2SOut = MockI2SOut


class MockAudioMixer:
    """Mock audiomixer module."""
    Mixer = MockMixer


class MockAudioCore:
    """Mock audiocore module."""
    pass


# Replace the imports
sys.modules['audiobusio'] = MockAudioBusIO
sys.modules['audiocore'] = MockAudioCore
sys.modules['audiomixer'] = MockAudioMixer

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'managers'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from audio_manager import AudioManager
from utilities import AudioChannels


def test_default_voice_count():
    """Test that AudioManager uses required voice count by default."""
    print("Testing default voice_count...")
    
    manager = AudioManager(None, None, None)
    
    # Should have the required number of voices
    expected_count = AudioChannels.get_required_voice_count()
    assert manager.mixer.voice_count == expected_count, \
        f"Default voice count should be {expected_count}, got {manager.mixer.voice_count}"
    
    print(f"  ✓ Default voice_count is {expected_count}")
    print("✓ Default voice_count test passed")


def test_explicit_voice_count_sufficient():
    """Test that AudioManager accepts sufficient voice_count."""
    print("\nTesting explicit sufficient voice_count...")
    
    required = AudioChannels.get_required_voice_count()
    
    # Test with exactly the required count
    manager1 = AudioManager(None, None, None, voice_count=required)
    assert manager1.mixer.voice_count == required
    print(f"  ✓ voice_count={required} (minimum) accepted")
    
    # Test with more than required
    manager2 = AudioManager(None, None, None, voice_count=required + 2)
    assert manager2.mixer.voice_count == required + 2
    print(f"  ✓ voice_count={required + 2} (more than minimum) accepted")
    
    print("✓ Explicit sufficient voice_count test passed")


def test_insufficient_voice_count_raises_error():
    """Test that AudioManager raises error for insufficient voice_count."""
    print("\nTesting insufficient voice_count raises ValueError...")
    
    required = AudioChannels.get_required_voice_count()
    
    # Test with voice_count less than required
    try:
        manager = AudioManager(None, None, None, voice_count=required - 1)
        assert False, "Should have raised ValueError for insufficient voice_count"
    except ValueError as e:
        error_msg = str(e)
        assert f"voice_count ({required - 1})" in error_msg, \
            f"Error message should mention voice_count, got: {error_msg}"
        assert f"at least {required}" in error_msg, \
            f"Error message should mention required count, got: {error_msg}"
        print(f"  ✓ voice_count={required - 1} correctly rejected")
        print(f"  ✓ Error message: {error_msg}")
    
    print("✓ Insufficient voice_count validation test passed")


def test_channel_aliases_match():
    """Test that AudioManager channel aliases match AudioChannels."""
    print("\nTesting channel aliases match AudioChannels...")
    
    manager = AudioManager(None, None, None)
    
    assert manager.CH_ATMO == AudioChannels.CH_ATMO, "CH_ATMO should match"
    assert manager.CH_SFX == AudioChannels.CH_SFX, "CH_SFX should match"
    assert manager.CH_VOICE == AudioChannels.CH_VOICE, "CH_VOICE should match"
    assert manager.CH_SYNTH == AudioChannels.CH_SYNTH, "CH_SYNTH should match"
    
    print(f"  ✓ CH_ATMO = {manager.CH_ATMO}")
    print(f"  ✓ CH_SFX = {manager.CH_SFX}")
    print(f"  ✓ CH_VOICE = {manager.CH_VOICE}")
    print(f"  ✓ CH_SYNTH = {manager.CH_SYNTH}")
    print("✓ Channel aliases match test passed")


def test_channel_aliases_within_bounds():
    """Test that all channel aliases are within mixer voice bounds."""
    print("\nTesting channel aliases are within voice bounds...")
    
    manager = AudioManager(None, None, None)
    
    max_index = manager.mixer.voice_count - 1
    
    assert manager.CH_ATMO <= max_index, f"CH_ATMO ({manager.CH_ATMO}) should be <= {max_index}"
    assert manager.CH_SFX <= max_index, f"CH_SFX ({manager.CH_SFX}) should be <= {max_index}"
    assert manager.CH_VOICE <= max_index, f"CH_VOICE ({manager.CH_VOICE}) should be <= {max_index}"
    assert manager.CH_SYNTH <= max_index, f"CH_SYNTH ({manager.CH_SYNTH}) should be <= {max_index}"
    
    print(f"  ✓ All channel indices are within bounds [0, {max_index}]")
    print("✓ Channel aliases within bounds test passed")


if __name__ == "__main__":
    print("=" * 60)
    print("AudioManager Voice Count Validation Test Suite")
    print("=" * 60)
    
    try:
        test_default_voice_count()
        test_explicit_voice_count_sufficient()
        test_insufficient_voice_count_raises_error()
        test_channel_aliases_match()
        test_channel_aliases_within_bounds()
        
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
