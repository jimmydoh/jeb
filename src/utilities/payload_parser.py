# File: src/utilities/payload_parser.py
"""Payload parsing utilities for binary and text protocols."""

import struct


def parse_values(payload):
    """Parse payload into typed values, handling multiple input formats.
    
    This function works with both text-based and binary protocols:
    - For strings: Parses comma-separated values like "100,200,50"
    - For bytes: Unpacks binary data as unsigned bytes
    - For tuples/lists: Returns as-is (optimization from transport layer)
    
    Parameters:
        payload (str, bytes, tuple, or list): Payload in various formats
        
    Returns:
        list: List of parsed values (int or float)
        
    Example:
        >>> parse_values("100,200,50")
        [100, 200, 50]
        >>> parse_values(b'\\x64\\xc8\\x32')  # bytes: 100, 200, 50
        [100, 200, 50]
        >>> parse_values((100, 200, 50))  # tuple from optimized transport
        [100, 200, 50]
        >>> parse_values("")
        []
    """
    if not payload:
        return []
    
    # Handle tuple/list payloads (optimization: already parsed by transport layer)
    if isinstance(payload, (tuple, list)):
        return list(payload)
    
    # Handle binary payloads
    if isinstance(payload, bytes):
        # Unpack as unsigned bytes (each byte becomes an integer 0-255)
        return list(payload)
    
    # Handle string payloads
    values = []
    for part in payload.split(','):
        part = part.strip()
        if not part:
            continue
        
        # Try integer first
        try:
            values.append(int(part))
            continue
        except ValueError:
            pass
        
        # Try float
        try:
            values.append(float(part))
            continue
        except ValueError:
            pass
        
        # Keep as string if not numeric
        values.append(part)
    
    return values


def unpack_bytes(payload_bytes, format_string='B'):
    """Unpack binary payload using struct format string for high-speed decoding.
    
    This provides direct struct.unpack access for maximum performance when
    dealing with binary payloads.
    
    Parameters:
        payload_bytes (bytes): Binary payload data
        format_string (str): struct format string (default: 'B' for a single unsigned byte)
            Note: Default 'B' unpacks only ONE byte. For multiple bytes, specify the
            complete format (e.g., 'BBB' for 3 bytes, '<HH' for 2 shorts, etc.)
            
            Common formats:
            - 'B': unsigned byte (0-255)
            - 'b': signed byte (-128-127)
            - '<H': little-endian unsigned short (0-65535)
            - '<h': little-endian signed short (-32768-32767)
            - '<I': little-endian unsigned int (0-4294967295)
            - '<i': little-endian signed int
            - '<f': little-endian float (IEEE 754)
            
    Returns:
        tuple: Unpacked values
        
    Raises:
        struct.error: If the format string doesn't match the data size
        
    Example:
        >>> unpack_bytes(b'\\x64', 'B')  # Single byte
        (100,)
        >>> unpack_bytes(b'\\x64\\xc8', 'BB')  # Two bytes
        (100, 200)
        >>> unpack_bytes(b'\\x00\\x01\\x00\\x02', '<HH')  # Two little-endian shorts
        (256, 512)
    """
    if not payload_bytes:
        return ()
    
    return struct.unpack(format_string, payload_bytes)


def get_int(values, index, default=0):
    """Safely get integer value from list.
    
    Parameters:
        values (list): List of values
        index (int): Index to retrieve
        default: Default value if index out of range
        
    Returns:
        int: Value at index or default
    """
    if index < len(values):
        val = values[index]
        if isinstance(val, (int, float)):
            return int(val)
    return default


def get_float(values, index, default=0.0):
    """Safely get float value from list.
    
    Parameters:
        values (list): List of values
        index (int): Index to retrieve
        default: Default value if index out of range
        
    Returns:
        float: Value at index or default
    """
    if index < len(values):
        val = values[index]
        if isinstance(val, (int, float)):
            return float(val)
    return default


def get_str(values, index, default=""):
    """Safely get string value from list.
    
    Parameters:
        values (list): List of values
        index (int): Index to retrieve
        default: Default value if index out of range
        
    Returns:
        str: Value at index or default
    """
    if index < len(values):
        return str(values[index])
    return default
