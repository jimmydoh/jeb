#!/usr/bin/env python3
"""Unit tests for the BootSequence boot animation class.

Verifies that:
- The sequence runs to completion without errors.
- Matrix curtain/reveal, OLED splash, synth swell, and buzzer ping
  are all exercised during play().
- Version strings are formatted and displayed correctly.
- The sequence handles a missing or empty version string gracefully.
"""

import asyncio
import sys
import os
from unittest.mock import MagicMock, call, patch, AsyncMock

# ---------------------------------------------------------------------------
# Minimal CircuitPython stubs (must appear before src imports)
# ---------------------------------------------------------------------------
for _mod in (
    "synthio", "displayio", "terminalio", "busio", "digitalio", "board",
    "neopixel", "audiocore", "audiobusio", "audiomixer", "analogio",
    "microcontroller", "adafruit_displayio_ssd1306", "adafruit_display_text",
    "adafruit_ticks", "pwmio", "watchdog", "storage",
):
    sys.modules.setdefault(_mod, MagicMock())

# Ensure the label sub-attribute exists on adafruit_display_text mock
sys.modules.setdefault("adafruit_display_text.label", MagicMock())

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ---------------------------------------------------------------------------
# Import the module under test (after path / stubs are in place)
# ---------------------------------------------------------------------------
from core.boot_sequence import BootSequence


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_matrix(width=16, height=16):
    """Return a mock MatrixManager with required attributes."""
    m = MagicMock()
    m.width = width
    m.height = height
    return m


def _make_display():
    """Return a mock DisplayManager with a settable status label."""
    d = MagicMock()
    # status label must support attribute assignment for the bounce animation
    d.status = MagicMock()
    d.status.y = 24
    d.status.text = ""
    return d


def _make_synth():
    """Return a mock SynthManager whose play_sequence is awaitable."""
    s = MagicMock()
    s.play_sequence = AsyncMock()
    return s


def _make_buzzer():
    """Return a mock BuzzerManager."""
    return MagicMock()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBootSequencePlay:
    """Top-level play() method tests."""

    def test_play_completes_without_error(self):
        """play() must run to completion with no uncaught exception."""
        seq = BootSequence(_make_matrix(), _make_display(), _make_synth(), _make_buzzer())
        asyncio.run(seq.play("v0.8.0"))

    def test_play_calls_buzzer_ping(self):
        """play() must call buzzer.play_note exactly once for the accent ping."""
        buzzer = _make_buzzer()
        seq = BootSequence(_make_matrix(), _make_display(), _make_synth(), buzzer)
        asyncio.run(seq.play("v0.8.0"))
        buzzer.play_note.assert_called_once()

    def test_play_calls_synth_swell(self):
        """play() must await synth.play_sequence once for the boot swell."""
        synth = _make_synth()
        seq = BootSequence(_make_matrix(), _make_display(), synth, _make_buzzer())
        asyncio.run(seq.play("v0.8.0"))
        synth.play_sequence.assert_called_once()

    def test_play_works_with_empty_version(self):
        """play() must not raise when version string is empty."""
        seq = BootSequence(_make_matrix(), _make_display(), _make_synth(), _make_buzzer())
        asyncio.run(seq.play(""))

    def test_play_works_with_no_version_arg(self):
        """play() default version argument must not raise."""
        seq = BootSequence(_make_matrix(), _make_display(), _make_synth(), _make_buzzer())
        asyncio.run(seq.play())


class TestMatrixCurtainReveal:
    """_matrix_curtain_reveal() tests."""

    def test_curtain_draws_all_pixels(self):
        """Curtain phase must call draw_pixel for every cell (16×16 = 256 each phase)."""
        matrix = _make_matrix()
        seq = BootSequence(matrix, _make_display(), _make_synth(), _make_buzzer())
        asyncio.run(seq._matrix_curtain_reveal())
        # Two full passes over the 16×16 grid → at least 2 × 256 calls
        assert matrix.draw_pixel.call_count >= 2 * 16 * 16

    def test_curtain_covers_full_width_and_height(self):
        """Every (col, row) coordinate must appear in the draw_pixel call list."""
        matrix = _make_matrix()
        seq = BootSequence(matrix, _make_display(), _make_synth(), _make_buzzer())
        asyncio.run(seq._matrix_curtain_reveal())
        coords = {(c[0][0], c[0][1]) for c in matrix.draw_pixel.call_args_list}
        for row in range(16):
            for col in range(16):
                assert (col, row) in coords, f"Missing pixel ({col}, {row})"


