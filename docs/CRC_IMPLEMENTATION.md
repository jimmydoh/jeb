# JADNET Protocol CRC Implementation

## Overview

The JADNET protocol has been updated to include CRC16-CCITT checksums for data integrity verification. This protects against noise and corruption on the RJ45 UART lines.

## Packet Format

### Before (No Error Checking)
```
ID|CMD|VAL\n
```

### After (With CRC)
```
ID|CMD|VAL|CRC\n
```

Where:
- `ID`: Satellite ID
  - Assigned IDs: "01", "02", "03", etc.
  - Broadcast: "ALL"
  - Discovery placeholder: "??" (used before ID assignment)
- `CMD`: Command type (e.g., "STATUS", "LED", "POWER", "ID_ASSIGN")
- `VAL`: Command value/payload
- `CRC`: 4-character hexadecimal CRC16-CCITT checksum
- `\n`: Newline terminator

## Examples

### Valid Packets with CRC
```
ALL|ID_ASSIGN|0100|A7D4
01|LED|ALL,255,0,0|C58A
01|STATUS|encoder1:5,encoder2:3|D0C8
01|POWER|12.5,12.3,5.0|0E9F
??|NEW_SAT|01|<CRC>
```

### Corrupted Packets (Discarded)
```
01|LED|ALL,255,1,0|C58A  # Data corrupted, CRC invalid
01|LED|ALL,255,0,0|FFFF  # CRC corrupted
ALL|ID_ASSIGN|0100       # Missing CRC
```

## Implementation Details

### CRC Algorithm
- **Algorithm**: CRC16-CCITT
- **Polynomial**: 0x1021
- **Initial Value**: 0xFFFF
- **Output Format**: 4-digit uppercase hexadecimal (e.g., "A7D4")

### Sending Packets
Use the provided helper functions to automatically calculate and append CRC:

**Base Satellite Class** (`src/satellites/base.py`):
```python
satellite.send_cmd("LED", "ALL,255,0,0")
# Sends: 01|LED|ALL,255,0,0|C58A\n
```

**Industrial Satellite** (`src/satellites/sat_01_industrial.py`):
```python
self.send_upstream(f"{self.id}|STATUS|{data}")
self.send_downstream(f"ALL|ID_ASSIGN|{val}")
```

**Core Manager** (`src/core/core_manager.py`):
```python
packet_data = "ALL|ID_ASSIGN|0100"
crc = calculate_crc16(packet_data)
self.uart.write(f"{packet_data}|{crc}\n".encode())
```

### Receiving Packets
The `handle_packet()` method in `core_manager.py` and the RX loop in `sat_01_industrial.py` automatically verify CRC on all incoming packets:

```python
# Verify CRC first
is_valid, data_without_crc = verify_crc16(line)
if not is_valid:
    # Discard corrupted packet
    print(f"CRC FAILED: Corrupted packet discarded: {line}")
    return

# Process valid packet
parts = data_without_crc.split("|", 2)
sid, cmd, payload = parts[0], parts[1], parts[2]
# ... handle command
```

### Error Handling
- **Invalid CRC**: Packet is discarded, error message printed to console
- **Missing CRC**: Packet is treated as invalid and discarded
- **Malformed packets**: Packets without proper structure are discarded

## Testing

Run the CRC test suite to verify implementation:

```bash
python3 tests/test_crc.py
```

The test suite includes:
- CRC calculation correctness
- CRC verification for valid packets
- Detection of corrupted data
- Detection of corrupted CRC
- Noise simulation
- Real protocol examples

## Files Modified

1. **src/utilities/crc.py** (new)
   - `calculate_crc16(data)`: Calculate CRC for data string
   - `verify_crc16(data_with_crc)`: Verify and extract data from packet with CRC

2. **src/utilities/__init__.py**
   - Export CRC functions

3. **src/satellites/base.py**
   - Updated `send_cmd()` to append CRC

4. **src/core/core_manager.py**
   - Import CRC functions
   - Updated `discover_satellites()` to send CRC
   - Updated `handle_packet()` to verify CRC
   - Updated NEW_SAT command handler to send CRC

5. **src/satellites/sat_01_industrial.py**
   - Import CRC functions
   - Added `send_upstream()` and `send_downstream()` helper methods
   - Updated all UART write operations to include CRC
   - Updated RX loop to verify incoming CRC
   - Fixed NEW_SAT packet format to include proper ID field

6. **tests/test_crc.py** (new)
   - Comprehensive test suite for CRC implementation

## Benefits

1. **Data Integrity**: Detects single and multi-bit errors in transmitted data
2. **Noise Rejection**: Automatically discards corrupted packets due to RJ45 line noise
3. **Reliability**: Prevents processing of corrupted commands that could cause unexpected behavior
4. **Debugging**: Clear console messages when packets are discarded due to CRC failures

## Backward Compatibility

**This is a breaking change.** All devices in the JADNET system must be updated simultaneously:
- Core controller
- All satellite boxes

Devices with old firmware (without CRC) will have their packets rejected by devices with new firmware (with CRC), and vice versa.
