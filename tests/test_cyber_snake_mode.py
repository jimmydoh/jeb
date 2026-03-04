"""Test module for Cyber Snake mode registry entry.

This test verifies the Cyber Snake mode is correctly registered in the manifest
without importing the actual mode class (which has hardware dependencies).
"""

import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_cyber_snake_mode_file_exists():
    """Test that cyber_snake.py file exists."""
    cyber_snake_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'cyber_snake.py')
    assert os.path.exists(cyber_snake_path), "cyber_snake.py file does not exist"
    print("✓ Cyber Snake mode file exists")

def test_cyber_snake_in_manifest():
    """Test that Cyber Snake mode is registered in manifest."""
    from modes.manifest import MODE_REGISTRY
    
    assert "SNAKE" in MODE_REGISTRY, "SNAKE mode not found in MODE_REGISTRY"
    print("✓ SNAKE mode found in registry")
    
    snake_metadata = MODE_REGISTRY["SNAKE"]
    
    # Check required fields
    assert snake_metadata["id"] == "SNAKE", "SNAKE mode ID incorrect"
    assert snake_metadata["name"] == "CYBER SNAKE", "SNAKE mode name incorrect"
    assert snake_metadata["module_path"] == "modes.cyber_snake", "SNAKE module path incorrect"
    assert snake_metadata["class_name"] == "CyberSnakeMode", "SNAKE class name incorrect"
    assert snake_metadata["icon"] == "SNAKE", "SNAKE icon incorrect"
    assert "CORE" in snake_metadata["requires"], "SNAKE should require CORE"
    
    print("✓ SNAKE mode metadata is correct")

def test_cyber_snake_settings():
    """Test that Cyber Snake mode has difficulty and edges settings."""
    from modes.manifest import MODE_REGISTRY
    
    snake_metadata = MODE_REGISTRY["SNAKE"]
    assert "settings" in snake_metadata, "SNAKE mode missing settings"
    
    settings = snake_metadata["settings"]
    assert len(settings) >= 2, "SNAKE mode should have at least two settings (difficulty and edges)"
    
    # Check for difficulty setting
    difficulty_setting = next((s for s in settings if s["key"] == "difficulty"), None)
    assert difficulty_setting is not None, "SNAKE mode should have difficulty setting"
    assert "NORMAL" in difficulty_setting["options"], "Missing NORMAL difficulty"
    assert "HARD" in difficulty_setting["options"], "Missing HARD difficulty"
    assert "INSANE" in difficulty_setting["options"], "Missing INSANE difficulty"
    assert difficulty_setting["default"] == "NORMAL", "Default difficulty should be NORMAL"
    
    # Check for edges setting
    edges_setting = next((s for s in settings if s["key"] == "edges"), None)
    assert edges_setting is not None, "SNAKE mode should have edges setting"
    assert "WRAP" in edges_setting["options"], "Missing WRAP edge mode"
    assert "WALLS" in edges_setting["options"], "Missing WALLS edge mode"
    assert edges_setting["default"] == "WRAP", "Default edges should be WRAP"
    
    print("✓ SNAKE mode settings are correct (difficulty and edges)")

def test_cyber_snake_icon_exists():
    """Test that SNAKE icon exists in icon library."""
    from utilities.icons import Icons
    
    assert "SNAKE" in Icons.ICON_LIBRARY, "SNAKE icon not found in ICON_LIBRARY"
    
    print("✓ SNAKE icon exists")

def test_cyber_snake_imports():
    """Test that the module can be imported without errors (syntax check)."""
    try:
        # Just check that the file has valid Python syntax by attempting to compile it
        cyber_snake_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'cyber_snake.py')
        with open(cyber_snake_path, 'r') as f:
            code = f.read()
        compile(code, cyber_snake_path, 'exec')
        print("✓ Cyber Snake module has valid Python syntax")
    except SyntaxError as e:
        raise AssertionError(f"Syntax error in cyber_snake.py: {e}")

if __name__ == "__main__":
    print("Running Cyber Snake mode registry tests...\n")
    
    try:
        test_cyber_snake_mode_file_exists()
        test_cyber_snake_in_manifest()
        test_cyber_snake_settings()
        test_cyber_snake_icon_exists()
        test_cyber_snake_imports()
        
        print("\n✅ All Cyber Snake mode tests passed!")
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
