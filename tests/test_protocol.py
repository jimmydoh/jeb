#!/usr/bin/env python3
"""Unit tests for protocol definitions."""

import sys
import os

# Add src to path for direct module import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import protocol module
import protocol


def test_command_map_completeness():
    """Test that command map has expected entries."""
    print("Testing command map completeness...")
    
    # Check that key command codes exist
    expected_commands = [
        "STATUS", "ID_ASSIGN", "NEW_SAT", "ERROR", "LOG", "POWER",
        "LED", "LEDFLASH", "LEDBREATH", "LEDCYLON", "LEDCENTRI", "LEDRAINBOW", "LEDGLITCH",
        "DSP", "DSPCORRUPT", "DSPMATRIX",
        "SETENC"
    ]
    
    for cmd in expected_commands:
        assert cmd in protocol.COMMAND_MAP, f"Command '{cmd}' not found in COMMAND_MAP"
    
    print(f"✓ All {len(expected_commands)} expected commands found in COMMAND_MAP")


def test_command_map_values_are_bytes():
    """Test that all command values are valid byte values."""
    print("\nTesting command map values are valid bytes...")
    
    for cmd, value in protocol.COMMAND_MAP.items():
        assert isinstance(value, int), f"Command '{cmd}' value should be int, got {type(value)}"
        assert 0 <= value <= 255, f"Command '{cmd}' value {value} is not a valid byte (0-255)"
    
    print(f"✓ All {len(protocol.COMMAND_MAP)} command values are valid bytes")


def test_command_reverse_map():
    """Test that reverse command map is correct."""
    print("\nTesting command reverse map...")
    
    # Check that reverse map is the inverse of command map
    for cmd, code in protocol.COMMAND_MAP.items():
        assert code in protocol.COMMAND_REVERSE_MAP, f"Code {code} for command '{cmd}' not in reverse map"
        assert protocol.COMMAND_REVERSE_MAP[code] == cmd, f"Reverse mapping mismatch for command '{cmd}'"
    
    # Check that sizes match
    assert len(protocol.COMMAND_MAP) == len(protocol.COMMAND_REVERSE_MAP), \
        "COMMAND_MAP and COMMAND_REVERSE_MAP should have same size"
    
    print(f"✓ Command reverse map correctly mirrors command map")


def test_command_map_no_duplicates():
    """Test that command codes don't have duplicate values."""
    print("\nTesting command map has no duplicate values...")
    
    values = list(protocol.COMMAND_MAP.values())
    unique_values = set(values)
    
    assert len(values) == len(unique_values), \
        f"Found duplicate command codes! {len(values)} total, {len(unique_values)} unique"
    
    print(f"✓ All {len(values)} command codes are unique")


def test_destination_map():
    """Test destination map definitions."""
    print("\nTesting destination map...")
    
    assert "ALL" in protocol.DEST_MAP, "Destination 'ALL' should be defined"
    assert "SAT" in protocol.DEST_MAP, "Destination 'SAT' should be defined"
    
    # Check that ALL is broadcast (0xFF)
    assert protocol.DEST_MAP["ALL"] == 0xFF, "ALL destination should be 0xFF"
    
    # Check that SAT is satellite broadcast (0xFE)
    assert protocol.DEST_MAP["SAT"] == 0xFE, "SAT destination should be 0xFE"
    
    print(f"✓ Destination map correctly defined with {len(protocol.DEST_MAP)} entries")


def test_destination_reverse_map():
    """Test destination reverse map."""
    print("\nTesting destination reverse map...")
    
    for dest, code in protocol.DEST_MAP.items():
        assert code in protocol.DEST_REVERSE_MAP, f"Code {code} for dest '{dest}' not in reverse map"
        assert protocol.DEST_REVERSE_MAP[code] == dest, f"Reverse mapping mismatch for dest '{dest}'"
    
    assert len(protocol.DEST_MAP) == len(protocol.DEST_REVERSE_MAP), \
        "DEST_MAP and DEST_REVERSE_MAP should have same size"
    
    print("✓ Destination reverse map correctly mirrors destination map")


