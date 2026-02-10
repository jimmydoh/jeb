"""UART transport implementation with binary protocol and COBS framing."""

import asyncio
import struct
from utilities import cobs_encode, cobs_decode, calculate_crc8
from .message import Message

#region --- Helper Functions for Encoding/Decoding ---
def _encode_destination(dest_str, dest_map):
    """Encode destination string to byte(s).

    Parameters:
        dest_str (str): Destination like "ALL", "SAT", or "0101"
        dest_map (dict): Mapping of special destination strings to byte values

    Returns:
        bytes: Encoded destination (1 or 2 bytes depending on format):
            - 1 byte for special destinations (e.g., "ALL", "SAT")
            - 2 bytes for full device IDs with 4 digits (e.g., "0101" -> type=01, index=01)
    """
    if dest_str in dest_map:
        return bytes([dest_map[dest_str]])

    # Parse numeric ID like "0101" -> type=01, index=01
    if len(dest_str) == 4 and dest_str.isdigit():
        type_id = int(dest_str[:2])
        index = int(dest_str[2:])
        return bytes([type_id, index])

    raise ValueError(
        f"Invalid destination format: {dest_str}. "
        f"Expected 4-digit numeric ID (e.g., '0101') or mapped destination string (e.g., 'ALL', 'SAT')."
    )

def _decode_destination(data, offset, dest_reverse_map, max_index_value):
    """Decode destination from bytes.

    Parameters:
        data (bytes): Raw packet data
        offset (int): Starting offset for destination
        dest_reverse_map (dict): Reverse mapping of byte values to destination strings
        max_index_value (int): Maximum value for single-byte index

    Returns:
        tuple: (dest_str, bytes_consumed)
    """
    if offset >= len(data):
        raise ValueError("Insufficient data for destination")

    dest_byte = data[offset]

    # Check for special destinations
    if dest_byte in dest_reverse_map:
        return dest_reverse_map[dest_byte], 1

    # Check if next byte is part of ID (indices are typically < MAX_INDEX_VALUE)
    if offset + 1 < len(data) and data[offset + 1] < max_index_value:
        # Two-byte ID: type + index
        type_id = dest_byte
        index = data[offset + 1]
        return f"{type_id:02d}{index:02d}", 2

    # Single byte: type only
    return f"{dest_byte:02d}", 1

def _encode_command(cmd_str, command_map):
    """Encode command string to byte.

    Parameters:
        cmd_str (str): Command string like "LED"
        command_map (dict): Mapping of command strings to byte values

    Returns:
        int: Command byte
    """
    if cmd_str in command_map:
        return command_map[cmd_str]

    raise ValueError(f"Unknown command: {cmd_str}")

def _decode_command(cmd_byte, command_reverse_map):
    """Decode command byte to string.

    Parameters:
        cmd_byte (int): Command byte
        command_reverse_map (dict): Reverse mapping of byte values to command strings

    Returns:
        str: Command string
    """
    if cmd_byte in command_reverse_map:
        return command_reverse_map[cmd_byte]

    raise ValueError(f"Unknown command byte: 0x{cmd_byte:02X}")

