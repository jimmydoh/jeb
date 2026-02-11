"""Shared helper functions for JEB unit tests.

This module provides common utilities used across multiple test files,
particularly for testing the transport layer with synchronous test code.
"""


def drain_tx_buffer(transport, mock_uart):
    """Helper function to manually drain TX buffer for synchronous tests.
    
    Simulates what the async TX worker does, but synchronously.
    
    Parameters:
        transport: The UARTTransport instance
        mock_uart: The mock UART manager
    """
    while transport._tx_head != transport._tx_tail:
        head = transport._tx_head
        tail = transport._tx_tail
        size = transport._tx_buffer_size
        
        # Determine contiguous chunk to write
        if head > tail:
            chunk = transport._tx_mv[tail:head]
        else:
            chunk = transport._tx_mv[tail:size]
        
        # Write to mock UART (convert memoryview to bytes)
        transport.uart.write(bytes(chunk))
        
        # Advance tail
        transport._tx_tail = (tail + len(chunk)) % size


def receive_message_sync(transport):
    """Helper function to manually receive a message for synchronous tests.
    
    Simulates what the async RX worker does, but synchronously.
    Returns a message if available, None otherwise.
    
    Parameters:
        transport: The UARTTransport instance
        
    Returns:
        Message object if available, None otherwise
    """
    # First try to get from queue if workers have been run
    msg = transport.receive_nowait()
    if msg is not None:
        return msg
    
    # Otherwise, manually process incoming data
    transport._read_hw()
    return transport._try_decode_one()