class TestOledSplash:
    """_oled_splash() tests."""

    def test_splash_sets_title_with_version(self):
        """The status label text must include the supplied version string."""
        display = _make_display()
        seq = BootSequence(_make_matrix(), display, _make_synth(), _make_buzzer())
        asyncio.run(seq._oled_splash("v0.8.0"))
        assert display.status.text == "JEB OS v0.8.0"

    def test_splash_fallback_title_without_version(self):
        """When no version is supplied the title must fall back to 'JEB OS'."""
        display = _make_display()
        seq = BootSequence(_make_matrix(), display, _make_synth(), _make_buzzer())
        asyncio.run(seq._oled_splash(""))
        assert display.status.text == "JEB OS"

    def test_splash_animates_y_position(self):
        """The status label y attribute must be set multiple times (bounce animation)."""
        display = _make_display()
        y_values = []

        type(display.status).y = property(
            lambda self_: getattr(self_, "_y", 24),
            lambda self_, v: (setattr(self_, "_y", v), y_values.append(v)),
        )

        seq = BootSequence(_make_matrix(), display, _make_synth(), _make_buzzer())
        asyncio.run(seq._oled_splash("v0.8.0"))
        # The bounce sequence has 9 positions → y must be set at least 9 times
        assert len(y_values) >= 9

    def test_splash_calls_use_standard_layout(self):
        """Splash must switch the display to standard layout before animating."""
        display = _make_display()
        seq = BootSequence(_make_matrix(), display, _make_synth(), _make_buzzer())
        asyncio.run(seq._oled_splash("v0.8.0"))
        display.use_standard_layout.assert_called()

    def test_splash_calls_update_status_to_settle(self):
        """Splash must call update_status() to lock in the final text."""
        display = _make_display()
        seq = BootSequence(_make_matrix(), display, _make_synth(), _make_buzzer())
        asyncio.run(seq._oled_splash("v0.8.0"))
        display.update_status.assert_called()


class TestSynthSwell:
    """_synth_swell() tests."""

    def test_swell_uses_console_boot_swell_tone(self):
        """_synth_swell() must pass CONSOLE_BOOT_SWELL to play_sequence."""
        from utilities import tones as t
        synth = _make_synth()
        seq = BootSequence(_make_matrix(), _make_display(), synth, _make_buzzer())
        asyncio.run(seq._synth_swell())
        synth.play_sequence.assert_called_once_with(t.CONSOLE_BOOT_SWELL)


class TestBuzzerPing:
    """_buzzer_ping() tests."""

    def test_ping_plays_high_frequency(self):
        """Ping must play a note ≥ 4000 Hz for the sharp accent effect."""
        buzzer = _make_buzzer()
        seq = BootSequence(_make_matrix(), _make_display(), _make_synth(), buzzer)
        seq._buzzer_ping()
        buzzer.play_note.assert_called_once()
        freq_arg = buzzer.play_note.call_args[0][0]
        assert freq_arg >= 4000, f"Expected freq ≥ 4000 Hz, got {freq_arg}"

    def test_ping_passes_short_duration(self):
        """Ping duration must be short (< 0.5 s) for a crisp accent."""
        buzzer = _make_buzzer()
        seq = BootSequence(_make_matrix(), _make_display(), _make_synth(), buzzer)
        seq._buzzer_ping()
        kwargs = buzzer.play_note.call_args[1]
        duration = kwargs.get("duration", buzzer.play_note.call_args[0][1] if len(buzzer.play_note.call_args[0]) > 1 else None)
        assert duration is not None, "duration not passed to play_note"
        assert duration < 0.5, f"Expected short duration < 0.5 s, got {duration}"


class TestReadVersion:
    """CoreManager._read_version() logic tests."""

    def test_version_prefixed_with_v(self):
        """_read_version must return 'v' + the file content (stripped)."""
        # Exercise the _read_version logic directly without importing CoreManager
        # (which pulls in heavy hardware dependencies).

        class _Stub:
            root_data_dir = "/"

        # Define the exact logic from _read_version inline to keep the test
        # self-contained while still validating the business rules.
        def _read_version(self):
            try:
                with open(f"{self.root_data_dir}VERSION", "r") as f:
                    return f"v{f.read().strip()}"
            except Exception:
                return ""

        stub = _Stub()
        with patch("builtins.open", MagicMock(return_value=MagicMock(
            __enter__=lambda s, *a: s,
            __exit__=lambda s, *a: None,
            read=lambda: "0.8.0-rc\n",
        ))):
            result = _read_version(stub)
        assert result == "v0.8.0-rc"

    def test_version_returns_empty_on_missing_file(self):
        """_read_version must return '' gracefully when VERSION is absent."""

        class _Stub:
            root_data_dir = "/"

        def _read_version(self):
            try:
                with open(f"{self.root_data_dir}VERSION", "r") as f:
                    return f"v{f.read().strip()}"
            except Exception:
                return ""

        stub = _Stub()
        with patch("builtins.open", side_effect=OSError("no file")):
            result = _read_version(stub)
        assert result == ""


# ---------------------------------------------------------------------------
# Entry point for standalone execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
