"""UART transport implementation with binary protocol and COBS framing."""

import struct
from utilities import cobs_encode, cobs_decode, calculate_crc8
from .message import Message


# Command string to byte mapping
COMMAND_MAP = {
    # Core commands
    "STATUS": 0x01,
    "ID_ASSIGN": 0x02,
    "NEW_SAT": 0x03,
    "ERROR": 0x04,
    "LOG": 0x05,
    "POWER": 0x06,
    
    # LED commands
    "LED": 0x10,
    "LEDFLASH": 0x11,
    "LEDBREATH": 0x12,
    "LEDCYLON": 0x13,
    "LEDCENTRI": 0x14,
    "LEDRAINBOW": 0x15,
    "LEDGLITCH": 0x16,
    
    # Display commands
    "DSP": 0x20,
    "DSPCORRUPT": 0x21,
    "DSPMATRIX": 0x22,
    
    # Encoder commands
    "SETENC": 0x30,
}

# Reverse mapping for decoding
COMMAND_REVERSE_MAP = {v: k for k, v in COMMAND_MAP.items()}


# Special destination IDs
DEST_MAP = {
    "ALL": 0xFF,
    "SAT": 0xFE,
}

DEST_REVERSE_MAP = {v: k for k, v in DEST_MAP.items()}

# Maximum value for single-byte index (used to distinguish 1-byte vs 2-byte dest IDs)
MAX_INDEX_VALUE = 100


def _encode_destination(dest_str):
    """Encode destination string to byte(s).
    
    Parameters:
        dest_str (str): Destination like "ALL", "SAT", or "0101"
        
    Returns:
        bytes: Encoded destination (1-2 bytes)
    """
    if dest_str in DEST_MAP:
        return bytes([DEST_MAP[dest_str]])
    
    # Parse numeric ID like "0101" -> type=01, index=01
    if len(dest_str) == 4 and dest_str.isdigit():
        type_id = int(dest_str[:2])
        index = int(dest_str[2:])
        return bytes([type_id, index])
    
    # Default: treat as type-only (backward compat)
    if dest_str.isdigit():
        type_id = int(dest_str)
        return bytes([type_id])
    
    raise ValueError(f"Invalid destination format: {dest_str}")


def _decode_destination(data, offset):
    """Decode destination from bytes.
    
    Parameters:
        data (bytes): Raw packet data
        offset (int): Starting offset for destination
        
    Returns:
        tuple: (dest_str, bytes_consumed)
    """
    if offset >= len(data):
        raise ValueError("Insufficient data for destination")
    
    dest_byte = data[offset]
    
    # Check for special destinations
    if dest_byte in DEST_REVERSE_MAP:
        return DEST_REVERSE_MAP[dest_byte], 1
    
    # Check if next byte is part of ID (indices are typically < MAX_INDEX_VALUE)
    if offset + 1 < len(data) and data[offset + 1] < MAX_INDEX_VALUE:
        # Two-byte ID: type + index
        type_id = dest_byte
        index = data[offset + 1]
        return f"{type_id:02d}{index:02d}", 2
    
    # Single byte: type only
    return f"{dest_byte:02d}", 1


def _encode_command(cmd_str):
    """Encode command string to byte.
    
    Parameters:
        cmd_str (str): Command string like "LED"
        
    Returns:
        int: Command byte
    """
    if cmd_str in COMMAND_MAP:
        return COMMAND_MAP[cmd_str]
    
    raise ValueError(f"Unknown command: {cmd_str}")


def _decode_command(cmd_byte):
    """Decode command byte to string.
    
    Parameters:
        cmd_byte (int): Command byte
        
    Returns:
        str: Command string
    """
    if cmd_byte in COMMAND_REVERSE_MAP:
        return COMMAND_REVERSE_MAP[cmd_byte]
    
    raise ValueError(f"Unknown command byte: 0x{cmd_byte:02X}")


def _encode_payload(payload_str):
    """Encode payload string to bytes.
    
    For comma-separated numeric values, encode as packed bytes.
    For text strings, encode as UTF-8.
    
    Parameters:
        payload_str (str): Payload string
        
    Returns:
        bytes: Encoded payload
    """
    if not payload_str:
        return b''
    
    # Try to parse as comma-separated values
    parts = payload_str.split(',')
    
    # Check if all parts are numeric
    try:
        values = []
        for part in parts:
            # Try integer
            if part.isdigit() or (part.startswith('-') and part[1:].isdigit()):
                val = int(part)
                values.append(val)
            else:
                # Try float
                val = float(part)
                # Encode float as 4-byte IEEE 754
                values.append(struct.pack('<f', val))
        
        # Pack integers as bytes (use appropriate size)
        result = bytearray()
        for val in values:
            if isinstance(val, bytes):
                result.extend(val)
            elif -128 <= val <= 255:
                result.append(val & 0xFF)
            elif -32768 <= val <= 32767:
                result.extend(struct.pack('<h', val))
            else:
                result.extend(struct.pack('<i', val))
        
        return bytes(result)
    except (ValueError, OverflowError):
        # Not all numeric - encode as UTF-8 string
        return payload_str.encode('utf-8')


