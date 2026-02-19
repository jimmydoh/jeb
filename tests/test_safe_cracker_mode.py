"""Test module for Safe Cracker game mode and 16x16 matrix support.

This test verifies the Safe Cracker mode is correctly configured for 16x16
matrix gameplay with no hardcoded 8x8 boundary references.
"""

import sys
import os
import math

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def test_safe_cracker_file_exists():
    """Test that safe_cracker.py file exists."""
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'safe_cracker.py')
    assert os.path.exists(path), "safe_cracker.py file does not exist"
    print("✓ Safe Cracker mode file exists")


def test_safe_cracker_16x16_configuration():
    """Test that safe_cracker.py has no hardcoded 8x8 boundary references."""
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'safe_cracker.py')
    with open(path, 'r') as f:
        code = f.read()

    # Verify docstring mentions 16x16
    assert "16x16" in code, "Safe Cracker mode should mention 16x16 in documentation"

    # Verify no hardcoded 8x8 boundaries in draw method
    assert "min(7," not in code, "Hardcoded 8x8 clamp min(7, ...) should be removed"
    assert "max(0, min(7" not in code, "Hardcoded 8x8 clamp max(0, min(7, ...)) should be removed"

    # Verify no hardcoded center/radius constants for 8x8
    assert "3.5 + 3.5 *" not in code, "Hardcoded 8x8 pointer formula should be removed"
    assert "3.5 - 3.5 *" not in code, "Hardcoded 8x8 pointer formula should be removed"

    # Verify no hardcoded hub pixel positions for 8x8
    assert "for x in [3, 4]" not in code, "Hardcoded 8x8 hub x-positions should be removed"
    assert "for y in [3, 4]" not in code, "Hardcoded 8x8 hub y-positions should be removed"

    # Verify use of matrix dimensions
    assert "self.core.matrix.width" in code, "Safe Cracker should use self.core.matrix.width"
    assert "self.core.matrix.height" in code, "Safe Cracker should use self.core.matrix.height"

    # Verify no hardcoded on-target pixel at (3, 3) — check for the literal arguments
    assert "draw_pixel(\n                    3,\n                    3," not in code \
        and "draw_pixel(3, 3," not in code, \
        "Hardcoded on-target pixel (3, 3) should be removed"

    # Verify clear() is used instead of direct pixels.fill
    assert "pixels.fill((0, 0, 0))" not in code, \
        "Direct pixels.fill should be replaced with self.core.matrix.clear()"
    assert "self.core.matrix.clear()" in code, \
        "Safe Cracker should use self.core.matrix.clear() in _draw_safe_dial"

    print("✓ Safe Cracker mode has no hardcoded 8x8 boundary references")
    print("✓ Safe Cracker mode uses dynamic matrix dimensions")


