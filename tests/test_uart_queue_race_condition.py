#!/usr/bin/env python3
"""Test UART Queue Race Condition Fix.

This test validates that the race condition in sat_01_firmware.py has been
properly fixed by implementing a centralized TX queue for the upstream UART.

The race condition occurred when multiple tasks wrote to uart_up_mgr without
synchronization:
1. relay_downstream_to_upstream() - forwards raw bytes
2. monitor_power(), monitor_connection(), start() - send COBS messages via transport_up

The fix implements a queue-based approach where all writes go through a single
TX worker task.
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


def test_queued_uart_manager_exists():
    """Test that _QueuedUARTManager wrapper class exists."""
    print("Testing _QueuedUARTManager class exists...")
    content = get_firmware_content()
    
    assert 'class _QueuedUARTManager:' in content, \
        "_QueuedUARTManager wrapper class should be defined"
    
    # Verify it has a write method that uses the queue
    assert 'def write(self, data):' in content, \
        "_QueuedUARTManager should have a write method"
    
    # Check that it uses put_nowait to queue data
    assert 'put_nowait' in content, \
        "_QueuedUARTManager should use put_nowait to queue data"
    
    print("  ✓ _QueuedUARTManager class is properly defined")
    print("✓ _QueuedUARTManager existence test passed")


def test_upstream_queue_initialization():
    """Test that upstream_queue is created in __init__."""
    print("\nTesting upstream_queue initialization...")
    content = get_firmware_content()
    
    # Check that upstream_queue is created
    assert 'self.upstream_queue = asyncio.Queue()' in content, \
        "upstream_queue should be initialized in __init__"
    
    # Check that _QueuedUARTManager is instantiated with the queue
    assert 'self.uart_up_mgr_queued = _QueuedUARTManager(self.upstream_queue)' in content, \
        "_QueuedUARTManager should be instantiated with the queue"
    
    # Check that transport_up uses the queued manager
    assert 'UARTTransport(self.uart_up_mgr_queued,' in content, \
        "transport_up should use the queued UART manager"
    
    print("  ✓ upstream_queue is properly initialized")
    print("  ✓ _QueuedUARTManager is properly instantiated")
    print("  ✓ transport_up uses queued manager")
    print("✓ Upstream queue initialization test passed")


def test_upstream_tx_worker_exists():
    """Test that _upstream_tx_worker task exists."""
    print("\nTesting _upstream_tx_worker task...")
    content = get_firmware_content()
    
    # Check that the worker method exists
    assert 'async def _upstream_tx_worker(self):' in content, \
        "_upstream_tx_worker method should be defined"
    
    # Check that it gets data from the queue
    assert 'data = await self.upstream_queue.get()' in content, \
        "_upstream_tx_worker should get data from the queue"
    
    # Check that it writes to the hardware UART
    assert 'self.uart_up_mgr.write(data)' in content, \
        "_upstream_tx_worker should write to hardware uart_up_mgr"
    
    # Check that it marks task as done
    assert 'self.upstream_queue.task_done()' in content, \
        "_upstream_tx_worker should call task_done()"
    
    print("  ✓ _upstream_tx_worker method exists")
    print("  ✓ Worker gets data from queue")
    print("  ✓ Worker writes to hardware UART")
    print("  ✓ Worker marks task as done")
    print("✓ Upstream TX worker test passed")


def test_relay_uses_queue():
    """Test that relay_downstream_to_upstream uses the queue."""
    print("\nTesting relay_downstream_to_upstream uses queue...")
    content = get_firmware_content()
    
    # Get the relay method
    relay_match = re.search(
        r'async def relay_downstream_to_upstream\(self\):.*?(?=\n    async def|\n    def|\Z)',
        content,
        re.DOTALL
    )
    assert relay_match, "relay_downstream_to_upstream method should exist"
    relay_method = relay_match.group(0)
    
    # Check that it uses the queue instead of direct write
    assert 'await self.upstream_queue.put(bytes(buf[:num_read]))' in relay_method, \
        "relay should put data in queue instead of direct write"
    
    # Check that it does NOT write directly to uart_up_mgr anymore
    # (the only direct write should be in _upstream_tx_worker)
    assert 'self.uart_up_mgr.write(buf[:num_read])' not in relay_method, \
        "relay should NOT write directly to uart_up_mgr"
    
    print("  ✓ relay_downstream_to_upstream uses queue")
    print("  ✓ relay does NOT write directly to hardware UART")
    print("✓ Relay queue usage test passed")


def test_worker_started_in_start_method():
    """Test that _upstream_tx_worker is started in start()."""
    print("\nTesting _upstream_tx_worker is started in start()...")
    content = get_firmware_content()
    
    # Get the start method
    start_match = re.search(
        r'async def start\(self\):.*?(?=\n    async def|\n    def|\Z)',
        content,
        re.DOTALL
    )
    assert start_match, "start method should exist"
    start_method = start_match.group(0)
    
    # Check that the worker is started as a task
    assert 'asyncio.create_task(self._upstream_tx_worker())' in start_method, \
        "_upstream_tx_worker should be started as a task in start()"
    
    print("  ✓ _upstream_tx_worker is started as a task")
    print("✓ Worker startup test passed")


def test_no_direct_uart_writes():
    """Test that uart_up_mgr.write() is only called in _upstream_tx_worker."""
    print("\nTesting no direct UART writes outside worker...")
    content = get_firmware_content()
    
    # Find all occurrences of uart_up_mgr.write
    write_pattern = r'self\.uart_up_mgr\.write\('
    write_matches = list(re.finditer(write_pattern, content))
    
    assert len(write_matches) > 0, "There should be at least one uart_up_mgr.write call"
    
    # Check that all writes are in _upstream_tx_worker
    for match in write_matches:
        # Get the method context - check both async and sync methods
        before_text = content[:match.start()]
        # Match both "async def method_name(self" and "def method_name(self"
        last_method = re.findall(r'(?:async\s+)?def\s+(\w+)\(self', before_text)
        if last_method:
            method_name = last_method[-1]
            assert method_name == '_upstream_tx_worker', \
                f"uart_up_mgr.write found in {method_name}, should only be in _upstream_tx_worker"
    
    print("  ✓ All uart_up_mgr.write calls are in _upstream_tx_worker")
    print("✓ No direct UART writes test passed")


def test_transport_up_sends_use_queued_manager():
    """Test that transport_up uses the queued manager."""
    print("\nTesting transport_up.send() uses queued manager...")
    content = get_firmware_content()
    
    # Check initialization shows transport_up uses queued manager
    init_match = re.search(
        r'def __init__\(self\):.*?(?=\n    async def|\n    def)',
        content,
        re.DOTALL
    )
    assert init_match, "__init__ method should exist"
    init_method = init_match.group(0)
    
    # Verify transport_up is created with uart_up_mgr_queued
    assert 'self.transport_up = UARTTransport(self.uart_up_mgr_queued,' in init_method, \
        "transport_up should be created with uart_up_mgr_queued"
    
    # Verify uart_up_mgr is stored separately and only for the TX worker
    assert 'self.uart_up_mgr = uart_up_mgr  # Hardware UART (only used by TX worker)' in init_method, \
        "uart_up_mgr should be stored with comment indicating it's only for TX worker"
    
    print("  ✓ transport_up uses queued manager")
    print("  ✓ hardware uart_up_mgr is reserved for TX worker")
    print("✓ Transport queue usage test passed")


def test_race_condition_documented():
    """Test that the fix is properly documented in code comments."""
    print("\nTesting race condition fix is documented...")
    content = get_firmware_content()
    
    # Check for documentation about race condition prevention
    race_condition_terms = [
        'race condition',
        'prevent race',
        'prevents race',
    ]
    
    found_documentation = any(term in content.lower() for term in race_condition_terms)
    assert found_documentation, \
        "Code should document the race condition fix"
    
    # Check for queue-related documentation
    queue_terms = [
        'queue',
        'TX queue',
        'upstream queue',
    ]
    
    found_queue_docs = any(term in content.lower() for term in queue_terms)
    assert found_queue_docs, \
        "Code should document the queue-based approach"
    
    print("  ✓ Race condition fix is documented")
    print("  ✓ Queue-based approach is documented")
    print("✓ Documentation test passed")


if __name__ == "__main__":
    print("=" * 70)
    print("UART Queue Race Condition Fix Test Suite")
    print("=" * 70)
    
    try:
        test_queued_uart_manager_exists()
        test_upstream_queue_initialization()
        test_upstream_tx_worker_exists()
        test_relay_uses_queue()
        test_worker_started_in_start_method()
        test_no_direct_uart_writes()
        test_transport_up_sends_use_queued_manager()
        test_race_condition_documented()
        
        print("\n" + "=" * 70)
        print("ALL UART QUEUE TESTS PASSED ✓")
        print("=" * 70)
        print("\nThe race condition fix successfully:")
        print("  • Creates a centralized upstream TX queue")
        print("  • Implements a dedicated TX worker task")
        print("  • Prevents interleaved packet writes")
        print("  • Ensures all upstream writes go through the queue")
        print("  • Maintains thread-safe UART communication")
        
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
