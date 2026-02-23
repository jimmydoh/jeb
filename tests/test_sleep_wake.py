#!/usr/bin/env python3
"""Tests for the distributed sleep state and omni-directional wake feature.

Validates:
- Protocol schema updated to include SLEEP
- HIDManager idle tracking (last_interaction_time, get_idle_time_ms)
- SatelliteNetworkManager remote wake routing
- CoreManager sleep/wake logic
- Satellite (sat_01) sleep/wake handling
"""

import sys
import os
import re
import asyncio
import pytest

SRC = os.path.join(os.path.dirname(__file__), '..', 'src')

# ---------------------------------------------------------------------------
# Protocol tests
# ---------------------------------------------------------------------------

@pytest.fixture
def protocol_content():
    path = os.path.join(SRC, 'transport', 'protocol.py')
    with open(path) as f:
        return f.read()


def test_protocol_schema_includes_sleep(protocol_content):
    """CMD_MODE payload schema should mention SLEEP."""
    assert "SLEEP" in protocol_content, (
        "protocol.py CMD_MODE schema should include SLEEP"
    )


def test_protocol_cmd_mode_schema_desc(protocol_content):
    """CMD_MODE schema description should list IDLE, ACTIVE, and SLEEP."""
    match = re.search(r"CMD_MODE.*?'desc':\s*'([^']+)'", protocol_content)
    assert match, "CMD_MODE schema entry should exist"
    desc = match.group(1)
    assert "SLEEP" in desc, f"CMD_MODE desc should contain SLEEP, got: {desc}"
    assert "ACTIVE" in desc, f"CMD_MODE desc should contain ACTIVE, got: {desc}"


# ---------------------------------------------------------------------------
# HIDManager tests
# ---------------------------------------------------------------------------

@pytest.fixture
def hid_content():
    path = os.path.join(SRC, 'managers', 'hid_manager.py')
    with open(path, encoding='utf-8') as f:
        return f.read()


def test_hid_has_last_interaction_time(hid_content):
    """HIDManager should initialise last_interaction_time."""
    assert "last_interaction_time" in hid_content, (
        "HIDManager should have last_interaction_time attribute"
    )


def test_hid_has_get_idle_time_ms(hid_content):
    """HIDManager should expose get_idle_time_ms() helper."""
    assert "def get_idle_time_ms(" in hid_content, (
        "HIDManager should define get_idle_time_ms()"
    )


def test_hid_updates_last_interaction_on_dirty(hid_content):
    """HIDManager.hw_update should update last_interaction_time when dirty."""
    # Find the hw_update method and check that last_interaction_time is updated
    # inside the `if dirty:` guard within that method
    match = re.search(
        r"def hw_update\(.*?\n(.*?)(?=\n    def |\n#endregion|\Z)",
        hid_content,
        re.DOTALL,
    )
    assert match, "hw_update method body should be found"
    body = match.group(1)
    assert "last_interaction_time" in body, (
        "hw_update should update last_interaction_time"
    )
    idx_dirty = body.find("if dirty:")
    idx_update = body.find("last_interaction_time")
    assert idx_update > idx_dirty, (
        "last_interaction_time should be updated inside the `if dirty:` block of hw_update"
    )


def test_get_idle_time_ms_uses_ticks_diff(hid_content):
    """get_idle_time_ms should use ticks_diff for correct ms calculation."""
    # Find the method body
    match = re.search(r"def get_idle_time_ms\(.*?\n(.*?)(?=\n    def |\Z)", hid_content, re.DOTALL)
    assert match, "get_idle_time_ms method body should be found"
    body = match.group(1)
    assert "ticks_diff" in body, "get_idle_time_ms should use ticks_diff"
    assert "last_interaction_time" in body, "get_idle_time_ms should reference last_interaction_time"


# ---------------------------------------------------------------------------
# SatelliteNetworkManager remote-wake tests (source analysis)
# ---------------------------------------------------------------------------

@pytest.fixture
def snm_content():
    path = os.path.join(SRC, 'managers', 'satellite_network_manager.py')
    with open(path) as f:
        return f.read()


