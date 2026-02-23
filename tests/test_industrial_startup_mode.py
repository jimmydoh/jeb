"""Tests for the refactored IndustrialStartup mode.

Validates:
- Correct audio API keyword capitalization (all lowercase interrupt/wait)
- Phase pool randomization (3 of 4 middle phases selected)
- Reactor Balance constants and render logic
- Boot splash method presence
- Bug fix: Auth Code phase no longer uses self.core.current_mode_step
- Bug fix: Toggle sequence randint upper bound is 4 (not 5) to avoid IndexError
- Bug fix: Auth Code clears keypad buffer after "Go!" cue, not before dictation
- Bug fix: matrix.fill uses show=False inside animation loops to prevent flickering
- Polish: Reactor Balance meltdown triggers red flash + SFX before returning GAME_OVER
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


def test_toggle_randint_max_is_4():
    """Toggle selection must roll 0-4 (not 0-5) to avoid IndexError with one momentary toggle."""
    src = _source()
    method_start = src.find("async def _phase_toggles")
    next_method = src.find("\n    async def ", method_start + 1)
    method_body = src[method_start:next_method] if next_method != -1 else src[method_start:]

    assert "random.randint(0, 4)" in method_body, (
        "_phase_toggles must use randint(0, 4) to avoid IndexError on the single momentary toggle"
    )
    assert "random.randint(0, 5)" not in method_body, (
        "_phase_toggles must NOT use randint(0, 5) — index 5 would cause IndexError"
    )
    print("✓ Toggle randint upper bound is 4")


def test_auth_code_clears_buffer_after_go_cue():
    """clear_key() must appear AFTER keypad_go.wav wait, not before dictation starts."""
    src = _source()
    method_start = src.find("async def _phase_auth_code")
    next_method = src.find("\n    async def ", method_start + 1)
    method_body = src[method_start:next_method] if next_method != -1 else src[method_start:]

    go_pos = method_body.find("keypad_go.wav")
    assert go_pos != -1, "keypad_go.wav not found in _phase_auth_code"

    # clear_key() must come AFTER keypad_go.wav
    clear_after_go = method_body.find("sat.clear_key()", go_pos)
    assert clear_after_go != -1, (
        "sat.clear_key() must be called AFTER the 'keypad_go.wav' cue to drop premature presses"
    )

    # clear_key() must NOT appear before keypad_go.wav (except inside the entry loop for individual keys)
    # The only clear_key() before the entry loop should not exist as a standalone flush
    clear_before_go = method_body.find("sat.clear_key()", 0)
    # If there's a clear_key before go_pos, it must be inside the entry loop (after start_time)
    entry_loop_pos = method_body.find("start_time = ticks_ms()")
    assert entry_loop_pos != -1, "start_time = ticks_ms() entry loop marker not found in _phase_auth_code"
    if clear_before_go < go_pos:
        # Allow if it's inside the entry loop
        assert clear_before_go > entry_loop_pos, (
            "sat.clear_key() must not appear before the 'keypad_go.wav' cue as a pre-flush"
        )
    print("✓ Auth Code clears keypad buffer after 'Go!' cue")


def test_no_show_true_in_animation_loops():
    """matrix.fill(Palette.OFF) inside animation loops must use show=False to prevent flickering."""
    src = _source()

    # Check _phase_brackets
    brackets_start = src.find("async def _phase_brackets")
    brackets_end_candidate = src.find("\n    async def ", brackets_start + 1)
    brackets_body = src[brackets_start:brackets_end_candidate] if brackets_end_candidate != -1 else src[brackets_start:]

    assert "fill(Palette.OFF, show=True)" not in brackets_body, (
        "_phase_brackets must use show=False for matrix.fill(Palette.OFF) to prevent flickering"
    )

    # Check _phase_reactor_balance
    reactor_start = src.find("async def _phase_reactor_balance")
    reactor_end = src.find("\n    async def ", reactor_start + 1)
    reactor_body = src[reactor_start:reactor_end] if reactor_end != -1 else src[reactor_start:]

    # The render clear inside the loop must be show=False
    # (the meltdown red flash uses show=True intentionally — that's OK)
    fill_off_idx = reactor_body.find("fill(Palette.OFF, show=True)")
    assert fill_off_idx == -1, (
        "_phase_reactor_balance must use show=False for the per-tick matrix clear to prevent flickering"
    )
    print("✓ matrix.fill(Palette.OFF) uses show=False in animation loops")


def test_reactor_balance_meltdown_drama():
    """Reactor Balance meltdown must flash matrix red and play crash SFX before returning."""
    src = _source()
    method_start = src.find("async def _phase_reactor_balance")
    next_method = src.find("\n    async def ", method_start + 1)
    method_body = src[method_start:next_method] if next_method != -1 else src[method_start:]

    # Red flash must precede the GAME_OVER return
    red_fill_pos = method_body.find("Palette.RED")
    game_over_pos = method_body.find('return "GAME_OVER"')
    assert red_fill_pos != -1, (
        "_phase_reactor_balance meltdown must flash the matrix red"
    )
    assert red_fill_pos < game_over_pos, (
        "Red matrix flash must appear before the 'return GAME_OVER' statement"
    )

    # Crash SFX must be present before the GAME_OVER return
    crash_sfx_pos = method_body.find("crash.wav")
    assert crash_sfx_pos != -1, (
        "_phase_reactor_balance meltdown must play crash.wav SFX"
    )
    assert crash_sfx_pos < game_over_pos, (
        "crash.wav must be played before the 'return GAME_OVER' statement"
    )
    print("✓ Reactor Balance meltdown triggers red flash and crash SFX")


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
        test_toggle_randint_max_is_4,
        test_auth_code_clears_buffer_after_go_cue,
        test_no_show_true_in_animation_loops,
        test_reactor_balance_meltdown_drama,
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
