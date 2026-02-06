"""UART transport implementation with CRC and line framing."""

from utilities import calculate_crc8, verify_crc8
from .message import Message


class UARTTransport:
    """UART transport implementation.
    
    Handles UART-specific concerns:
    - Message formatting: "DEST|CMD|PAYLOAD|CRC\n"
    - CRC-8 calculation and verification
    - Line-based framing with newline termination
    - Integration with UARTManager for buffered I/O
    
    This transport uses the existing UARTManager for low-level
    buffering and line reading, while adding the protocol layer.
    """
    
    def __init__(self, uart_manager):
        """Initialize UART transport.
        
        Parameters:
            uart_manager (UARTManager): The UART manager for physical I/O.
        """
        self.uart_manager = uart_manager
    
    def send(self, message):
        """Send a message over UART.
        
        Formats the message as "DEST|CMD|PAYLOAD|CRC\n" and transmits.
        
        Parameters:
            message (Message): The message to send.
        """
        # Format data without CRC
        data = f"{message.destination}|{message.command}|{message.payload}"
        
        # Calculate CRC (returns bytes)
        crc = calculate_crc8(data)
        
        # Format complete packet with CRC and newline
        packet = f"{data}|".encode() + crc + b"\n"
        
        # Send via UART
        self.uart_manager.write(packet)
    
    def receive(self):
        """Receive a message from UART if available.
        
        Reads buffered lines from UART, verifies CRC, and parses into Message.
        
        Returns:
            Message or None: Received message if available and valid, None otherwise.
            
        Raises:
            ValueError: If buffer overflow occurs (propagated from UARTManager).
        """
        # Read line from UART buffer (non-blocking)
        line = self.uart_manager.read_line()
        
        if not line:
            return None
        
        # Verify CRC
        is_valid, data = verify_crc8(line)
        if not is_valid:
            # Discard corrupted packet
            print(f"CRC check failed, discarding packet: {line}")
            return None
        
        # Parse message components (handle both str and bytes)
        if isinstance(data, bytes):
            parts = data.split(b"|", 2)
        else:
            parts = data.split("|", 2)
            
        if len(parts) < 3:
            # Malformed packet (not enough fields)
            return None
        
        # Decode bytes to strings for Message if needed
        if isinstance(data, bytes):
            destination, command, payload = parts[0].decode(), parts[1].decode(), parts[2].decode()
        else:
            destination, command, payload = parts[0], parts[1], parts[2]
        
        # Return parsed message
        return Message(destination, command, payload)
    
    def clear_buffer(self):
        """Clear the UART buffer."""
        self.uart_manager.clear_buffer()
