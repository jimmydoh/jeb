# Transport Layer Abstraction

## Overview

The JEB communication system has been refactored to separate protocol logic from transport implementation. This allows easy switching between different physical transports (UART, I2C, CAN bus) without changing the core application logic.

## Architecture

### Before

```
CoreManager/Satellite
    ↓ (directly formats packets with CRC)
    ↓ (calls uart.write/read_line)
UARTManager
    ↓
Physical UART Hardware
```

Protocol concerns (CRC, framing) were tightly coupled with application logic.

### After

```
CoreManager/Satellite
    ↓ (works with Message objects)
Transport Layer (UARTTransport, future: I2CTransport, CANTransport)
    ↓ (handles CRC, framing, serialization)
UARTManager
    ↓
Physical UART Hardware
```

Protocol concerns are encapsulated in the transport layer.

## Hardware Requirements

### Non-Blocking UART Operation

**CRITICAL**: The `uart_hw` object passed to `UARTTransport` MUST operate in non-blocking mode with a reliable `in_waiting` property implementation.

#### Why This Matters

The `UARTTransport.read_raw_into()` method checks `in_waiting` before calling `readinto()` to ensure non-blocking operation:

```python
def read_raw_into(self, buf):
    if self.uart.in_waiting > 0:
        return self.uart.readinto(buf)
    return 0
```

If `in_waiting` is not implemented correctly or returns inaccurate values, the fallback to `readinto()` could block the entire asyncio event loop for the duration of the UART timeout (typically 10ms-100ms). This would:

1. **Stall the event loop**: Other async tasks cannot run while waiting for UART data
2. **Cause watchdog timeouts**: The watchdog timer may not be fed in time
3. **Degrade UI responsiveness**: Display updates, button handling, and other tasks freeze
4. **Break satellite communication**: Message relay and network coordination fail

#### Required Interface

The `uart_hw` object must implement the following interface:

```python
class UARTHardwareInterface:
    @property
    def in_waiting(self):
        """Return number of bytes available in receive buffer without blocking.
        
        This MUST be a non-blocking operation that accurately reflects the
        current state of the receive buffer. Returning inaccurate values
        (e.g., always returning 0 or a stale count) will cause the transport
        layer to either miss data or block unexpectedly.
        
        Returns:
            int: Number of bytes available to read (>= 0)
        """
        
    def readinto(self, buf):
        """Read available bytes into the provided buffer.
        
        Should only be called when in_waiting > 0 to ensure non-blocking behavior.
        
        Parameters:
            buf (bytearray): Buffer to read data into
            
        Returns:
            int: Number of bytes actually read
        """
        
    def read(self, n):
        """Read n bytes from the receive buffer.
        
        Parameters:
            n (int): Maximum number of bytes to read
            
        Returns:
            bytes: Data read from buffer (may be less than n bytes)
        """
        
    def write(self, data):
        """Write data to UART transmit buffer.
        
        Parameters:
            data (bytes): Data to transmit
        """
        
    def reset_input_buffer(self):
        """Clear the receive buffer, discarding all unread data."""
```

#### CircuitPython busio.UART

The standard CircuitPython `busio.UART` class meets these requirements when properly configured:

```python
import busio
import board

# Create UART with appropriate timeout
# A small timeout (0.01s = 10ms) prevents long blocking on read operations
uart = busio.UART(board.TX, board.RX, baudrate=115200, timeout=0.01)

# The in_waiting property is implemented correctly and non-blocking
bytes_available = uart.in_waiting  # Returns immediately with count

# The readinto() method respects the timeout parameter
if uart.in_waiting > 0:
    buf = bytearray(64)
    count = uart.readinto(buf)  # Returns after reading or timeout
```

#### Custom Hardware Adapters

If you're implementing a custom UART adapter or wrapping a different interface:

1. **Ensure `in_waiting` is truly non-blocking**: Don't perform I/O operations or wait for hardware in the property getter
2. **Keep the count accurate**: Update `in_waiting` whenever data is received or consumed
3. **Test under load**: Verify behavior when receiving rapid bursts of data
4. **Document deviations**: If your hardware has limitations, clearly document them

Example of a correct wrapper:

