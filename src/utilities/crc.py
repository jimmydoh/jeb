# File: src/utilities/crc.py
"""CRC-8 utility for UART packet integrity checking."""


def calculate_crc8(data):
    """Calculate CRC-8 checksum for a given string.
    
    Uses CRC-8-CCITT polynomial (0x07) for error detection in UART packets.
    
    Parameters:
        data (str): The data string to calculate CRC for (e.g., "ID|CMD|VAL").
        
    Returns:
        str: Two-character hexadecimal CRC value (e.g., "A3").
    """
    crc = 0x00
    polynomial = 0x07
    
    for byte in data.encode('utf-8'):
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = (crc << 1) ^ polynomial
            else:
                crc <<= 1
            crc &= 0xFF
    
    return f"{crc:02X}"


def verify_crc8(packet):
    """Verify CRC-8 checksum of a received packet.
    
    Parameters:
        packet (str): Complete packet with CRC (e.g., "ID|CMD|VAL|A3").
        
    Returns:
        tuple: (is_valid: bool, data: str) where data is the packet without CRC.
    """
    parts = packet.rsplit("|", 1)
    if len(parts) != 2:
        return False, None
    
    data, received_crc = parts
    calculated_crc = calculate_crc8(data)
    
    return calculated_crc == received_crc, data