def _encode_payload(payload_str, cmd_schema=None, encoding_constants=None):
    """Encode payload string/list/tuple/bytes to bytes with explicit type handling.

    This function eliminates the fragility of "magic" type guessing by using
    command-specific schemas that explicitly define expected data types.

    Parameters:
        payload_str (str, list, tuple, or bytes): Payload to encode. Can be:
            - str: Comma-separated values or text
            - list/tuple: Direct numeric values (avoids string parsing overhead)
            - bytes: Already encoded payload (returned as-is)
        cmd_schema (dict, optional): Schema defining payload structure
        encoding_constants (dict, optional): Dictionary with ENCODING_* constants

    Returns:
        bytes: Encoded payload
    """
    if not payload_str:
        return b''
    if isinstance(payload_str, (bytes, bytearray)):
        return bytes(payload_str)

    # Efficient list/tuple packing
    if isinstance(payload_str, (list, tuple)):
        if cmd_schema and encoding_constants:
            etype = cmd_schema.get('type')
            if etype == encoding_constants.get('ENCODING_NUMERIC_BYTES'):
                return bytes([int(x) for x in payload_str])
            elif etype == encoding_constants.get('ENCODING_NUMERIC_WORDS'):
                return b''.join([struct.pack('<h', int(x)) for x in payload_str])
            elif etype == encoding_constants.get('ENCODING_FLOATS'):
                return b''.join([struct.pack('<f', float(x)) for x in payload_str])

        # Heuristic fallback
        out = bytearray()
        for v in payload_str:
            if isinstance(v, float):
                out.extend(struct.pack('<f', v))
            elif isinstance(v, int):
                if -128 <= v <= 255:
                    out.append(v & 0xFF)
                else: out.extend(struct.pack('<i', v))
            else: out.extend(struct.pack('<f', float(v)))
        return bytes(out)

    if cmd_schema and encoding_constants:
        etype = cmd_schema.get('type')
        if etype == encoding_constants.get('ENCODING_RAW_TEXT'):
            return payload_str.encode('utf-8')
        elif etype == encoding_constants.get('ENCODING_NUMERIC_BYTES'):
            # Parse comma-separated integers as bytes
            if ',' in payload_str:
                values = [int(x.strip()) for x in payload_str.split(',')]
                return bytes(values)
            else:
                return bytes([int(payload_str)])
        elif etype == encoding_constants.get('ENCODING_NUMERIC_WORDS'):
            # Parse comma-separated integers as 16-bit words
            if ',' in payload_str:
                values = [int(x.strip()) for x in payload_str.split(',')]
            else:
                values = [int(payload_str)]
            # Validate signed 16-bit range
            if not all(-32768 <= v <= 32767 for v in values):
                raise ValueError(f'Word values must be in range -32768 to 32767')
            return b''.join([struct.pack('<h', v) for v in values])
        elif etype == encoding_constants.get('ENCODING_FLOATS'):
            # Parse comma-separated floats
            try:
                if ',' in payload_str:
                    values = [float(x.strip()) for x in payload_str.split(',')]
                else:
                    values = [float(payload_str)]
                return b''.join([struct.pack('<f', v) for v in values])
            except ValueError as e:
                raise ValueError(f'Invalid float format: {e}')

    # Fallback for comma-separated strings
    # Try to parse as comma-separated numeric values (backward compatibility)
    if ',' in payload_str:
        try:
            parts = payload_str.split(',')
            # Try to parse as integers
            values = [int(p.strip()) for p in parts]
            # Pack as bytes if all values fit in byte range
            if all(0 <= v <= 255 for v in values):
                return bytes(values)
            # Otherwise fall through to text encoding
        except ValueError:
            pass  # Not numeric, treat as text

    # Default to text encoding
    return payload_str.encode('utf-8')

def _decode_payload(payload_bytes, cmd_schema=None, encoding_constants=None):
    """Decode payload bytes to appropriate type with explicit type handling.

    Uses command-specific schemas to properly interpret binary data.
    Optimization: Returns tuples for numeric data instead of comma-separated strings
    to reduce string allocations and GC pressure.

    Parameters:
        payload_bytes (bytes): Raw binary payload data
        cmd_schema (dict, optional): Schema defining payload structure
        encoding_constants (dict, optional): Dictionary with ENCODING_* constants

    Returns:
        tuple, str, or bytes:
            - tuple of int/float for numeric encodings (ENCODING_NUMERIC_*, ENCODING_FLOATS)
            - str for text encodings (ENCODING_RAW_TEXT) or printable UTF-8
            - bytes for unknown binary data (fallback)
    """
    if not payload_bytes:
        return ""
    if cmd_schema and encoding_constants:
        etype = cmd_schema.get('type')
        if etype == encoding_constants.get('ENCODING_RAW_TEXT'):
            return payload_bytes.decode('utf-8')
        if etype == encoding_constants.get('ENCODING_NUMERIC_BYTES'):
            return tuple(payload_bytes)
        if etype == encoding_constants.get('ENCODING_NUMERIC_WORDS'):
            count = len(payload_bytes) // 2
            return struct.unpack(f'<{count}h', payload_bytes)
        if etype == encoding_constants.get('ENCODING_FLOATS'):
            count = len(payload_bytes) // 4
            return struct.unpack(f'<{count}f', payload_bytes)

    try:
        decoded = payload_bytes.decode('utf-8')
        if all(32 <= ord(c) <= 126 or c in '\n\r\t' for c in decoded):
            return decoded
    except UnicodeDecodeError:
        # Fallback: return raw bytes if payload is not valid UTF-8
        return payload_bytes
#endregion