```python
class NonBlockingUARTWrapper:
    def __init__(self, hardware_uart):
        self._uart = hardware_uart
        self._buffer = bytearray()
        
    @property
    def in_waiting(self):
        # Non-blocking: just return the buffer length
        return len(self._buffer)
        
    def readinto(self, buf):
        # Only read from internal buffer (already received)
        count = min(len(buf), len(self._buffer))
        buf[:count] = self._buffer[:count]
        del self._buffer[:count]
        return count
        
    def _background_receive(self):
        # Called periodically by async task to populate buffer
        if self._uart.in_waiting > 0:
            data = self._uart.read(self._uart.in_waiting)
            self._buffer.extend(data)
```

#### Verification Checklist

Before deploying a new UART hardware interface with `UARTTransport`:

- [ ] `in_waiting` property returns immediately without blocking
- [ ] `in_waiting` accurately reflects available data at all times
- [ ] `readinto()` respects configured timeout and doesn't block indefinitely
- [ ] Rapid data bursts don't cause `in_waiting` to report stale values
- [ ] Event loop continues to run smoothly during UART operations
- [ ] Watchdog timer is fed regularly (no unexpected resets)

## Key Components

### Message Class

Represents a protocol-level message, independent of transport:

```python
from transport import Message

# Create a message
msg = Message(destination="0101", command="LED", payload="ALL,255,0,0")

# Messages are transport-agnostic
# No CRC, no framing, just logical data
```

### BaseTransport Interface

Abstract base class defining the transport API:

```python
class BaseTransport:
    def send(self, message):
        """Send a message over the transport."""
        
    def receive(self):
        """Receive a message if available (non-blocking)."""
        
    def clear_buffer(self):
        """Clear buffered data."""
```

### UARTTransport Implementation

Handles UART-specific concerns:

- Message formatting: `DEST|CMD|PAYLOAD|CRC\n`
- CRC-8 calculation and verification
- Line-based framing with newline termination
- Integration with UARTManager for buffered I/O

```python
from transport import UARTTransport
from managers import UARTManager

# Create UART transport
uart_hw = busio.UART(tx_pin, rx_pin, baudrate=115200)
uart_mgr = UARTManager(uart_hw)
transport = UARTTransport(uart_mgr)

# Send a message (CRC is handled transparently)
msg = Message("ALL", "ID_ASSIGN", "0100")
transport.send(msg)

# Receive messages (CRC verification is automatic)
msg = transport.receive()
if msg:
    print(f"Received: {msg.command}")
```

## Benefits

### 1. Separation of Concerns

- **CoreManager** focuses on game logic and satellite coordination
- **Transport** handles serialization, integrity checking, and physical I/O
- **UARTManager** handles low-level buffering and hardware access

### 2. Easy to Extend

Adding a new transport (e.g., I2C or CAN bus) only requires:

1. Implement `BaseTransport` interface
2. Handle transport-specific formatting and integrity checking
3. No changes to CoreManager or game logic

Example future I2C transport:

```python
class I2CTransport(BaseTransport):
    def send(self, message):
        # Format for I2C protocol
        # Different framing, different integrity check
        pass
    
    def receive(self):
        # Parse I2C packets
        pass
```

### 3. Testability

The transport layer can be tested independently with mock hardware:

```python
mock_uart = MockUARTManager()
transport = UARTTransport(mock_uart)

# Test message sending
msg = Message("0101", "LED", "ALL,255,0,0")
transport.send(msg)

# Verify packet format
assert mock_uart.sent_packets[0].decode() == "0101|LED|ALL,255,0,0|XX\n"
```

### 4. Backwards Compatibility

The wire protocol remains unchanged:
- Packets still use binary protocol with COBS framing
- CRC-8 calculation is identical
- Existing hardware works without modification

Only the software architecture has improved.

### 5. Race Condition Prevention

The queued mode eliminates UART race conditions in satellite firmware:

**Problem**: Multiple async tasks writing to UART concurrently can interleave packet bytes, causing:
- CRC failures (checksum calculated on incomplete packet)
- Protocol errors (malformed frames)
- Data corruption (mixed payload bytes from different messages)

**Solution**: Queued transport with dedicated TX worker:
- All `send()` calls and relay operations add data to a single queue
- One worker task serializes all writes to hardware
- Guarantees atomic packet transmission
- Minimal performance impact (queue operations are O(1) and async overhead is negligible)

This is critical for satellites that:
1. Send periodic status messages
2. Relay downstream messages
3. Send event-driven alerts (power, errors)
4. Forward commands downstream

Without queuing, these concurrent operations would corrupt the UART stream.

## Migration Guide

### Sending Messages

