#!/usr/bin/env python3
"""Unit tests for BaseTransport abstract class."""

import sys
import os
import asyncio

# Add src/transport to path for direct module import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'transport'))

# Import BaseTransport and Message classes
import base_transport
import message

BaseTransport = base_transport.BaseTransport
Message = message.Message


def test_base_transport_is_abstract():
    """Test that BaseTransport is abstract and cannot be used directly."""
    print("Testing BaseTransport abstract nature...")
    
    # BaseTransport can be instantiated but methods should raise NotImplementedError
    transport = BaseTransport()
    
    # Test that send() raises NotImplementedError
    try:
        msg = Message("CORE", "0101", "TEST", "data")
        transport.send(msg)
        assert False, "send() should raise NotImplementedError"
    except NotImplementedError as e:
        assert "send()" in str(e), "Error should mention send()"
    
    print("✓ BaseTransport send() abstract test passed")


def test_base_transport_receive_not_implemented():
    """Test that receive() raises NotImplementedError."""
    print("\nTesting BaseTransport receive() not implemented...")
    
    transport = BaseTransport()
    
    # receive() is async, so we need to test it with asyncio
    async def test_receive():
        try:
            await transport.receive()
            assert False, "receive() should raise NotImplementedError"
        except NotImplementedError as e:
            assert "receive()" in str(e), "Error should mention receive()"
    
    asyncio.run(test_receive())
    print("✓ BaseTransport receive() abstract test passed")


def test_base_transport_clear_buffer_not_implemented():
    """Test that clear_buffer() raises NotImplementedError."""
    print("\nTesting BaseTransport clear_buffer() not implemented...")
    
    transport = BaseTransport()
    
    try:
        transport.clear_buffer()
        assert False, "clear_buffer() should raise NotImplementedError"
    except NotImplementedError as e:
        assert "clear_buffer()" in str(e), "Error should mention clear_buffer()"
    
    print("✓ BaseTransport clear_buffer() abstract test passed")


def test_concrete_transport_implementation():
    """Test that a concrete implementation can override all methods."""
    print("\nTesting concrete transport implementation...")
    
    class ConcreteTransport(BaseTransport):
        """A concrete transport implementation for testing."""
        
        def __init__(self):
            self.sent_messages = []
            self.receive_queue = []
            self.buffer_cleared = False
        
        def send(self, message):
            """Store sent message."""
            self.sent_messages.append(message)
        
        async def receive(self):
            """Return queued message or None."""
            if self.receive_queue:
                return self.receive_queue.pop(0)
            return None
        
        async def receive_nowait(self):
            """Return queued message or None."""
            if self.receive_queue:
                return self.receive_queue.pop(0)
            return None
        
        def clear_buffer(self):
            """Clear the buffer."""
            self.receive_queue.clear()
            self.buffer_cleared = True
    
    async def test_impl():
        # Create instance
        transport = ConcreteTransport()
        
        # Test send
        msg = Message("CORE", "0101", "TEST", "data")
        transport.send(msg)
        assert len(transport.sent_messages) == 1, "Message should be stored"
        assert transport.sent_messages[0] == msg, "Stored message should match sent"
        
        # Test receive (empty)
        received = await transport.receive()
        assert received is None, "Should return None when queue is empty"
        
        # Test receive (with data)
        transport.receive_queue.append(msg)
        received = await transport.receive()
        assert received == msg, "Should return queued message"
        
        # Test clear_buffer
        transport.receive_queue = [msg, msg, msg]
        transport.clear_buffer()
        assert len(transport.receive_queue) == 0, "Buffer should be cleared"
        assert transport.buffer_cleared == True, "Clear flag should be set"
    
    asyncio.run(test_impl())
    print("✓ Concrete transport implementation test passed")


def test_transport_inheritance():
    """Test that subclasses properly inherit from BaseTransport."""
    print("\nTesting transport inheritance...")
    
    class TestTransport(BaseTransport):
        def send(self, message):
            pass
        
        async def receive(self):
            return None
        
        async def receive_nowait(self):
            return None
        
        def clear_buffer(self):
            pass
    
    async def test_inherit():
        transport = TestTransport()
        
        # Check that it's an instance of BaseTransport
        assert isinstance(transport, BaseTransport), "Should be instance of BaseTransport"
        
        # Check that methods can be called without error
        msg = Message("CORE", "0101", "TEST", "data")
        transport.send(msg)  # Should not raise
        result = await transport.receive()  # Should not raise
        transport.clear_buffer()  # Should not raise
    
    asyncio.run(test_inherit())
    print("✓ Transport inheritance test passed")


def test_multiple_transport_implementations():
    """Test that multiple transport implementations can coexist."""
    print("\nTesting multiple transport implementations...")
    
    class UARTTransport(BaseTransport):
        def __init__(self):
            self.name = "UART"
            self.sent = []
        
        def send(self, message):
            self.sent.append(("UART", message))
        
        async def receive(self):
            return None
        
        async def receive_nowait(self):
            return None
        
        def clear_buffer(self):
            pass
    
    class I2CTransport(BaseTransport):
        def __init__(self):
            self.name = "I2C"
            self.sent = []
        
        def send(self, message):
            self.sent.append(("I2C", message))
        
        async def receive(self):
            return None
        
        async def receive_nowait(self):
            return None
        
        def clear_buffer(self):
            pass
    
    uart = UARTTransport()
    i2c = I2CTransport()
    
    msg = Message("CORE", "0101", "TEST", "data")
    
    uart.send(msg)
    i2c.send(msg)
    
    assert uart.sent[0][0] == "UART", "UART should mark its messages"
    assert i2c.sent[0][0] == "I2C", "I2C should mark its messages"
    assert uart.sent[0][1] == msg, "UART should send the message"
    assert i2c.sent[0][1] == msg, "I2C should send the message"
    
    print("✓ Multiple transport implementations test passed")


def run_all_tests():
    """Run all BaseTransport tests."""
    print("=" * 60)
    print("BaseTransport Abstract Class Test Suite")
    print("=" * 60)
    
    try:
        test_base_transport_is_abstract()
        test_base_transport_receive_not_implemented()
        test_base_transport_clear_buffer_not_implemented()
        test_concrete_transport_implementation()
        test_transport_inheritance()
        test_multiple_transport_implementations()
        
        print("\n" + "=" * 60)
        print("✓ All BaseTransport tests passed!")
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
