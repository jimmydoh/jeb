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