**Before:**
```python
from utilities import calculate_crc8

data = f"{sid}|LED|ALL,255,0,0"
crc = calculate_crc8(data)
self.uart.write(f"{data}|{crc}\n".encode())
```

**After:**
```python
from transport import Message

msg = Message(sid, "LED", "ALL,255,0,0")
self.transport.send(msg)
```

### Receiving Messages

**Before:**
```python
from utilities import verify_crc8

line = self.uart.read_line()
if line:
    is_valid, data = verify_crc8(line)
    if is_valid:
        parts = data.split("|", 2)
        sid, cmd, payload = parts[0], parts[1], parts[2]
        # Process command
```

**After:**
```python
msg = self.transport.receive()
if msg:
    # msg.destination, msg.command, msg.payload
    # CRC already verified
```

### Satellite Initialization

**Before:**
```python
from managers import UARTManager

uart_hw = busio.UART(tx, rx, baudrate=115200)
self.uart = UARTManager(uart_hw)
```

**After:**
```python
from managers import UARTManager
from transport import UARTTransport

uart_hw = busio.UART(tx, rx, baudrate=115200)
uart_mgr = UARTManager(uart_hw)
self.transport = UARTTransport(uart_mgr)
```

## Advanced Features

### Queued Mode

The UARTTransport supports a `queued` mode that prevents race conditions when multiple async tasks send messages concurrently:

```python
# Create a queued transport (recommended for upstream satellite communication)
transport = UARTTransport(uart_hw, command_map, dest_map, max_index_value, 
                          payload_schemas, queued=True)
```

In queued mode:
- All `send()` calls are non-blocking and add packets to an internal queue
- A dedicated `_tx_worker` task drains the queue to hardware
- Prevents interleaved packet writes that would corrupt CRC checksums
- Essential for satellites that both relay messages and send their own status

### Relay Functionality

The UARTTransport provides built-in relay capability for daisy-chained satellite networks:

```python
# Enable automatic data relay from downstream to upstream
transport_up.enable_relay_from(transport_down)
```

The relay feature:
- Runs an async `_relay_worker` task that continuously reads raw bytes
- Forwards data transparently without parsing (zero overhead)
- Integrates with queued mode automatically
- Allows satellites to pass through messages from downstream satellites

**Example Use Case**: Industrial Satellite 01 firmware

```python
# Create upstream transport with queued mode (prevents race conditions)
self.transport_up = UARTTransport(uart_up_hw, ..., queued=True)

# Create downstream transport (direct mode is fine)
self.transport_down = UARTTransport(uart_down_hw, ...)

# Enable relay - downstream messages automatically flow upstream
self.transport_up.enable_relay_from(self.transport_down)

# Now the satellite can:
# 1. Send its own status messages via transport_up.send()
# 2. Relay messages from downstream satellites automatically
# 3. No race conditions - all writes go through the queue
```

## Files Changed

### New Files
- `src/transport/__init__.py` - Transport package exports
- `src/transport/message.py` - Message class
- `src/transport/base_transport.py` - Transport interface
- `src/transport/uart_transport.py` - UART implementation with queued mode and relay
- `src/transport/ring_buffer.py` - Ring buffer utility for transport
- `tests/test_transport.py` - Transport layer tests
- `tests/test_uart_queue_race_condition.py` - Tests for queued mode and relay

### Modified Files
- `src/core/core_manager.py` - Uses transport layer
- `src/satellites/base.py` - Uses transport layer
- `src/satellites/sat_01_driver.py` - Uses transport layer
- `src/satellites/sat_01_firmware.py` - Uses transport layer with queued mode and relay

### Unchanged Files
- `src/utilities/crc.py` - Still provides CRC functions (used by transport)
- All game modes and UI code - Unaffected by changes

## Testing

All existing tests continue to pass:

```bash
# Transport layer tests
python3 tests/test_transport.py

# Transport consolidation tests (queued mode and relay)
python3 tests/test_uart_queue_race_condition.py

# CRC tests (ensures integrity checking still works)
python3 tests/test_crc.py
```

## Future Enhancements

Possible future transport implementations:

1. **I2CTransport** - For shorter-range, lower-speed satellite connections
2. **CANTransport** - For industrial environments with CAN bus
3. **MockTransport** - For unit testing without hardware
4. **LoggingTransport** - Wrapper that logs all messages for debugging

Each can be added without modifying CoreManager or game logic.