def _decode_payload(payload_bytes):
    """Decode payload bytes, returning raw bytes for binary data or string for text.
    
    Parameters:
        payload_bytes (bytes): Raw payload data
        
    Returns:
        bytes or str: Raw bytes for binary data, decoded string for text data
    """
    if not payload_bytes:
        return ""
    
    # Try to decode as UTF-8 text first
    try:
        text = payload_bytes.decode('utf-8')
        # Check if it's printable ASCII-ish
        if all(32 <= ord(c) <= 126 or c in '\n\r\t' for c in text):
            return text
    except UnicodeDecodeError:
        pass
    
    # Return raw bytes for binary data - let the application layer decide how to decode
    # This avoids the "String Boomerang" problem where we convert bytes -> string -> bytes
    return payload_bytes


class UARTTransport:
    """UART transport implementation with binary protocol and COBS framing.
    
    Binary Protocol Format:
    - [DEST][CMD][PAYLOAD][CRC] (before COBS encoding)
    - DEST: 1-2 bytes (special values or type+index)
    - CMD: 1 byte (command code)
    - PAYLOAD: N bytes (binary data)
    - CRC: 1 byte (CRC-8 checksum)
    
    COBS Framing:
    - Packets are COBS-encoded to eliminate 0x00 bytes
    - 0x00 is used as packet terminator
    - No newlines or text-based parsing required
    
    This replaces the old text-based protocol:
    - Old: "DEST|CMD|PAYLOAD|CRC\n" (expensive string parsing)
    - New: [DEST][CMD][PAYLOAD][CRC] + COBS (zero parsing, direct byte access)
    """
    
    def __init__(self, uart_manager):
        """Initialize UART transport.
        
        Parameters:
            uart_manager (UARTManager): The UART manager for physical I/O.
        """
        self.uart_manager = uart_manager
    
    def send(self, message):
        """Send a message over UART using binary protocol with COBS framing.
        
        Parameters:
            message (Message): The message to send.
        """
        # Encode destination
        dest_bytes = _encode_destination(message.destination)
        
        # Encode command
        cmd_byte = bytes([_encode_command(message.command)])
        
        # Encode payload
        payload_bytes = _encode_payload(message.payload)
        
        # Build raw packet (before COBS)
        raw_packet = dest_bytes + cmd_byte + payload_bytes
        
        # Calculate CRC on raw packet
        crc = calculate_crc8(raw_packet)
        crc_byte = bytes([crc])
        
        # Add CRC to packet
        packet_with_crc = raw_packet + crc_byte
        
        # COBS encode (eliminates 0x00 bytes)
        cobs_encoded = cobs_encode(packet_with_crc)
        
        # Append 0x00 terminator
        final_packet = cobs_encoded + b'\x00'
        
        # Send via UART
        self.uart_manager.write(final_packet)
    
    def receive(self):
        """Receive a message from UART if available.
        
        Reads COBS-framed packets, decodes, verifies CRC, and parses into Message.
        
        Returns:
            Message or None: Received message if available and valid, None otherwise.
            
        Raises:
            ValueError: If buffer overflow occurs (propagated from UARTManager).
        """
        # Read until we find a 0x00 terminator
        packet = self.uart_manager.read_until(b'\x00')
        
        if not packet:
            return None
        
        # Remove terminator
        if packet.endswith(b'\x00'):
            packet = packet[:-1]
        
        if not packet:
            return None
        
        try:
            # COBS decode
            decoded_packet = cobs_decode(packet)
        except ValueError as e:
            print(f"COBS decode error: {e}")
            return None
        
        if len(decoded_packet) < 3:  # Minimum: dest(1) + cmd(1) + crc(1)
            return None
        
        # Extract CRC (last byte)
        crc_byte = decoded_packet[-1]
        data = decoded_packet[:-1]
        
        # Verify CRC
        calculated_crc = calculate_crc8(data)
        
        if crc_byte != calculated_crc:
            print(f"CRC check failed: expected 0x{calculated_crc:02X}, got 0x{crc_byte:02X}")
            return None
        
        # Parse destination
        try:
            destination, dest_len = _decode_destination(data, 0)
        except ValueError as e:
            print(f"Destination decode error: {e}")
            return None
        
        offset = dest_len
        
        # Parse command
        if offset >= len(data):
            return None
        
        try:
            command = _decode_command(data[offset])
        except ValueError as e:
            print(f"Command decode error: {e}")
            return None
        
        offset += 1
        
        # Parse payload
        payload_bytes = data[offset:]
        payload = _decode_payload(payload_bytes)
        
        return Message(destination, command, payload)
    
    def clear_buffer(self):
        """Clear the UART buffer."""
        self.uart_manager.clear_buffer()
