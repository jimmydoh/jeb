"""Protocol definitions for JEB communication system.

This module defines the command codes and destination IDs used in the
binary protocol. These are application-specific constants that can be
used by both the transport layer and higher-level components.

By centralizing these definitions here, the transport layer remains
reusable for other projects while applications can inject their specific
command sets.
"""

# Command string to byte mapping
COMMAND_MAP = {
    # Core commands
    "STATUS": 0x01,
    "ID_ASSIGN": 0x02,
    "NEW_SAT": 0x03,
    "ERROR": 0x04,
    "LOG": 0x05,
    "POWER": 0x06,
    
    # LED commands
    "LED": 0x10,
    "LEDFLASH": 0x11,
    "LEDBREATH": 0x12,
    "LEDCYLON": 0x13,
    "LEDCENTRI": 0x14,
    "LEDRAINBOW": 0x15,
    "LEDGLITCH": 0x16,
    
    # Display commands
    "DSP": 0x20,
    "DSPCORRUPT": 0x21,
    "DSPMATRIX": 0x22,
    
    # Encoder commands
    "SETENC": 0x30,
}

# Reverse mapping for decoding
COMMAND_REVERSE_MAP = {v: k for k, v in COMMAND_MAP.items()}


# Special destination IDs
DEST_MAP = {
    "ALL": 0xFF,
    "SAT": 0xFE,
}

DEST_REVERSE_MAP = {v: k for k, v in DEST_MAP.items()}

# Maximum value for single-byte index (used to distinguish 1-byte vs 2-byte dest IDs)
MAX_INDEX_VALUE = 100
