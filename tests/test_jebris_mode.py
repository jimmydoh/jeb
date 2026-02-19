"""Test module for Jebris mode registry entry and 16x16 matrix support.

This test verifies the Jebris mode is correctly registered in the manifest
and properly configured for 16x16 matrix gameplay.
"""

import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_jebris_mode_file_exists():
    """Test that jebris.py file exists."""
    jebris_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'jebris.py')
    assert os.path.exists(jebris_path), "jebris.py file does not exist"
    print("✓ Jebris mode file exists")

def test_jebris_in_manifest():
    """Test that Jebris mode is registered in manifest."""
    from modes.manifest import MODE_REGISTRY
    
    assert "JEBRIS" in MODE_REGISTRY, "JEBRIS mode not found in MODE_REGISTRY"
    print("✓ JEBRIS mode found in registry")
    
    jebris_metadata = MODE_REGISTRY["JEBRIS"]
    
    # Check required fields
    assert jebris_metadata["id"] == "JEBRIS", "JEBRIS mode ID incorrect"
    assert jebris_metadata["name"] == "JEBRIS", "JEBRIS mode name incorrect"
    assert jebris_metadata["module_path"] == "modes.jebris", "JEBRIS module path incorrect"
    assert jebris_metadata["class_name"] == "JEBris", "JEBRIS class name incorrect"
    assert jebris_metadata["icon"] == "JEBRIS", "JEBRIS icon incorrect"
    assert "CORE" in jebris_metadata["requires"], "JEBRIS should require CORE"
    
    print("✓ JEBRIS mode metadata is correct")

def test_jebris_settings():
    """Test that Jebris mode has difficulty and music settings."""
    from modes.manifest import MODE_REGISTRY
    
    jebris_metadata = MODE_REGISTRY["JEBRIS"]
    assert "settings" in jebris_metadata, "JEBRIS mode missing settings"
    
    settings = jebris_metadata["settings"]
    assert len(settings) >= 2, "JEBRIS mode should have at least two settings (difficulty and music)"
    
    # Check for difficulty setting
    difficulty_setting = next((s for s in settings if s["key"] == "difficulty"), None)
    assert difficulty_setting is not None, "JEBRIS mode should have difficulty setting"
    assert "EASY" in difficulty_setting["options"], "Missing EASY difficulty"
    assert "NORMAL" in difficulty_setting["options"], "Missing NORMAL difficulty"
    assert "HARD" in difficulty_setting["options"], "Missing HARD difficulty"
    assert "INSANE" in difficulty_setting["options"], "Missing INSANE difficulty"
    assert difficulty_setting["default"] == "NORMAL", "Default difficulty should be NORMAL"
    
    # Check for music setting
    music_setting = next((s for s in settings if s["key"] == "music"), None)
    assert music_setting is not None, "JEBRIS mode should have music setting"
    assert "ON" in music_setting["options"], "Missing ON option for music"
    assert "OFF" in music_setting["options"], "Missing OFF option for music"
    assert music_setting["default"] == "ON", "Default music should be ON"
    
    print("✓ JEBRIS mode settings are correct (difficulty and music)")

def test_jebris_icon_exists():
    """Test that JEBRIS icon exists in icon library."""
    from utilities.icons import Icons
    
    assert "JEBRIS" in Icons.ICON_LIBRARY, "JEBRIS icon not found in ICON_LIBRARY"
    
    jebris_icon = Icons.ICON_LIBRARY["JEBRIS"]
    # Icon can be 64 (8x8) or 256 (16x16) pixels
    assert len(jebris_icon) in [64, 256], f"JEBRIS icon should have 64 (8x8) or 256 (16x16) pixels, found {len(jebris_icon)}"
    
    print(f"✓ JEBRIS icon exists and has correct dimensions ({len(jebris_icon)} pixels)")

def test_jebris_16x16_configuration():
    """Test that jebris.py is configured for 16x16 matrix with proper constants."""
    jebris_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'jebris.py')
    with open(jebris_path, 'r') as f:
        code = f.read()
    
    # Verify docstring mentions 16x16
    assert "16x16" in code, "Jebris mode should mention 16x16 in documentation"
    
    # Verify no hardcoded 8x8 dimensions in critical areas
    assert "self.width = 8" not in code, "Jebris should not have hardcoded width = 8"
    assert "self.height = 8" not in code, "Jebris should not have hardcoded height = 8"
    
    # Verify use of matrix dimensions
    assert "self.core.matrix.width" in code, "Jebris should use self.core.matrix.width"
    assert "self.core.matrix.height" in code, "Jebris should use self.core.matrix.height"
    
    # Verify playfield configuration
    assert "self.playfield_width" in code, "Jebris should define playfield_width"
    assert "self.playfield_height" in code, "Jebris should define playfield_height"
    assert "playfield_width = 10" in code, "Jebris playfield should be 10 columns wide"
    
    # Verify next piece preview
    assert "next_piece" in code, "Jebris should have next piece tracking"
    assert "draw_next_piece_preview" in code, "Jebris should have next piece preview method"
    
    print("✓ JEBRIS mode properly configured for 16x16 matrix")
    print("  - Uses dynamic matrix dimensions from core.matrix")
    print("  - Has 10-column playfield")
    print("  - Includes next piece preview")

def test_jebris_imports():
    """Test that the module has valid Python syntax."""
    try:
        jebris_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'jebris.py')
        with open(jebris_path, 'r') as f:
            code = f.read()
        compile(code, jebris_path, 'exec')
        print("✓ Jebris module has valid Python syntax")
    except SyntaxError as e:
        raise AssertionError(f"Syntax error in jebris.py: {e}")

if __name__ == "__main__":
    print("Running Jebris mode tests...\n")
    
    try:
        test_jebris_mode_file_exists()
        test_jebris_in_manifest()
        test_jebris_settings()
        test_jebris_icon_exists()
        test_jebris_16x16_configuration()
        test_jebris_imports()
        
        print("\n✅ All Jebris mode tests passed!")
        print("\nNote: Actual mode class functionality requires CircuitPython hardware,")
        print("but the registry integration and 16x16 configuration are correctly implemented.")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