def test_max_index_value():
    """Test MAX_INDEX_VALUE constant."""
    print("\nTesting MAX_INDEX_VALUE constant...")
    
    assert hasattr(protocol, 'MAX_INDEX_VALUE'), "MAX_INDEX_VALUE should be defined"
    assert isinstance(protocol.MAX_INDEX_VALUE, int), "MAX_INDEX_VALUE should be an integer"
    assert protocol.MAX_INDEX_VALUE > 0, "MAX_INDEX_VALUE should be positive"
    assert protocol.MAX_INDEX_VALUE == 100, "MAX_INDEX_VALUE should be 100"
    
    print(f"✓ MAX_INDEX_VALUE correctly set to {protocol.MAX_INDEX_VALUE}")


def test_encoding_constants():
    """Test encoding type constants."""
    print("\nTesting encoding constants...")
    
    expected_encodings = [
        'ENCODING_RAW_TEXT',
        'ENCODING_NUMERIC_BYTES',
        'ENCODING_NUMERIC_WORDS',
        'ENCODING_FLOATS'
    ]
    
    for enc in expected_encodings:
        assert hasattr(protocol, enc), f"Encoding constant '{enc}' should be defined"
        value = getattr(protocol, enc)
        assert isinstance(value, str), f"Encoding constant '{enc}' should be a string"
    
    print(f"✓ All {len(expected_encodings)} encoding constants defined")


def test_payload_schemas():
    """Test payload schema definitions."""
    print("\nTesting payload schemas...")
    
    assert hasattr(protocol, 'PAYLOAD_SCHEMAS'), "PAYLOAD_SCHEMAS should be defined"
    assert isinstance(protocol.PAYLOAD_SCHEMAS, dict), "PAYLOAD_SCHEMAS should be a dictionary"
    
    # Check that key commands have schemas
    expected_schema_commands = [
        "ID_ASSIGN", "NEW_SAT", "ERROR", "LOG",
        "LED", "LEDFLASH", "LEDBREATH",
        "DSP", "POWER", "STATUS", "SETENC"
    ]
    
    for cmd in expected_schema_commands:
        assert cmd in protocol.PAYLOAD_SCHEMAS, f"Command '{cmd}' should have a payload schema"
        schema = protocol.PAYLOAD_SCHEMAS[cmd]
        assert 'type' in schema, f"Schema for '{cmd}' should have 'type' field"
        assert 'desc' in schema, f"Schema for '{cmd}' should have 'desc' field"
    
    print(f"✓ Payload schemas defined for {len(protocol.PAYLOAD_SCHEMAS)} commands")


def test_payload_schema_encoding_types():
    """Test that payload schemas use valid encoding types."""
    print("\nTesting payload schema encoding types...")
    
    valid_types = {
        protocol.ENCODING_RAW_TEXT,
        protocol.ENCODING_NUMERIC_BYTES,
        protocol.ENCODING_NUMERIC_WORDS,
        protocol.ENCODING_FLOATS
    }
    
    for cmd, schema in protocol.PAYLOAD_SCHEMAS.items():
        encoding_type = schema['type']
        assert encoding_type in valid_types, \
            f"Command '{cmd}' has invalid encoding type '{encoding_type}'"
    
    print(f"✓ All {len(protocol.PAYLOAD_SCHEMAS)} payload schemas use valid encoding types")


def test_text_payload_commands():
    """Test that text-based commands are properly marked."""
    print("\nTesting text payload commands...")
    
    # Commands that should use raw text
    text_commands = ["ID_ASSIGN", "NEW_SAT", "ERROR", "LOG", "DSP"]
    
    for cmd in text_commands:
        schema = protocol.PAYLOAD_SCHEMAS.get(cmd)
        assert schema is not None, f"Command '{cmd}' should have a schema"
        assert schema['type'] == protocol.ENCODING_RAW_TEXT, \
            f"Command '{cmd}' should use ENCODING_RAW_TEXT"
    
    print(f"✓ All {len(text_commands)} text commands correctly marked")


