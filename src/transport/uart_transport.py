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


# Payload encoding type constants
ENCODING_RAW_TEXT = 'text'
ENCODING_NUMERIC_BYTES = 'bytes'
ENCODING_NUMERIC_WORDS = 'words'
ENCODING_FLOATS = 'floats'

# Command-specific payload schemas
# This eliminates ambiguity in type interpretation
PAYLOAD_SCHEMAS = {
    # Core commands - these use text IDs that must not be interpreted as numbers
    "ID_ASSIGN": {'type': ENCODING_RAW_TEXT, 'desc': 'Device ID string like "0100"'},
    "NEW_SAT": {'type': ENCODING_RAW_TEXT, 'desc': 'Satellite type ID like "01"'},
    "ERROR": {'type': ENCODING_RAW_TEXT, 'desc': 'Error description text'},
    "LOG": {'type': ENCODING_RAW_TEXT, 'desc': 'Log message text'},
    
    # LED commands - RGB values plus parameters (variable count OK)
    "LED": {'type': ENCODING_NUMERIC_BYTES, 'desc': 'R,G,B,brightness bytes'},
    "LEDFLASH": {'type': ENCODING_NUMERIC_BYTES, 'desc': 'R,G,B,brightness'},
    "LEDBREATH": {'type': ENCODING_NUMERIC_BYTES, 'desc': 'R,G,B,brightness'},
    "LEDCYLON": {'type': ENCODING_NUMERIC_BYTES, 'desc': 'R,G,B,brightness'},
    "LEDCENTRI": {'type': ENCODING_NUMERIC_BYTES, 'desc': 'R,G,B,brightness'},
    "LEDRAINBOW": {'type': ENCODING_NUMERIC_BYTES, 'desc': 'speed,brightness'},
    "LEDGLITCH": {'type': ENCODING_NUMERIC_BYTES, 'desc': 'intensity,brightness'},
    
    # Display commands
    "DSP": {'type': ENCODING_RAW_TEXT, 'desc': 'Display message text'},
    "DSPCORRUPT": {'type': ENCODING_NUMERIC_BYTES, 'desc': 'level,duration'},
    "DSPMATRIX": {'type': ENCODING_NUMERIC_BYTES, 'desc': 'speed,density'},
    
    # Power and status - use floats for voltage/current measurements
    "POWER": {'type': ENCODING_FLOATS, 'desc': 'voltage1,voltage2,current'},
    "STATUS": {'type': ENCODING_NUMERIC_BYTES, 'desc': 'status bytes (variable length)'},
    
    # Encoder
    "SETENC": {'type': ENCODING_NUMERIC_WORDS, 'desc': 'encoder position'},
}


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


def _encode_payload(payload_str, cmd_schema=None):
    """Encode payload string to bytes with explicit type handling.
    
    This function eliminates the fragility of "magic" type guessing by using
    command-specific schemas that explicitly define expected data types.
    
    Parameters:
        payload_str (str): Payload string to encode
        cmd_schema (dict, optional): Schema defining payload structure
        
    Returns:
        bytes: Encoded payload
    """
    if not payload_str:
        return b''
    
    # Use schema if provided to avoid ambiguous type interpretation
    if cmd_schema:
        encoding_type = cmd_schema.get('type')
        
        # Text encoding - preserve the string exactly as-is
        if encoding_type == ENCODING_RAW_TEXT:
            return payload_str.encode('utf-8')
        
        # Parse comma-separated values for numeric encodings
        value_list = [v.strip() for v in payload_str.split(',')]
        expected_count = cmd_schema.get('count')
        
        # Validate count only if specified in schema
        if expected_count is not None and len(value_list) != expected_count:
            raise ValueError(
                f"Schema expects {expected_count} values but got {len(value_list)} in '{payload_str}'"
            )
        
        # Byte encoding (0-255 range)
        if encoding_type == ENCODING_NUMERIC_BYTES:
            output = bytearray()
            for val_str in value_list:
                numeric_val = int(val_str)
                if not (0 <= numeric_val <= 255):
                    raise ValueError(f"Byte value {numeric_val} outside 0-255 range")
                output.append(numeric_val)
            return bytes(output)
        
        # Word encoding (16-bit signed integers)
        elif encoding_type == ENCODING_NUMERIC_WORDS:
            output = bytearray()
            for val_str in value_list:
                numeric_val = int(val_str)
                output.extend(struct.pack('<h', numeric_val))
            return bytes(output)
        
        # Float encoding (IEEE 754 single precision)
        elif encoding_type == ENCODING_FLOATS:
            output = bytearray()
            for val_str in value_list:
                float_val = float(val_str)
                output.extend(struct.pack('<f', float_val))
            return bytes(output)
    
    # Backward compatibility: heuristic encoding for commands without schemas
    # This maintains existing behavior but is being phased out
    value_list = payload_str.split(',')
    
    try:
        parsed_values = []
        for item in value_list:
            # Integer check
            if item.isdigit() or (item.startswith('-') and item[1:].isdigit()):
                parsed_values.append(int(item))
            else:
                # Float check
                parsed_values.append(float(item))
        
        # Pack the parsed values
        output = bytearray()
        for val in parsed_values:
            if isinstance(val, float):
                output.extend(struct.pack('<f', val))
            elif -128 <= val <= 255:
                output.append(val & 0xFF)
            elif -32768 <= val <= 32767:
                output.extend(struct.pack('<h', val))
            else:
                output.extend(struct.pack('<i', val))
        
        return bytes(output)
    except (ValueError, OverflowError):
        # Not numeric - treat as text
        return payload_str.encode('utf-8')


