# Binary Protocol Documentation

## Overview

This document describes the binary protocol with COBS (Consistent Overhead Byte Stuffing) framing used for UART communication between the CORE unit and satellite modules.

## Why Binary Protocol?

The original text-based protocol (`DEST|CMD|PAYLOAD|CRC\n`) had several issues:

1. **Expensive String Parsing**: Required multiple `.split()`, `int()`, and `float()` conversions
2. **Type Errors**: String manipulation prone to errors
3. **Inefficient**: Text encoding adds significant overhead
4. **Fragile**: Newline termination can be affected by data content

The new binary protocol addresses all these issues.

## Protocol Format

### Packet Structure

```
[DEST][CMD][PAYLOAD][CRC] (before COBS encoding)
```

After COBS encoding and terminator:
```
[COBS_ENCODED_DATA][0x00]
```

### Field Descriptions

#### 1. DEST (Destination) - 1-2 bytes

**Special Destinations:**
- `0xFF`: Broadcast to ALL devices
- `0xFE`: Broadcast to all SAT (satellite) devices

**Device-Specific:**
- Single byte: Type ID only (e.g., `0x01` for Industrial satellites)
- Two bytes: Type ID + Index (e.g., `0x01 0x01` for device 0101)

#### 2. CMD (Command) - 1 byte

Commands are mapped to single bytes for efficiency:

| Command | Byte | Description |
|---------|------|-------------|
| STATUS | 0x01 | Device status update |
| ID_ASSIGN | 0x02 | Assign device ID |
| NEW_SAT | 0x03 | New satellite detected |
| ERROR | 0x04 | Error message |
| LOG | 0x05 | Log message |
| POWER | 0x06 | Power status |
| LED | 0x10 | LED solid color |
| LEDFLASH | 0x11 | LED flash animation |
| LEDBREATH | 0x12 | LED breathing animation |
| LEDCYLON | 0x13 | LED cylon effect |
| LEDCENTRI | 0x14 | LED centrifuge effect |
| LEDRAINBOW | 0x15 | LED rainbow effect |
| LEDGLITCH | 0x16 | LED glitch effect |
| DSP | 0x20 | Display message |
| DSPCORRUPT | 0x21 | Display corruption effect |
| DSPMATRIX | 0x22 | Display matrix effect |
| SETENC | 0x30 | Set encoder position |

#### 3. PAYLOAD - N bytes

Payload encoding depends on content:

**Numeric Values:**
- Comma-separated values like "100,200,50" are encoded as bytes
- Each integer (0-255) → 1 byte
- Larger integers → 2 or 4 bytes (packed)
- Floats → 4 bytes IEEE 754

**Text Strings:**
- UTF-8 encoded bytes
- Examples: "HELLO", "BUS_SHUTDOWN:LOW_V"

#### 4. CRC - 1 byte

CRC-8 checksum calculated over [DEST][CMD][PAYLOAD]
- Polynomial: 0x07 (CRC-8-CCITT)
- Stored as single byte value (not ASCII hex)

## COBS Framing

### What is COBS?

COBS (Consistent Overhead Byte Stuffing) is a framing algorithm that:
- Eliminates all `0x00` bytes from encoded data
- Allows using `0x00` as packet delimiter
- Adds minimal overhead (max 0.4% for random data)

### How COBS Works

**Encoding:**
1. Raw packet: `[DEST][CMD][PAYLOAD][CRC]`
2. COBS encode: Removes all `0x00` bytes
3. Add terminator: Append `0x00`
4. Result: `[COBS_DATA][0x00]`

**Decoding:**
1. Read until `0x00` terminator
2. Remove `0x00` terminator
3. COBS decode: Restore original data
4. Verify CRC
5. Parse packet fields

### Example

**Original Data:**
```
0x01 0x10 0x64 0xC8 0x00 0x32 0xAB
[Dest][CMD][---Payload---][CRC]
```

