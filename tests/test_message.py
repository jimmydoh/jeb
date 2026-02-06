#!/usr/bin/env python3
"""Unit tests for Message class."""

import sys
import os

# Add src/transport to path for direct module import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'transport'))

# Import Message class
import message
Message = message.Message


def test_message_creation_with_string_payload():
    """Test creating a message with string payload."""
    print("Testing message creation with string payload...")
    
    msg = Message("0101", "STATUS", "0000,C,N,0,0")
    
    assert msg.destination == "0101", f"Expected destination '0101', got {msg.destination}"
    assert msg.command == "STATUS", f"Expected command 'STATUS', got {msg.command}"
    assert msg.payload == "0000,C,N,0,0", f"Expected payload '0000,C,N,0,0', got {msg.payload}"
    
    print("✓ Message creation with string payload test passed")


def test_message_creation_with_bytes_payload():
    """Test creating a message with bytes payload."""
    print("\nTesting message creation with bytes payload...")
    
    payload_bytes = b'\x01\x02\x03\x04'
    msg = Message("0102", "DATA", payload_bytes)
    
    assert msg.destination == "0102"
    assert msg.command == "DATA"
    assert msg.payload == payload_bytes
    assert isinstance(msg.payload, bytes), "Payload should be bytes type"
    
    print("✓ Message creation with bytes payload test passed")


def test_message_broadcast():
    """Test creating a broadcast message."""
    print("\nTesting broadcast message...")
    
    msg = Message("ALL", "ID_ASSIGN", "0100")
    
    assert msg.destination == "ALL", "Broadcast should use 'ALL' destination"
    assert msg.command == "ID_ASSIGN"
    assert msg.payload == "0100"
    
    print("✓ Broadcast message test passed")


def test_message_repr_string():
    """Test string representation with string payload."""
    print("\nTesting message __repr__ with string...")
    
    msg = Message("0101", "LED", "0,255,0,0,2.0,0.5,2")
    repr_str = repr(msg)
    
    assert "0101" in repr_str, "Repr should contain destination"
    assert "LED" in repr_str, "Repr should contain command"
    assert "0,255,0,0,2.0,0.5,2" in repr_str, "Repr should contain payload"
    assert repr_str.startswith("Message("), "Repr should start with 'Message('"
    
    print("✓ Message repr with string test passed")


def test_message_repr_bytes():
    """Test string representation with bytes payload."""
    print("\nTesting message __repr__ with bytes...")
    
    payload_bytes = b'\x01\x02\x03\x04\x05'
    msg = Message("0102", "BINARY", payload_bytes)
    repr_str = repr(msg)
    
    assert "0102" in repr_str, "Repr should contain destination"
    assert "BINARY" in repr_str, "Repr should contain command"
    assert "<bytes:5>" in repr_str, "Repr should show bytes length"
    assert "0,255,0,0,2.0,0.5,2" not in repr_str, "Repr should not show raw bytes"
    
    print("✓ Message repr with bytes test passed")


def test_message_equality_same():
    """Test message equality for identical messages."""
    print("\nTesting message equality (same)...")
    
    msg1 = Message("0101", "STATUS", "online")
    msg2 = Message("0101", "STATUS", "online")
    
    assert msg1 == msg2, "Identical messages should be equal"
    
    print("✓ Message equality (same) test passed")


def test_message_equality_different_destination():
    """Test message inequality for different destinations."""
    print("\nTesting message inequality (different destination)...")
    
    msg1 = Message("0101", "STATUS", "online")
    msg2 = Message("0102", "STATUS", "online")
    
    assert msg1 != msg2, "Messages with different destinations should not be equal"
    
    print("✓ Message inequality (destination) test passed")


def test_message_equality_different_command():
    """Test message inequality for different commands."""
    print("\nTesting message inequality (different command)...")
    
    msg1 = Message("0101", "STATUS", "data")
    msg2 = Message("0101", "LED", "data")
    
    assert msg1 != msg2, "Messages with different commands should not be equal"
    
    print("✓ Message inequality (command) test passed")


def test_message_equality_different_payload():
    """Test message inequality for different payloads."""
    print("\nTesting message inequality (different payload)...")
    
    msg1 = Message("0101", "STATUS", "payload1")
    msg2 = Message("0101", "STATUS", "payload2")
    
    assert msg1 != msg2, "Messages with different payloads should not be equal"
    
    print("✓ Message inequality (payload) test passed")


def test_message_equality_bytes_payload():
    """Test message equality with bytes payloads."""
    print("\nTesting message equality with bytes payloads...")
    
    payload = b'\x01\x02\x03'
    msg1 = Message("0101", "DATA", payload)
    msg2 = Message("0101", "DATA", payload)
    
    assert msg1 == msg2, "Messages with identical bytes payloads should be equal"
    
    # Different bytes should not be equal
    msg3 = Message("0101", "DATA", b'\x04\x05\x06')
    assert msg1 != msg3, "Messages with different bytes should not be equal"
    
    print("✓ Message equality with bytes test passed")


def test_message_equality_non_message():
    """Test message equality comparison with non-Message object."""
    print("\nTesting message equality with non-Message...")
    
    msg = Message("0101", "STATUS", "test")
    
    assert msg != "not a message", "Message should not equal non-Message object"
    assert msg != None, "Message should not equal None"
    assert msg != 123, "Message should not equal integer"
    assert msg != {"destination": "0101"}, "Message should not equal dict"
    
    print("✓ Message equality with non-Message test passed")


def test_message_common_commands():
    """Test creating messages with common protocol commands."""
    print("\nTesting common protocol commands...")
    
    # Status message
    status_msg = Message("0101", "STATUS", "0000,C,N,0,0")
    assert status_msg.command == "STATUS"
    
    # LED control
    led_msg = Message("0101", "LED", "0,255,0,0,2.0,0.5,2")
    assert led_msg.command == "LED"
    
    # Display message
    display_msg = Message("0101", "DSP", "HELLO,1,0.2,L")
    assert display_msg.command == "DSP"
    
    # Power message
    power_msg = Message("0101", "POWER", "24.2,23.8,5.0")
    assert power_msg.command == "POWER"
    
    # Error message
    error_msg = Message("0101", "ERROR", "LOGIC_BROWNOUT:4.5V")
    assert error_msg.command == "ERROR"
    
    print("✓ Common protocol commands test passed")


def test_message_empty_payload():
    """Test creating message with empty payload."""
    print("\nTesting message with empty payload...")
    
    msg = Message("0101", "PING", "")
    
    assert msg.destination == "0101"
    assert msg.command == "PING"
    assert msg.payload == ""
    
    print("✓ Message with empty payload test passed")


def run_all_tests():
    """Run all Message tests."""
    print("=" * 60)
    print("Message Class Test Suite")
    print("=" * 60)
    
    try:
        test_message_creation_with_string_payload()
        test_message_creation_with_bytes_payload()
        test_message_broadcast()
        test_message_repr_string()
        test_message_repr_bytes()
        test_message_equality_same()
        test_message_equality_different_destination()
        test_message_equality_different_command()
        test_message_equality_different_payload()
        test_message_equality_bytes_payload()
        test_message_equality_non_message()
        test_message_common_commands()
        test_message_empty_payload()
        
        print("\n" + "=" * 60)
        print("✓ All Message tests passed!")
        print("=" * 60)
        return True
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return False
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