#region --- Main Transport Class ---
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

    # Maximum size for internal receive buffer to prevent unbounded growth
    MAX_BUFFER_SIZE = 1024  # ample space for ~2-4 packets

    # Overflow handling thresholds
    # When overflow occurs after extracting a packet, use these to manage remaining data
    MAX_DELIMITER_DISTANCE_THRESHOLD = MAX_BUFFER_SIZE // 2  # If next packet is beyond this, likely garbage
    OVERFLOW_REMOVAL_SIZE = MAX_BUFFER_SIZE // 4  # Amount of old data to remove when distant delimiter found
    PARTIAL_PACKET_BUFFER_SIZE = MAX_BUFFER_SIZE // 2  # Amount of recent data to keep when no delimiters

    def __init__(self, uart_hw, command_map=None, dest_map=None, max_index_value=100, payload_schemas=None, queued=False):
        """Initialize UART transport.

        Parameters:
            uart_hw (UART): The UART hardware for physical I/O.
            command_map (dict, optional): Command string to byte mapping.
                If None, an empty map is used (transport won't encode/decode commands).
            dest_map (dict, optional): Special destination string to byte mapping.
                If None, an empty map is used (only numeric IDs supported).
            max_index_value (int, optional): Maximum value for single-byte index.
                Defaults to 100.
            payload_schemas (dict, optional): Command-specific payload schemas defining
                encoding/decoding types. If None, uses heuristic encoding.
            queued (bool, optional): If True, uses a queued UART manager for upstream
                to prevent blocking on writes. Defaults to False.
        """
        self.uart = uart_hw
        self.queued = queued

        # Protocol config
        self.command_map = command_map or {}
        self.command_reverse_map = {v: k for k, v in self.command_map.items()}
        self.dest_map = dest_map or {}
        self.dest_reverse_map = {v: k for k, v in self.dest_map.items()}
        self.max_index_value = max_index_value
        self.payload_schemas = payload_schemas or {}

        # Create encoding constants dictionary for payload functions
        self.encoding_constants = {
            'ENCODING_RAW_TEXT': 'text',
            'ENCODING_NUMERIC_BYTES': 'bytes',
            'ENCODING_NUMERIC_WORDS': 'words',
            'ENCODING_FLOATS': 'floats'
        }

        # Internal buffer for non-blocking receive
        self._receive_buffer = bytearray()

        # Relay task
        self._relay_task = None

        # TX Queue Setup for queued mode
        if self.queued:
            self._tx_queue = asyncio.Queue()
            self._tx_task = None

#region --- Harware / IO Methods ---
    def read_raw_into(self, buf):
        """Read available raw bytes into a buffer.

        Parameters:
            buf (bytearray): Buffer to read into.

        Returns:
            int: Number of bytes read.
        """
        # We delegate directly to the internal manager
        if self.uart.in_waiting > 0:
            return self.uart.readinto(buf)
        return 0

    def enable_relay_from(self, source_transport):
        """Enable raw data relay from a source transport to this transport.

        Useful for daisy-chaining where data received on `source_transport`
        should be immediately forwarded out via this transport.

        Parameters:
            source_transport (UARTTransport): The transport to read raw bytes from.
        """
        if self._relay_task:
            self._relay_task.cancel()
        self._relay_task = asyncio.create_task(self._relay_worker(source_transport))

    async def _relay_worker(self, source_transport):
        """Background task to relay raw bytes."""
        buf = bytearray(64)
        while True:
            # Read raw bytes from the source transport
            count = source_transport.read_raw_into(buf)
            if count > 0:
                data = bytes(buf[:count])
                # Write to our output (Queued or Direct)
                if self.queued:
                    self._tx_queue.put_nowait(data)
                else:
                    self.uart.write(data)
            # Yield to allow other tasks to run
            await asyncio.sleep(0)

    async def _tx_worker(self):
        """Dedicated task to drain the TX queue to hardware.

        This is the ONLY task that should write directly to uart_mgr.
        All other code must push data to uart_queue.

        This prevents race conditions where multiple tasks interleave
        partial packets, causing CRC failures and data corruption.
        """
        while True:
            # Wait for data to be available in the queue
            data = await self._tx_queue.get()
            # Write to hardware UART
            self.uart.write(data)
            # Mark task as done
            self._tx_queue.task_done()

    def clear_buffer(self):
        """Clear the UART buffer and internal receive buffer."""
        self.uart.reset_input_buffer()
        self._receive_buffer.clear()