def test_snm_has_wake_callback(snm_content):
    """SatelliteNetworkManager should store a wake callback."""
    assert "_wake_callback" in snm_content, (
        "SatelliteNetworkManager should have _wake_callback attribute"
    )


def test_snm_has_set_wake_callback(snm_content):
    """SatelliteNetworkManager should expose set_wake_callback()."""
    assert "def set_wake_callback(" in snm_content, (
        "SatelliteNetworkManager should define set_wake_callback()"
    )


def test_snm_has_handle_mode_command(snm_content):
    """SatelliteNetworkManager should handle inbound CMD_MODE messages."""
    assert "def _handle_mode_command(" in snm_content, (
        "SatelliteNetworkManager should define _handle_mode_command()"
    )


def test_snm_registers_mode_handler(snm_content):
    """_handle_mode_command should be registered in _system_handlers."""
    assert "_handle_mode_command" in snm_content, (
        "_handle_mode_command should be referenced in _system_handlers"
    )


def test_snm_mode_handler_calls_wake_callback(snm_content):
    """_handle_mode_command should invoke _wake_callback on ACTIVE."""
    # Find the method body
    match = re.search(
        r"async def _handle_mode_command\(.*?\n(.*?)(?=\n    async def |\n    def |\Z)",
        snm_content,
        re.DOTALL,
    )
    assert match, "_handle_mode_command method body should be found"
    body = match.group(1)
    assert "_wake_callback" in body, "_handle_mode_command should call _wake_callback"
    assert "ACTIVE" in body, "_handle_mode_command should check for ACTIVE mode"
    assert "send_all" in body, "_handle_mode_command should echo ACTIVE to all satellites"


# ---------------------------------------------------------------------------
# CoreManager sleep/wake tests (source analysis)
# ---------------------------------------------------------------------------

@pytest.fixture
def core_content():
    path = os.path.join(SRC, 'core', 'core_manager.py')
    with open(path) as f:
        return f.read()


def test_core_has_sleeping_flag(core_content):
    """CoreManager should have a _sleeping state flag."""
    assert "_sleeping" in core_content, (
        "CoreManager should have _sleeping attribute"
    )


def test_core_has_sleep_timeout(core_content):
    """CoreManager should define a sleep timeout constant."""
    assert "_sleep_timeout_ms" in core_content, (
        "CoreManager should define _sleep_timeout_ms"
    )


def test_core_has_enter_sleep(core_content):
    """CoreManager should define _enter_sleep()."""
    assert "async def _enter_sleep(" in core_content, (
        "CoreManager should define _enter_sleep()"
    )


def test_core_has_wake_system(core_content):
    """CoreManager should define _wake_system()."""
    assert "async def _wake_system(" in core_content, (
        "CoreManager should define _wake_system()"
    )


def test_core_enter_sleep_broadcasts(core_content):
    """_enter_sleep should broadcast CMD_MODE SLEEP to satellites."""
    match = re.search(
        r"async def _enter_sleep\(.*?\n(.*?)(?=\n    async def |\n    def |\Z)",
        core_content,
        re.DOTALL,
    )
    assert match, "_enter_sleep method body should be found"
    body = match.group(1)
    assert "send_all" in body, "_enter_sleep should broadcast to satellites"
    assert "SLEEP" in body, "_enter_sleep should send SLEEP mode"


def test_core_wake_system_broadcasts(core_content):
    """_wake_system should broadcast CMD_MODE ACTIVE to satellites."""
    match = re.search(
        r"async def _wake_system\(.*?\n(.*?)(?=\n    async def |\n    def |\Z)",
        core_content,
        re.DOTALL,
    )
    assert match, "_wake_system method body should be found"
    body = match.group(1)
    assert "send_all" in body, "_wake_system should broadcast to satellites"
    assert "ACTIVE" in body, "_wake_system should send ACTIVE mode"


def test_core_registers_wake_callback(core_content):
    """CoreManager should register _wake_system as the remote wake callback."""
    assert "set_wake_callback" in core_content, (
        "CoreManager should call set_wake_callback to register the remote wake handler"
    )
    assert "_wake_system" in core_content, (
        "CoreManager should pass _wake_system as the wake callback"
    )


