# File: src/utilities/crc.py
"""CRC-8 utility for UART packet integrity checking."""


def _build_crc_table():
    """Build CRC-8 lookup table at module initialization.
    
    Generates all 256 possible CRC values for byte inputs 0x00-0xFF
    using the CRC-8-CCITT polynomial (0x07). This table is computed
    once and reused for all subsequent CRC calculations.
    
    Returns:
        tuple: 256-element tuple of pre-calculated CRC values.
    """
    poly = 0x07
    table = []
    
    for byte_val in range(256):
        crc_val = byte_val
        for _ in range(8):
            if crc_val & 0x80:
                crc_val = (crc_val << 1) ^ poly
            else:
                crc_val <<= 1
            crc_val &= 0xFF
        table.append(crc_val)
    
    return tuple(table)


# Generate lookup table once at module load time
_CRC_TABLE = _build_crc_table()


def calculate_crc8(data):
    """Calculate CRC-8 checksum for a given string or bytes using lookup table.
    
    Uses CRC-8-CCITT polynomial (0x07) for error detection in UART packets.
    Optimized with pre-calculated lookup table for ~10x performance improvement.
    
    Parameters:
        data (str or bytes): The data to calculate CRC for (e.g., b"ID|CMD|VAL" or "ID|CMD|VAL").
        
    Returns:
        bytes: Two-byte hexadecimal CRC value (e.g., b"A3").
    """
    crc = 0x00
    
    # Handle both str and bytes input
    if isinstance(data, str):
        data = data.encode('utf-8')
    
    for byte in data:
        crc = _CRC_TABLE[crc ^ byte]
    
    return f"{crc:02X}".encode('ascii')


def verify_crc8(packet):
    """Verify CRC-8 checksum of a received packet.
    
    Parameters:
        packet (str or bytes): Complete packet with CRC (e.g., b"ID|CMD|VAL|A3" or "ID|CMD|VAL|A3").
        
    Returns:
        tuple: (is_valid: bool, data: bytes or str) where data is the packet without CRC.
    """
    # Handle both str and bytes input
    if isinstance(packet, str):
        separator = "|"
    else:
        separator = b"|"
    
    parts = packet.rsplit(separator, 1)
    if len(parts) != 2:
        return False, None
    
    data, received_crc = parts
    calculated_crc = calculate_crc8(data)
    
    # Compare CRCs (handle type mismatch)
    if isinstance(received_crc, str):
        # Decode bytes CRC for comparison with string CRC
        calculated_crc = calculated_crc.decode('ascii')
    
    return calculated_crc == received_crc, data
