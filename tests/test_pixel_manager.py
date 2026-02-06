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


# Mock BasePixelManager for testing clear_animation
class MockPixelObject:
    def __init__(self, n):
        self.n = n

class MockBasePixelManager:
    """Minimal mock of BasePixelManager to test clear_animation."""
    def __init__(self, num_pixels):
        self.num_pixels = num_pixels
        self.active_animations = [AnimationSlot() for _ in range(num_pixels)]
        self._active_count = 0
    
    def clear_animation(self, idx, priority=0):
        """Clear animation for a specific pixel."""
        if idx < 0 or idx >= self.num_pixels:
            return False
        
        slot = self.active_animations[idx]
        if slot.active:
            if priority < slot.priority:
                return False
            slot.clear()
            self._active_count -= 1
            return True
        return False
    
    def set_animation_for_test(self, idx, anim_type, priority):
        """Helper to set up animation for testing."""
        slot = self.active_animations[idx]
        if not slot.active:
            self._active_count += 1
        slot.set(anim_type, (255, 0, 0), 1.0, 0.0, None, priority)


def test_animation_slot_initialization():
    """Test that AnimationSlot initializes correctly."""
    print("Testing AnimationSlot initialization...")
    
    slot = AnimationSlot()
    assert not slot.active, "New slot should be inactive"
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
    
    assert slot.active, "Slot should be active after set"
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
    assert slot.active, "Slot should be active after set"
    
    slot.clear()
    assert not slot.active, "Slot should be inactive after clear"
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


def test_clear_animation_abstraction():
    """Test that clear_animation properly abstracts slot manipulation."""
    print("\nTesting clear_animation abstraction...")
    
    manager = MockBasePixelManager(5)
    
    # Test 1: Clear animation that doesn't exist returns False
    result = manager.clear_animation(0, priority=1)
    assert result is False, "Clearing inactive slot should return False"
    assert manager._active_count == 0, "Active count should be 0"
    
    # Test 2: Set and clear animation successfully
    manager.set_animation_for_test(0, "BLINK", priority=2)
    assert manager._active_count == 1, "Active count should be 1"
    result = manager.clear_animation(0, priority=2)
    assert result is True, "Clearing active slot with sufficient priority should return True"
    assert not manager.active_animations[0].active, "Slot should be inactive"
    assert manager._active_count == 0, "Active count should be decremented"
    
    # Test 3: Priority check - cannot clear higher priority animation
    manager.set_animation_for_test(1, "PULSE", priority=5)
    assert manager._active_count == 1, "Active count should be 1"
    result = manager.clear_animation(1, priority=3)
    assert result is False, "Clearing with insufficient priority should return False"
    assert manager.active_animations[1].active, "Slot should still be active"
    assert manager._active_count == 1, "Active count should remain 1"
    
    # Test 4: Clear with higher priority succeeds
    result = manager.clear_animation(1, priority=6)
    assert result is True, "Clearing with higher priority should succeed"
    assert not manager.active_animations[1].active, "Slot should be inactive"
    assert manager._active_count == 0, "Active count should be 0"
    
    # Test 5: Bounds checking
    result = manager.clear_animation(-1, priority=99)
    assert result is False, "Out of bounds index should return False"
    result = manager.clear_animation(10, priority=99)
    assert result is False, "Out of bounds index should return False"
    
    print("✓ clear_animation abstraction test passed")


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
        test_clear_animation_abstraction()
        
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
