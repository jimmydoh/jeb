#!/usr/bin/env python3
"""Unit tests for AudioChannels configuration and AudioManager voice_count validation."""

import sys
import os

# Mock CircuitPython modules before any imports
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

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utilities.audio_channels import AudioChannels


def test_audio_channels_attributes():
    """Test that AudioChannels has all expected channel aliases."""
    print("Testing AudioChannels attributes...")

    assert hasattr(AudioChannels, 'CH_ATMO'), "AudioChannels should have CH_ATMO"
    assert hasattr(AudioChannels, 'CH_SFX'), "AudioChannels should have CH_SFX"
    assert hasattr(AudioChannels, 'CH_VOICE'), "AudioChannels should have CH_VOICE"
    assert hasattr(AudioChannels, 'CH_SYNTH'), "AudioChannels should have CH_SYNTH"

    assert AudioChannels.CH_ATMO == 0, "CH_ATMO should be 0"
    assert AudioChannels.CH_SFX == 1, "CH_SFX should be 1"
    assert AudioChannels.CH_VOICE == 2, "CH_VOICE should be 2"
    assert AudioChannels.CH_SYNTH == 3, "CH_SYNTH should be 3"

    print("  ✓ All channel aliases present with correct values")
    print("✓ AudioChannels attributes test passed")


def test_get_required_voice_count():
    """Test that get_required_voice_count returns the correct minimum voice count."""
    print("\nTesting get_required_voice_count()...")

    required = AudioChannels.voice_count()

    # Should be 6 (highest index is 3, plus 2 additional SFX pool channels)
    assert required == 6, f"Required voice count should be 6, got {required}"

    print(f"  ✓ Required voice count is {required}")
    print("✓ get_required_voice_count() test passed")


def test_channel_indices_unique():
    """Test that all channel indices are unique."""
    print("\nTesting channel indices uniqueness...")

    indices = [
        AudioChannels.CH_ATMO,
        AudioChannels.CH_SFX,
        AudioChannels.CH_VOICE,
        AudioChannels.CH_SYNTH,
    ]

    assert len(indices) == len(set(indices)), "All channel indices should be unique"

    print("  ✓ All channel indices are unique")
    print("✓ Channel indices uniqueness test passed")


def test_channel_indices_non_negative():
    """Test that all channel indices are non-negative."""
    print("\nTesting channel indices are non-negative...")

    indices = [
        AudioChannels.CH_ATMO,
        AudioChannels.CH_SFX,
        AudioChannels.CH_VOICE,
        AudioChannels.CH_SYNTH,
    ]

    for idx in indices:
        assert idx >= 0, f"Channel index {idx} should be non-negative"

    print("  ✓ All channel indices are non-negative")
    print("✓ Channel indices non-negative test passed")


if __name__ == "__main__":
    print("=" * 60)
    print("AudioChannels Configuration Test Suite")
    print("=" * 60)

    try:
        test_audio_channels_attributes()
        test_get_required_voice_count()
        test_channel_indices_unique()
        test_channel_indices_non_negative()

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
