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
- Packets still use `DEST|CMD|PAYLOAD|CRC\n` format
- CRC-8 calculation is identical
- Existing hardware works without modification

Only the software architecture has improved.

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

## Files Changed

### New Files
- `src/transport/__init__.py` - Transport package exports
- `src/transport/message.py` - Message class
- `src/transport/base_transport.py` - Transport interface
- `src/transport/uart_transport.py` - UART implementation
- `tests/test_transport.py` - Transport layer tests

### Modified Files
- `src/core/core_manager.py` - Uses transport layer
- `src/satellites/base.py` - Uses transport layer
- `src/satellites/sat_01_driver.py` - Uses transport layer
- `src/satellites/sat_01_firmware.py` - Uses transport layer

### Unchanged Files
- `src/utilities/crc.py` - Still provides CRC functions (used by transport)
- `src/managers/uart_manager.py` - Still provides buffering (used by transport)
- All game modes and UI code - Unaffected by changes

## Testing

All existing tests continue to pass:

```bash
# Transport layer tests
python3 tests/test_transport.py

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