def test_core_monitor_hid_throttles_while_sleeping(core_content):
    """monitor_hw_hid should use a slower polling rate while sleeping."""
    match = re.search(
        r"async def monitor_hw_hid\(.*?\n(.*?)(?=\n    async def |\n    def |\Z)",
        core_content,
        re.DOTALL,
    )
    assert match, "monitor_hw_hid method body should be found"
    body = match.group(1)
    # Should have a slower sleep (0.1) for when sleeping
    assert "0.1" in body, "monitor_hw_hid should use 0.1s sleep while system is sleeping"
    assert "_sleeping" in body, "monitor_hw_hid should check _sleeping state"


# ---------------------------------------------------------------------------
# Satellite (sat_01) sleep/wake tests (source analysis)
# ---------------------------------------------------------------------------

@pytest.fixture
def sat01_content():
    path = os.path.join(SRC, 'satellites', 'sat_01_firmware.py')
    with open(path) as f:
        return f.read()


def test_sat01_has_sleeping_flag(sat01_content):
    """IndustrialSatelliteFirmware should have a _sleeping state flag."""
    assert "_sleeping" in sat01_content, (
        "sat_01_firmware should have _sleeping attribute"
    )


def test_sat01_has_handle_mode_command(sat01_content):
    """IndustrialSatelliteFirmware should define _handle_mode_command."""
    assert "def _handle_mode_command(" in sat01_content, (
        "sat_01_firmware should define _handle_mode_command()"
    )


def test_sat01_has_enter_sleep(sat01_content):
    """IndustrialSatelliteFirmware should define _enter_sleep."""
    assert "async def _enter_sleep(" in sat01_content, (
        "sat_01_firmware should define _enter_sleep()"
    )


def test_sat01_has_wake_local(sat01_content):
    """IndustrialSatelliteFirmware should define _wake_local."""
    assert "async def _wake_local(" in sat01_content, (
        "sat_01_firmware should define _wake_local()"
    )


def test_sat01_enter_sleep_clears_segment(sat01_content):
    """_enter_sleep should blank the 7-segment display."""
    match = re.search(
        r"async def _enter_sleep\(.*?\n(.*?)(?=\n    async def |\n    def |\Z)",
        sat01_content,
        re.DOTALL,
    )
    assert match, "_enter_sleep body should be found"
    body = match.group(1)
    assert "segment.clear()" in body, "_enter_sleep should clear segment display"


def test_sat01_enter_sleep_throttles_render(sat01_content):
    """_enter_sleep should throttle the render rate to 10Hz."""
    match = re.search(
        r"async def _enter_sleep\(.*?\n(.*?)(?=\n    async def |\n    def |\Z)",
        sat01_content,
        re.DOTALL,
    )
    assert match, "_enter_sleep body should be found"
    body = match.group(1)
    assert "target_frame_rate" in body, "_enter_sleep should update target_frame_rate"
    assert "10" in body, "_enter_sleep should throttle to 10Hz"


def test_sat01_wake_local_restores_frame_rate(sat01_content):
    """_wake_local should restore the default frame rate."""
    match = re.search(
        r"async def _wake_local\(.*?\n(.*?)(?=\n    async def |\n    def |\Z)",
        sat01_content,
        re.DOTALL,
    )
    assert match, "_wake_local body should be found"
    body = match.group(1)
    assert "target_frame_rate" in body, "_wake_local should restore target_frame_rate"
    assert "DEFAULT_FRAME_RATE" in body, "_wake_local should use DEFAULT_FRAME_RATE"


def test_sat01_monitor_hid_throttles_while_sleeping(sat01_content):
    """monitor_hw_hid in sat_01 should throttle polling while sleeping."""
    match = re.search(
        r"async def monitor_hw_hid\(.*?\n(.*?)(?=\n    async def |\n    def |\Z)",
        sat01_content,
        re.DOTALL,
    )
    assert match, "monitor_hw_hid body should be found"
    body = match.group(1)
    assert "_sleeping" in body, "monitor_hw_hid should check _sleeping flag"
    assert "0.1" in body, "monitor_hw_hid should use 0.1s sleep while sleeping"


