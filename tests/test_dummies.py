# tests/test_dummies.py
"""
Tests for dummy hardware manager classes.

Verifies that each dummy:
 - Can be instantiated without hardware
 - Exposes all public methods with correct sync/async signatures
 - Returns safe default values that won't trigger CoreManager alerts
"""

import asyncio
import inspect
import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_async(method):
    """Return True if method is a coroutine function."""
    return inspect.iscoroutinefunction(method)


def run(coro):
    """Run a coroutine synchronously for testing."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# AudioManager dummy
# ---------------------------------------------------------------------------

class TestDummyAudioManager:
    def setup_method(self):
        from dummies.audio_manager import AudioManager
        self.mgr = AudioManager()

    def test_instantiation(self):
        assert self.mgr is not None

    def test_channel_constants(self):
        # Must expose the standard channel attributes
        assert hasattr(self.mgr, 'CH_ATMO')
        assert hasattr(self.mgr, 'CH_SFX')
        assert hasattr(self.mgr, 'CH_VOICE')
        assert hasattr(self.mgr, 'CH_SYNTH')

    def test_preload_is_sync(self):
        assert not is_async(self.mgr.preload)
        self.mgr.preload(["file.wav"])  # Should not raise

    def test_attach_synth_is_sync(self):
        assert not is_async(self.mgr.attach_synth)
        self.mgr.attach_synth(None)

    def test_play_is_async(self):
        assert is_async(self.mgr.play)
        run(self.mgr.play("sound.wav"))

    def test_stop_is_sync(self):
        assert not is_async(self.mgr.stop)
        self.mgr.stop(0)

    def test_stop_all_is_sync(self):
        assert not is_async(self.mgr.stop_all)
        self.mgr.stop_all()

    def test_set_level_is_sync(self):
        assert not is_async(self.mgr.set_level)
        self.mgr.set_level(0, 0.5)


# ---------------------------------------------------------------------------
# BuzzerManager dummy
# ---------------------------------------------------------------------------

class TestDummyBuzzerManager:
    def setup_method(self):
        from dummies.buzzer_manager import BuzzerManager
        self.mgr = BuzzerManager()

    def test_instantiation(self):
        assert self.mgr is not None

    def test_stop_is_async(self):
        assert is_async(self.mgr.stop)
        run(self.mgr.stop())

    def test_play_note_is_sync(self):
        assert not is_async(self.mgr.play_note)
        self.mgr.play_note(440, duration=0.1)

    def test_play_sequence_is_sync(self):
        assert not is_async(self.mgr.play_sequence)
        self.mgr.play_sequence({})


# ---------------------------------------------------------------------------
# DisplayManager dummy
# ---------------------------------------------------------------------------

class TestDummyDisplayManager:
    def setup_method(self):
        from dummies.display_manager import DisplayManager
        self.mgr = DisplayManager()

    def test_instantiation(self):
        assert self.mgr is not None

    def test_layout_methods_sync(self):
        assert not is_async(self.mgr.use_standard_layout)
        assert not is_async(self.mgr.use_custom_layout)
        self.mgr.use_standard_layout()
        self.mgr.use_custom_layout()

    def test_update_methods_sync(self):
        self.mgr.update_header("HDR")
        self.mgr.update_footer("FTR")
        self.mgr.update_status("MAIN", "SUB")

    def test_scroll_loop_is_async(self):
        assert is_async(self.mgr.scroll_loop)

    def test_scroll_loop_does_not_return_immediately(self):
        """scroll_loop should yield control rather than completing synchronously."""
        async def _run():
            coro = self.mgr.scroll_loop()
            task = asyncio.create_task(coro)
            # Give the loop a single tick - the infinite loop should still be running
            await asyncio.sleep(0)
            assert not task.done()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        asyncio.run(_run())

    def test_show_methods_sync(self):
        self.mgr.show_waveform([0.5] * 128)
        self.mgr.show_eq_bands([4] * 16)
        self.mgr.show_settings_menu(show=True)
        self.mgr.update_settings_menu(["Item A", "Item B"], 0)


# ---------------------------------------------------------------------------
# HIDManager dummy
# ---------------------------------------------------------------------------

class TestDummyHIDManager:
    def setup_method(self):
        from dummies.hid_manager import HIDManager
        self.mgr = HIDManager()

    def test_instantiation(self):
        assert self.mgr is not None

    def test_button_always_unpressed(self):
        assert self.mgr.is_button_pressed(0) is False
        assert self.mgr.is_button_pressed(0, long=True) is False

    def test_latching_always_off(self):
        assert self.mgr.is_latching_toggled(0) is False

    def test_momentary_always_off(self):
        assert self.mgr.is_momentary_toggled(0) is False

    def test_encoder_always_zero(self):
        assert self.mgr.encoder_position() == 0
        assert self.mgr.encoder_position_scaled() == 0

    def test_estop_property_false(self):
        assert self.mgr.estop is False

    def test_hw_update_is_sync(self):
        assert not is_async(self.mgr.hw_update)
        result = self.mgr.hw_update()
        assert result is False

    def test_keypad_returns_none(self):
        assert self.mgr.get_keypad_next_key() is None

    def test_status_methods(self):
        assert self.mgr.get_status_bytes() == b''
        assert self.mgr.get_status_string() == ''


# ---------------------------------------------------------------------------
# MatrixManager dummy
# ---------------------------------------------------------------------------

class TestDummyMatrixManager:
    def setup_method(self):
        from dummies.matrix_manager import MatrixManager
        self.mgr = MatrixManager(None, width=16, height=16)

    def test_instantiation(self):
        assert self.mgr is not None

    def test_dimensions_stored(self):
        assert self.mgr.width == 16
        assert self.mgr.height == 16

    def test_draw_methods_sync(self):
        self.mgr.draw_pixel(0, 0, (255, 0, 0))
        self.mgr.fill((0, 0, 0))
        self.mgr.show_icon("SMILEY")
        self.mgr.draw_quadrant(0, (0, 255, 0))
        self.mgr.draw_eq_bands([4] * 16)
        self.mgr.draw_wedge(0, (0, 0, 255))

    def test_animate_loop_is_async(self):
        assert is_async(self.mgr.animate_loop)
        run(self.mgr.animate_loop(step=True))


class TestDummyPanelLayout:
    def test_constants_present(self):
        from dummies.matrix_manager import PanelLayout
        assert PanelLayout.Z_PATTERN == "z_pattern"
        assert PanelLayout.SERPENTINE == "serpentine"
        assert PanelLayout.CUSTOM == "custom"


# ---------------------------------------------------------------------------
# SynthManager dummy
# ---------------------------------------------------------------------------

class TestDummySynthManager:
    def setup_method(self):
        from dummies.synth_manager import SynthManager
        self.mgr = SynthManager()

    def test_instantiation(self):
        assert self.mgr is not None

    def test_source_property(self):
        assert self.mgr.source is None

    def test_play_note_sync(self):
        assert not is_async(self.mgr.play_note)
        result = self.mgr.play_note(440)
        assert result is None

    def test_stop_note_sync(self):
        assert not is_async(self.mgr.stop_note)
        self.mgr.stop_note(None)

    def test_release_all_sync(self):
        assert not is_async(self.mgr.release_all)
        self.mgr.release_all()

    def test_play_sequence_is_async(self):
        assert is_async(self.mgr.play_sequence)
        run(self.mgr.play_sequence({}))

    def test_generative_drone_is_async(self):
        assert is_async(self.mgr.start_generative_drone)


# ---------------------------------------------------------------------------
# LEDManager dummy
# ---------------------------------------------------------------------------

class TestDummyLEDManager:
    def setup_method(self):
        from dummies.led_manager import LEDManager
        self.mgr = LEDManager()

    def test_instantiation(self):
        assert self.mgr is not None

    def test_led_control_methods_sync(self):
        self.mgr.set_led(0, (255, 0, 0))
        self.mgr.off_led(0)
        self.mgr.solid_led(0, (0, 255, 0))
        self.mgr.flash_led(0, (0, 0, 255))
        self.mgr.breathe_led(0, (255, 255, 0))

    def test_strip_animation_methods_sync(self):
        self.mgr.start_cylon((255, 0, 0))
        self.mgr.start_centrifuge((0, 255, 0))
        self.mgr.start_rainbow()
        self.mgr.start_glitch([(255, 0, 0), (0, 0, 255)])

    def test_apply_command_sync(self):
        assert not is_async(self.mgr.apply_command)
        self.mgr.apply_command("LED", "0,255,0,0")

    def test_animate_loop_is_async(self):
        assert is_async(self.mgr.animate_loop)
        run(self.mgr.animate_loop(step=True))


# ---------------------------------------------------------------------------
# SegmentManager dummy
# ---------------------------------------------------------------------------

class TestDummySegmentManager:
    def setup_method(self):
        from dummies.segment_manager import SegmentManager
        self.mgr = SegmentManager()

    def test_instantiation(self):
        assert self.mgr is not None

    def test_start_message_is_async(self):
        assert is_async(self.mgr.start_message)
        run(self.mgr.start_message("HELLO"))

    def test_apply_command_is_async(self):
        assert is_async(self.mgr.apply_command)
        run(self.mgr.apply_command("DSP", "HELLO,0,0.3,L"))

    def test_start_corruption_is_async(self):
        assert is_async(self.mgr.start_corruption)
        run(self.mgr.start_corruption(duration=1.0))

    def test_start_matrix_is_async(self):
        assert is_async(self.mgr.start_matrix)
        run(self.mgr.start_matrix(duration=1.0))


# ---------------------------------------------------------------------------
# ADCManager dummy
# ---------------------------------------------------------------------------

class TestDummyADCManager:
    def setup_method(self):
        from dummies.adc_manager import ADCManager
        self.mgr = ADCManager()

    def test_instantiation(self):
        assert self.mgr is not None

    def test_add_channel_sync(self):
        assert not is_async(self.mgr.add_channel)
        self.mgr.add_channel("test_channel", 0, 11.0)  # Should not raise

    def test_read_returns_zero(self):
        assert self.mgr.read("any_channel") == 0.0

    def test_read_all_returns_empty_dict(self):
        result = self.mgr.read_all()
        assert isinstance(result, dict)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# PowerManager dummy
# ---------------------------------------------------------------------------

class TestDummyPowerManager:
    def setup_method(self):
        from dummies.power_manager import PowerManager
        self.mgr = PowerManager()

    def test_instantiation(self):
        assert self.mgr is not None

    def test_check_power_integrity_is_async_and_true(self):
        assert is_async(self.mgr.check_power_integrity)
        result = run(self.mgr.check_power_integrity())
        assert result is True

    def test_status_returns_safe_voltages(self):
        v = self.mgr.status
        # Must not trigger alert conditions in CoreManager monitor_power:
        # v["led_5v"] < 4.5 AND v["input_20v"] > 18.0  -> LED failure alert
        # v["main_5v"] < 4.7                           -> brownout alert
        assert v["led_5v"] >= 4.5 or v["input_20v"] <= 18.0
        assert v["main_5v"] >= 4.7

    def test_status_unknown_key_safe(self):
        """Any unknown voltage key should return a safe (non-alerting) value."""
        v = self.mgr.status
        assert v["unknown_rail"] >= 4.7

    def test_satbus_properties(self):
        assert self.mgr.satbus_connected is False
        assert self.mgr.satbus_powered is False

    def test_soft_start_returns_true(self):
        result = run(self.mgr.soft_start_satellites())
        assert isinstance(result, tuple) and len(result) == 2
        success, msg = result
        assert success is True

    def test_emergency_kill_sync(self):
        assert not is_async(self.mgr.emergency_kill)
        self.mgr.emergency_kill()  # Should not raise


# ---------------------------------------------------------------------------
# Module injection helper (code.py logic, tested in isolation)
# ---------------------------------------------------------------------------

@pytest.fixture
def clean_manager_modules():
    """Remove cached manager modules before and after each injection test."""
    import sys
    _modules_to_clean = [
        "managers.audio_manager", "managers.synth_manager",
        "managers.display_manager", "managers.matrix_manager",
        "managers.led_manager", "managers.hid_manager",
        "managers.buzzer_manager", "managers.power_manager",
        "managers.adc_manager", "managers.segment_manager",
    ]
    for mod in _modules_to_clean:
        sys.modules.pop(mod, None)
    yield
    for mod in _modules_to_clean:
        sys.modules.pop(mod, None)


class TestInjectHardwareDummies:
    """Verify the sys.modules injection logic without running code.py."""

    def _make_injector(self):
        """Recreate the _inject_hardware_dummies logic for isolated testing."""
        import sys

        feature_map = {
            "audio":   ["managers.audio_manager", "managers.synth_manager"],
            "display": ["managers.display_manager"],
            "matrix":  ["managers.matrix_manager"],
            "leds":    ["managers.led_manager"],
            "hid":     ["managers.hid_manager"],
            "buzzer":  ["managers.buzzer_manager"],
            "power":   ["managers.power_manager", "managers.adc_manager"],
            "segment": ["managers.segment_manager"],
        }
        dummy_map = {
            "managers.audio_manager":   "dummies.audio_manager",
            "managers.synth_manager":   "dummies.synth_manager",
            "managers.display_manager": "dummies.display_manager",
            "managers.matrix_manager":  "dummies.matrix_manager",
            "managers.led_manager":     "dummies.led_manager",
            "managers.hid_manager":     "dummies.hid_manager",
            "managers.buzzer_manager":  "dummies.buzzer_manager",
            "managers.power_manager":   "dummies.power_manager",
            "managers.adc_manager":     "dummies.adc_manager",
            "managers.segment_manager": "dummies.segment_manager",
        }

        def inject(features):
            for feature, enabled in features.items():
                if enabled or feature not in feature_map:
                    continue
                for manager_module in feature_map[feature]:
                    dummy_module_name = dummy_map.get(manager_module)
                    if dummy_module_name is None:
                        continue
                    __import__(dummy_module_name)
                    sys.modules[manager_module] = sys.modules[dummy_module_name]

        return inject

    def test_disabled_audio_injects_dummy(self, clean_manager_modules):
        import sys
        inject = self._make_injector()

        inject({"audio": False})

        from managers.audio_manager import AudioManager
        from dummies.audio_manager import AudioManager as DummyAudio
        assert AudioManager is DummyAudio

    def test_enabled_feature_does_not_inject(self, clean_manager_modules):
        import sys
        inject = self._make_injector()

        inject({"display": True})

        # Module should not have been replaced with dummy
        # (it was removed from cache and will reload from real source)
        assert "managers.display_manager" not in sys.modules

    def test_empty_features_no_injection(self, clean_manager_modules):
        """Empty hardware_features dict means no dummies are injected."""
        inject = self._make_injector()
        inject({})  # Should be a no-op

    def test_unknown_feature_ignored(self, clean_manager_modules):
        """Unknown feature keys should be silently ignored."""
        inject = self._make_injector()
        inject({"nonexistent_feature": False})  # Should not raise
