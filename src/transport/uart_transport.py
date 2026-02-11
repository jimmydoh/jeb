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
    # Ring buffer constants
    RING_BUFFER_SIZE = 2048  # Fixed 2KB ring buffer
    MAX_PACKET_SIZE = 256    # Maximum packet size for scanning and scratchpad

    def __init__(self, uart_hw, command_map=None, dest_map=None, max_index_value=100, payload_schemas=None):
        """Initialize UART transport.

        Parameters:
            uart_hw (UART): The UART hardware for physical I/O.
                **CRITICAL REQUIREMENT**: uart_hw MUST operate in non-blocking mode
                with a reliable `in_waiting` property implementation. If `in_waiting`
                is not implemented correctly or returns inaccurate values, the fallback
                to `readinto()` in `read_raw_into()` could block the entire asyncio
                event loop for the duration of the UART timeout (typically 10ms-100ms).

                Required uart_hw interface:
                - `in_waiting`: Property that accurately returns the number of bytes
                  available in the receive buffer without blocking.
                - `readinto(buf)`: Method to read available bytes into a buffer.
                - `read(n)`: Method to read n bytes from the buffer.
                - `write(data)`: Method to write data to UART.
                - `reset_input_buffer()`: Method to clear the receive buffer.

            command_map (dict, optional): Command string to byte mapping.
                If None, an empty map is used (transport won't encode/decode commands).
            dest_map (dict, optional): Special destination string to byte mapping.
                If None, an empty map is used (only numeric IDs supported).
            max_index_value (int, optional): Maximum value for single-byte index.
                Defaults to 100.
            payload_schemas (dict, optional): Command-specific payload schemas defining
                encoding/decoding types. If None, uses heuristic encoding.
        """
        self.uart = uart_hw

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

        # RX Queue implemented as zero-allocation ring buffer
        self._rx_buf_size = self.RING_BUFFER_SIZE
        self._rx_buffer = bytearray(self._rx_buf_size)
        self._rx_mv = memoryview(self._rx_buffer)
        self._rx_head = 0
        self._rx_tail = 0
        self._rx_queue = asyncio.Queue()
        self._rx_task = None

        # Linear Scratchpad for Packet Unwrapping
        self._packet_rx_buf = bytearray(self.MAX_PACKET_SIZE)
        self._packet_rx_mv = memoryview(self._packet_rx_buf)

        # TX Queue implemented as zero-allocation ring buffer
        self._tx_buffer_size = self.RING_BUFFER_SIZE
        self._tx_buffer = bytearray(self._tx_buffer_size)
        self._tx_mv = memoryview(self._tx_buffer)
        self._tx_head = 0
        self._tx_tail = 0
        self._tx_event = asyncio.Event()
        self._tx_task = None

        # Relay task
        self._relay_task = None