def test_numeric_payload_commands():
    """Test that numeric-based commands are properly marked."""
    print("\nTesting numeric payload commands...")
    
    # Commands that should use numeric bytes
    numeric_commands = ["LED", "LEDFLASH", "LEDBREATH", "STATUS"]
    
    for cmd in numeric_commands:
        schema = protocol.PAYLOAD_SCHEMAS.get(cmd)
        assert schema is not None, f"Command '{cmd}' should have a schema"
        assert schema['type'] == protocol.ENCODING_NUMERIC_BYTES, \
            f"Command '{cmd}' should use ENCODING_NUMERIC_BYTES"
    
    print(f"✓ All {len(numeric_commands)} numeric commands correctly marked")


def test_float_payload_commands():
    """Test that float-based commands are properly marked."""
    print("\nTesting float payload commands...")
    
    # Commands that should use floats
    float_commands = ["POWER"]
    
    for cmd in float_commands:
        schema = protocol.PAYLOAD_SCHEMAS.get(cmd)
        assert schema is not None, f"Command '{cmd}' should have a schema"
        assert schema['type'] == protocol.ENCODING_FLOATS, \
            f"Command '{cmd}' should use ENCODING_FLOATS"
    
    print(f"✓ All {len(float_commands)} float commands correctly marked")


def test_command_categories():
    """Test that commands are organized by category."""
    print("\nTesting command categories...")
    
    # Core commands (0x01-0x0F)
    core_commands = ["STATUS", "ID_ASSIGN", "NEW_SAT", "ERROR", "LOG", "POWER"]
    for cmd in core_commands:
        value = protocol.COMMAND_MAP[cmd]
        assert 0x01 <= value <= 0x0F, f"Core command '{cmd}' should be in range 0x01-0x0F"
    
    # LED commands (0x10-0x1F)
    led_commands = ["LED", "LEDFLASH", "LEDBREATH", "LEDCYLON", "LEDCENTRI", "LEDRAINBOW", "LEDGLITCH"]
    for cmd in led_commands:
        value = protocol.COMMAND_MAP[cmd]
        assert 0x10 <= value <= 0x1F, f"LED command '{cmd}' should be in range 0x10-0x1F"
    
    # Display commands (0x20-0x2F)
    display_commands = ["DSP", "DSPCORRUPT", "DSPMATRIX"]
    for cmd in display_commands:
        value = protocol.COMMAND_MAP[cmd]
        assert 0x20 <= value <= 0x2F, f"Display command '{cmd}' should be in range 0x20-0x2F"
    
    # Encoder commands (0x30-0x3F)
    encoder_commands = ["SETENC"]
    for cmd in encoder_commands:
        value = protocol.COMMAND_MAP[cmd]
        assert 0x30 <= value <= 0x3F, f"Encoder command '{cmd}' should be in range 0x30-0x3F"
    
    print("✓ All commands correctly organized by category")


def run_all_tests():
    """Run all protocol tests."""
    print("="*60)
    print("Running Protocol Definition Tests")
    print("="*60)
    
    tests = [
        test_command_map_completeness,
        test_command_map_values_are_bytes,
        test_command_reverse_map,
        test_command_map_no_duplicates,
        test_destination_map,
        test_destination_reverse_map,
        test_max_index_value,
        test_encoding_constants,
        test_payload_schemas,
        test_payload_schema_encoding_types,
        test_text_payload_commands,
        test_numeric_payload_commands,
        test_float_payload_commands,
        test_command_categories,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"\n✗ {test.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"\n✗ {test.__name__} ERROR: {e}")
            failed += 1
    
    print("\n" + "="*60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("="*60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
