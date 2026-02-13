#!/usr/bin/env python3
"""Unit tests for Tones utility functions and constants."""

import sys
import os
import importlib.util

# Mock CircuitPython modules before any imports
class MockModule:
    """Mock module that allows any attribute access."""
    def __getattr__(self, name):
        return lambda *args, **kwargs: None

sys.modules['synthio'] = MockModule()

# Add src to path for module import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import tones module using importlib to bypass package issues
spec = importlib.util.spec_from_file_location(
    "tones",
    os.path.join(os.path.dirname(__file__), '..', 'src', 'utilities', 'tones.py')
)
tones_module = importlib.util.module_from_spec(spec)
sys.modules['tones'] = tones_module
spec.loader.exec_module(tones_module)
tones = tones_module


def test_note_frequencies_defined():
    """Test that NOTE_FREQUENCIES dictionary contains expected notes."""
    print("Testing note frequency definitions...")
    
    expected_notes = ['C4', 'C#4', 'D4', 'D#4', 'E4', 'F4', 
                      'F#4', 'G4', 'G#4', 'A4', 'A#4', 'B4']
    
    for note in expected_notes:
        assert note in tones.NOTE_FREQUENCIES, f"Note {note} not found in NOTE_FREQUENCIES"
        freq = tones.NOTE_FREQUENCIES[note]
        assert isinstance(freq, float), f"Frequency for {note} should be float"
        assert 200 < freq < 500, f"Frequency for {note} seems out of range: {freq}"
    
    # Test specific known frequency (A4 = 440 Hz)
    assert tones.NOTE_FREQUENCIES['A4'] == 440.0, "A4 should be 440 Hz"
    
    print("✓ Note frequencies test passed")


def test_duration_constants():
    """Test that standard duration constants are defined."""
    print("\nTesting duration constants...")
    
    assert tones.W == 4.0, "Whole note should be 4.0 beats"
    assert tones.H == 2.0, "Half note should be 2.0 beats"
    assert tones.Q == 1.0, "Quarter note should be 1.0 beat"
    assert tones.E == 0.5, "Eighth note should be 0.5 beats"
    assert tones.S == 0.25, "Sixteenth note should be 0.25 beats"
    assert abs(tones.T - 0.33) < 0.01, "Triplet should be approximately 0.33 beats"
    
    print("✓ Duration constants test passed")


def test_tone_library_structure():
    """Test that tone library entries have correct structure."""
    print("\nTesting tone library structure...")
    
    tone_names = ['BEEP', 'ERROR', 'SUCCESS', 'POWER_UP', 'ALARM', 'UI_CONFIRM']
    
    for tone_name in tone_names:
        tone = getattr(tones, tone_name)
        assert 'bpm' in tone, f"{tone_name} should have 'bpm' key"
        assert 'sequence' in tone, f"{tone_name} should have 'sequence' key"
        assert isinstance(tone['bpm'], int), f"{tone_name} bpm should be int"
        assert isinstance(tone['sequence'], list), f"{tone_name} sequence should be list"
        assert len(tone['sequence']) > 0, f"{tone_name} sequence should not be empty"
        
        # Check sequence items are tuples
        for item in tone['sequence']:
            assert isinstance(item, tuple), f"{tone_name} sequence items should be tuples"
            assert len(item) == 2, f"{tone_name} sequence items should be (note, duration) pairs"
    
    print("✓ Tone library structure test passed")


def test_sound_fx_library():
    """Test sound FX library entries."""
    print("\nTesting sound FX library...")
    
    fx_names = ['COIN', 'JUMP', 'FIREBALL', 'ONE_UP', 'SECRET_FOUND', 'GAME_OVER']
    
    for fx_name in fx_names:
        fx = getattr(tones, fx_name)
        assert 'bpm' in fx, f"{fx_name} should have 'bpm' key"
        assert 'sequence' in fx, f"{fx_name} should have 'sequence' key"
        assert len(fx['sequence']) > 0, f"{fx_name} should have non-empty sequence"
    
    print("✓ Sound FX library test passed")


def test_song_library():
    """Test song library entries."""
    print("\nTesting song library...")
    
    song_names = ['MARIO_THEME', 'MARIO_THEME_ALT', 'MARIO_UNDERGROUND', 
                  'TETRIS_THEME', 'WARP_CORE_IDLE', 'MAINFRAME_THINKING']
    
    for song_name in song_names:
        song = getattr(tones, song_name)
        assert 'bpm' in song, f"{song_name} should have 'bpm' key"
        assert 'sequence' in song, f"{song_name} should have 'sequence' key"
        assert len(song['sequence']) >= 4, \
            f"{song_name} should have at least 4 notes"
    
    print("✓ Song library test passed")