#region --- Harware / IO Methods ---
    def _write_to_tx_buffer(self, data):
        """Write data to the TX ring buffer.

        This method is used by the send() method to enqueue data for transmission.
        It handles ring buffer wrap-around and ensures that data is not overwritten
        if the buffer is full. If the buffer is full, it raises an exception.

        Parameters:
            data (bytes): Data to write to the TX buffer.

        Raises:
            BufferError: If there is not enough space in the TX buffer to write the data.
        """
        data_len = len(data)
        head = self._tx_head
        tail = self._tx_tail
        size = self._tx_buffer_size

        # Calculate free space in buffer
        if tail > head:
            free_space = tail - head - 1
        elif tail == head:
            free_space = size - 1
        else:
            free_space = size - head

        if data_len > free_space:
            raise BufferError("TX buffer overflow: Not enough space to write data")

        # Perform the copy (handling wrap-around)
        # Case A: Data fits in the remainder of the buffer
        if head + data_len <= size:
            self._tx_mv[head : head + data_len] = data
            self._tx_head = (head + data_len) % size
        # Case B: Data wraps around
        else:
            first_chunk = size - head
            second_chunk = data_len - first_chunk
            self._tx_mv[head : size] = data[:first_chunk]
            self._tx_mv[0 : second_chunk] = data[first_chunk:]
            self._tx_head = second_chunk

        self._tx_event.set()  # Signal TX worker that new data is available

    def read_raw_into(self, buf):
        """Read available raw bytes into a buffer.

        This method checks `in_waiting` before calling `readinto()` to ensure
        non-blocking operation. The `in_waiting` check is critical for preventing
        the asyncio event loop from blocking.

        **IMPORTANT**: This implementation assumes that `self.uart.in_waiting` is
        implemented correctly and returns accurate values. If `in_waiting` is not
        reliable or not implemented, the fallback to `readinto()` could block the
        entire asyncio loop for the duration of the UART timeout (default 10ms-100ms).

        To ensure proper non-blocking behavior:
        1. The uart_hw object must implement `in_waiting` as a non-blocking property
           that accurately reflects the number of bytes available in the receive buffer.
        2. The `readinto()` method should only be called when `in_waiting > 0` to
           avoid potential blocking behavior.
        3. If swapping to a different hardware interface, verify that it meets these
           requirements or implement appropriate non-blocking wrappers.

        Parameters:
            buf (bytearray): Buffer to read into.

        Returns:
            int: Number of bytes read.
        """
        # We delegate directly to the internal manager
        if self.uart.in_waiting > 0:
            return self.uart.readinto(buf)
        return 0

    def _read_hw(self):
        """Read UART data into ring buffer using zero-allocation readinto.

        This method reads available UART data directly into the ring buffer
        using memoryview slicing, avoiding any memory allocation or copying.
        Handles ring buffer wrap-around automatically.
        """
        if not self.uart.in_waiting:
            return

        # Calculate available contiguous space in ring buffer
        if self._rx_tail > self._rx_head:
            # Space wraps around: can write from head to tail (minus 1 for full detection)
            space = self._rx_tail - self._rx_head - 1
        elif self._rx_tail == self._rx_head:
            # Buffer Empty: We can use the whole contiguous chunk to the end
            space = self._rx_buf_size - self._rx_head
            # EXCEPTION: If head is 0, we can't fill the ENTIRE buffer (2048)
            # because head would wrap to 0, matching tail (looks empty).
            if self._rx_head == 0:
                space -= 1
        else:
            # Tail < Head: Write to end of physical buffer
            space = self._rx_buf_size - self._rx_head

        if space <= 0:
            return  # Buffer full

        # Read directly into ring buffer memoryview slice
        try:
            count = self.uart.readinto(self._rx_mv[self._rx_head : self._rx_head + space])
            if count and count > 0:
                self._rx_head = (self._rx_head + count) % self._rx_buf_size
        except Exception:
            pass  # Ignore read errors

    def _try_decode_one(self):
        """Receive a message from UART if available.

        Non-blocking stateful receive that reads available bytes into a fixed-size
        ring buffer. Returns a complete message when found, or None otherwise.

        This implementation uses a zero-allocation ring buffer with memoryview slicing
        to eliminate heap fragmentation and improve performance.

        Returns:
            Message or None: Received message if available and valid, None otherwise.
        """
        # Check if we have any data
        if self._rx_head == self._rx_tail:
            return None  # Buffer empty

        # Find delimiter (0x00) in ring buffer
        # Scan from tail to head, handling wrap-around
        bytes_available = (self._rx_head - self._rx_tail) % self._rx_buf_size

        # Limit scan to MAX_PACKET_SIZE to prevent hanging on massive garbage data
        scan_limit = min(bytes_available, self.MAX_PACKET_SIZE)

        packet_len = 0
        found_delimiter = False

        for i in range(scan_limit):
            idx = (self._rx_tail + i) % self._rx_buf_size
            if self._rx_buffer[idx] == 0x00:
                found_delimiter = True
                packet_len = i
                break

        if not found_delimiter:
            # No delimiter found
            # SAFETY: If buffer is nearly full and no delimiter, clear the buffer to prevent deadlock
            # This is aggressive but necessary when flooded with garbage data
            if bytes_available > self._rx_buf_size - self.MAX_PACKET_SIZE:
                # Buffer is critically full - reset it
                self._rx_head = 0
                self._rx_tail = 0
            elif bytes_available >= self.MAX_PACKET_SIZE:
                # Advance tail by a larger chunk to clear garbage faster
                self._rx_tail = (self._rx_tail + 100) % self._rx_buf_size
            return None

        # Unwrap packet from ring buffer into linear scratchpad
        # This uses fast memoryview slice assignment instead of Python loops

        if packet_len > len(self._packet_rx_buf):
            # Packet too large - skip it
            self._rx_tail = (self._rx_tail + packet_len + 1) % self._rx_buf_size
            return None

        # Case A: Packet is contiguous (no wrap-around)
        if self._rx_tail + packet_len <= self._rx_buf_size:
            # Fast copy: Linear slice to linear slice
            self._packet_rx_mv[:packet_len] = self._rx_mv[self._rx_tail : self._rx_tail + packet_len]
        else:
            # Case B: Packet wraps around end of ring buffer
            # Copy in two chunks using fast slice assignment
            first_chunk = self._rx_buf_size - self._rx_tail
            second_chunk = packet_len - first_chunk

            # Copy part 1: tail to end of buffer
            self._packet_rx_mv[:first_chunk] = self._rx_mv[self._rx_tail:]
            # Copy part 2: start of buffer to remainder
            self._packet_rx_mv[first_chunk:packet_len] = self._rx_mv[:second_chunk]

        # Advance tail past packet and delimiter
        self._rx_tail = (self._rx_tail + packet_len + 1) % self._rx_buf_size

        # Decode packet using linear scratchpad
        try:
            decoded = cobs_decode(self._packet_rx_mv[:packet_len])
            if len(decoded) < 3:
                return None

            crc_rx = decoded[-1]
            content = decoded[:-1]

            if calculate_crc8(content) != crc_rx:
                return None  # CRC fail

            # Parse fields
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

    def enable_relay_from(self, source_transport, heartbeat_callback=None):
        """Enable raw data relay from a source transport to this transport.

        Useful for daisy-chaining where data received on `source_transport`
        should be immediately forwarded out via this transport.

        Parameters:
            source_transport (UARTTransport): The transport to read raw bytes from.
        """
        if self._relay_task:
            self._relay_task.cancel()
        self._relay_task = asyncio.create_task(self._relay_worker(source_transport, heartbeat_callback))

    def clear_buffer(self):
        """Clear the UART buffer and internal ring buffer."""
        self.uart.reset_input_buffer()
        self._rx_head = 0
        self._rx_tail = 0
