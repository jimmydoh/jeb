"""Protocol definitions for JEB communication system.

This module defines the command codes, destination IDs, and payload schemas
used in the binary protocol. These are application-specific constants that
can be used by both the transport layer and higher-level components.

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


# Payload encoding type constants
ENCODING_RAW_TEXT = 'text'
ENCODING_NUMERIC_BYTES = 'bytes'
ENCODING_NUMERIC_WORDS = 'words'
ENCODING_FLOATS = 'floats'


# Command-specific payload schemas
# This eliminates ambiguity in type interpretation
# 
# Schema fields:
#   'type': One of the ENCODING_* constants above
#   'desc': Human-readable description
#   'count': (optional) Expected number of values for validation
PAYLOAD_SCHEMAS = {
    # Core commands - these use text IDs that must not be interpreted as numbers
    "ID_ASSIGN": {'type': ENCODING_RAW_TEXT, 'desc': 'Device ID string like "0100"'},
    "NEW_SAT": {'type': ENCODING_RAW_TEXT, 'desc': 'Satellite type ID like "01"'},
    "ERROR": {'type': ENCODING_RAW_TEXT, 'desc': 'Error description text'},
    "LOG": {'type': ENCODING_RAW_TEXT, 'desc': 'Log message text'},
    
    # LED commands - RGB values plus parameters (variable count OK)
    "LED": {'type': ENCODING_NUMERIC_BYTES, 'desc': 'R,G,B,brightness bytes'},
    "LEDFLASH": {'type': ENCODING_NUMERIC_BYTES, 'desc': 'R,G,B,brightness'},
    "LEDBREATH": {'type': ENCODING_NUMERIC_BYTES, 'desc': 'R,G,B,brightness'},
    "LEDCYLON": {'type': ENCODING_NUMERIC_BYTES, 'desc': 'R,G,B,brightness'},
    "LEDCENTRI": {'type': ENCODING_NUMERIC_BYTES, 'desc': 'R,G,B,brightness'},
    "LEDRAINBOW": {'type': ENCODING_NUMERIC_BYTES, 'desc': 'speed,brightness'},
    "LEDGLITCH": {'type': ENCODING_NUMERIC_BYTES, 'desc': 'intensity,brightness'},
    
    # Display commands
    "DSP": {'type': ENCODING_RAW_TEXT, 'desc': 'Display message text'},
    "DSPCORRUPT": {'type': ENCODING_NUMERIC_BYTES, 'desc': 'level,duration'},
    "DSPMATRIX": {'type': ENCODING_NUMERIC_BYTES, 'desc': 'speed,density'},
    
    # Power and status - use floats for voltage/current measurements
    "POWER": {'type': ENCODING_FLOATS, 'desc': 'voltage1,voltage2,current'},
    "STATUS": {'type': ENCODING_NUMERIC_BYTES, 'desc': 'status bytes (variable length)'},
    
    # Encoder
    "SETENC": {'type': ENCODING_NUMERIC_WORDS, 'desc': 'encoder position'},
}
