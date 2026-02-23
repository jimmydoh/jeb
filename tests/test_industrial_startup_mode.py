"""Tests for the refactored IndustrialStartup mode.

Validates:
- Correct audio API keyword capitalisation (all lowercase interrupt/wait)
- Phase pool randomisation (3 of 4 middle phases selected)
- Reactor Balance constants and render logic
- Boot splash method presence
- Bug fix: Auth Code phase no longer uses self.core.current_mode_step
- Valid Python syntax
"""

import sys
import os
import re

# ---------------------------------------------------------------------------
# Source path setup
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'src', 'modes', 'industrial_startup.py'
)


def _source():
    with open(_PATH, 'r') as f:
        return f.read()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_file_exists():
    assert os.path.exists(_PATH), "industrial_startup.py does not exist"
    print("✓ industrial_startup.py exists")


def test_valid_syntax():
    import ast
    src = _source()
    try:
        ast.parse(src)
    except SyntaxError as e:
        raise AssertionError(f"Syntax error in industrial_startup.py: {e}")
    print("✓ Valid Python syntax")


def test_audio_api_no_uppercase_interrupt():
    """All audio play() calls must use lowercase 'interrupt', not 'Interrupt'."""
    src = _source()
    # Find all audio.play() calls and ensure 'Interrupt=' does not appear
    assert "Interrupt=" not in src, (
        "Found capitalised 'Interrupt=' in audio call(s). Must be 'interrupt='."
    )
    print("✓ No 'Interrupt=' found in audio calls")


def test_audio_api_no_uppercase_wait():
    """All audio play() calls must use lowercase 'wait', not 'Wait'."""
    src = _source()
    assert "Wait=" not in src, (
        "Found capitalised 'Wait=' in audio call(s). Must be 'wait='."
    )
    print("✓ No 'Wait=' found in audio calls")


def test_no_current_mode_step_increment():
    """Auth Code phase must no longer increment self.core.current_mode_step."""
    src = _source()
    assert "self.core.current_mode_step += 1" not in src, (
        "Found 'self.core.current_mode_step += 1' — should have been removed."
    )
    print("✓ self.core.current_mode_step += 1 not present")


def test_phase_methods_exist():
    """All four standalone phase methods must be defined."""
    src = _source()
    for method in [
        "_phase_boot_splash",
        "_phase_toggles",
        "_phase_auth_code",
        "_phase_brackets",
        "_phase_reactor_balance",
    ]:
        assert f"async def {method}" in src, (
            f"Method '{method}' not found in industrial_startup.py"
        )
    print("✓ All phase helper methods defined")


def test_phase_pool_uses_shuffle_and_slice():
    """run() must shuffle the phase_pool and select 3 items."""
    src = _source()
    assert "random.shuffle(phase_pool)" in src, (
        "run() must call random.shuffle(phase_pool)"
    )
    assert "phase_pool[:3]" in src, (
        "run() must slice 3 items from phase_pool"
    )
    print("✓ Phase pool uses shuffle and [:3] slice")


def test_phase_pool_contains_all_four_phases():
    """The phase pool list must contain all four mini-game references."""
    src = _source()
    for phase in [
        "self._phase_toggles",
        "self._phase_auth_code",
        "self._phase_brackets",
        "self._phase_reactor_balance",
    ]:
        assert phase in src, f"Phase reference '{phase}' missing from phase pool"
    print("✓ Phase pool contains all four mini-game references")


def test_reactor_balance_class_constants():
    """Reactor Balance constants must be defined as class attributes."""
    src = _source()
    assert "REACTOR_BALANCE_DURATION" in src, (
        "REACTOR_BALANCE_DURATION constant missing"
    )
    assert "_REACTOR_COL_COUNT" in src, (
        "_REACTOR_COL_COUNT constant missing"
    )
    assert "_REACTOR_SAFE_MIN" in src, (
        "_REACTOR_SAFE_MIN constant missing"
    )
    assert "_REACTOR_SAFE_MAX" in src, (
        "_REACTOR_SAFE_MAX constant missing"
    )
    print("✓ Reactor Balance class constants defined")


def test_reactor_balance_countdown_format():
    """Reactor Balance must format a 'T-' countdown and send to satellite DSP."""
    src = _source()
    # The countdown string must be sent to satellite display
    assert 'sat.send("DSP"' in src or "sat.send('DSP'" in src, (
        "Reactor Balance must send DSP command to satellite display"
    )
    # T- prefix must be present in the format string
    assert "T-" in src, (
        "Reactor Balance countdown must include 'T-' prefix"
    )
    print("✓ Reactor Balance countdown format sends to satellite DSP")