#endregion

#region --- Background Worker Tasks ---
    async def _relay_worker(self, source_transport, heartbeat_callback):
        """Background task to relay raw bytes."""
        while True:
            if heartbeat_callback:
                heartbeat_callback()

            # Calculate free space in TX ring buffer
            head = self._tx_head
            tail = self._tx_tail
            size = self._tx_buffer_size
            if tail > head:
                free_space = tail - head - 1
            elif tail == head:
                free_space = size - 1
            else:
                free_space = size - head

            if free_space <= 0:
                # Buffer full, wait for space to be available
                await asyncio.sleep(0.005)
                continue

            # Read directly into the TX buffer
            # We pass the slice of our TX buffer directly to the source's read method.
            count = source_transport.read_raw_into(self._tx_mv[head : head + free_space])

            if count and count > 0:
                self._tx_head = (head + count) % size
                self._tx_event.set()  # Wake up TX worker if waiting
                await asyncio.sleep(0)  # Yield to event loop
            else:
                # Sleep briefly when idle to reduce CPU usage
                await asyncio.sleep(0.005)

    async def _rx_worker(self):
        """
        Dedicated task to read from UART and fill RX ring buffer.

        This is the ONLY task that should read directly from uart_mgr.
        All other code must call receive() which reads from the ring buffer.

        This prevents race conditions where multiple tasks interleave reads,
        causing data corruption and lost messages.
        """
        while True:
            # Pump hardware data into ring buffer
            self._read_hw()

            # Decode a packet and put it in the RX queue
            msg = self._try_decode_one()

            if msg:
                self._rx_queue.put_nowait(msg)
                await asyncio.sleep(0)  # Yield to event loop after processing a message
            else:
                if self.uart.in_waiting > 0:
                    # Sleep briefly when idle to reduce CPU usage
                    await asyncio.sleep(0.005)
                else:
                    await asyncio.sleep(0.02)  # Longer sleep when no data is available

    async def _tx_worker(self):
        """Dedicated task to drain the TX queue to hardware.

        This is the ONLY task that should write directly to uart_mgr.
        All other code must push data to uart_queue.

        This prevents race conditions where multiple tasks interleave
        partial packets, causing CRC failures and data corruption.
        """
        while True:
            # Wait until we have data to send
            await self._tx_event.wait()

            # While there is data to send
            while self._tx_head != self._tx_tail:
                # Calculate available data in TX buffer
                head = self._tx_head
                tail = self._tx_tail
                size = self._tx_buffer_size

                # Determine contiguous chunk to write
                if head > tail:
                    # Contiguous from tail to head
                    chunk = self._tx_mv[tail:head]
                else:
                    # Wraps around; write from tail to end of buffer first
                    chunk = self._tx_mv[tail:size]

                written = self.uart.write(chunk)

                if written is None:
                    # Some UART implementations return None instead of number of bytes written
                    # In this case, we assume all bytes were written successfully
                    written = len(chunk)

                # Advance tail by number of bytes written
                self._tx_tail = (tail + written) % size

                # If we couldn't write all bytes, we'll try again immediately
                if written < len(chunk):
                    await asyncio.sleep(0.005)  # Brief sleep to yield to event loop

            # Buffer empty, clear the event
            self._tx_event.clear()
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

        try:
            self._write_to_tx_buffer(packet)
        except BufferError as e:
            print(f"TX Buffer Error: {e}")
            # Optionally, we could implement a retry mechanism here or drop the packet
            # For now, we just log the error and drop the packet

    async def receive(self):
        """Asynchronously receive a message from the RX queue.

        This method should be called by external code to get messages received
        from UART. It waits for a message to be available in the RX queue and
        returns it.

        Returns:
            Message: The next received message.
        """
        return await self._rx_queue.get()

    def receive_nowait(self):
        """Attempt to receive a message from the RX queue without waiting.

        This method returns immediately with a message if available, or None if
        the queue is empty.

        Returns:
            Message or None: The next received message if available, or None if the queue is empty.
        """
        try:
            return self._rx_queue.get_nowait()
        except asyncio.QueueEmpty:
            return None
#endregion

    def start(self):
        """Start any background tasks required by the transport."""
        if self._tx_task is None:
            self._tx_task = asyncio.create_task(self._tx_worker())
        if self._rx_task is None:
            self._rx_task = asyncio.create_task(self._rx_worker())

#endregion