#endregion

#region --- Protocol Methods ---
    def send(self, message):
        """Send a message over UART using binary protocol with COBS framing.

        Parameters:
            message (Message): The message to send.
        """
        # Encoding Logic
        dest = _encode_destination(message.destination, self.dest_map)
        cmd = bytes([_encode_command(message.command, self.command_map)])
        schema = self.payload_schemas.get(message.command)
        payload = _encode_payload(message.payload, schema, self.encoding_constants)

        # Packet Construction
        raw = dest + cmd + payload
        crc = bytes([calculate_crc8(raw)])
        packet = cobs_encode(raw + crc) + b'\x00'

        # Transmission
        if self.queued:
            # put_nowait is safe here as queue is unbounded in CP or ample size
            self._tx_queue.put_nowait(packet)
        else:
            self.uart.write(packet)

    def receive(self):
        """Receive a message from UART if available.

        Non-blocking stateful receive that reads available bytes and buffers them
        internally. Returns a complete message when found, or None otherwise.

        This implementation eliminates blocking read_until() calls that can stall
        the event loop when processing garbage data without delimiters.

        Returns:
            Message or None: Received message if available and valid, None otherwise.
        """
        packet = None

        # Read from Hardware and add any bytes to the internal buffer
        if self.uart.in_waiting:
            data = self.uart.read(self.uart.in_waiting)
            if data:
                self._receive_buffer.extend(data)

        # Check if we have a complete packet (terminated by 0x00) in the buffer
        delimiter_idx = self._receive_buffer.find(b'\x00')
        if delimiter_idx < 0:
            # No complete packet yet
            # SAFETY: Prevent buffer explosion from noise when no valid packets present
            if len(self._receive_buffer) > self.MAX_BUFFER_SIZE:
                print("⚠️ UART Buffer Overflow - Clearing garbage (no packets found)")
                self._receive_buffer.clear()
            return None
        # Otherwise, we have at least one complete packet to process
        packet = bytes(self._receive_buffer[:delimiter_idx])
        # Remove extracted packet and delimiter from buffer
        del self._receive_buffer[:delimiter_idx + 1]

        # SAFETY: After processing a packet, check if buffer still too large
        # This handles case where buffer has valid packet(s) plus excess garbage
        if len(self._receive_buffer) > self.MAX_BUFFER_SIZE:
            print("⚠️ UART Buffer Overflow - Removing excess data")
            # First, discard oldest complete packets until we are back under the cap
            while len(self._receive_buffer) > self.MAX_BUFFER_SIZE:
                next_delimiter_idx = self._receive_buffer.find(b'\x00')
                if next_delimiter_idx < 0:
                    # No complete packets left to discard; stop and fall back to tail retention
                    break
                # Drop the oldest complete packet (up to and including its delimiter)
                del self._receive_buffer[:next_delimiter_idx + 1]
            # If still too large (e.g., only partial/garbage data remains), keep only a bounded tail
            if len(self._receive_buffer) > self.MAX_BUFFER_SIZE:
                keep_bytes = min(self.PARTIAL_PACKET_BUFFER_SIZE, self.MAX_BUFFER_SIZE)
                if len(self._receive_buffer) > keep_bytes:
                    del self._receive_buffer[:-keep_bytes]

        if not packet:
            return None

        # 3. Decoding
        try:
            decoded = cobs_decode(packet)
            if len(decoded) < 3:
                return None

            crc_rx = decoded[-1]
            content = decoded[:-1]

            if calculate_crc8(content) != crc_rx:
                return None # CRC Fail

            # Parse Fields
            dest_str, offset = _decode_destination(
                content,
                0,
                self.dest_reverse_map,
                self.max_index_value
            )
            if offset >= len(content):
                return None

            cmd_str = _decode_command(content[offset], self.command_reverse_map)
            offset += 1

            schema = self.payload_schemas.get(cmd_str)
            payload = _decode_payload(content[offset:], schema, self.encoding_constants)

            return Message(dest_str, cmd_str, payload)

        except (ValueError, IndexError) as e:
            print(f"Protocol Error: {e}")
            return None
#endregion

    def start(self):
        """Start any background tasks required by the transport."""
        if self.queued and self._tx_task is None:
            self._tx_task = asyncio.create_task(self._tx_worker())

#endregion
