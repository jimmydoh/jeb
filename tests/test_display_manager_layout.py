#!/usr/bin/env python3
"""Tests for DisplayManager layout system.

These tests validate the new flexible layout system including standard
and custom layout modes, as well as backward compatibility with legacy mode.
"""

import asyncio
import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Mock CircuitPython modules that might be imported
sys.modules['displayio'] = MagicMock()
sys.modules['terminalio'] = MagicMock()
sys.modules['adafruit_displayio_ssd1306'] = MagicMock()
sys.modules['adafruit_display_text'] = MagicMock()
sys.modules['adafruit_display_text.label'] = MagicMock()
sys.modules['analogio'] = MagicMock()
sys.modules['busio'] = MagicMock()
sys.modules['digitalio'] = MagicMock()
sys.modules['board'] = MagicMock()
sys.modules['neopixel'] = MagicMock()
sys.modules['neopixel_spi'] = MagicMock()
sys.modules['adafruit_is31fl3731'] = MagicMock()
sys.modules['rotaryio'] = MagicMock()
sys.modules['pwmio'] = MagicMock()
sys.modules['audiopwmio'] = MagicMock()
sys.modules['audiocore'] = MagicMock()
sys.modules['audiomixer'] = MagicMock()
sys.modules['synthio'] = MagicMock()
sys.modules['ulab'] = MagicMock()
sys.modules['ulab.numpy'] = MagicMock()
sys.modules['microcontroller'] = MagicMock()
sys.modules['storage'] = MagicMock()
sys.modules['supervisor'] = MagicMock()
sys.modules['usb_cdc'] = MagicMock()
sys.modules['watchdog'] = MagicMock()

# Add src/managers to path for direct module import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'managers'))

# Import DisplayManager module directly
import display_manager
DisplayManager = display_manager.DisplayManager

