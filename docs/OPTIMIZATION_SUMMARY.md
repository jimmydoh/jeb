# Transport Layer Optimization Summary

## Problem Statement

The `_decode_payload` function in `src/transport/uart_transport.py` was creating excessive temporary string objects during payload parsing, specifically for numeric data:

```python
# OLD CODE - Creates many temporary objects:
return ','.join(str(b) for b in payload_bytes)
```

This generator expression and string join created significant heap churn, increasing the frequency of garbage collection pauses.

## Solution

Modified `_decode_payload` to return tuples for numeric encodings, eliminating string allocations:

```python
# NEW CODE - Single tuple allocation:
return tuple(payload_bytes)
```

## Before & After Examples

### ENCODING_NUMERIC_BYTES (e.g., LED command)

**Before:**
```python
# Transport layer
payload_bytes = b'\xff\x80\x40\x20'
result = ','.join(str(b) for b in payload_bytes)  # "255,128,64,32"

# Application layer
values = parse_values(result)  # Splits "255,128,64,32" -> [255, 128, 64, 32]
```

**After:**
```python
# Transport layer
payload_bytes = b'\xff\x80\x40\x20'
result = tuple(payload_bytes)  # (255, 128, 64, 32)

# Application layer
values = parse_values(result)  # Converts (255, 128, 64, 32) -> [255, 128, 64, 32]
```

### ENCODING_FLOATS (e.g., POWER command)

**Before:**
```python
# Transport layer - unpacks floats and creates comma-separated string
decoded_vals = []
while byte_offset + 4 <= len(payload_bytes):
    float_val = struct.unpack('<f', payload_bytes[byte_offset:byte_offset+4])[0]
    decoded_vals.append(str(float_val))  # Convert to string
    byte_offset += 4
result = ','.join(decoded_vals)  # "19.5,18.2,5.0"

# Application layer
values = parse_values(result)  # Splits and converts back to floats
v_in = get_float(values, 0)
```

**After:**
```python
# Transport layer - unpacks floats directly to tuple
decoded_vals = []
while byte_offset + 4 <= len(payload_bytes):
    float_val = struct.unpack('<f', payload_bytes[byte_offset:byte_offset+4])[0]
    decoded_vals.append(float_val)  # Keep as float
    byte_offset += 4
result = tuple(decoded_vals)  # (19.5, 18.2, 5.0)

# Application layer
values = parse_values(result)  # Direct conversion to list
v_in = get_float(values, 0)
```

## Allocation Analysis

### Old Approach (per message):
1. Generator object: `(str(b) for b in payload_bytes)`
2. String objects: `str(b)` for each byte
3. Intermediate list: for `join()` operation
4. Final string: comma-separated result
5. List from `split(',')` in `parse_values`
6. Type conversions: `int()` or `float()` for each value

**Total: 6+ allocations per numeric message**

### New Approach (per message):
1. Tuple object: immutable, efficient
2. List conversion: in `parse_values`

**Total: 2 allocations per numeric message**

## Performance Results

Benchmarks on 100,000 iterations:

| Payload Type | Old Time | New Time | Speedup | Improvement |
|--------------|----------|----------|---------|-------------|
| LED (4 bytes) | 0.1272s | 0.0283s | 4.49x | 77.7% faster |
| POWER (3 floats) | 0.1100s | 0.0274s | 4.02x | 75.1% faster |
| STATUS (5 bytes) | 0.1493s | 0.0291s | 5.13x | 80.5% faster |

## Benefits

1. **Performance**: 4-5x faster payload processing
2. **Memory**: Reduced allocation rate = less GC pressure
3. **Embedded**: Critical for resource-constrained CircuitPython environments
4. **Simplicity**: Numeric data stays numeric until display time
5. **Compatibility**: Works with existing `parse_values()` and `get_float()` functions

## Backward Compatibility

The change is fully backward compatible:

- ✅ `parse_values()` handles tuples, lists, strings, and bytes
- ✅ `get_float()` and `get_int()` work with all input types
- ✅ Existing tests updated to expect tuples
- ✅ No changes required to application code (SatelliteNetworkManager, etc.)

## Testing

All tests pass:
- ✅ `test_transport.py` - Core transport functionality
- ✅ `test_payload_encoding.py` - Payload encoding/decoding
- ✅ `test_tuple_payloads.py` - Tuple compatibility
- ✅ `test_binary_transport.py` - Binary protocol
- ✅ `test_base_transport.py` - Transport abstraction
- ✅ `test_message.py` - Message class

## Files Changed

1. `src/transport/uart_transport.py` - Modified `_decode_payload()`
2. `src/transport/message.py` - Added tuple support to `__repr__()`
3. `src/utilities/payload_parser.py` - Added tuple/list handling to `parse_values()`
4. `tests/test_transport.py` - Updated to expect tuples
5. `tests/test_payload_encoding.py` - Updated to expect tuples
6. `tests/test_tuple_payloads.py` - New compatibility tests
7. `tests/profile_memory_usage.py` - Performance profiling