def test_note_function_with_frequency():
    """Test note() function with raw frequency input."""
    print("\nTesting note() function with frequencies...")
    
    # Test with integer frequency
    result = tones.note(440)
    assert result == 440, f"Expected 440, got {result}"
    
    # Test with float frequency
    result = tones.note(523.25)
    assert result == 523.25, f"Expected 523.25, got {result}"
    
    print("✓ Note function with frequency test passed")


def test_note_function_with_rests():
    """Test note() function with rest/silence indicators."""
    print("\nTesting note() function with rests...")
    
    rest_indicators = ['0', '-', '_', ' ', 0]
    
    for rest in rest_indicators:
        result = tones.note(rest)
        assert result == 0, f"Rest indicator '{rest}' should return 0, got {result}"
    
    print("✓ Note function with rests test passed")


def test_note_function_with_note_names():
    """Test note() function with note name strings."""
    print("\nTesting note() function with note names...")
    
    # Test A4 = 440 Hz
    result = tones.note('A4')
    assert result == 440.0, f"A4 should be 440 Hz, got {result}"
    
    # Test C4
    result = tones.note('C4')
    assert abs(result - 261.63) < 0.01, f"C4 should be ~261.63 Hz, got {result}"
    
    # Test octave shifting (A5 should be double A4)
    a4_freq = tones.note('A4')
    a5_freq = tones.note('A5')
    assert abs(a5_freq - a4_freq * 2) < 1, \
        f"A5 should be double A4 frequency, A4={a4_freq}, A5={a5_freq}"
    
    # Test A3 should be half A4
    a3_freq = tones.note('A3')
    assert abs(a3_freq - a4_freq / 2) < 1, \
        f"A3 should be half A4 frequency, A3={a3_freq}, A4={a4_freq}"
    
    print("✓ Note function with note names test passed")


def test_note_function_with_sharps():
    """Test note() function with sharp notes."""
    print("\nTesting note() function with sharps...")
    
    # Test C#4
    result = tones.note('C#4')
    assert 270 < result < 280, f"C#4 should be ~277 Hz, got {result}"
    
    # Test F#4
    result = tones.note('F#4')
    assert 365 < result < 375, f"F#4 should be ~370 Hz, got {result}"
    
    print("✓ Note function with sharps test passed")


def test_note_function_with_flats():
    """Test note() function with flat notes."""
    print("\nTesting note() function with flats...")
    
    # Db4 should equal C#4
    db_freq = tones.note('Db4')
    cs_freq = tones.note('C#4')
    assert abs(db_freq - cs_freq) < 0.01, \
        f"Db4 should equal C#4, got Db={db_freq}, C#={cs_freq}"
    
    # Eb4 should equal D#4
    eb_freq = tones.note('Eb4')
    ds_freq = tones.note('D#4')
    assert abs(eb_freq - ds_freq) < 0.01, \
        f"Eb4 should equal D#4, got Eb={eb_freq}, D#={ds_freq}"
    
    print("✓ Note function with flats test passed")


def test_note_function_invalid_input():
    """Test note() function with invalid input."""
    print("\nTesting note() function with invalid input...")
    
    # Test with invalid note names
    assert tones.note('Z9') == 0, "Invalid note should return 0"
    assert tones.note('XYZ') == 0, "Invalid note should return 0"
    assert tones.note('') == 0, "Empty string should return 0"
    
    print("✓ Note function invalid input test passed")


def test_note_function_case_insensitive():
    """Test note() function is case insensitive."""
    print("\nTesting note() function case sensitivity...")
    
    # Test lowercase
    lower = tones.note('a4')
    upper = tones.note('A4')
    assert lower == upper, f"Note names should be case insensitive: {lower} vs {upper}"
    
    # Test with sharps
    lower = tones.note('c#5')
    upper = tones.note('C#5')
    assert lower == upper, f"Sharp note names should be case insensitive: {lower} vs {upper}"
    
    print("✓ Note function case sensitivity test passed")


def run_all_tests():
    """Run all tones tests."""
    print("=" * 60)
    print("Tones Utility Test Suite")
    print("=" * 60)
    
    try:
        test_note_frequencies_defined()
        test_duration_constants()
        test_tone_library_structure()
        test_sound_fx_library()
        test_song_library()
        test_note_function_with_frequency()
        test_note_function_with_rests()
        test_note_function_with_note_names()
        test_note_function_with_sharps()
        test_note_function_with_flats()
        test_note_function_invalid_input()
        test_note_function_case_insensitive()
        
        print("\n" + "=" * 60)
        print("✓ All tones tests passed!")
        print("=" * 60)
        return True
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return False
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