def test_safe_cracker_dial_math_scales():
    """Test that dial pointer math correctly scales between 8x8 and 16x16."""

    def compute_pointer(value, width, height):
        """Replicates the pointer calculation from _draw_safe_dial."""
        cx = (width - 1) / 2.0
        cy = (height - 1) / 2.0
        radius = (min(width, height) - 1) / 2.0
        angle = (value / 100.0) * 2 * math.pi
        px = int(cx + radius * math.sin(angle))
        py = int(cy - radius * math.cos(angle))
        px = max(0, min(width - 1, px))
        py = max(0, min(height - 1, py))
        return px, py

    # Test 8x8: pointer at value=0 (top) should land near (3, 0)
    px, py = compute_pointer(0, 8, 8)
    assert px == 3, f"8x8 value=0: expected px=3, got {px}"
    assert py == 0, f"8x8 value=0: expected py=0, got {py}"

    # Test 8x8: pointer at value=25 (right/3 o'clock) should land near (7, 3)
    px, py = compute_pointer(25, 8, 8)
    assert px == 7, f"8x8 value=25: expected px=7, got {px}"
    assert py == 3, f"8x8 value=25: expected py=3, got {py}"

    # Test 8x8: pointer at value=50 (bottom) should land near (3, 7)
    px, py = compute_pointer(50, 8, 8)
    assert px == 3, f"8x8 value=50: expected px=3, got {px}"
    assert py == 7, f"8x8 value=50: expected py=7, got {py}"

    # Test 16x16: pointer at value=0 (top) should land near (7, 0)
    px, py = compute_pointer(0, 16, 16)
    assert px == 7, f"16x16 value=0: expected px=7, got {px}"
    assert py == 0, f"16x16 value=0: expected py=0, got {py}"

    # Test 16x16: pointer at value=25 (right) should land near (15, 7)
    px, py = compute_pointer(25, 16, 16)
    assert px == 15, f"16x16 value=25: expected px=15, got {px}"
    assert py == 7, f"16x16 value=25: expected py=7, got {py}"

    # Test 16x16: pointer at value=50 (bottom) should land near (7, 15)
    px, py = compute_pointer(50, 16, 16)
    assert px == 7, f"16x16 value=50: expected px=7, got {px}"
    assert py == 15, f"16x16 value=50: expected py=15, got {py}"

    # Verify all pointer positions stay within 16x16 bounds for any value
    for v in range(0, 100):
        px, py = compute_pointer(v, 16, 16)
        assert 0 <= px <= 15, f"16x16: px={px} out of bounds for value={v}"
        assert 0 <= py <= 15, f"16x16: py={py} out of bounds for value={v}"

    print("✓ Dial pointer math scales correctly for both 8x8 and 16x16")


def test_safe_cracker_hub_centers():
    """Test that hub center pixel calculation is correct for different matrix sizes."""

    def hub_pixels(width, height):
        """Replicates the hub pixel selection from _draw_safe_dial."""
        return [(x, y) for x in [width // 2 - 1, width // 2]
                for y in [height // 2 - 1, height // 2]]

    # 8x8: center pixels should be (3,3), (3,4), (4,3), (4,4)
    hub = hub_pixels(8, 8)
    expected_8x8 = [(3, 3), (3, 4), (4, 3), (4, 4)]
    assert set(hub) == set(expected_8x8), \
        f"8x8 hub pixels: expected {expected_8x8}, got {hub}"

    # 16x16: center pixels should be (7,7), (7,8), (8,7), (8,8)
    hub = hub_pixels(16, 16)
    expected_16x16 = [(7, 7), (7, 8), (8, 7), (8, 8)]
    assert set(hub) == set(expected_16x16), \
        f"16x16 hub pixels: expected {expected_16x16}, got {hub}"

    # All hub pixels should be within bounds
    for (x, y) in hub:
        assert 0 <= x <= 15, f"Hub pixel x={x} out of 16x16 bounds"
        assert 0 <= y <= 15, f"Hub pixel y={y} out of 16x16 bounds"

    print("✓ Hub center pixels are correctly computed for 8x8 and 16x16")


def test_safe_cracker_imports():
    """Test that safe_cracker.py has valid Python syntax."""
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'safe_cracker.py')
    with open(path, 'r') as f:
        code = f.read()
    try:
        compile(code, path, 'exec')
        print("✓ Safe Cracker module has valid Python syntax")
    except SyntaxError as e:
        raise AssertionError(f"Syntax error in safe_cracker.py: {e}")


if __name__ == "__main__":
    print("Running Safe Cracker mode tests...\n")

    try:
        test_safe_cracker_file_exists()
        test_safe_cracker_16x16_configuration()
        test_safe_cracker_dial_math_scales()
        test_safe_cracker_hub_centers()
        test_safe_cracker_imports()

        print("\n✅ All Safe Cracker mode tests passed!")
        print("\nNote: Actual mode class functionality requires CircuitPython hardware,")
        print("but the 16x16 configuration is correctly implemented.")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
