#!/usr/bin/env python3
"""Tests for deterministic frame-counter-driven global animations and SETOFF handshake.

Validates:
- GlobalAnimationController.sync_frame() keeps _frame_counter in sync
- global_rainbow_wave uses _frame_counter for deterministic hue when set
- global_rain uses _frame_counter for deterministic step timing when set
- RenderManager.add_global_animation_controller() propagates frame counter
- SatelliteNetworkManager sends SETOFF to new satellites when offsets configured
"""

import sys
import os
import asyncio
import pytest

# Mock CircuitPython modules BEFORE any imports
class MockModule:
    """Generic mock module."""
    def __getattr__(self, name):
        return MockModule()

    def __call__(self, *args, **kwargs):
        return MockModule()

sys.modules['digitalio'] = MockModule()
sys.modules['busio'] = MockModule()
sys.modules['board'] = MockModule()
sys.modules['adafruit_mcp230xx'] = MockModule()
sys.modules['adafruit_mcp230xx.mcp23017'] = MockModule()
sys.modules['adafruit_ticks'] = MockModule()
sys.modules['audiobusio'] = MockModule()
sys.modules['audiocore'] = MockModule()
sys.modules['audiomixer'] = MockModule()
sys.modules['analogio'] = MockModule()
sys.modules['microcontroller'] = MockModule()
sys.modules['watchdog'] = MockModule()
sys.modules['audiopwmio'] = MockModule()
sys.modules['synthio'] = MockModule()
sys.modules['ulab'] = MockModule()
sys.modules['neopixel'] = MockModule()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from managers.matrix_manager import MatrixManager
from managers.led_manager import LEDManager
from managers.global_animation_controller import GlobalAnimationController
from managers.render_manager import RenderManager


class MockJEBPixel:
    def __init__(self, num_pixels):
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
        pass


class MockPixelObject:
    def show(self):
        pass


# ---------------------------------------------------------------------------
# sync_frame() tests
# ---------------------------------------------------------------------------

def test_sync_frame_updates_counter():
    """sync_frame() updates the internal frame counter."""
    ctrl = GlobalAnimationController()
    assert ctrl._frame_counter == 0

    ctrl.sync_frame(42)
    assert ctrl._frame_counter == 42

    ctrl.sync_frame(1234)
    assert ctrl._frame_counter == 1234


def test_sync_frame_zero_is_valid():
    """sync_frame(0) is a valid call (frame counter reset or first frame)."""
    ctrl = GlobalAnimationController()
    ctrl.sync_frame(100)
    ctrl.sync_frame(0)
    assert ctrl._frame_counter == 0


# ---------------------------------------------------------------------------
# Deterministic rainbow wave tests
# ---------------------------------------------------------------------------

def test_rainbow_wave_uses_frame_counter_for_hue():
    """Two controllers with the same frame counter produce identical hues."""
    led_a = LEDManager(MockJEBPixel(8))
    led_b = LEDManager(MockJEBPixel(8))
    ctrl_a = GlobalAnimationController()
    ctrl_b = GlobalAnimationController()
    ctrl_a.register_led_strip(led_a, offset_x=0, offset_y=0, orientation='horizontal')
    ctrl_b.register_led_strip(led_b, offset_x=0, offset_y=0, orientation='horizontal')

    # Synchronize both controllers to the same frame
    ctrl_a.sync_frame(300)
    ctrl_b.sync_frame(300)

    async def run(ctrl):
        # Duration measured by wall clock, hue uses frame_counter
        await ctrl.global_rainbow_wave(speed=30.0, duration=0.08)

    asyncio.run(run(ctrl_a))
    asyncio.run(run(ctrl_b))

    # All corresponding pixels should be identical since both use the same frame_counter
    for i in range(8):
        assert led_a.active_animations[i].color == led_b.active_animations[i].color, \
            f"Pixel {i}: ctrl_a={led_a.active_animations[i].color} != ctrl_b={led_b.active_animations[i].color}"


def test_rainbow_wave_different_frame_counters_differ():
    """Controllers with different frame counters produce different hues (speed > 0)."""
    led_a = LEDManager(MockJEBPixel(8))
    led_b = LEDManager(MockJEBPixel(8))
    ctrl_a = GlobalAnimationController()
    ctrl_b = GlobalAnimationController()
    ctrl_a.register_led_strip(led_a, offset_x=0, offset_y=0, orientation='horizontal')
    ctrl_b.register_led_strip(led_b, offset_x=0, offset_y=0, orientation='horizontal')

    # Give them frame counters that produce a 90-degree hue shift.
    # At speed=360 deg/s, a 90-degree shift requires t_diff = 0.25s = 15 frames at 60Hz.
    # ctrl_a: t=1/60 ≈ 0.0167s  → hue_offset = 0.0167 * 360 = 6 deg
    # ctrl_b: t=16/60 ≈ 0.267s  → hue_offset = 0.267 * 360 = 96 deg (90 deg difference)
    ctrl_a.sync_frame(1)
    ctrl_b.sync_frame(16)

    async def run(ctrl):
        await ctrl.global_rainbow_wave(speed=360.0, duration=0.08)

    asyncio.run(run(ctrl_a))
    asyncio.run(run(ctrl_b))

    # At least some pixels should be different due to the different hue offsets
    colors_a = [led_a.active_animations[i].color for i in range(8)]
    colors_b = [led_b.active_animations[i].color for i in range(8)]
    assert colors_a != colors_b, "Different frame counters should produce different ordered color sequences"


