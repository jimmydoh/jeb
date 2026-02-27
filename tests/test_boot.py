#!/usr/bin/env python3
"""Unit tests for boot.py - VBUS sensing and filesystem unlock logic.

These tests inspect the boot.py source to verify the VBUS-based filesystem
access policy and the encoder-button override without requiring CircuitPython
hardware.
"""

import sys
import os
import re

BOOT_PY_PATH = os.path.join(os.path.dirname(__file__), '..', 'src', 'boot.py')


def get_boot_source():
    """Return the full source of boot.py."""
    with open(BOOT_PY_PATH, 'r', encoding='utf-8') as f:
        return f.read()


def get_satellite_branch(source):
    """Return the source text of the satellite-mode branch (if … not vbus_high …)."""
    match = re.search(
        r'if not vbus_high and not force_readonly:.*?(?=elif|else)',
        source, re.DOTALL
    )
    assert match, "Could not find satellite-mode branch in boot.py"
    return match.group(0)


def get_ota_branch(source):
    """Return the source text of the OTA update-mode branch (elif update_mode:)."""
    match = re.search(
        r'elif update_mode:.*?(?=else:)',
        source, re.DOTALL
    )
    assert match, "Could not find OTA update-mode branch (elif update_mode) in boot.py"
    return match.group(0)


def get_normal_branch(source):
    """Return the source text of the normal/forced-readonly else branch."""
    match = re.search(
        r'else:\s*#.*?(?=print\("boot\.py: Initialization complete"\))',
        source, re.DOTALL
    )
    assert match, "Could not find normal-mode else branch in boot.py"
    return match.group(0)


# ---------------------------------------------------------------------------
# VBUS sense detection
# ---------------------------------------------------------------------------

def test_vbus_sense_pin_read():
    """boot.py must read GP24 (VBUS sense) as a digital input."""
    source = get_boot_source()
    assert 'GP24' in source, "boot.py should reference GP24 (VBUS sense pin)"
    assert 'vbus_sense' in source, "boot.py should have a vbus_sense variable"
    assert 'vbus_high' in source, "boot.py should capture the VBUS logic level"
    print("  ✓ GP24 VBUS sense pin is read")


def test_vbus_sense_direction_input():
    """GP24 must be configured as an input (no drive)."""
    source = get_boot_source()
    assert 'Direction.INPUT' in source, \
        "boot.py should set GP24 direction to INPUT"
    print("  ✓ GP24 direction set to INPUT")


# ---------------------------------------------------------------------------
# Override button
# ---------------------------------------------------------------------------

def test_override_button_pin_read():
    """boot.py must read GP12 (encoder push) for the force-readonly override."""
    source = get_boot_source()
    assert 'GP12' in source, "boot.py should reference GP12 (override button)"
    assert 'force_readonly' in source, \
        "boot.py should have a force_readonly variable"
    print("  ✓ GP12 override button is read")


def test_override_button_pull_up():
    """GP12 must use a pull-up (active-low button)."""
    source = get_boot_source()
    assert 'Pull.UP' in source, \
        "boot.py should configure GP12 with Pull.UP (active-low)"
    print("  ✓ GP12 configured with Pull.UP")


def test_override_button_active_low():
    """force_readonly must be True when the pin reads LOW (button pressed)."""
    source = get_boot_source()
    assert 'not override_pin.value' in source, \
        "force_readonly should be 'not override_pin.value' (active-low)"
    print("  ✓ force_readonly uses active-low logic")


# ---------------------------------------------------------------------------
# Satellite deployment mode (VBUS LOW, no override)
# ---------------------------------------------------------------------------

def test_satellite_mode_condition():
    """When VBUS is LOW and override is off, boot.py enters satellite mode."""
    source = get_boot_source()
    assert 'not vbus_high and not force_readonly' in source, \
        "boot.py should check 'not vbus_high and not force_readonly' for satellite mode"
    print("  ✓ Satellite mode condition present")


def test_satellite_mode_remounts_writable():
    """Satellite mode must remount the filesystem as writable."""
    source = get_boot_source()
    branch = get_satellite_branch(source)
    assert "readonly=False" in branch, \
        "Satellite mode should call storage.remount with readonly=False"
    print("  ✓ Satellite mode remounts filesystem as writable")