def test_reactor_balance_game_over_returned_not_called():
    """_phase_reactor_balance must return 'GAME_OVER', not call self.game_over()."""
    src = _source()
    # Extract the _phase_reactor_balance method body
    # Find method start
    method_start = src.find("async def _phase_reactor_balance")
    assert method_start != -1, "_phase_reactor_balance method not found"

    # Find the next method definition after reactor balance
    next_method = src.find("\n    async def ", method_start + 1)
    if next_method == -1:
        method_body = src[method_start:]
    else:
        method_body = src[method_start:next_method]

    assert 'return "GAME_OVER"' in method_body, (
        "_phase_reactor_balance must return 'GAME_OVER' (not call game_over())"
    )
    assert "await self.game_over()" not in method_body, (
        "_phase_reactor_balance must not call self.game_over() directly"
    )
    print("✓ _phase_reactor_balance returns 'GAME_OVER' string, not direct call")


def test_run_calls_game_over_on_failure():
    """run() must call await self.game_over() when a phase returns GAME_OVER."""
    src = _source()
    # Extract the run() method body
    method_start = src.find("    async def run(self):")
    assert method_start != -1, "run() method not found"
    method_body = src[method_start:]

    assert "return await self.game_over()" in method_body, (
        "run() must call 'return await self.game_over()' on phase failure"
    )
    print("✓ run() calls await self.game_over() on phase failure")


def test_reactor_balance_uses_latching_toggles():
    """Reactor Balance must read is_latching_toggled for the 4 columns."""
    src = _source()
    method_start = src.find("async def _phase_reactor_balance")
    next_method = src.find("\n    async def ", method_start + 1)
    method_body = src[method_start:next_method] if next_method != -1 else src[method_start:]

    assert "is_latching_toggled" in method_body, (
        "_phase_reactor_balance must check is_latching_toggled for column control"
    )
    print("✓ _phase_reactor_balance uses is_latching_toggled")


def test_core_oled_shows_critical_temp():
    """Core OLED must show CORE TEMP: CRITICAL during Reactor Balance."""
    src = _source()
    assert "CORE TEMP: CRITICAL" in src, (
        "Core OLED must display 'CORE TEMP: CRITICAL' during Reactor Balance"
    )
    print("✓ 'CORE TEMP: CRITICAL' present in Reactor Balance phase")


def test_boot_splash_uses_matrix_dimensions():
    """Boot splash must use dynamic matrix width/height."""
    src = _source()
    method_start = src.find("async def _phase_boot_splash")
    next_method = src.find("\n    async def ", method_start + 1)
    method_body = src[method_start:next_method] if next_method != -1 else src[method_start:]

    assert "self.core.matrix.width" in method_body, (
        "_phase_boot_splash must use self.core.matrix.width"
    )
    assert "self.core.matrix.height" in method_body, (
        "_phase_boot_splash must use self.core.matrix.height"
    )
    print("✓ Boot splash uses dynamic matrix dimensions")


def test_reactor_balance_safe_zone_colors():
    """Reactor Balance must differentiate safe/warning/danger colours."""
    src = _source()
    method_start = src.find("async def _phase_reactor_balance")
    next_method = src.find("\n    async def ", method_start + 1)
    method_body = src[method_start:next_method] if next_method != -1 else src[method_start:]

    assert "Palette.GREEN" in method_body, (
        "_phase_reactor_balance must use Palette.GREEN for safe zone"
    )
    assert "Palette.RED" in method_body or "Palette.YELLOW" in method_body, (
        "_phase_reactor_balance must use Palette.RED or YELLOW for danger zone"
    )
    print("✓ Reactor Balance uses safe-zone colour coding")


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Running IndustrialStartup mode tests...\n")
    tests = [
        test_file_exists,
        test_valid_syntax,
        test_audio_api_no_uppercase_interrupt,
        test_audio_api_no_uppercase_wait,
        test_no_current_mode_step_increment,
        test_phase_methods_exist,
        test_phase_pool_uses_shuffle_and_slice,
        test_phase_pool_contains_all_four_phases,
        test_reactor_balance_class_constants,
        test_reactor_balance_countdown_format,
        test_reactor_balance_game_over_returned_not_called,
        test_run_calls_game_over_on_failure,
        test_reactor_balance_uses_latching_toggles,
        test_core_oled_shows_critical_temp,
        test_boot_splash_uses_matrix_dimensions,
        test_reactor_balance_safe_zone_colors,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            print(f"\n❌ {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"\n❌ {t.__name__} (unexpected): {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'✅ All tests passed!' if not failed else f'❌ {failed} test(s) failed.'}")
    sys.exit(0 if not failed else 1)
