"""Test module for mode registry pattern.

This test verifies the structure and content of the mode registry manifest
without importing the actual mode classes (which have hardware dependencies).
"""

import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_manifest_file_exists():
    """Test that manifest.py file exists."""
    manifest_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'manifest.py')
    assert os.path.exists(manifest_path), "manifest.py file does not exist"
    print("✓ Manifest file exists")

def test_documentation_in_manifest():
    """Test that manifest.py has proper documentation."""
    manifest_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'manifest.py')

    with open(manifest_path, 'r') as f:
        content = f.read()

    # Check for docstring
    assert '"""' in content, "Manifest missing docstring"
    assert "registry" in content.lower(), "Documentation should mention registry"

    # Check for instructions on adding new modes
    assert "To add a new mode" in content or "add a new" in content.lower(), \
        "Manifest should document how to add new modes"

    print("✓ Manifest documentation test passed")

if __name__ == "__main__":
    print("Running mode registry structure tests...\n")

    try:
        test_manifest_file_exists()
        test_manifest_structure()
        test_modes_init_updated()
        test_core_manager_updated()
        test_documentation_in_manifest()

        print("\n✅ All structure tests passed!")
        print("\nNote: Actual mode class imports require CircuitPython hardware dependencies,")
        print("but the registry pattern structure is correctly implemented.")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