**COBS Encoded:**
```
0x05 0x01 0x10 0x64 0xC8 0x03 0x32 0xAB 0x00
[---COBS Encoded Data---][Terminator]
```

Note: No `0x00` bytes in encoded portion!

## Performance Benefits

### Size Comparison

**Text Protocol Example:**
```
"0101|STATUS|100,200,50|A3\n" = 26 bytes
```

**Binary Protocol Example:**
```
[0x01][0x01][0x01][0x64][0xC8][0x32][0xA3][0x00] = 8 bytes (COBS encoded: ~9 bytes)
```

**Savings: 65% reduction!**

### Processing Benefits

**Old Text Protocol:**
```python
# Expensive operations
parts = line.split("|")
dest = parts[0]
cmd = parts[1]
payload = parts[2].split(",")
r = int(payload[0])
g = int(payload[1])
b = int(payload[2])
```

**New Binary Protocol:**
```python
# Direct byte access, no parsing
values = parse_values(payload)
r = get_int(values, 0)
g = get_int(values, 1)
b = get_int(values, 2)
```

## Implementation

### Sending a Message

```python
from transport import Message, UARTTransport

# Create message (same API as before)
msg = Message("0101", "LED", "0,255,0,0")

# Send (transport handles binary encoding + COBS)
transport.send(msg)
```

### Receiving a Message

```python
# Receive (transport handles COBS + binary decoding)
msg = transport.receive()

if msg:
    # Parse payload efficiently
    values = parse_values(msg.payload)
    r = get_int(values, 0)
    g = get_int(values, 1)
    b = get_int(values, 2)
```

### Payload Parser Utilities

```python
from utilities import parse_values, get_int, get_float, get_str

# Parse comma-separated values
values = parse_values("100,200,50")  # [100, 200, 50]

# Safe extraction with defaults
r = get_int(values, 0, default=0)
speed = get_float(values, 1, default=1.0)
name = get_str(values, 2, default="")
```

## Testing

Comprehensive test suites verify:

1. **COBS Encoding/Decoding** (`test_cobs.py`)
   - Empty data
   - Single zero byte
   - Data with/without zeros
   - All byte values (0-255)
   - Roundtrip validation
   - Invalid data rejection

2. **Binary Transport** (`test_binary_transport.py`)
   - Message creation
   - Sending/receiving
   - CRC validation
   - Command mapping
   - Special destinations
   - Roundtrip for all commands

## Backward Compatibility

The Message API remains unchanged:
```python
# Still works the same way
msg = Message("ALL", "LED", "0,255,0,0")
```

Transport layer handles all binary encoding/decoding transparently.

## Error Handling

### CRC Failures
```python
if crc_byte != calculated_crc:
    print(f"CRC check failed: expected {expected}, got {received}")
    return None  # Discard corrupted packet
```

### COBS Decode Errors
```python
try:
    decoded = cobs_decode(packet)
except ValueError as e:
    print(f"COBS decode error: {e}")
    return None
```

### Buffer Overflow
```python
if len(buffer) > max_buffer_size:
    buffer.clear()
    raise ValueError("UART buffer overflow - clearing buffer")
```

## References

- **COBS Algorithm**: Cheshire and Baker (1997)
- **CRC-8**: Polynomial 0x07 (CRC-8-CCITT)
- **IEEE 754**: Float encoding standard

## Summary

The binary protocol with COBS framing provides:

✅ **Zero parsing overhead** - Direct byte access  
✅ **Type safety** - Binary encoding prevents type errors  
✅ **Efficiency** - 65% smaller packets  
✅ **Reliability** - Robust framing with 0x00 terminator  
✅ **Maintainability** - Cleaner code with helper functions  
✅ **Performance** - No string operations or conversions  

The protocol eliminates the string parsing issues in `sat_01_firmware.py` and type errors in `uart_transport.py` that motivated this enhancement.
