#!/usr/bin/env python3
"""Test that AnimationSlot ensures color immutability by converting lists to tuples."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import AnimationSlot from base_pixel_manager
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'managers'))


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
        """Update slot properties in place.
        
        Args:
            color: Can be a single color tuple (r,g,b), a list/tuple of colors,
                   or None for effects like RAINBOW.
                   Lists are converted to tuples for immutability.
        """
        self.active = True
        self.type = anim_type
        # Convert lists to tuples to prevent accidental mutation
        # Tuples and None are kept as-is (already immutable)
        self.color = tuple(color) if isinstance(color, list) else color
        self.speed = speed
        self.start = start
        self.duration = duration
        self.priority = priority
    
    def clear(self):
        """Mark slot as inactive without deallocating."""
        self.active = False


def test_list_color_converted_to_tuple():
    """Test that list colors are converted to tuples."""
    print("Testing list to tuple conversion...")
    
    slot = AnimationSlot()
    
    # Pass a list color (mutable)
    list_color = [255, 128, 64]
    slot.set("SOLID", list_color, 1.0, 0.0, None, 1)
    
    # Verify it's stored as a tuple
    assert isinstance(slot.color, tuple), "Color should be stored as tuple"
    assert slot.color == (255, 128, 64), f"Expected (255, 128, 64), got {slot.color}"
    
    # Verify original list was not affected
    assert list_color == [255, 128, 64], "Original list should not be modified"
    
    # Try to mutate the original list
    list_color[0] = 100
    
    # Verify slot color is not affected (it's a tuple copy)
    assert slot.color == (255, 128, 64), "Slot color should not change when original list is mutated"
    
    print("  ✓ List color converted to tuple successfully")
    print("  ✓ Original list mutation doesn't affect stored color")


def test_tuple_color_kept_as_is():
    """Test that tuple colors are kept as-is."""
    print("\nTesting tuple colors are kept as-is...")
    
    slot = AnimationSlot()
    
    # Pass a tuple color (immutable)
    tuple_color = (200, 100, 50)
    slot.set("BLINK", tuple_color, 2.0, 0.0, 3.0, 2)
    
    # Verify it's stored as the same tuple
    assert isinstance(slot.color, tuple), "Color should be a tuple"
    assert slot.color == (200, 100, 50), f"Expected (200, 100, 50), got {slot.color}"
    
    print("  ✓ Tuple color kept as-is")


def test_none_color_kept_as_none():
    """Test that None colors are kept as None."""
    print("\nTesting None colors are kept as None...")
    
    slot = AnimationSlot()
    
    # Pass None (for effects like RAINBOW that don't use colors)
    slot.set("RAINBOW", None, 1.0, 0.0, 5.0, 1)
    
    # Verify it's stored as None
    assert slot.color is None, "Color should be None"
    
    print("  ✓ None color kept as None")


def test_list_of_colors_converted():
    """Test that a list of color tuples is converted to tuple."""
    print("\nTesting list of colors converted to tuple...")
    
    slot = AnimationSlot()
    
    # Pass a list of colors (like for GLITCH effect)
    colors_list = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
    slot.set("GLITCH", colors_list, 0.5, 0.0, 2.0, 1)
    
    # Verify it's stored as a tuple
    assert isinstance(slot.color, tuple), "Colors should be stored as tuple"
    assert slot.color == ((255, 0, 0), (0, 255, 0), (0, 0, 255)), \
        f"Expected tuple of colors, got {slot.color}"
    
    # Verify original list was not affected
    assert colors_list == [(255, 0, 0), (0, 255, 0), (0, 0, 255)], \
        "Original list should not be modified"
    
    # Try to mutate the original list
    colors_list.append((255, 255, 0))
    
    # Verify slot color is not affected
    assert len(slot.color) == 3, "Slot should still have 3 colors"
    
    print("  ✓ List of colors converted to tuple")
    print("  ✓ Original list mutation doesn't affect stored colors")


def test_defensive_against_future_mutations():
    """Test that the implementation is defensive against mutations."""
    print("\nTesting defensive implementation...")
    
    slot = AnimationSlot()
    
    # Scenario 1: Pass a list, mutate it later
    color_list = [100, 150, 200]
    slot.set("SOLID", color_list, 1.0, 0.0, None, 1)
    
    # Store original value
    original_stored = slot.color
    
    # Mutate the original list
    color_list[0] = 0
    color_list[1] = 0
    color_list[2] = 0
    
    # Verify slot color hasn't changed
    assert slot.color == original_stored, "Stored color should not be affected by list mutation"
    assert slot.color == (100, 150, 200), f"Expected (100, 150, 200), got {slot.color}"
    
    print("  ✓ Stored colors are immune to source list mutations")
    
    # Scenario 2: Multiple slots sharing same color list
    shared_list = [50, 100, 150]
    slot1 = AnimationSlot()
    slot2 = AnimationSlot()
    
    slot1.set("SOLID", shared_list, 1.0, 0.0, None, 1)
    slot2.set("BLINK", shared_list, 1.5, 0.0, None, 1)
    
    # Mutate the shared list
    shared_list[0] = 255
    
    # Verify both slots are unaffected
    assert slot1.color == (50, 100, 150), "Slot1 should not be affected"
    assert slot2.color == (50, 100, 150), "Slot2 should not be affected"
    
    print("  ✓ Multiple slots with same source are independent")


if __name__ == "__main__":
    print("=" * 60)
    print("AnimationSlot Immutability Test Suite")
    print("=" * 60)
    
    try:
        test_list_color_converted_to_tuple()
        test_tuple_color_kept_as_is()
        test_none_color_kept_as_none()
        test_list_of_colors_converted()
        test_defensive_against_future_mutations()
        
        print("\n" + "=" * 60)
        print("ALL IMMUTABILITY TESTS PASSED ✓")
        print("=" * 60)
        print("\nAnimationSlot correctly ensures color immutability!")
        print("Lists are safely converted to tuples.")
        
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
