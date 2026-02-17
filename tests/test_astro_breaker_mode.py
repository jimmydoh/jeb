"""Test module for Astro Breaker mode registry entry.

This test verifies the Astro Breaker mode is correctly registered in the manifest
without importing the actual mode class (which has hardware dependencies).
"""

import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_astro_breaker_mode_file_exists():
    """Test that astro_breaker.py file exists."""
    astro_breaker_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'astro_breaker.py')
    assert os.path.exists(astro_breaker_path), "astro_breaker.py file does not exist"
    print("✓ Astro Breaker mode file exists")

def test_astro_breaker_in_manifest():
    """Test that Astro Breaker mode is registered in manifest."""
    from modes.manifest import MODE_REGISTRY
    
    assert "ASTRO_BREAKER" in MODE_REGISTRY, "ASTRO_BREAKER mode not found in MODE_REGISTRY"
    print("✓ ASTRO_BREAKER mode found in registry")
    
    astro_breaker_metadata = MODE_REGISTRY["ASTRO_BREAKER"]
    
    # Check required fields
    assert astro_breaker_metadata["id"] == "ASTRO_BREAKER", "ASTRO_BREAKER mode ID incorrect"
    assert astro_breaker_metadata["name"] == "ASTRO BREAKER", "ASTRO_BREAKER mode name incorrect"
    assert astro_breaker_metadata["module_path"] == "modes.astro_breaker", "ASTRO_BREAKER module path incorrect"
    assert astro_breaker_metadata["class_name"] == "AstroBreaker", "ASTRO_BREAKER class name incorrect"
    assert astro_breaker_metadata["icon"] == "ASTRO_BREAKER", "ASTRO_BREAKER icon incorrect"
    assert "CORE" in astro_breaker_metadata["requires"], "ASTRO_BREAKER should require CORE"
    
    print("✓ ASTRO_BREAKER mode metadata is correct")

def test_astro_breaker_difficulty_settings():
    """Test that Astro Breaker mode has difficulty settings."""
    from modes.manifest import MODE_REGISTRY
    
    astro_breaker_metadata = MODE_REGISTRY["ASTRO_BREAKER"]
    assert "settings" in astro_breaker_metadata, "ASTRO_BREAKER mode missing settings"
    
    settings = astro_breaker_metadata["settings"]
    assert len(settings) >= 1, "ASTRO_BREAKER mode should have at least one setting (difficulty)"
    
    # Check for difficulty setting
    difficulty_setting = next((s for s in settings if s["key"] == "difficulty"), None)
    assert difficulty_setting is not None, "ASTRO_BREAKER mode should have difficulty setting"
    assert "NORMAL" in difficulty_setting["options"], "Missing NORMAL difficulty"
    assert "HARD" in difficulty_setting["options"], "Missing HARD difficulty"
    assert "INSANE" in difficulty_setting["options"], "Missing INSANE difficulty"
    assert difficulty_setting["default"] == "NORMAL", "Default difficulty should be NORMAL"
    
    print("✓ ASTRO_BREAKER mode settings are correct (difficulty)")

def test_astro_breaker_icon_exists():
    """Test that ASTRO_BREAKER icon exists in icon library."""
    from utilities.icons import Icons
    
    assert "ASTRO_BREAKER" in Icons.ICON_LIBRARY, "ASTRO_BREAKER icon not found in ICON_LIBRARY"
    
    astro_breaker_icon = Icons.ICON_LIBRARY["ASTRO_BREAKER"]
    assert len(astro_breaker_icon) == 64, "ASTRO_BREAKER icon should have 64 pixels (8x8 matrix)"
    
    print("✓ ASTRO_BREAKER icon exists and has correct dimensions")

def test_astro_breaker_imports():
    """Test that the module can be imported without errors (syntax check)."""
    try:
        # Just check that the file has valid Python syntax by attempting to compile it
        astro_breaker_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'astro_breaker.py')
        with open(astro_breaker_path, 'r') as f:
            code = f.read()
        compile(code, astro_breaker_path, 'exec')
        print("✓ Astro Breaker module has valid Python syntax")
    except SyntaxError as e:
        raise AssertionError(f"Syntax error in astro_breaker.py: {e}")

if __name__ == "__main__":
    print("Running Astro Breaker mode registry tests...\n")
    
    try:
        test_astro_breaker_mode_file_exists()
        test_astro_breaker_in_manifest()
        test_astro_breaker_difficulty_settings()
        test_astro_breaker_icon_exists()
        test_astro_breaker_imports()
        
        print("\n✅ All Astro Breaker mode tests passed!")
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
