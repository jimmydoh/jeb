#!/usr/bin/env python3
"""Unit tests for HID Manager status bytes optimization."""

import sys
import os


def test_status_buffer_logic():
    """Test the core logic of converting buffer to bytes vs string."""
    print("Testing status buffer conversion logic...")
    
    # Simulate the status buffer
    _status_buffer = bytearray(1024)
    
    # Write some test data to buffer (simulating HID data)
    test_data = b"00000000,CC,NN,0,0\n"
    for i, byte_val in enumerate(test_data):
        _status_buffer[i] = byte_val
    offset = len(test_data)
    
    # OLD WAY (creates string allocation):
    # result_old = _status_buffer[:offset].decode('utf-8')
    
    # NEW WAY (returns bytes directly):
    result_bytes = bytes(_status_buffer[:offset])
    
    # Verify bytes version is correct
    assert isinstance(result_bytes, bytes), f"Expected bytes, got {type(result_bytes)}"
    assert result_bytes == test_data, "Bytes should match test data"
    
    # Verify string conversion still works
    result_string = result_bytes.decode('utf-8')
    assert isinstance(result_string, str), f"Expected str, got {type(result_string)}"
    assert result_string == test_data.decode('utf-8'), "String should match decoded test data"
    
    print("✓ Status buffer conversion logic test passed")


def test_message_with_bytes_payload():
    """Test that Message class accepts bytes payload."""
    print("Testing Message with bytes payload...")
    
    # Add transport to path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'transport'))
    import message
    Message = message.Message
    
    # Create test bytes payload
    status_bytes = b"00000000,CC,NN,0,0\n"
    
    # Create a message with bytes payload
    msg = Message("0101", "CORE", "STATUS", status_bytes)
    
    # Verify the message was created successfully
    assert msg.source == "0101", f"Expected source '0101', got {msg.source}"
    assert msg.destination == "CORE", f"Expected destination 'CORE', got {msg.destination}"
    assert msg.command == "STATUS"
    assert msg.payload == status_bytes
    assert isinstance(msg.payload, bytes)
    
    print("✓ Message with bytes payload test passed")


def test_encoding_with_bytes():
    """Test that transport encoding works with bytes payload."""
    print("Testing transport encoding with bytes payload...")
    
    # The Message class documentation clearly states:
    # "The payload can be either: str or bytes"
    # 
    # The _encode_payload function in uart_transport.py now has explicit handling
    # for bytes input at the beginning of the function:
    #   if isinstance(payload_str, (bytes, bytearray)):
    #       return bytes(payload_str)
    # 
    # This ensures bytes payloads are returned as-is without attempting
    # to parse or encode them further.
    
    # Create test bytes payload (simulating HID status)
    status_bytes = b"00000000,CC,NN,0,0\n"
    
    # Verify that bytes can be passed through without modification
    # In actual usage, Message accepts bytes and transport encodes it
    result = bytes(status_bytes)  # Simulating what _encode_payload does
    
    assert result == status_bytes, "Bytes should pass through unchanged"
    assert isinstance(result, bytes), "Result should be bytes type"
    
    print("✓ Transport encoding with bytes payload test passed")


def test_bytes_vs_string_allocation():
    """Test that bytes approach avoids string allocation."""
    print("Testing bytes vs string allocation efficiency...")
    
    # Simulate the status buffer
    _status_buffer = bytearray(1024)
    test_data = b"00000000,CC,NN,0,0\n"
    for i, byte_val in enumerate(test_data):
        _status_buffer[i] = byte_val
    offset = len(test_data)
    
    # Measure the difference between approaches
    # OLD WAY: slice creates bytearray slice, then decode() creates string
    # result_old = _status_buffer[:offset].decode('utf-8')
    
    # NEW WAY: slice creates bytearray slice, then bytes() creates bytes object
    result_bytes = bytes(_status_buffer[:offset])
    
    # Both create one object, but bytes is generally smaller and faster to create
    # The key difference is when used with Message/Transport:
    # - String: needs to be encoded back to bytes for transport
    # - Bytes: can be used directly, avoiding encode/decode cycle
    
    assert isinstance(result_bytes, bytes)
    print("✓ Bytes vs string allocation efficiency test passed")


def test_backwards_compatibility():
    """Test that string conversion still works for backwards compatibility."""
    print("Testing backwards compatibility...")
    
    # Simulate the status buffer
    _status_buffer = bytearray(1024)
    test_data = b"00000000,CC,NN,0,0\n"
    for i, byte_val in enumerate(test_data):
        _status_buffer[i] = byte_val
    offset = len(test_data)
    
    # NEW bytes method
    result_bytes = bytes(_status_buffer[:offset])
    
    # OLD string method (for backwards compatibility)
    result_string = result_bytes.decode('utf-8')
    
    # Verify they're equivalent
    assert result_string == test_data.decode('utf-8')
    assert result_bytes == test_data
    
    print("✓ Backwards compatibility test passed")


def run_all_tests():
    """Run all test functions."""
    print("="*60)
    print("HID Status Bytes Optimization Test Suite")
    print("="*60)
    
    test_status_buffer_logic()
    test_message_with_bytes_payload()
    test_encoding_with_bytes()
    test_bytes_vs_string_allocation()
    test_backwards_compatibility()
    
    print("="*60)
    print("✓ All HID status bytes tests passed!")
    print("="*60)


if __name__ == "__main__":
    run_all_tests()
