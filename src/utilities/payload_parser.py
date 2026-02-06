# File: src/utilities/payload_parser.py
"""Payload parsing utilities for binary and text protocols."""

import struct


def parse_values(payload_str):
    """Parse comma-separated payload string into typed values.
    
    This is a compatibility function that works with both text-based
    and binary protocols. It parses strings like "100,200,50" into
    a list of integers/floats.
    
    Parameters:
        payload_str (str): Comma-separated values or empty string
        
    Returns:
        list: List of parsed values (int or float)
        
    Example:
        >>> parse_values("100,200,50")
        [100, 200, 50]
        >>> parse_values("1.5,2.0")
        [1.5, 2.0]
        >>> parse_values("")
        []
    """
    if not payload_str:
        return []
    
    values = []
    for part in payload_str.split(','):
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
