# File: src/utilities/crc.py
"""CRC calculation utilities for JADNET protocol."""

def calculate_crc16(data):
    """
    Calculate CRC16-CCITT checksum for the given data.
    
    Parameters:
        data (str): The data string to calculate CRC for.
        
    Returns:
        str: 4-character hexadecimal string representation of CRC16.
    """
    crc = 0xFFFF
    polynomial = 0x1021
    
    for byte in data.encode():
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ polynomial
            else:
                crc = crc << 1
            crc &= 0xFFFF
    
    return f"{crc:04X}"


def verify_crc16(data_with_crc):
    """
    Verify CRC16 checksum for a data string with CRC appended.
    
    Parameters:
        data_with_crc (str): The data string with CRC appended (format: data|CRC).
        
    Returns:
        tuple: (bool, str) - (is_valid, data_without_crc)
               is_valid: True if CRC is valid, False otherwise
               data_without_crc: The data string without the CRC
    """
    parts = data_with_crc.rsplit("|", 1)
    if len(parts) != 2:
        return False, data_with_crc
    
    data, received_crc = parts
    calculated_crc = calculate_crc16(data)
    
    return calculated_crc == received_crc, data
