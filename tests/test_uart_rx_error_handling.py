#!/usr/bin/env python3
"""Test UART RX Hardware Error Handling.

This test validates that _read_hw() properly logs UART hardware errors
and tracks them with an error counter instead of silently discarding them.
"""

import sys
import os
import asyncio
import pytest

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from transport.uart_transport import UARTTransport


class MockUARTRaisesOnRead:
    """Mock UART that raises an exception on readinto."""

    def __init__(self, error=None):
        self.in_waiting = 16
        self.error = error or OSError("UART hardware fault")

    def readinto(self, buf):
        raise self.error

    def write(self, data):
        return len(data)

    def read(self, n):
        return b''

    def reset_input_buffer(self):
        pass


class MockUARTNormal:
    """Mock UART that works normally."""

    def __init__(self):
        self.in_waiting = 0
        self.read_buffer = bytearray()

    def readinto(self, buf):
        return 0

    def write(self, data):
        return len(data)

    def read(self, n):
        return b''

    def reset_input_buffer(self):
        pass


def test_rx_error_count_initialized():
    """Test that _rx_error_count is initialized to zero."""
    transport = UARTTransport(uart_hw=MockUARTNormal())
    assert hasattr(transport, '_rx_error_count'), \
        "UARTTransport should have _rx_error_count attribute"
    assert transport._rx_error_count == 0, \
        "_rx_error_count should start at 0"


def test_rx_error_increments_on_hardware_fault(capsys):
    """Test that _read_hw() increments error counter and logs on hardware fault."""
    mock_uart = MockUARTRaisesOnRead()
    transport = UARTTransport(uart_hw=mock_uart)

    assert transport._rx_error_count == 0

    # Call _read_hw() - UART will raise
    transport._read_hw()

    # Error count should be incremented
    assert transport._rx_error_count == 1, \
        "_rx_error_count should be 1 after one hardware error"

    # Error should have been printed
    captured = capsys.readouterr()
    assert "RX Hardware Error" in captured.out, \
        "Hardware error should be printed to stdout"
    assert "count=1" in captured.out, \
        "Error count should be included in the log message"


def test_rx_error_count_accumulates(capsys):
<<<<<<< HEAD
    """Test that repeated hardware errors accumulate in the counter."""
=======
    """Test that repeated hardware errors accumulate in the counter.

    With throttled logging, only the first error and every 100th error
    are printed; intermediate errors are counted but not logged.
    """
>>>>>>> 7b8c9bce433424a8abe7b8f711a8c279f371eba4
    mock_uart = MockUARTRaisesOnRead()
    transport = UARTTransport(uart_hw=mock_uart)

    for i in range(3):
        transport._read_hw()

    assert transport._rx_error_count == 3, \
        "_rx_error_count should be 3 after three hardware errors"

<<<<<<< HEAD
    captured = capsys.readouterr()
    assert "count=3" in captured.out, \
        "Third error log should show count=3"
=======
    # With throttled logging, only the first error is printed for counts 1-99
    captured = capsys.readouterr()
    assert "count=1" in captured.out, \
        "First error log should show count=1"
    # Counts 2 and 3 should not be logged (throttled until count=100)
    assert "count=2" not in captured.out, \
        "Second error should be throttled (not logged)"
    assert "count=3" not in captured.out, \
        "Third error should be throttled (not logged)"
>>>>>>> 7b8c9bce433424a8abe7b8f711a8c279f371eba4


def test_rx_no_error_on_normal_operation():
    """Test that _rx_error_count stays at 0 when UART works normally."""
    mock_uart = MockUARTNormal()
    transport = UARTTransport(uart_hw=mock_uart)

    # No data waiting; should return without error
    transport._read_hw()

    assert transport._rx_error_count == 0, \
        "_rx_error_count should remain 0 on normal operation"


def test_rx_error_message_includes_exception_detail(capsys):
    """Test that logged error message includes the exception description."""
    error_message = "UART parity error"
    mock_uart = MockUARTRaisesOnRead(error=OSError(error_message))
    transport = UARTTransport(uart_hw=mock_uart)

    transport._read_hw()

    captured = capsys.readouterr()
    assert error_message in captured.out, \
        "Exception message should appear in the log output"


<<<<<<< HEAD
=======
def test_rx_error_throttle_logs_100th_error(capsys):
    """Test that the 100th error is logged (throttle boundary)."""
    mock_uart = MockUARTRaisesOnRead()
    transport = UARTTransport(uart_hw=mock_uart)

    for _ in range(100):
        transport._read_hw()

    assert transport._rx_error_count == 100

    captured = capsys.readouterr()
    assert "count=100" in captured.out, \
        "100th error should be logged (throttle boundary)"


def test_rx_error_last_rx_error_stored():
    """Test that the most recent error is stored in _last_rx_error."""
    error = OSError("storage error")
    mock_uart = MockUARTRaisesOnRead(error=error)
    transport = UARTTransport(uart_hw=mock_uart)

    transport._read_hw()

    assert transport._last_rx_error is error, \
        "_last_rx_error should hold the most recent exception"


>>>>>>> 7b8c9bce433424a8abe7b8f711a8c279f371eba4
async def run_all_tests():
    """Run all tests standalone."""
    print("=" * 70)
    print("UART RX Error Handling Test Suite")
    print("=" * 70)

    def run_test(name, fn):
        try:
            fn()
            print(f"  ✓ {name}")
        except AssertionError as e:
            print(f"  ✗ {name}: {e}")
            raise

    run_test("_rx_error_count initialized to zero", test_rx_error_count_initialized)
    run_test("no error on normal operation", test_rx_no_error_on_normal_operation)

    print("\n" + "=" * 70)
    print("ALL RX ERROR HANDLING TESTS PASSED ✓")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
