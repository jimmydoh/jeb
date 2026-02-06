# File: src/utilities/cobs.py
"""COBS (Consistent Overhead Byte Stuffing) encoding for binary protocol framing.

COBS is a framing algorithm that encodes data to eliminate a specific byte value
(typically 0x00) from the encoded output. This allows us to use 0x00 as a reliable
packet delimiter/terminator instead of newline characters.

Benefits:
- Binary data safe (no newline or special character conflicts)
- Efficient (max 0.4% overhead for random data)
- Zero parsing overhead (direct byte access)
- Deterministic framing with 0x00 terminator

References:
- Original paper: Cheshire and Baker (1997)
- Wikipedia: https://en.wikipedia.org/wiki/Consistent_Overhead_Byte_Stuffing
"""


def cobs_encode(data):
    """Encode data using COBS algorithm.
    
    Removes all 0x00 bytes from data and replaces them with a special
    encoding that allows the original data to be recovered. The encoded
    data will never contain 0x00 bytes, making 0x00 safe to use as a
    packet delimiter.
    
    Parameters:
        data (bytes): Raw data to encode (may contain 0x00 bytes).
        
    Returns:
        bytes: COBS-encoded data (no 0x00 bytes present).
        
    Example:
        >>> cobs_encode(b'\\x00')
        b'\\x01\\x01'
        >>> cobs_encode(b'\\x01\\x02\\x03')
        b'\\x04\\x01\\x02\\x03'
        >>> cobs_encode(b'\\x01\\x00\\x02')
        b'\\x02\\x01\\x02\\x02'
    """
    if not data:
        return b'\x01'
    
    output = bytearray()
    code_idx = 0
    code = 0x01
    
    output.append(0)  # Placeholder for first code byte
    
    for byte in data:
        if byte == 0x00:
            # Found a zero - write the distance code and reset
            output[code_idx] = code
            code_idx = len(output)
            output.append(0)  # Placeholder for next code byte
            code = 0x01
        else:
            # Non-zero byte - add it and increment code
            output.append(byte)
            code += 1
            
            # If we've run 254 bytes without a zero, need to insert a code
            if code == 0xFF:
                output[code_idx] = code
                code_idx = len(output)
                output.append(0)
                code = 0x01
    
    # Write final code byte
    output[code_idx] = code
    
    return bytes(output)


def cobs_decode(data):
    """Decode COBS-encoded data back to original format.
    
    Reverses the COBS encoding process to restore the original data,
    including any 0x00 bytes that were present.
    
    Parameters:
        data (bytes): COBS-encoded data (no 0x00 bytes).
        
    Returns:
        bytes: Decoded original data (may contain 0x00 bytes).
        
    Raises:
        ValueError: If data is malformed or invalid COBS encoding.
        
    Example:
        >>> cobs_decode(b'\\x01\\x01')
        b'\\x00'
        >>> cobs_decode(b'\\x04\\x01\\x02\\x03')
        b'\\x01\\x02\\x03'
        >>> cobs_decode(b'\\x02\\x01\\x02\\x02')
        b'\\x01\\x00\\x02'
    """
    if not data:
        raise ValueError("Cannot decode empty data")
    
    # Check for any 0x00 bytes in encoded data (invalid)
    if b'\x00' in data:
        idx = data.index(b'\x00')
        raise ValueError(f"Invalid COBS encoding: found 0x00 at position {idx}")
    
    if data == b'\x01':
        return b''
    
    output = bytearray()
    idx = 0
    
    while idx < len(data):
        code = data[idx]
        idx += 1
        
        # Copy the next (code-1) bytes
        for _ in range(code - 1):
            if idx >= len(data):
                raise ValueError("Invalid COBS encoding: unexpected end of data")
            output.append(data[idx])
            idx += 1
        
        # Add a zero if this wasn't the last block
        if code < 0xFF and idx < len(data):
            output.append(0x00)
    
    return bytes(output)
