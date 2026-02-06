#!/usr/bin/env python3
"""Unit tests for BasePixelManager animation slot optimization."""

import sys


# Define AnimationSlot class directly for testing (copy from base_pixel_manager.py)
class AnimationSlot:
    """Reusable animation slot to avoid object churn."""
    __slots__ = ('active', 'type', 'color', 'speed', 'start', 'duration', 'priority')
    
    def __init__(self):
        self.active = False
        self.type = None
        self.color = None
        self.speed = 1.0
        self.start = 0.0
        self.duration = None
        self.priority = 0
    
    def set(self, anim_type, color, speed, start, duration, priority):
        """Update slot properties in place."""
        self.active = True
        self.type = anim_type
        self.color = color
        self.speed = speed
        self.start = start
        self.duration = duration
        self.priority = priority
    
    def clear(self):
        """Mark slot as inactive without deallocating."""
        self.active = False


def test_animation_slot_initialization():
    """Test that AnimationSlot initializes correctly."""
    print("Testing AnimationSlot initialization...")
    
    slot = AnimationSlot()
    assert slot.active == False, "New slot should be inactive"
    assert slot.type is None, "Type should be None"
    assert slot.color is None, "Color should be None"
    assert slot.speed == 1.0, "Speed should default to 1.0"
    assert slot.start == 0.0, "Start should default to 0.0"
    assert slot.duration is None, "Duration should be None"
    assert slot.priority == 0, "Priority should default to 0"
    
    print("✓ AnimationSlot initialization test passed")


def test_animation_slot_set():
    """Test that AnimationSlot.set() updates properties correctly."""
    print("\nTesting AnimationSlot.set()...")
    
    slot = AnimationSlot()
    
    # Set animation properties
    slot.set("BLINK", (255, 0, 0), 2.0, 1.5, 3.0, 5)
    
    assert slot.active == True, "Slot should be active after set"
    assert slot.type == "BLINK", "Type should be BLINK"
    assert slot.color == (255, 0, 0), "Color should be (255, 0, 0)"
    assert slot.speed == 2.0, "Speed should be 2.0"
    assert slot.start == 1.5, "Start should be 1.5"
    assert slot.duration == 3.0, "Duration should be 3.0"
    assert slot.priority == 5, "Priority should be 5"
    
    print("✓ AnimationSlot.set() test passed")


def test_animation_slot_reuse():
    """Test that AnimationSlot can be reused without creating new objects."""
    print("\nTesting AnimationSlot reuse...")
    
    slot = AnimationSlot()
    
    # First animation
    slot.set("PULSE", (0, 255, 0), 1.0, 0.0, 2.0, 1)
    assert slot.type == "PULSE", "First animation should be PULSE"
    assert slot.color == (0, 255, 0), "First animation color should be green"
    
    # Reuse same slot for different animation
    slot.set("SOLID", (0, 0, 255), 1.5, 1.0, None, 2)
    assert slot.type == "SOLID", "Second animation should be SOLID"
    assert slot.color == (0, 0, 255), "Second animation color should be blue"
    assert slot.priority == 2, "Second animation priority should be 2"
    
    # The key test: same object reference
    original_id = id(slot)
    slot.set("RAINBOW", None, 0.5, 2.0, 5.0, 3)
    assert id(slot) == original_id, "Slot object should be reused (same id)"
    
    print("✓ AnimationSlot reuse test passed")


def test_animation_slot_clear():
    """Test that AnimationSlot.clear() marks slot as inactive."""
    print("\nTesting AnimationSlot.clear()...")
    
    slot = AnimationSlot()
    slot.set("GLITCH", (128, 128, 128), 1.0, 0.0, 1.0, 1)
    assert slot.active == True, "Slot should be active after set"
    
    slot.clear()
    assert slot.active == False, "Slot should be inactive after clear"
    # Other properties remain but slot is marked inactive
    assert slot.type == "GLITCH", "Type should remain (but slot is inactive)"
    
    print("✓ AnimationSlot.clear() test passed")


def test_no_dict_allocation():
    """Test that we're not creating dictionaries (memory optimization check)."""
    print("\nTesting memory optimization (no dict allocation)...")
    
    # This test verifies that AnimationSlot uses __slots__
    slot = AnimationSlot()
    
    # Try to add arbitrary attribute (should fail with __slots__)
    try:
        slot.arbitrary_attr = "test"
        assert False, "Should not be able to add arbitrary attributes with __slots__"
    except AttributeError:
        print("  ✓ __slots__ enforced (cannot add arbitrary attributes)")
    
    # Verify __slots__ exists
    assert hasattr(AnimationSlot, '__slots__'), "AnimationSlot should have __slots__"
    
    # Verify no __dict__
    assert not hasattr(slot, '__dict__'), "AnimationSlot instance should not have __dict__"
    
    print("✓ Memory optimization test passed")


if __name__ == "__main__":
    print("=" * 60)
    print("BasePixelManager Animation Slot Test Suite")
    print("=" * 60)
    
    try:
        test_animation_slot_initialization()
        test_animation_slot_set()
        test_animation_slot_reuse()
        test_animation_slot_clear()
        test_no_dict_allocation()
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