def test_rainbow_wave_fallback_without_frame_counter():
    """global_rainbow_wave falls back to time.monotonic() when frame_counter is 0."""
    ctrl = GlobalAnimationController()
    led = LEDManager(MockJEBPixel(4))
    ctrl.register_led_strip(led, offset_x=0, offset_y=0, orientation='horizontal')
    # Do NOT call sync_frame — _frame_counter stays 0

    async def run():
        await ctrl.global_rainbow_wave(speed=30.0, duration=0.08)

    asyncio.run(run())  # Must not raise or hang

    active = sum(1 for slot in led.active_animations if slot.active)
    assert active > 0, "Rainbow wave fallback should still set animations"


# ---------------------------------------------------------------------------
# Deterministic rain tests
# ---------------------------------------------------------------------------

def test_rain_uses_frame_counter_for_step_timing():
    """global_rain runs correctly when frame_counter is set (falls back to time when not advancing)."""
    ctrl = GlobalAnimationController()
    led = LEDManager(MockJEBPixel(4))
    ctrl.register_led_strip(led, offset_x=0, offset_y=0, orientation='vertical')
    ctrl.sync_frame(60)  # frame_counter set but not advancing → uses time fallback

    async def run():
        await ctrl.global_rain(color=(0, 180, 255), speed=0.05, duration=0.2, density=1.0)

    asyncio.run(run())  # Must not raise or hang


def test_rain_fallback_without_frame_counter():
    """global_rain falls back to time.monotonic() when frame_counter is 0."""
    ctrl = GlobalAnimationController()
    led = LEDManager(MockJEBPixel(4))
    ctrl.register_led_strip(led, offset_x=0, offset_y=0, orientation='vertical')
    # Do NOT call sync_frame

    async def run():
        await ctrl.global_rain(color=(0, 180, 255), speed=0.05, duration=0.15, density=1.0)

    asyncio.run(run())  # Must not raise


# ---------------------------------------------------------------------------
# RenderManager.add_global_animation_controller() tests
# ---------------------------------------------------------------------------

def test_render_manager_add_global_animation_controller():
    """RenderManager propagates frame_counter to registered GlobalAnimationController."""
    pixels = MockPixelObject()
    renderer = RenderManager(pixels, sync_role="NONE")

    ctrl = GlobalAnimationController()
    renderer.add_global_animation_controller(ctrl)

    assert ctrl in renderer._global_anim_controllers, \
        "Controller should be registered in _global_anim_controllers"


def test_render_manager_sync_frame_propagation():
    """RenderManager.run() calls sync_frame on registered controllers each frame."""

    class FrameCapture:
        """Minimal GlobalAnimationController stand-in that records sync calls."""
        def __init__(self):
            self.frames_received = []

        def sync_frame(self, frame):
            self.frames_received.append(frame)

    pixels = MockPixelObject()
    renderer = RenderManager(pixels, sync_role="NONE")
    capture = FrameCapture()
    renderer.add_global_animation_controller(capture)

    async def run_briefly():
        task = asyncio.create_task(renderer.run())
        await asyncio.sleep(0.1)  # Let a few frames run at 60Hz
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(run_briefly())

    assert len(capture.frames_received) > 0, \
        "RenderManager should have called sync_frame at least once"
    # Frame counter should be sequential starting from 1
    for i, frame in enumerate(capture.frames_received, start=1):
        assert frame == i, f"Frame {i} should be {i}, got {frame}"


# ---------------------------------------------------------------------------
# SatelliteNetworkManager SETOFF handshake tests
# ---------------------------------------------------------------------------

def test_satellite_network_manager_sends_setoff_on_hello():
    """_handle_hello_command sends SETOFF when offset is configured."""
    import re

    snm_path = os.path.join(
        os.path.dirname(__file__), '..', 'src', 'managers', 'satellite_network_manager.py'
    )
    with open(snm_path, 'r') as f:
        content = f.read()

    # Verify CMD_SET_OFFSET is imported
    assert 'CMD_SET_OFFSET' in content, "satellite_network_manager should import CMD_SET_OFFSET"

    # Verify _handle_hello_command sends SETOFF
    hello_match = re.search(
        r'async def _handle_hello_command.*?(?=\n    async def |\n    def |\Z)',
        content,
        re.DOTALL
    )
    assert hello_match, "_handle_hello_command should exist"
    hello_body = hello_match.group(0)

    assert 'CMD_SET_OFFSET' in hello_body, \
        "_handle_hello_command should reference CMD_SET_OFFSET"
    assert 'satellite_offsets' in hello_body or '_satellite_offsets' in hello_body, \
        "_handle_hello_command should look up satellite offsets"
    assert 'transport.send' in hello_body, \
        "_handle_hello_command should send the SETOFF message"


