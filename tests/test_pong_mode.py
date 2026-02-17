"""Test module for Pong mode registry entry.

This test verifies the Pong mode is correctly registered in the manifest
without importing the actual mode class (which has hardware dependencies).
"""

import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_pong_mode_file_exists():
    """Test that pong.py file exists."""
    pong_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'pong.py')
    assert os.path.exists(pong_path), "pong.py file does not exist"
    print("✓ Pong mode file exists")

def test_pong_in_manifest():
    """Test that Pong mode is registered in manifest."""
    from modes.manifest import MODE_REGISTRY
    
    assert "PONG" in MODE_REGISTRY, "PONG mode not found in MODE_REGISTRY"
    print("✓ PONG mode found in registry")
    
    pong_metadata = MODE_REGISTRY["PONG"]
    
    # Check required fields
    assert pong_metadata["id"] == "PONG", "PONG mode ID incorrect"
    assert pong_metadata["name"] == "MINI PONG", "PONG mode name incorrect"
    assert pong_metadata["module_path"] == "modes.pong", "PONG module path incorrect"
    assert pong_metadata["class_name"] == "PongMode", "PONG class name incorrect"
    assert pong_metadata["icon"] == "pong", "PONG icon incorrect"
    assert "CORE" in pong_metadata["requires"], "PONG should require CORE"
    
    print("✓ PONG mode metadata is correct")

def test_pong_difficulty_settings():
    """Test that Pong mode has difficulty settings."""
    from modes.manifest import MODE_REGISTRY
    
    pong_metadata = MODE_REGISTRY["PONG"]
    assert "settings" in pong_metadata, "PONG mode missing settings"
    
    settings = pong_metadata["settings"]
    assert len(settings) >= 2, "PONG mode should have at least two settings (mode and difficulty)"
    
    # Check for mode setting
    mode_setting = next((s for s in settings if s["key"] == "mode"), None)
    assert mode_setting is not None, "PONG mode should have mode setting"
    assert "1P" in mode_setting["options"], "Missing 1P mode"
    assert "2P" in mode_setting["options"], "Missing 2P mode"
    assert mode_setting["default"] == "1P", "Default mode should be 1P"
    
    # Check for difficulty setting
    difficulty_setting = next((s for s in settings if s["key"] == "difficulty"), None)
    assert difficulty_setting is not None, "PONG mode should have difficulty setting"
    assert "EASY" in difficulty_setting["options"], "Missing EASY difficulty"
    assert "NORMAL" in difficulty_setting["options"], "Missing NORMAL difficulty"
    assert "HARD" in difficulty_setting["options"], "Missing HARD difficulty"
    assert "INSANE" in difficulty_setting["options"], "Missing INSANE difficulty"
    assert difficulty_setting["default"] == "NORMAL", "Default difficulty should be NORMAL"
    
    print("✓ PONG mode settings are correct (mode and difficulty)")

def test_pong_optional_satellite():
    """Test that Pong mode has optional INDUSTRIAL satellite."""
    from modes.manifest import MODE_REGISTRY
    
    pong_metadata = MODE_REGISTRY["PONG"]
    assert "optional" in pong_metadata, "PONG mode missing optional field"
    assert "INDUSTRIAL" in pong_metadata["optional"], "PONG mode should list INDUSTRIAL as optional"
    
    print("✓ PONG mode has optional INDUSTRIAL satellite")

def test_pong_icon_exists():
    """Test that PONG icon exists in icon library."""
    from utilities.icons import Icons
    
    assert "PONG" in Icons.ICON_LIBRARY, "PONG icon not found in ICON_LIBRARY"
    
    pong_icon = Icons.ICON_LIBRARY["PONG"]
    assert len(pong_icon) == 64, "PONG icon should have 64 pixels (8x8 matrix)"
    
    print("✓ PONG icon exists and has correct dimensions")

if __name__ == "__main__":
    print("Running Pong mode registry tests...\n")
    
    try:
        test_pong_mode_file_exists()
        test_pong_in_manifest()
        test_pong_difficulty_settings()
        test_pong_optional_satellite()
        test_pong_icon_exists()
        
        print("\n✅ All Pong mode tests passed!")
        print("\nNote: Actual mode class functionality requires CircuitPython hardware,")
        print("but the registry integration is correctly implemented.")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