def _decode_payload(payload_bytes, cmd_schema=None):
    """Decode payload bytes to string with explicit type handling.
    
    Uses command-specific schemas to properly interpret binary data.
    
    Parameters:
        payload_bytes (bytes): Raw binary payload data
        cmd_schema (dict, optional): Schema defining payload structure
        
    Returns:
        str: Decoded payload string
    """
    if not payload_bytes:
        return ""
    
    # Use schema if provided
    if cmd_schema:
        encoding_type = cmd_schema.get('type')
        
        # Text decoding
        if encoding_type == ENCODING_RAW_TEXT:
            return payload_bytes.decode('utf-8')
        
        # Byte decoding (0-255 values)
        if encoding_type == ENCODING_NUMERIC_BYTES:
            return ','.join(str(b) for b in payload_bytes)
        
        # Word decoding (16-bit signed)
        elif encoding_type == ENCODING_NUMERIC_WORDS:
            decoded_vals = []
            byte_offset = 0
            while byte_offset + 2 <= len(payload_bytes):
                word_val = struct.unpack('<h', payload_bytes[byte_offset:byte_offset+2])[0]
                decoded_vals.append(str(word_val))
                byte_offset += 2
            return ','.join(decoded_vals)
        
        # Float decoding (IEEE 754)
        elif encoding_type == ENCODING_FLOATS:
            decoded_vals = []
            byte_offset = 0
            while byte_offset + 4 <= len(payload_bytes):
                float_val = struct.unpack('<f', payload_bytes[byte_offset:byte_offset+4])[0]
                decoded_vals.append(str(float_val))
                byte_offset += 4
            return ','.join(decoded_vals)
    
    # Backward compatibility: heuristic decoding
    # Try UTF-8 text interpretation first
    try:
        decoded_text = payload_bytes.decode('utf-8')
        # Verify it's printable
        if all(32 <= ord(ch) <= 126 or ch in '\n\r\t' for ch in decoded_text):
            return decoded_text
    except UnicodeDecodeError:
        pass
    
    # Default: treat as byte sequence
    return ','.join(str(b) for b in payload_bytes)


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
        
        # Look up schema for this command to ensure proper type handling
        cmd_schema = PAYLOAD_SCHEMAS.get(message.command)
        
        # Encode payload with schema (prevents "magic" type guessing)
        payload_bytes = _encode_payload(message.payload, cmd_schema)
        
        # Build raw packet (before COBS)
        raw_packet = dest_bytes + cmd_byte + payload_bytes
        
        # Calculate CRC on raw packet
        crc = calculate_crc8(raw_packet)
        crc_byte = bytes([int(crc.decode('ascii'), 16)])
        
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
        calculated_crc_int = int(calculated_crc.decode('ascii'), 16)
        
        if crc_byte != calculated_crc_int:
            print(f"CRC check failed: expected 0x{calculated_crc_int:02X}, got 0x{crc_byte:02X}")
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
        
        # Look up schema for this command to ensure proper type handling
        cmd_schema = PAYLOAD_SCHEMAS.get(command)
        
        # Parse payload with schema (avoids ambiguous type interpretation)
        payload_bytes = data[offset:]
        payload = _decode_payload(payload_bytes, cmd_schema)
        
        return Message(destination, command, payload)
    
    def clear_buffer(self):
        """Clear the UART buffer."""
        self.uart_manager.clear_buffer()
