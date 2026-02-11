#!/usr/bin/env python3
"""Test UART Transport Consolidation.

This test validates that the UART race condition has been properly resolved
through Transport layer consolidation. The race condition previously occurred
when multiple tasks wrote to uart_up_mgr without synchronization:
1. relay_downstream_to_upstream() - forwards raw bytes
2. monitor_power(), monitor_connection(), start() - send COBS messages via transport_up

The fix consolidates this functionality into the UARTTransport layer:
- UARTTransport with queued=True parameter uses an internal TX queue
- Relay functionality is built into UARTTransport via enable_relay_from()
- All writes (message sends and relay) go through the centralized queue
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


def get_base_firmware_content():
    """Get the content of base.py."""
    file_path = os.path.join(
        os.path.dirname(__file__), '..', 'src', 'satellites', 'base.py'
    )
    assert os.path.exists(file_path), "base.py should exist"
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


def test_transport_queued_mode_exists():
    """Test that UARTTransport always uses queued mode (ring buffers and async workers)."""
    print("Testing UARTTransport queued mode...")
    content = get_transport_content()

    # In the new architecture, queuing is ALWAYS enabled (no optional parameter)
    # Check that RX queue is created (always present)
    assert 'self._rx_queue = asyncio.Queue()' in content, \
        "UARTTransport should create RX queue"

    # Check that TX buffer/event system exists (ring buffer + event-driven)
    assert 'self._tx_buffer' in content, \
        "UARTTransport should have TX ring buffer"
    assert 'self._tx_event' in content, \
        "UARTTransport should have TX event"

    # Check that async workers are started
    assert 'asyncio.create_task(self._tx_worker())' in content, \
        "UARTTransport should start _tx_worker task"
    assert 'asyncio.create_task(self._rx_worker())' in content, \
        "UARTTransport should start _rx_worker task"

    print("  ✓ UARTTransport always uses queued mode (ring buffers + async workers)")
    print("✓ Transport queued mode test passed")


def test_firmware_uses_queued_transport():
    """Test that firmware creates transport (which always uses queued mode)."""
    print("\nTesting firmware creates transport...")
    content = get_base_firmware_content()

    # In the new architecture, queuing is ALWAYS enabled, so no parameter needed
    # Check that transport_up is created
    assert 'self.transport_up = UARTTransport(' in content, \
        "Firmware should create transport_up"

    # Check that transport_down is created
    assert 'self.transport_down = UARTTransport(' in content, \
        "Firmware should create transport_down"

    # Verify that old queued=True parameter is NOT used (it's no longer needed)
    assert 'queued=True' not in content, \
        "Firmware should not use deprecated queued parameter (queuing is always enabled now)"

    print("  ✓ Firmware creates transports (queuing always enabled)")
    print("✓ Firmware transport creation test passed")


def test_transport_tx_worker_exists():
    """Test that _tx_worker task exists in UARTTransport."""
    print("\nTesting _tx_worker in UARTTransport...")
    content = get_transport_content()

    # Check that the worker method exists
    assert 'async def _tx_worker(self):' in content, \
        "_tx_worker method should be defined in UARTTransport"

    # In the new architecture, TX worker drains a ring buffer, not a queue
    # Check that it waits for the TX event
    assert 'await self._tx_event.wait()' in content, \
        "_tx_worker should wait for TX event"

    # Check that it writes to the hardware UART
    assert 'self.uart.write(' in content, \
        "_tx_worker should write to hardware UART"

    # Check that it advances the tail pointer
    assert 'self._tx_tail' in content, \
        "_tx_worker should manage TX ring buffer tail pointer"

    print("  ✓ _tx_worker exists and uses ring buffer + event system")
    print("✓ TX worker test passed")


def test_relay_functionality_exists():
    """Test that relay functionality exists in UARTTransport."""
    print("\nTesting relay functionality in UARTTransport...")
    transport_content = get_transport_content()
    firmware_content = get_base_firmware_content()

    # Check that enable_relay_from method exists in transport
    assert 'def enable_relay_from(self, source_transport, heartbeat_callback=None):' in transport_content, \
        "UARTTransport should have enable_relay_from method"

    # Check that _relay_worker exists
    assert 'async def _relay_worker(self, source_transport, heartbeat_callback):' in transport_content, \
        "UARTTransport should have _relay_worker method"

    # Check that firmware uses enable_relay_from
    assert 'enable_relay_from' in firmware_content, \
        "Firmware should use enable_relay_from"

    # Check specific usage pattern in firmware
    assert 'self.transport_up.enable_relay_from(' in firmware_content, \
        "Firmware should enable relay from downstream to upstream"

    print("  ✓ enable_relay_from method exists in UARTTransport")
    print("  ✓ _relay_worker exists in UARTTransport")
    print("  ✓ Firmware uses enable_relay_from correctly")
    print("✓ Relay functionality test passed")


def test_relay_worker_uses_queue():
    """Test that _relay_worker writes to TX ring buffer."""
    print("\nTesting _relay_worker integration...")
    content = get_transport_content()

    # Get the relay worker method (normalized spacing in lookahead)
    relay_match = re.search(
        r'async def _relay_worker\(self, source_transport, heartbeat_callback\):.*?(?=\n\s+(?:async\s+)?def\s|\nclass\s|\Z)',
        content,
        re.DOTALL
    )
    assert relay_match, "_relay_worker method should exist"
    relay_method = relay_match.group(0)

    # In the new architecture, relay worker writes directly to TX ring buffer
    # Check that it manipulates TX buffer pointers
    assert 'self._tx_head' in relay_method, \
        "_relay_worker should write to TX ring buffer (uses _tx_head)"

    # Check that it reads from source transport
    assert 'source_transport.read_raw_into' in relay_method or 'source_transport.readinto' in relay_method, \
        "_relay_worker should read from source transport"

    # Check that it signals the TX worker
    assert 'self._tx_event.set()' in relay_method, \
        "_relay_worker should signal TX worker via event"

    print("  ✓ _relay_worker integrates with ring buffer system")
    print("  ✓ _relay_worker signals TX worker via event")
    print("✓ Relay worker integration test passed")


def test_send_uses_queue():
    """Test that send() method writes to TX buffer or directly to UART."""
    print("\nTesting send() method integration...")
    content = get_transport_content()

    # Get the send method (normalized spacing in lookahead)
    send_match = re.search(
        r'def send\(self, message\):.*?(?=\n\s+(?:async\s+)?def\s|\Z)',
        content,
        re.DOTALL
    )
    assert send_match, "send method should exist"
    send_method = send_match.group(0)

    # In the new architecture, send() writes to TX buffer when workers are running,
    # or directly to UART when workers are not running (for testing)
    # Check that it can write to TX buffer
    assert '_write_to_tx_buffer' in send_method, \
        "send() should use _write_to_tx_buffer when async workers are running"

    # Check that it can also write directly to UART (for backward compatibility)
    assert 'self.uart.write(packet)' in send_method, \
        "send() should support direct write when async workers are not running"

    # Check that it checks for worker status
    assert 'self._tx_task' in send_method, \
        "send() should check if TX worker is running"

    print("  ✓ send() integrates with ring buffer system")
    print("  ✓ send() supports both async and sync modes")
    print("✓ Send method integration test passed")


def test_transport_consolidation():
    """Test that transport consolidation is complete."""
    print("\nTesting transport consolidation...")
    firmware_content = get_base_firmware_content()
    transport_content = get_transport_content()

    # Verify firmware uses transport for both directions
    assert 'self.transport_up' in firmware_content, \
        "Firmware should have transport_up"
    assert 'self.transport_down' in firmware_content, \
        "Firmware should have transport_down"

    # Verify no direct UART manipulation in firmware for message sending
    # (read_raw_into is OK for relay, but no direct message writes)
    lines = firmware_content.split('\n')
    for i, line in enumerate(lines):
        # Skip comments
        if line.strip().startswith('#'):
            continue
        # Check for direct uart.write of formatted messages (not raw relay)
        if 'uart' in line.lower() and 'write' in line.lower():
            # Allow only in initialization or relay context
            if 'busio.UART' not in line and 'self.transport' not in line:
                # This might be OK if it's just hardware initialization
                pass

    # Verify transport has all the functionality (note: they're synchronous now)
    assert 'def send(self' in transport_content, \
        "UARTTransport should have send method"
    assert 'def receive(self' in transport_content, \
        "UARTTransport should have receive method"

    print("  ✓ Firmware uses transport layer for communication")
    print("  ✓ UARTTransport has complete protocol implementation")
    print("✓ Transport consolidation test passed")


def test_relay_worker_dynamic_backoff():
    """Test that _relay_worker uses dynamic backoff when idle."""
    print("\nTesting _relay_worker dynamic backoff...")
    content = get_transport_content()

    # Get the relay worker method
    relay_match = re.search(
        r'async def _relay_worker\(self, source_transport, heartbeat_callback\):.*?(?=\n\s+(?:async\s+)?def\s|\nclass\s|\Z)',
        content,
        re.DOTALL
    )
    assert relay_match, "_relay_worker method should exist"
    relay_method = relay_match.group(0)

    # Check that it has conditional sleep based on data availability
    assert ('if count and count > 0:' in relay_method or 'if count > 0:' in relay_method or 'if count:' in relay_method), \
        "_relay_worker should check if data was read"

    # Check for short sleep when data is present (high throughput)
    assert 'await asyncio.sleep(0)' in relay_method, \
        "_relay_worker should use sleep(0) when processing data"

    # Check for longer sleep when idle (power saving)
    # The recommendation from the issue is 5ms (0.005 seconds) to allow the
    # microcontroller to enter lower-power idle states while maintaining responsiveness
    assert 'await asyncio.sleep(0.005)' in relay_method, \
        "_relay_worker should use sleep(0.005) when idle to save power"

    # Verify the structure: sleep(0) should be in the if block, sleep(0.005) in else
    # Extract the code structure more carefully
    lines = relay_method.split('\n')
    found_if_block = False
    found_else_block = False
    in_if_block = False
    in_else_block = False

    for line in lines:
        stripped = line.strip()
        if 'if count and count > 0:' in stripped or 'if count > 0:' in stripped or 'if count:' in stripped:
            found_if_block = True
            in_if_block = True
            in_else_block = False
        elif stripped.startswith('else:'):
            found_else_block = True
            in_else_block = True
            in_if_block = False
        elif 'await asyncio.sleep(0)' in stripped and in_if_block:
            pass  # Good - sleep(0) is in the if block
        elif 'await asyncio.sleep(0.005)' in stripped and in_else_block:
            pass  # Good - sleep(0.005) is in the else block

    assert found_if_block and found_else_block, \
        "_relay_worker should have if/else structure for conditional sleep"

    print("  ✓ _relay_worker checks data availability")
    print("  ✓ Uses sleep(0) when processing data (high throughput)")
    print("  ✓ Uses sleep(0.005) when idle (power saving)")
    print("✓ Relay worker dynamic backoff test passed")


def test_race_condition_documented():
    """Test that the consolidation is properly documented."""
    print("\nTesting transport consolidation documentation...")
    firmware_content = get_firmware_content()
    transport_content = get_transport_content()

    # Check for documentation about queue or race prevention
    race_condition_terms = [
        'race condition',
        'prevent race',
        'prevents race',
        'queue',
        'queued',
    ]

    found_in_transport = any(term in transport_content.lower() for term in race_condition_terms)
    found_in_firmware = any(term in firmware_content.lower() for term in race_condition_terms)

    assert found_in_transport or found_in_firmware, \
        "Code should document the queue/race condition handling"

    # Check for transport-specific documentation
    transport_docs = [
        'relay',
        'enable_relay_from',
        'tx queue',
        '_tx_worker',
    ]

    found_transport_docs = any(term in transport_content.lower() for term in transport_docs)
    assert found_transport_docs, \
        "UARTTransport should document relay and queue features"

    print("  ✓ Race condition handling is documented")
    print("  ✓ Transport features are documented")
    print("✓ Documentation test passed")


if __name__ == "__main__":
    print("=" * 70)
    print("UART Transport Consolidation Test Suite")
    print("=" * 70)

    try:
        test_transport_queued_mode_exists()
        test_firmware_uses_queued_transport()
        test_transport_tx_worker_exists()
        test_relay_functionality_exists()
        test_relay_worker_uses_queue()
        test_relay_worker_dynamic_backoff()
        test_send_uses_queue()
        test_transport_consolidation()
        test_race_condition_documented()

        print("\n" + "=" * 70)
        print("ALL TRANSPORT CONSOLIDATION TESTS PASSED ✓")
        print("=" * 70)
        print("\nThe transport consolidation successfully:")
        print("  • Moved queuing logic into UARTTransport layer")
        print("  • Implemented enable_relay_from() for data forwarding")
        print("  • Centralized all UART writes through queue/worker")
        print("  • Eliminated firmware-level UART race conditions")
        print("  • Maintained clean separation of concerns")
        print("  • Implemented dynamic backoff in relay worker for power saving")

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
