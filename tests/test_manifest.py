"""Test the mode manifest functionality."""

import sys
import os
from unittest.mock import MagicMock

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Mock CircuitPython modules
adafruit_ticks = MagicMock()
adafruit_ticks.ticks_ms = MagicMock(return_value=0)
adafruit_ticks.ticks_diff = MagicMock(return_value=0)
sys.modules['adafruit_ticks'] = adafruit_ticks

sys.modules['busio'] = MagicMock()
sys.modules['microcontroller'] = MagicMock()
sys.modules['neopixel'] = MagicMock()

utilities = MagicMock()
utilities.Palette = MagicMock()
utilities.tones = MagicMock()
sys.modules['utilities'] = utilities

sys.modules['transport'] = MagicMock()
sys.modules['managers'] = MagicMock()
sys.modules['satellites'] = MagicMock()

# Mock satellite class for testing
class MockSatellite:
    def __init__(self, sat_type_name):
        self.sat_type_name = sat_type_name

def test_mode_registry_structure():
    """Test that MODE_REGISTRY has expected structure."""
    from modes.manifest import MODE_REGISTRY
    
    assert "JEBRIS" in MODE_REGISTRY
    assert "SIMON" in MODE_REGISTRY
    assert "SAFE" in MODE_REGISTRY
    assert "IND" in MODE_REGISTRY
    
    # Check structure of entries
    for key, value in MODE_REGISTRY.items():
        assert "class" in value, f"Missing 'class' in {key}"
        assert "requires_satellite" in value, f"Missing 'requires_satellite' in {key}"
        assert "name" in value, f"Missing 'name' in {key}"
        assert "icon" in value, f"Missing 'icon' in {key}"
        assert "settings" in value, f"Missing 'settings' in {key}"
    
    print("✓ MODE_REGISTRY structure is valid")

def test_get_mode_class():
    """Test getting mode classes."""
    from modes.manifest import get_mode_class, MODE_REGISTRY
    
    # Just verify the function returns the right keys from the registry
    assert get_mode_class("JEBRIS") == MODE_REGISTRY["JEBRIS"]["class"]
    assert get_mode_class("SIMON") == MODE_REGISTRY["SIMON"]["class"]
    assert get_mode_class("SAFE") == MODE_REGISTRY["SAFE"]["class"]
    assert get_mode_class("IND") == MODE_REGISTRY["IND"]["class"]
    assert get_mode_class("NONEXISTENT") is None
    
    print("✓ get_mode_class() works correctly")

def test_get_required_satellite():
    """Test getting required satellite types."""
    from modes.manifest import get_required_satellite
    
    assert get_required_satellite("JEBRIS") is None
    assert get_required_satellite("SIMON") is None
    assert get_required_satellite("SAFE") is None
    assert get_required_satellite("IND") == "INDUSTRIAL"
    assert get_required_satellite("NONEXISTENT") is None
    
    print("✓ get_required_satellite() works correctly")

def test_is_mode_available():
    """Test mode availability checking."""
    from modes.manifest import is_mode_available
    
    # Test with no satellites
    assert is_mode_available("JEBRIS", {}) is True
    assert is_mode_available("SIMON", {}) is True
    assert is_mode_available("SAFE", {}) is True
    assert is_mode_available("IND", {}) is False
    
    # Test with industrial satellite
    satellites = {"01": MockSatellite("INDUSTRIAL")}
    assert is_mode_available("JEBRIS", satellites) is True
    assert is_mode_available("IND", satellites) is True
    
    # Test with wrong satellite type
    satellites = {"01": MockSatellite("OTHER_TYPE")}
    assert is_mode_available("IND", satellites) is False
    
    print("✓ is_mode_available() works correctly")

def test_get_available_modes():
    """Test getting list of available modes."""
    from modes.manifest import get_available_modes
    
    # Test with no satellites
    available = get_available_modes({})
    assert "JEBRIS" in available
    assert "SIMON" in available
    assert "SAFE" in available
    assert "IND" not in available
    
    # Test with industrial satellite
    satellites = {"01": MockSatellite("INDUSTRIAL")}
    available = get_available_modes(satellites)
    assert "JEBRIS" in available
    assert "SIMON" in available
    assert "SAFE" in available
    assert "IND" in available
    
    print("✓ get_available_modes() works correctly")

def test_mode_settings():
    """Test that mode settings are properly defined."""
    from modes.manifest import MODE_REGISTRY
    
    # JEBRIS should have difficulty and music settings
    jebris = MODE_REGISTRY["JEBRIS"]
    assert len(jebris["settings"]) == 2
    assert jebris["settings"][0]["key"] == "difficulty"
    assert jebris["settings"][1]["key"] == "music"
    
    # SIMON should have mode and difficulty settings
    simon = MODE_REGISTRY["SIMON"]
    assert len(simon["settings"]) == 2
    assert simon["settings"][0]["key"] == "mode"
    assert simon["settings"][1]["key"] == "difficulty"
    
    # SAFE should have no settings
    safe = MODE_REGISTRY["SAFE"]
    assert len(safe["settings"]) == 0
    
    # IND should have no settings
    ind = MODE_REGISTRY["IND"]
    assert len(ind["settings"]) == 0
    
    print("✓ Mode settings are properly defined")

if __name__ == "__main__":
    print("Testing mode manifest functionality...")
    print()
    
    try:
        test_mode_registry_structure()
        test_get_mode_class()
        test_get_required_satellite()
        test_is_mode_available()
        test_get_available_modes()
        test_mode_settings()
        
        print()
        print("=" * 50)
        print("All tests passed! ✓")
        print("=" * 50)
    except AssertionError as e:
        print()
        print("=" * 50)
        print(f"Test failed: {e}")
        print("=" * 50)
        sys.exit(1)
    except Exception as e:
        print()
        print("=" * 50)
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 50)
        sys.exit(1)
