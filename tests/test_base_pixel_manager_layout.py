#!/usr/bin/env python3
"""Unit tests for BasePixelManager shape/layout awareness."""

import sys
import pytest


# Mock JEBPixel for testing
class MockJEBPixel:
    """Mock JEBPixel wrapper for testing."""
    def __init__(self, num_pixels=10):
        self.n = num_pixels
        self._pixels = [(0, 0, 0)] * num_pixels

    def __setitem__(self, idx, color):
        if 0 <= idx < self.n:
            self._pixels[idx] = color

    def __getitem__(self, idx):
        return self._pixels[idx]

    def fill(self, color):
        self._pixels = [color] * self.n

    def show(self):
        pass  # Mock - does nothing


# Import after mocks are defined
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

# Import directly to avoid __init__.py which has CircuitPython dependencies
import importlib.util
spec = importlib.util.spec_from_file_location(
    "base_pixel_manager", 
    os.path.join(os.path.dirname(__file__), '..', 'src', 'managers', 'base_pixel_manager.py')
)
base_pixel_manager_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base_pixel_manager_module)

BasePixelManager = base_pixel_manager_module.BasePixelManager
PixelLayout = base_pixel_manager_module.PixelLayout


def test_pixel_layout_enum():
    """Test that PixelLayout enum has expected values."""
    print("Testing PixelLayout enum...")
    
    assert hasattr(PixelLayout, 'LINEAR'), "PixelLayout should have LINEAR"
    assert hasattr(PixelLayout, 'MATRIX_2D'), "PixelLayout should have MATRIX_2D"
    assert hasattr(PixelLayout, 'CIRCLE'), "PixelLayout should have CIRCLE"
    assert hasattr(PixelLayout, 'CUSTOM'), "PixelLayout should have CUSTOM"
    
    assert PixelLayout.LINEAR.value == "linear"
    assert PixelLayout.MATRIX_2D.value == "matrix_2d"
    assert PixelLayout.CIRCLE.value == "circle"
    assert PixelLayout.CUSTOM.value == "custom"
    
    print("✓ PixelLayout enum test passed")


def test_base_pixel_manager_default_layout():
    """Test that BasePixelManager defaults to LINEAR layout."""
    print("\nTesting BasePixelManager default layout...")
    
    mock_pixel = MockJEBPixel(10)
    manager = BasePixelManager(mock_pixel)
    
    assert manager.get_layout_type() == PixelLayout.LINEAR, \
        "Default layout type should be LINEAR"
    assert manager.get_dimensions() == (10,), \
        "Default dimensions should be (num_pixels,)"
    
    print("✓ Default layout test passed")


def test_base_pixel_manager_linear_layout():
    """Test BasePixelManager with explicit LINEAR layout."""
    print("\nTesting BasePixelManager LINEAR layout...")
    
    mock_pixel = MockJEBPixel(20)
    manager = BasePixelManager(mock_pixel, layout_type=PixelLayout.LINEAR, dimensions=(20,))
    
    assert manager.get_layout_type() == PixelLayout.LINEAR
    assert manager.get_dimensions() == (20,)
    
    shape = manager.get_shape()
    assert shape['type'] == PixelLayout.LINEAR
    assert shape['dimensions'] == (20,)
    
    print("✓ LINEAR layout test passed")


def test_base_pixel_manager_matrix_layout():
    """Test BasePixelManager with MATRIX_2D layout."""
    print("\nTesting BasePixelManager MATRIX_2D layout...")
    
    mock_pixel = MockJEBPixel(64)
    manager = BasePixelManager(mock_pixel, layout_type=PixelLayout.MATRIX_2D, dimensions=(8, 8))
    
    assert manager.get_layout_type() == PixelLayout.MATRIX_2D
    assert manager.get_dimensions() == (8, 8)
    
    shape = manager.get_shape()
    assert shape['type'] == PixelLayout.MATRIX_2D
    assert shape['dimensions'] == (8, 8)
    
    print("✓ MATRIX_2D layout test passed")


def test_base_pixel_manager_circle_layout():
    """Test BasePixelManager with CIRCLE layout."""
    print("\nTesting BasePixelManager CIRCLE layout...")
    
    mock_pixel = MockJEBPixel(24)
    manager = BasePixelManager(mock_pixel, layout_type=PixelLayout.CIRCLE, dimensions=(12,))
    
    assert manager.get_layout_type() == PixelLayout.CIRCLE
    assert manager.get_dimensions() == (12,)
    
    shape = manager.get_shape()
    assert shape['type'] == PixelLayout.CIRCLE
    assert shape['dimensions'] == (12,)
    
    print("✓ CIRCLE layout test passed")


def test_base_pixel_manager_custom_layout():
    """Test BasePixelManager with CUSTOM layout."""
    print("\nTesting BasePixelManager CUSTOM layout...")
    
    mock_pixel = MockJEBPixel(50)
    manager = BasePixelManager(mock_pixel, layout_type=PixelLayout.CUSTOM, dimensions=(5, 10))
    
    assert manager.get_layout_type() == PixelLayout.CUSTOM
    assert manager.get_dimensions() == (5, 10)
    
    shape = manager.get_shape()
    assert shape['type'] == PixelLayout.CUSTOM
    assert shape['dimensions'] == (5, 10)
    
    print("✓ CUSTOM layout test passed")


def test_get_shape_returns_dict():
    """Test that get_shape returns a properly structured dict."""
    print("\nTesting get_shape() return structure...")
    
    mock_pixel = MockJEBPixel(64)
    manager = BasePixelManager(mock_pixel, layout_type=PixelLayout.MATRIX_2D, dimensions=(8, 8))
    
    shape = manager.get_shape()
    
    assert isinstance(shape, dict), "get_shape should return a dict"
    assert 'type' in shape, "shape dict should have 'type' key"
    assert 'dimensions' in shape, "shape dict should have 'dimensions' key"
    assert isinstance(shape['type'], PixelLayout), "shape['type'] should be PixelLayout enum"
    assert isinstance(shape['dimensions'], tuple), "shape['dimensions'] should be a tuple"
    
    print("✓ get_shape() structure test passed")


def test_layout_persists_after_operations():
    """Test that layout properties persist after animation operations."""
    print("\nTesting layout persistence...")
    
    mock_pixel = MockJEBPixel(64)
    manager = BasePixelManager(mock_pixel, layout_type=PixelLayout.MATRIX_2D, dimensions=(8, 8))
    
    # Perform some operations
    manager.set_animation(0, "SOLID", (255, 0, 0))
    manager.fill_animation("BLINK", (0, 255, 0))
    manager.clear_animation(0)
    manager.clear()
    
    # Layout should still be the same
    assert manager.get_layout_type() == PixelLayout.MATRIX_2D
    assert manager.get_dimensions() == (8, 8)
    
    print("✓ Layout persistence test passed")


if __name__ == "__main__":
    print("=" * 60)
    print("BasePixelManager Layout/Shape Awareness Test Suite")
    print("=" * 60)
    
    try:
        test_pixel_layout_enum()
        test_base_pixel_manager_default_layout()
        test_base_pixel_manager_linear_layout()
        test_base_pixel_manager_matrix_layout()
        test_base_pixel_manager_circle_layout()
        test_base_pixel_manager_custom_layout()
        test_get_shape_returns_dict()
        test_layout_persists_after_operations()
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)
        sys.exit(0)
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
