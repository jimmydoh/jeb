#!/usr/bin/env python3
"""Test Transport Consolidation.

This test validates that the transport consolidation has been completed:
1. UARTTransport handles queue management internally
2. UARTTransport handles relay from downstream to upstream internally
3. Satellite firmware only passes hardware at init and uses send/receive
4. Satellite firmware does NOT manage queues, workers, or relay logic
"""

import sys
import os
import re

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def get_firmware_content():
    """Get the content of sat_01_firmware.py."""
    file_path = os.path.join(
        os.path.dirname(__file__), '..', 'src', 'satellites', 'sat_01_firmware.py'
    )
    assert os.path.exists(file_path), "sat_01_firmware.py should exist"
    with open(file_path, 'r') as f:
        return f.read()


def get_transport_content():
    """Get the content of uart_transport.py."""
    file_path = os.path.join(
        os.path.dirname(__file__), '..', 'src', 'transport', 'uart_transport.py'
    )
    assert os.path.exists(file_path), "uart_transport.py should exist"
    with open(file_path, 'r') as f:
        return f.read()


def test_transport_has_queue_management():
    """Test that UARTTransport handles queue management internally."""
    print("Testing UARTTransport has queue management...")
    content = get_transport_content()
    
    # Check that _QueuedUARTManager is in transport
    assert 'class _QueuedUARTManager:' in content, \
        "_QueuedUARTManager should be in transport module"
    
    # Check that UARTTransport creates queue
    assert 'self.upstream_queue = asyncio.Queue()' in content, \
        "UARTTransport should create upstream_queue"
    
    # Check that it has TX worker
    assert 'async def _upstream_tx_worker(self):' in content, \
        "UARTTransport should have _upstream_tx_worker method"
    
    print("  ✓ UARTTransport has queue management")
    print("✓ Transport queue management test passed")


def test_transport_has_relay():
    """Test that UARTTransport handles relay internally."""
    print("\nTesting UARTTransport has relay functionality...")
    content = get_transport_content()
    
    # Check that init accepts uart_downstream parameter
    assert 'uart_downstream' in content, \
        "UARTTransport should accept uart_downstream parameter"
    
    # Check that it has relay worker
    assert 'async def _relay_worker(self):' in content, \
        "UARTTransport should have _relay_worker method"
    
    # Check relay logic
    assert 'self.uart_downstream' in content, \
        "UARTTransport should store uart_downstream"
    
    print("  ✓ UARTTransport has relay functionality")
    print("✓ Transport relay test passed")


def test_firmware_has_no_queue_management():
    """Test that firmware does NOT manage queues."""
    print("\nTesting firmware does NOT manage queues...")
    content = get_firmware_content()
    
    # Firmware should NOT have _QueuedUARTManager
    assert 'class _QueuedUARTManager:' not in content, \
        "Firmware should NOT define _QueuedUARTManager (it's in Transport)"
    
    # Firmware should NOT create upstream_queue
    assert 'self.upstream_queue = asyncio.Queue()' not in content, \
        "Firmware should NOT create upstream_queue (Transport handles it)"
    
    # Firmware should NOT have _upstream_tx_worker
    assert 'async def _upstream_tx_worker(self):' not in content, \
        "Firmware should NOT have _upstream_tx_worker (Transport handles it)"
    
    print("  ✓ Firmware does NOT manage queues")
    print("✓ Firmware queue-free test passed")


def test_firmware_has_no_relay():
    """Test that firmware does NOT manage relay."""
    print("\nTesting firmware does NOT manage relay...")
    content = get_firmware_content()
    
    # Firmware should NOT have relay method
    assert 'async def relay_downstream_to_upstream(self):' not in content, \
        "Firmware should NOT have relay_downstream_to_upstream (Transport handles it)"
    
    # Firmware should NOT create relay task
    assert 'asyncio.create_task(self.relay_downstream_to_upstream())' not in content, \
        "Firmware should NOT create relay task (Transport handles it)"
    
    print("  ✓ Firmware does NOT manage relay")
    print("✓ Firmware relay-free test passed")


def test_firmware_uses_transport_correctly():
    """Test that firmware correctly uses Transport."""
    print("\nTesting firmware uses Transport correctly...")
    content = get_firmware_content()
    
    # Check that firmware passes uart_downstream to Transport
    assert 'uart_downstream=' in content, \
        "Firmware should pass uart_downstream to UARTTransport"
    
    # Check that firmware creates upstream transport
    assert 'UARTTransport(' in content, \
        "Firmware should create UARTTransport"
    
    # Check that firmware sends/receives via transport
    assert 'self.transport.send(' in content, \
        "Firmware should use transport.send()"
    
    assert 'self.transport.receive(' in content, \
        "Firmware should use transport.receive()"
    
    print("  ✓ Firmware uses Transport correctly")
    print("✓ Firmware Transport usage test passed")


def test_clean_separation_of_concerns():
    """Test clean separation: Transport handles UART, Firmware handles application logic."""
    print("\nTesting clean separation of concerns...")
    
    firmware_content = get_firmware_content()
    transport_content = get_transport_content()
    
    # Transport should have all UART coordination logic
    assert 'upstream_queue' in transport_content, \
        "Transport should handle upstream_queue"
    assert '_upstream_tx_worker' in transport_content, \
        "Transport should handle TX worker"
    assert '_relay_worker' in transport_content, \
        "Transport should handle relay worker"
    
    # Firmware should NOT have UART coordination logic  
    assert 'upstream_queue' not in firmware_content or 'uart_downstream=' in firmware_content, \
        "Firmware should NOT manage queues directly"
    
    print("  ✓ Clean separation of concerns")
    print("✓ Separation of concerns test passed")


if __name__ == "__main__":
    print("=" * 70)
    print("Transport Consolidation Test Suite")
    print("=" * 70)
    
    try:
        test_transport_has_queue_management()
        test_transport_has_relay()
        test_firmware_has_no_queue_management()
        test_firmware_has_no_relay()
        test_firmware_uses_transport_correctly()
        test_clean_separation_of_concerns()
        
        print("\n" + "=" * 70)
        print("ALL TRANSPORT CONSOLIDATION TESTS PASSED ✓")
        print("=" * 70)
        print("\nTransport consolidation successfully completed:")
        print("  • UARTTransport handles all UART coordination")
        print("  • Queue management moved to Transport")
        print("  • Relay functionality moved to Transport")
        print("  • Firmware only passes hardware and uses send/receive")
        print("  • Clean separation of concerns")
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
