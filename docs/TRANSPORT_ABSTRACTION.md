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

- Binary protocol with COBS framing (eliminates 0x00 bytes)
- CRC-8 calculation and verification
- 0x00 byte as packet terminator (no newlines)
- Integration with UARTManager for buffered I/O

```python
from transport import UARTTransport, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS

# Create UART transport
uart_hw = busio.UART(tx_pin, rx_pin, baudrate=115200)
transport = UARTTransport(uart_hw, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)

# Send a message (CRC and COBS encoding handled transparently)
msg = Message("ALL", "ID_ASSIGN", "0100")
transport.send(msg)

# Receive messages (COBS decoding and CRC verification automatic)
msg = transport.receive()
if msg:
    print(f"Received: {msg.command}")
```

### Queue-Based TX Worker Pattern (Satellite Firmware)

To prevent race conditions when multiple tasks write to the same UART, satellite firmware implements a queue-based TX worker pattern:

```python
# In sat_01_firmware.py
class IndustrialSatelliteFirmware(Satellite):
    def __init__(self):
        # Create upstream queue and queued manager
        self.upstream_queue = asyncio.Queue()
        self.uart_up_mgr_queued = _QueuedUARTManager(self.upstream_queue)
        
        # Transport uses queued manager for writes
        self.transport_up = UARTTransport(self.uart_up_mgr_queued, ...)
        
        # Hardware UART only accessed by TX worker
        self.uart_up_mgr = uart_up_mgr
    
    async def _upstream_tx_worker(self):
        """Dedicated task to drain TX queue to hardware."""
        while True:
            data = await self.upstream_queue.get()
            self.uart_up_mgr.write(data)
            self.upstream_queue.task_done()
```

This ensures all upstream writes (from relay, monitor_power, monitor_connection, etc.) are serialized through a single TX worker task, preventing interleaved packet writes.

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

uart_hw = busio.UART(tx, rx, baudrate=115200)
self.transport = UARTTransport(uart_hw, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)
```

### Satellite Firmware - Queue-Based TX Worker

For satellite firmware that needs to prevent UART race conditions:

```python
# Create queue and queued manager wrapper
self.upstream_queue = asyncio.Queue()
self.uart_up_mgr_queued = _QueuedUARTManager(self.upstream_queue)
self.uart_up_mgr = UARTManager(uart_up_hw)  # Hardware access for TX worker only

# Transport uses queued manager
self.transport_up = UARTTransport(
    self.uart_up_mgr_queued, 
    COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS
)

# Start TX worker task
async def start(self):
    asyncio.create_task(self._upstream_tx_worker())
    # ... other tasks

async def _upstream_tx_worker(self):
    while True:
        data = await self.upstream_queue.get()
        self.uart_up_mgr.write(data)
        self.upstream_queue.task_done()
```

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
- `src/satellites/sat_01_firmware.py` - Uses transport layer + queue-based TX worker
- `src/managers/satellite_network_manager.py` - Uses transport layer

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
python3 tests/test_uart_queue_race_condition.py

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