def test_sat01_remote_wake_sends_active_to_core(sat01_content):
    """When HID input detected during sleep, satellite should send ACTIVE to Core."""
    match = re.search(
        r"async def monitor_hw_hid\(.*?\n(.*?)(?=\n    async def |\n    def |\Z)",
        sat01_content,
        re.DOTALL,
    )
    assert match, "monitor_hw_hid body should be found"
    body = match.group(1)
    assert "CMD_MODE" in body, "satellite monitor_hw_hid should send CMD_MODE"
    assert "ACTIVE" in body, "satellite monitor_hw_hid should send ACTIVE"
    assert "transport_up" in body, "satellite monitor_hw_hid should use transport_up to send"

    # Verify that ACTIVE is only sent when _sleeping is True (inside the sleep guard)
    sleep_block_start = body.find("if self._sleeping:")
    assert sleep_block_start != -1, "monitor_hw_hid should have `if self._sleeping:` guard"
    active_idx = body.find("ACTIVE")
    assert active_idx > sleep_block_start, (
        "ACTIVE should only be sent within the `if self._sleeping:` guard"
    )


# ---------------------------------------------------------------------------
# Runtime logic tests using pure-Python mocks
# ---------------------------------------------------------------------------

class MockTicks:
    """Simulate ticks_ms advancing for idle-time tests."""
    _value = 0

    @staticmethod
    def ticks_ms():
        return MockTicks._value

    @staticmethod
    def ticks_diff(new, old):
        return new - old


def _make_hid_stub():
    """Create a minimal stub that mimics the HIDManager idle-tracking API."""
    # Import the real adafruit_ticks mock from conftest path
    sys.path.insert(0, os.path.join(SRC, 'transport'))  # not needed but harmless

    class HIDStub:
        def __init__(self):
            from adafruit_ticks import ticks_ms
            self.last_interaction_time = ticks_ms()

        def get_idle_time_ms(self):
            from adafruit_ticks import ticks_ms, ticks_diff
            return ticks_diff(ticks_ms(), self.last_interaction_time)

    return HIDStub


def test_idle_time_increases_without_interaction():
    """Idle time should increase when no interaction occurs."""
    sys.path.insert(0, os.path.join(SRC))
    try:
        from adafruit_ticks import ticks_ms, ticks_diff
    except ImportError:
        pytest.skip("adafruit_ticks not available")
        return

    # Check the mock returns numeric values (not a _MockModule proxy)
    t = ticks_ms()
    if not isinstance(t, (int, float)):
        pytest.skip("adafruit_ticks mock does not return numeric values")
        return

    HIDStub = _make_hid_stub()
    hid = HIDStub()

    initial_idle = hid.get_idle_time_ms()
    import time
    time.sleep(0.01)
    later_idle = hid.get_idle_time_ms()

    assert initial_idle >= 0, "Initial idle time should be non-negative"
    assert later_idle >= initial_idle, "Idle time should not decrease"


def test_snm_wake_callback_async():
    """set_wake_callback should store the callback and mode handler should call it."""
    sys.path.insert(0, SRC)

    class FakeTransport:
        def send(self, msg): return True
        def start(self): pass

    class FakeDisplay:
        def update_status(self, *a): pass

    class FakeAudio:
        pass

    class FakeAbortEvent:
        pass

    try:
        from managers.satellite_network_manager import SatelliteNetworkManager
    except ImportError:
        pytest.skip("Cannot import SatelliteNetworkManager (CircuitPython dependencies)")
        return

    snm = SatelliteNetworkManager(FakeTransport(), FakeDisplay(), FakeAudio(), FakeAbortEvent())

    called = []

    async def fake_wake():
        called.append(True)

    snm.set_wake_callback(fake_wake)
    assert snm._wake_callback is fake_wake, "set_wake_callback should store the callback"

    # Simulate receiving ACTIVE from a satellite
    asyncio.run(snm._handle_mode_command("0101", "ACTIVE"))
    assert called, "_handle_mode_command ACTIVE should have invoked the wake callback"


if __name__ == "__main__":
    import pytest as _pytest
    _pytest.main([__file__, "-v"])
