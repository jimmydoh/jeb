# File: src/managers/uart_manager.py
"""UART Manager with robust buffering for handling fragmented packets."""

from .ring_buffer import RingBuffer

class UARTManager:
    """Manages UART communication with non-blocking buffering.

    Provides a robust way to read UART data by accumulating bytes in a
    persistent buffer and only returning complete lines terminated by newline.
    This prevents crashes when packets arrive fragmented.
    """

    def __init__(self, uart, max_buffer_size=1024):
        """Initialize the UART Manager.

        Parameters:
            uart: The UART object to manage (busio.UART instance).
            max_buffer_size: Maximum buffer size in bytes (default: 1024).
        """
        self.uart = uart
        self.buffer = RingBuffer(capacity=max_buffer_size)
        self.max_buffer_size = max_buffer_size

    def write(self, data):
        """Write data to UART.

        Parameters:
            data: Bytes to write to UART.
        """
        self.uart.write(data)

    @property
    def in_waiting(self):
        """Get the number of bytes available in the underlying UART buffer.

        Returns:
            int: Number of bytes waiting to be read.
        """
        return self.uart.in_waiting

    def read_available(self):
        """Read all available bytes from UART without blocking.

        This is a non-blocking read that returns immediately with whatever
        bytes are available in the UART buffer.

        Returns:
            bytes: Available bytes from UART, or empty bytes if none available.
        """
        if self.uart.in_waiting > 0:
            return self.uart.read(self.uart.in_waiting)
        return b''

    def readinto(self, buf):
        """Read bytes directly into a buffer.

        This is a pass-through to the underlying UART for low-level operations
        like relaying raw bytes without line buffering.

        Parameters:
            buf: Buffer to read into.

        Returns:
            int: Number of bytes read.
        """
        return self.uart.readinto(buf)

    def read_line(self):
        """Read a complete line from UART if available.

        Non-blocking read that accumulates bytes into a buffer and only
        returns when a complete line (terminated by \\n) is available.

        Returns:
            str: Complete line (without \\n) if available, None otherwise.

        Raises:
            ValueError: If buffer exceeds max_buffer_size (potential malformed data).
        """
        # Read all available bytes into buffer at once for efficiency
        if self.uart.in_waiting > 0:
            available_bytes = self.uart.read(self.uart.in_waiting)
            if available_bytes:
                try:
                    self.buffer.extend(available_bytes)
                except ValueError:
                    # Buffer overflow - clear buffer and alert user
                    print("WARNING: UART buffer overflow - dropped packets. Buffer cleared.")
                    self.buffer.clear()
                    raise ValueError("UART buffer overflow - buffer has been cleared")

        # Check if we have a complete line
        newline_idx = self.buffer.find(b'\n')
        if newline_idx >= 0:
            # Extract the line (including \n)
            line_bytes = bytes(self.buffer[:newline_idx + 1])
            # Remove the extracted line from buffer in O(1) time
            del self.buffer[:newline_idx + 1]

            # Decode and return the line (without \n)
            try:
                return line_bytes.decode().strip()
            except UnicodeDecodeError:
                # Return None for malformed Unicode
                return None

        # No complete line available yet
        return None

    def read_until(self, delimiter):
        """Read bytes from UART until delimiter is found.

        Non-blocking read that accumulates bytes into a buffer and returns
        when the delimiter is found. Used for binary protocols with specific
        terminators (e.g., 0x00 for COBS framing).

        Parameters:
            delimiter (bytes): Delimiter to search for (e.g., b'\\x00')

        Returns:
            bytes: Data including delimiter if available, None otherwise.

        Raises:
            ValueError: If buffer exceeds max_buffer_size (potential malformed data).
        """
        # Read all available bytes into buffer
        if self.uart.in_waiting > 0:
            available_bytes = self.uart.read(self.uart.in_waiting)
            if available_bytes:
                try:
                    self.buffer.extend(available_bytes)
                except ValueError:
                    # Buffer overflow - clear buffer and alert user
                    print("WARNING: UART buffer overflow - dropped packets. Buffer cleared.")
                    self.buffer.clear()
                    raise ValueError("UART buffer overflow - buffer has been cleared")

        # Check if we have the delimiter
        delim_idx = self.buffer.find(delimiter)
        if delim_idx >= 0:
            # Extract data including delimiter
            data = bytes(self.buffer[:delim_idx + len(delimiter)])
            # Remove from buffer in O(1) time
            del self.buffer[:delim_idx + len(delimiter)]
            return data

        # Delimiter not found yet
        return None

    def clear_buffer(self):
        """Clear the internal buffer.

        Useful for recovery from error states.
        """
        self.buffer.clear()

    @property
    def buffer_size(self):
        """Get current buffer size.

        Returns:
            int: Number of bytes currently in buffer.
        """
        return len(self.buffer)