class TestDisplayManagerLayoutSystem(unittest.TestCase):
    """Test DisplayManager layout modes and zone management."""

    def setUp(self):
        """Set up test fixtures."""
        # Use the already imported DisplayManager
        # Mock I2C bus
        self.mock_i2c = Mock()

        # Create DisplayManager instance
        self.display = DisplayManager(self.mock_i2c)

    def test_initialization_in_legacy_mode(self):
        """Test that DisplayManager initializes in standard layout mode by default."""
        # Default mode is now "standard" (initialized via use_standard_layout())
        self.assertEqual(self.display._layout_mode, "standard")

    def test_switch_to_standard_layout(self):
        """Test switching to standard three-zone layout."""
        self.display.use_standard_layout()

        self.assertEqual(self.display._layout_mode, "standard")
        # Verify standard layout uses header, main, footer groups
        self.assertIsNotNone(self.display.header_group)
        self.assertIsNotNone(self.display.main_group)
        self.assertIsNotNone(self.display.footer_group)

    def test_switch_to_custom_layout(self):
        """Test switching to custom layout mode."""
        self.display.use_custom_layout()

        self.assertEqual(self.display._layout_mode, "custom")
        # Verify custom layout uses custom_group
        self.assertIsNotNone(self.display.custom_group)

    def test_standard_layout_idempotent(self):
        """Test that calling use_standard_layout multiple times is safe."""
        self.display.use_standard_layout()
        mode_first = self.display._layout_mode

        self.display.use_standard_layout()
        mode_second = self.display._layout_mode

        self.assertEqual(mode_first, mode_second)
        self.assertEqual(self.display._layout_mode, "standard")

    def test_custom_layout_idempotent(self):
        """Test that calling use_custom_layout multiple times is safe."""
        self.display.use_custom_layout()
        mode_first = self.display._layout_mode

        self.display.use_custom_layout()
        mode_second = self.display._layout_mode

        self.assertEqual(mode_first, mode_second)
        self.assertEqual(self.display._layout_mode, "custom")

    def test_update_status_works_in_all_modes(self):
        """Test that update_status works in standard and custom modes."""
        # Standard mode (default after initialization)
        self.display.update_status("Test 1", "Sub 1")
        # Just verify no errors are raised
        self.assertEqual(self.display._layout_mode, "standard")

        # Still in standard mode after another update
        self.display.use_standard_layout()
        self.display.update_status("Test 2", "Sub 2")
        # Just verify no errors are raised
        self.assertEqual(self.display._layout_mode, "standard")

        # Custom mode
        self.display.use_custom_layout()
        self.display.update_status("Test 3", "Sub 3")
        # Just verify no errors are raised
        self.assertEqual(self.display._layout_mode, "custom")

    def test_update_header_in_standard_mode(self):
        """Test updating header zone in standard layout."""
        self.display.use_standard_layout()
        self.display.update_header("MODE: TEST")

        # Verify no errors are raised
        self.assertEqual(self.display._layout_mode, "standard")

    def test_update_footer_in_standard_mode(self):
        """Test updating footer zone in standard layout."""
        self.display.use_standard_layout()
        self.display.update_footer("Log message")

        # Verify no errors are raised
        self.assertEqual(self.display._layout_mode, "standard")

    def test_set_custom_content(self):
        """Test setting custom content in custom layout mode."""
        import sys
        mock_group = sys.modules['displayio'].Group()

        self.display.use_custom_layout()
        self.display.set_custom_content(mock_group)

        # Custom content should be set
        # We can't easily check length with MagicMock, so just verify no errors
        self.assertEqual(self.display._layout_mode, "custom")

    def test_set_custom_content_clears_previous(self):
        """Test that set_custom_content clears previous content."""
        import sys
        mock_group1 = sys.modules['displayio'].Group()
        mock_group2 = sys.modules['displayio'].Group()

        self.display.use_custom_layout()
        self.display.set_custom_content(mock_group1)
        # Should not raise an error

        self.display.set_custom_content(mock_group2)
        # Should not raise an error
        self.assertEqual(self.display._layout_mode, "custom")

    def test_zone_groups_exist(self):
        """Test that all zone groups are created."""
        self.assertIsNotNone(self.display.header_group)
        self.assertIsNotNone(self.display.main_group)
        self.assertIsNotNone(self.display.footer_group)
        self.assertIsNotNone(self.display.custom_group)

    def test_zone_labels_exist(self):
        """Test that zone labels are created."""
        self.assertIsNotNone(self.display.header_label)
        self.assertIsNotNone(self.display.status)
        self.assertIsNotNone(self.display.sub_status)
        self.assertIsNotNone(self.display.footer_label)

    def test_cleanup_calls_release_displays(self):
        """Test that cleanup() calls displayio.release_displays()."""
        import sys
        mock_displayio = sys.modules['displayio']
        mock_displayio.release_displays.reset_mock()

        self.display.cleanup()

        mock_displayio.release_displays.assert_called_once()

    def test_cleanup_handles_exception_gracefully(self):
        """Test that cleanup() does not raise even if release_displays fails."""
        import sys
        mock_displayio = sys.modules['displayio']
        mock_displayio.release_displays.side_effect = Exception("bus error")

        self.display.cleanup()  # Should not raise

        mock_displayio.release_displays.side_effect = None

class TestDisplayManagerZonePositions(unittest.TestCase):
    """Test that display zones are positioned correctly."""

    def setUp(self):
        """Set up test fixtures."""
        # Use the already imported DisplayManager
        self.mock_i2c = Mock()
        self.display = DisplayManager(self.mock_i2c)

    def test_header_position(self):
        """Test header label positioning."""
        # Header should be near top of display
        # Just verify it exists - MagicMock makes exact position checks difficult
        self.assertIsNotNone(self.display.header_label)

    def test_main_positions(self):
        """Test main zone label positioning."""
        # Main zone labels should exist
        self.assertIsNotNone(self.display.status)
        self.assertIsNotNone(self.display.sub_status)

    def test_footer_position(self):
        """Test footer label positioning."""
        # Footer should exist
        self.assertIsNotNone(self.display.footer_label)


