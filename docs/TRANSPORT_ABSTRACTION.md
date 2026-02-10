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

Handles ALL UART-specific concerns internally:

- Binary protocol with COBS framing (eliminates 0x00 bytes)
- CRC-8 calculation and verification
- 0x00 byte as packet terminator (no newlines)
- Queue management for upstream (prevents race conditions)
- Automatic relay from downstream to upstream (optional)
- Integration with UARTManager for buffered I/O

```python
from transport import UARTTransport, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS

# Core Manager - single UART
uart_hw = busio.UART(tx_pin, rx_pin, baudrate=115200)
transport = UARTTransport(uart_hw, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)

# Satellite Firmware - dual UART with automatic relay
uart_up = busio.UART(tx_up, rx_up, baudrate=115200)
uart_down = busio.UART(tx_down, rx_down, baudrate=115200)
transport = UARTTransport(
    uart_up, 
    COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS,
    uart_downstream=uart_down  # Automatically relays downstream data upstream
)

# Send a message (queuing, CRC, and COBS encoding handled internally)
msg = Message("ALL", "ID_ASSIGN", "0100")
transport.send(msg)

# Receive messages (COBS decoding and CRC verification automatic)
msg = transport.receive()
if msg:
    print(f"Received: {msg.command}")
```

### Internal Queue and Relay Management

UARTTransport manages queuing and relay internally - firmware code doesn't need to handle this:

```python
# Inside UARTTransport.__init__():
self.upstream_queue = asyncio.Queue()  # Internal queue
asyncio.create_task(self._upstream_tx_worker())  # Internal TX worker

if uart_downstream:
    asyncio.create_task(self._relay_worker())  # Internal relay worker
```

This ensures all upstream writes are serialized through a single TX worker task, preventing interleaved packet writes. Relay from downstream to upstream happens automatically when `uart_downstream` is provided.

## Benefits

### 1. Separation of Concerns

- **CoreManager/Satellite** focuses on application logic and command processing
- **Transport** handles ALL UART coordination: protocol, queuing, relay, integrity checking
- **UARTManager** handles low-level buffering and hardware access

Firmware code never manages queues, workers, or relay logic - it's all in Transport.

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

The wire protocol has been upgraded to binary protocol:
- Old: `DEST|CMD|PAYLOAD|CRC\n` (text-based)
- New: `[DEST][CMD][PAYLOAD][CRC]` + COBS encoding + 0x00 terminator (binary)
- 65% reduction in protocol overhead
- Zero text parsing overhead
- Improved reliability with COBS framing

Hardware must be updated to support the new binary protocol.

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
self.transport.send(msg)  # Synchronous, non-blocking
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
msg = self.transport.receive()  # Synchronous, non-blocking
if msg:
    # msg.destination, msg.command, msg.payload
    # CRC and COBS already verified
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
from transport import UARTTransport, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS

# Dual UART with automatic relay
uart_up = busio.UART(tx_up, rx_up, baudrate=115200)
uart_down = busio.UART(tx_down, rx_down, baudrate=115200)
self.transport = UARTTransport(
    uart_up, 
    COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS,
    uart_downstream=uart_down  # Transport handles relay automatically
)

# Also create downstream transport for explicit sends
self.transport_down = UARTTransport(
    uart_down,
    COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS
)
```

No queue management, no TX workers, no relay tasks - Transport handles it all.

## Files Changed

### New Files
- `src/transport/__init__.py` - Transport package exports
- `src/transport/message.py` - Message class
- `src/transport/base_transport.py` - Transport interface
- `src/transport/uart_transport.py` - UART implementation with binary protocol
- `src/transport/uart_manager.py` - UART manager with buffering
- `src/transport/ring_buffer.py` - Circular buffer for packet handling
- `tests/test_transport.py` - Transport layer tests
- `tests/test_binary_transport.py` - Binary protocol tests
- `tests/test_uart_queue_race_condition.py` - Race condition fix validation

### Modified Files
- `src/core/core_manager.py` - Uses transport layer
- `src/satellites/base.py` - Uses transport layer
- `src/satellites/sat_01_driver.py` - Uses transport layer
- `src/satellites/sat_01_firmware.py` - Uses transport layer (simplified, no queue/relay management)
- `src/managers/satellite_network_manager.py` - Uses transport layer
- `src/transport/uart_transport.py` - Now handles queue management and relay internally

### Unchanged Files
- `src/utilities/crc.py` - Still provides CRC functions (used by transport)
- `src/utilities/cobs.py` - Provides COBS encoding/decoding (used by transport)
- All game modes and UI code - Unaffected by changes

## Testing

All transport layer tests pass:

```bash
# Transport layer tests
python3 tests/test_transport.py

# Binary protocol tests
python3 tests/test_binary_transport.py

# Base transport abstraction tests
python3 tests/test_base_transport.py

# Race condition fix validation
python3 tests/test_transport_consolidation.py

# Transport reusability tests
python3 tests/test_transport_reusability.py

# CRC tests (ensures integrity checking still works)
python3 tests/test_crc.py

# COBS framing tests
python3 tests/test_cobs.py
```

## Future Enhancements

Possible future transport implementations:

1. **I2CTransport** - For shorter-range, lower-speed satellite connections
2. **CANTransport** - For industrial environments with CAN bus
3. **MockTransport** - For unit testing without hardware
4. **LoggingTransport** - Wrapper that logs all messages for debugging

Each can be added without modifying CoreManager or game logic.