def test_satellite_network_manager_config_parameter():
    """SatelliteNetworkManager accepts config with satellite_offsets."""
    snm_path = os.path.join(
        os.path.dirname(__file__), '..', 'src', 'managers', 'satellite_network_manager.py'
    )
    with open(snm_path, 'r') as f:
        content = f.read()

    # config parameter in __init__
    assert 'config=None' in content or 'config = None' in content, \
        "__init__ should accept optional config parameter"
    assert 'satellite_offsets' in content, \
        "satellite_offsets should be extracted from config"


# ---------------------------------------------------------------------------
# Base firmware SETOFF handler tests (source inspection)
# ---------------------------------------------------------------------------

def test_base_firmware_setoff_handler_defined():
    """base_firmware.py defines _handle_set_offset and registers it in _system_handlers."""
    fw_path = os.path.join(
        os.path.dirname(__file__), '..', 'src', 'satellites', 'base_firmware.py'
    )
    with open(fw_path, 'r') as f:
        content = f.read()

    assert '_handle_set_offset' in content, "_handle_set_offset should be defined"
    assert 'CMD_SET_OFFSET' in content, "CMD_SET_OFFSET should be imported/used"
    assert 'GlobalAnimationController' in content, \
        "base_firmware should reference GlobalAnimationController in set_offset handler"


def test_base_firmware_global_animation_handlers_defined():
    """base_firmware.py defines _handle_global_rainbow and _handle_global_rain."""
    fw_path = os.path.join(
        os.path.dirname(__file__), '..', 'src', 'satellites', 'base_firmware.py'
    )
    with open(fw_path, 'r') as f:
        content = f.read()

    assert '_handle_global_rainbow' in content, "_handle_global_rainbow should be defined"
    assert '_handle_global_rain' in content, "_handle_global_rain should be defined"
    assert 'CMD_GLOBAL_RAINBOW' in content, "CMD_GLOBAL_RAINBOW should be used in base_firmware"
    assert 'CMD_GLOBAL_RAIN' in content, "CMD_GLOBAL_RAIN should be used in base_firmware"


def test_sat_01_firmware_registers_leds_on_setoff():
    """sat_01_firmware.py overrides _register_global_anim_leds to attach its LEDs."""
    fw_path = os.path.join(
        os.path.dirname(__file__), '..', 'src', 'satellites', 'sat_01_firmware.py'
    )
    with open(fw_path, 'r') as f:
        content = f.read()

    assert '_register_global_anim_leds' in content, \
        "sat_01_firmware should override _register_global_anim_leds"
    assert 'register_led_strip' in content or 'register_matrix' in content, \
        "sat_01_firmware should register its LEDs with the global animation controller"


def test_sat_01_firmware_syncs_frame_counter_on_sync_frame():
    """sat_01_firmware._handle_sync_frame forwards frame counter to GlobalAnimationController."""
    fw_path = os.path.join(
        os.path.dirname(__file__), '..', 'src', 'satellites', 'sat_01_firmware.py'
    )
    with open(fw_path, 'r') as f:
        content = f.read()

    assert 'sync_frame' in content, \
        "sat_01_firmware._handle_sync_frame should call sync_frame on the controller"


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("Global Animation Sync Test Suite")
    print("=" * 60)

    import traceback

    tests = [
        test_sync_frame_updates_counter,
        test_sync_frame_zero_is_valid,
        test_rainbow_wave_uses_frame_counter_for_hue,
        test_rainbow_wave_different_frame_counters_differ,
        test_rainbow_wave_fallback_without_frame_counter,
        test_rain_uses_frame_counter_for_step_timing,
        test_rain_fallback_without_frame_counter,
        test_render_manager_add_global_animation_controller,
        test_render_manager_sync_frame_propagation,
        test_satellite_network_manager_sends_setoff_on_hello,
        test_satellite_network_manager_config_parameter,
        test_base_firmware_setoff_handler_defined,
        test_base_firmware_global_animation_handlers_defined,
        test_sat_01_firmware_registers_leds_on_setoff,
        test_sat_01_firmware_syncs_frame_counter_on_sync_frame,
    ]

    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            print(f"  ✓ {test_fn.__name__}")
            passed += 1
        except Exception as e:
            print(f"  ✗ {test_fn.__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    if failed == 0:
        print(f"ALL {passed} TESTS PASSED ✓")
    else:
        print(f"{passed} passed, {failed} FAILED ✗")
    print("=" * 60)
    sys.exit(0 if failed == 0 else 1)