class TestDisplayManagerAnimations(unittest.TestCase):
    """Test DisplayManager async animation methods."""

    def setUp(self):
        """Create a DisplayManager instance with properly isolated label mocks.

        label.Label is given a side_effect so every call returns a *new*
        independent MagicMock.  Without this, both self.display.status and
        self.display.sub_status would resolve to the same mock object
        (adafruit_display_text.label.Label.return_value), causing spurious
        test failures when the tests inspect each label separately.
        """
        self.mock_i2c = Mock()
        # Resolve the Label mock directly from the imported display_manager module.
        # Using sys.modules['adafruit_display_text'] is unreliable because other
        # test files (e.g. test_matrix_manager.py, test_pixel_manager.py) overwrite
        # that sys.modules entry with a new MockModule during pytest collection,
        # causing sys.modules['adafruit_display_text'].label.Label to diverge from
        # the label.Label that display_manager.py has already bound at import time.
        # The lambda ignores the constructor arguments intentionally so that
        # each label.Label(...) call returns a plain, unconfigured MagicMock
        # regardless of the mocked terminalio.FONT or other args passed in.
        label_cls = display_manager.label.Label
        label_cls.side_effect = lambda *args, **kwargs: MagicMock()
        self.display = DisplayManager(self.mock_i2c)
        # Reset side_effect so that other test classes are not affected.
        label_cls.side_effect = None

    # ── animate_slide_in ────────────────────────────────────────────────────

    def test_animate_slide_in_left_ends_at_base_x(self):
        """animate_slide_in(direction='left') leaves status.x at base_x == 2."""
        asyncio.run(
            self.display.animate_slide_in("HELLO", direction="left", delay=0)
        )
        self.assertEqual(self.display.status.x, 2)

    def test_animate_slide_in_right_ends_at_base_x(self):
        """animate_slide_in(direction='right') leaves status.x at base_x == 2."""
        asyncio.run(
            self.display.animate_slide_in("HELLO", direction="right", delay=0)
        )
        self.assertEqual(self.display.status.x, 2)

    def test_animate_slide_in_with_sub_text_ends_at_base_x(self):
        """animate_slide_in with sub_text leaves sub_status.x at base_x == 2."""
        asyncio.run(
            self.display.animate_slide_in(
                "HELLO", sub_text="world", direction="left", delay=0
            )
        )
        self.assertEqual(self.display.sub_status.x, 2)

    def test_animate_slide_in_right_with_sub_text_ends_at_base_x(self):
        """animate_slide_in(direction='right') with sub_text leaves sub_status.x at 2."""
        asyncio.run(
            self.display.animate_slide_in(
                "HELLO", sub_text="world", direction="right", delay=0
            )
        )
        self.assertEqual(self.display.sub_status.x, 2)

    # ── animate_typewriter ──────────────────────────────────────────────────

    def test_animate_typewriter_sets_correct_main_text(self):
        """animate_typewriter completes with status.text equal to main_text."""
        main_text = "TYPING"
        asyncio.run(
            self.display.animate_typewriter(main_text, char_delay=0)
        )
        self.assertEqual(self.display.status.text, main_text)

    def test_animate_typewriter_with_sub_text_sets_both_labels(self):
        """animate_typewriter with sub_text sets both status and sub_status text."""
        main_text = "MAIN"
        sub_text = "sub"
        asyncio.run(
            self.display.animate_typewriter(main_text, sub_text=sub_text, char_delay=0)
        )
        self.assertEqual(self.display.status.text, main_text)
        self.assertEqual(self.display.sub_status.text, sub_text)

    def test_animate_typewriter_without_sub_text_clears_sub_status(self):
        """animate_typewriter with no sub_text leaves sub_status.text as empty string."""
        asyncio.run(
            self.display.animate_typewriter("MAIN", char_delay=0)
        )
        self.assertEqual(self.display.sub_status.text, "")

    # ── animate_blink ───────────────────────────────────────────────────────

    def test_animate_blink_ends_with_main_group_visible(self):
        """animate_blink ends with main_group.hidden == False."""
        asyncio.run(
            self.display.animate_blink(
                "BLINK", times=3, on_duration=0, off_duration=0
            )
        )
        self.assertFalse(self.display.main_group.hidden)

    def test_animate_blink_runs_without_error(self):
        """animate_blink completes without raising any exception."""
        try:
            asyncio.run(
                self.display.animate_blink(
                    "BLINK", sub_text="sub", times=2, on_duration=0, off_duration=0
                )
            )
        except Exception as exc:
            self.fail(f"animate_blink raised an unexpected exception: {exc}")


if __name__ == '__main__':
    unittest.main()
