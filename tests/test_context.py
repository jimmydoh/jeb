#!/usr/bin/env python3
"""Unit tests for HardwareContext utility."""

import sys
import os

# Add src/utilities to path for direct module import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'utilities'))

# Import context module directly
import context


class MockComponent:
    """Mock hardware component for testing."""
    def __init__(self, name):
        self.name = name
    
    def __repr__(self):
        return f"MockComponent({self.name})"


def test_hardware_context_initialization():
    """Test HardwareContext initialization with all None parameters."""
    print("Testing HardwareContext initialization with defaults...")
    
    ctx = context.HardwareContext()
    
    assert ctx.audio is None, "Default audio should be None"
    assert ctx.matrix is None, "Default matrix should be None"
    assert ctx.hid is None, "Default hid should be None"
    assert ctx.leds is None, "Default leds should be None"
    
    print("✓ HardwareContext initialization test passed")


def test_hardware_context_with_components():
    """Test HardwareContext initialization with provided components."""
    print("\nTesting HardwareContext with components...")
    
    audio = MockComponent("audio")
    matrix = MockComponent("matrix")
    hid = MockComponent("hid")
    leds = MockComponent("leds")
    
    ctx = context.HardwareContext(
        audio=audio,
        matrix=matrix,
        hid=hid,
        leds=leds
    )
    
    assert ctx.audio is audio, f"Expected audio to be {audio}, got {ctx.audio}"
    assert ctx.matrix is matrix, f"Expected matrix to be {matrix}, got {ctx.matrix}"
    assert ctx.hid is hid, f"Expected hid to be {hid}, got {ctx.hid}"
    assert ctx.leds is leds, f"Expected leds to be {leds}, got {ctx.leds}"
    
    print("✓ HardwareContext with components test passed")


def test_hardware_context_partial_components():
    """Test HardwareContext with only some components provided."""
    print("\nTesting HardwareContext with partial components...")
    
    audio = MockComponent("audio")
    hid = MockComponent("hid")
    
    ctx = context.HardwareContext(audio=audio, hid=hid)
    
    assert ctx.audio is audio, f"Expected audio to be {audio}, got {ctx.audio}"
    assert ctx.hid is hid, f"Expected hid to be {hid}, got {ctx.hid}"
    assert ctx.matrix is None, "Matrix should be None when not provided"
    assert ctx.leds is None, "LEDs should be None when not provided"
    
    print("✓ HardwareContext partial components test passed")


def test_hardware_context_attribute_assignment():
    """Test that HardwareContext attributes can be modified after creation."""
    print("\nTesting HardwareContext attribute assignment...")
    
    ctx = context.HardwareContext()
    
    # Initially all None
    assert ctx.audio is None
    
    # Assign new component
    audio = MockComponent("audio")
    ctx.audio = audio
    
    assert ctx.audio is audio, f"Expected audio to be {audio} after assignment"
    
    # Replace component
    new_audio = MockComponent("new_audio")
    ctx.audio = new_audio
    
    assert ctx.audio is new_audio, f"Expected audio to be {new_audio} after replacement"
    
    print("✓ HardwareContext attribute assignment test passed")


def test_hardware_context_multiple_instances():
    """Test that multiple HardwareContext instances are independent."""
    print("\nTesting multiple HardwareContext instances...")
    
    audio1 = MockComponent("audio1")
    audio2 = MockComponent("audio2")
    
    ctx1 = context.HardwareContext(audio=audio1)
    ctx2 = context.HardwareContext(audio=audio2)
    
    assert ctx1.audio is audio1, "First context should have audio1"
    assert ctx2.audio is audio2, "Second context should have audio2"
    assert ctx1.audio is not ctx2.audio, "Contexts should be independent"
    
    # Modify one shouldn't affect the other
    ctx1.audio = None
    assert ctx1.audio is None, "First context audio should be None"
    assert ctx2.audio is audio2, "Second context should still have audio2"
    
    print("✓ Multiple HardwareContext instances test passed")


def test_hardware_context_all_attributes_accessible():
    """Test that all expected attributes are accessible."""
    print("\nTesting all HardwareContext attributes are accessible...")
    
    ctx = context.HardwareContext()
    
    # Check that all attributes exist and can be accessed
    try:
        _ = ctx.audio
        _ = ctx.matrix
        _ = ctx.hid
        _ = ctx.leds
    except AttributeError as e:
        raise AssertionError(f"Attribute not accessible: {e}")
    
    print("✓ All HardwareContext attributes accessible test passed")


def test_hardware_context_keyword_order():
    """Test that keyword argument order doesn't matter."""
    print("\nTesting HardwareContext keyword argument order...")
    
    audio = MockComponent("audio")
    matrix = MockComponent("matrix")
    hid = MockComponent("hid")
    leds = MockComponent("leds")
    
    # Create with different keyword order
    ctx = context.HardwareContext(
        leds=leds,
        audio=audio,
        hid=hid,
        matrix=matrix
    )
    
    assert ctx.audio is audio, "Audio should be assigned correctly regardless of order"
    assert ctx.matrix is matrix, "Matrix should be assigned correctly regardless of order"
    assert ctx.hid is hid, "HID should be assigned correctly regardless of order"
    assert ctx.leds is leds, "LEDs should be assigned correctly regardless of order"
    
    print("✓ HardwareContext keyword order test passed")


def test_hardware_context_with_real_types():
    """Test HardwareContext with different types of objects."""
    print("\nTesting HardwareContext with different object types...")
    
    # Test with different types of objects
    ctx = context.HardwareContext(
        audio={"volume": 0.5},
        matrix=[1, 2, 3],
        hid="keyboard",
        leds=42
    )
    
    assert ctx.audio == {"volume": 0.5}, "Should handle dict type"
    assert ctx.matrix == [1, 2, 3], "Should handle list type"
    assert ctx.hid == "keyboard", "Should handle string type"
    assert ctx.leds == 42, "Should handle int type"
    
    print("✓ HardwareContext with different types test passed")


def run_all_tests():
    """Run all context tests."""
    print("=" * 60)
    print("HardwareContext Test Suite")
    print("=" * 60)
    
    try:
        test_hardware_context_initialization()
        test_hardware_context_with_components()
        test_hardware_context_partial_components()
        test_hardware_context_attribute_assignment()
        test_hardware_context_multiple_instances()
        test_hardware_context_all_attributes_accessible()
        test_hardware_context_keyword_order()
        test_hardware_context_with_real_types()
        
        print("\n" + "=" * 60)
        print("✓ All context tests passed!")
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