def test_satellite_mode_disables_usb_drive():
    """Satellite mode must disable USB mass storage (no USB cable present)."""
    source = get_boot_source()
    branch = get_satellite_branch(source)
    assert "disable_usb_drive" in branch, \
        "Satellite mode should call storage.disable_usb_drive()"
    print("  ✓ Satellite mode disables USB mass storage")


# ---------------------------------------------------------------------------
# OTA update mode (existing behaviour preserved)
# ---------------------------------------------------------------------------

def test_ota_update_mode_preserved():
    """OTA update mode must still work when VBUS is HIGH and flag is set."""
    source = get_boot_source()
    assert 'update_mode' in source, \
        "boot.py should still check for an OTA update flag"
    assert '.update_flag' in source, \
        "boot.py should still detect .update_flag for OTA updates"
    print("  ✓ OTA update mode detection is preserved")


def test_ota_update_mode_remounts_writable():
    """OTA update mode must remount the filesystem as writable."""
    source = get_boot_source()
    branch = get_ota_branch(source)
    assert "readonly=False" in branch, \
        "OTA update mode should call storage.remount with readonly=False"
    print("  ✓ OTA update mode remounts filesystem as writable")


# ---------------------------------------------------------------------------
# Normal / debug mode (VBUS HIGH or force_readonly)
# ---------------------------------------------------------------------------

def test_normal_mode_remounts_readonly():
    """Normal/debug mode must keep the filesystem read-only for code."""
    source = get_boot_source()
    branch = get_normal_branch(source)
    assert "readonly=True" in branch, \
        "Normal mode should call storage.remount with readonly=True"
    print("  ✓ Normal mode keeps filesystem read-only")


def test_force_readonly_message():
    """boot.py must print a distinct message when the override button is held."""
    source = get_boot_source()
    assert 'FORCED READONLY MODE' in source, \
        "boot.py should print 'FORCED READONLY MODE' when override button forces readonly"
    print("  ✓ Force-readonly override prints a distinct message")


# ---------------------------------------------------------------------------
# Priority / ordering
# ---------------------------------------------------------------------------

def test_satellite_mode_has_priority_over_update_mode():
    """Satellite deployment mode must be evaluated before OTA update mode."""
    source = get_boot_source()
    sat_pos = source.find('not vbus_high and not force_readonly')
    ota_pos = source.find('elif update_mode')
    assert sat_pos != -1, "Satellite mode condition not found"
    assert ota_pos != -1, "OTA update mode condition not found"
    assert sat_pos < ota_pos, \
        "Satellite mode check must appear before OTA update mode check"
    print("  ✓ Satellite mode is checked before OTA update mode")


def test_vbus_sense_read_before_mode_decision():
    """VBUS sense must be read before the mode-decision block."""
    source = get_boot_source()
    vbus_pos = source.find('vbus_high = vbus_sense.value')
    mode_pos = source.find('not vbus_high and not force_readonly')
    assert vbus_pos != -1, "vbus_high assignment not found"
    assert mode_pos != -1, "Satellite mode condition not found"
    assert vbus_pos < mode_pos, \
        "VBUS sense must be read before the mode-decision block"
    print("  ✓ VBUS sense is read before the mode-decision block")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("boot.py VBUS Sensing Test Suite")
    print("=" * 60)

    tests = [
        test_vbus_sense_pin_read,
        test_vbus_sense_direction_input,
        test_override_button_pin_read,
        test_override_button_pull_up,
        test_override_button_active_low,
        test_satellite_mode_condition,
        test_satellite_mode_remounts_writable,
        test_satellite_mode_disables_usb_drive,
        test_ota_update_mode_preserved,
        test_ota_update_mode_remounts_writable,
        test_normal_mode_remounts_readonly,
        test_force_readonly_message,
        test_satellite_mode_has_priority_over_update_mode,
        test_vbus_sense_read_before_mode_decision,
    ]

    passed = 0
    failed = 0
    for test in tests:
        print(f"\n{test.__name__}")
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  ❌ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    if failed == 0:
        print(f"ALL {passed} TESTS PASSED ✓")
        sys.exit(0)
    else:
        print(f"{passed} passed, {failed} FAILED ✗")
        sys.exit(1)
