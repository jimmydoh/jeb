"""Protocol definitions for JEB communication system.

This module defines the command codes, destination IDs, and payload schemas
used in the binary protocol. These are application-specific constants that
can be used by both the transport layer and higher-level components.

By centralizing these definitions here, the transport layer remains
reusable for other projects while applications can inject their specific
command sets.
"""

# --- Command Constants (Avoid Magic Strings in Logic) ---
CMD_PING = "PING"
CMD_ACK = "ACK"
CMD_NACK = "NACK"
CMD_ID_ASSIGN = "ID_ASSIGN"
CMD_NEW_SAT = "NEW_SAT"
CMD_STATUS = "STATUS"
CMD_MODE = "MODE"
CMD_ERROR = "ERROR"
CMD_LOG = "LOG"
CMD_SYNC_FRAME = "SYNC_FRAME"
CMD_POWER = "POWER"
CMD_REBOOT = "REBOOT"
CMD_HELLO = "HELLO"

# LED Commands
CMD_LED = "LED"
CMD_LEDFLASH = "LEDFLASH"
CMD_LEDBREATH = "LEDBREATH"
CMD_LEDCYLON = "LEDCYLON"
CMD_LEDCENTRI = "LEDCENTRI"
CMD_LEDRAINBOW = "LEDRAINBOW"
CMD_LEDGLITCH = "LEDGLITCH"

# Display Commands
CMD_DSP = "DSP"
CMD_DSPCORRUPT = "DSPCORRUPT"
CMD_DSPMATRIX = "DSPMATRIX"

# Encoder Commands
CMD_SETENC = "SETENC"

# File Transfer Commands
CMD_FILE_START = "FILE_START"
CMD_FILE_CHUNK = "FILE_CHUNK"
CMD_FILE_END = "FILE_END"

# Firmware Update Handshake Commands
CMD_VERSION_CHECK = "VERSION_CHECK"
CMD_UPDATE_START = "UPDATE_START"
CMD_UPDATE_WAIT = "UPDATE_WAIT"

# --- Command Mapping ---
COMMAND_MAP = {
    # System & Discovery
    CMD_HELLO: 0xAA,
    CMD_PING: 0x01,
    CMD_ACK: 0x02,
    CMD_NACK: 0x03,
    CMD_ID_ASSIGN: 0x04,
    CMD_NEW_SAT: 0x05,
    CMD_STATUS: 0x06,
    CMD_ERROR: 0x07,
    CMD_LOG: 0x08,
    CMD_SYNC_FRAME: 0x09,
    CMD_POWER: 0x0A,
    CMD_REBOOT: 0x0B,
    CMD_MODE: 0x0C,

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
    CMD_SETENC: 0x30,

    # File Transfer commands
    CMD_FILE_START: 0x40,
    CMD_FILE_CHUNK: 0x41,
    CMD_FILE_END: 0x42,

    # Firmware update handshake commands
    CMD_VERSION_CHECK: 0x50,
    CMD_UPDATE_START: 0x51,
    CMD_UPDATE_WAIT: 0x52,

}

# Special destination IDs
DEST_MAP = {
    "ALL": 0xFF,
    "CORE": 0x00,
    "DRIV": 0xFD,
    "SAT": 0xFE,
}

# --- Command Groups (The Source of Truth for Dispatch) ---
#These sets allow the firmware to ask "Is this an LED command?"
# without knowing the specific command names.

# Dynamically generate these based on your naming convention,
# or explicitly list them if you want strict control.
LED_COMMANDS = {k for k in COMMAND_MAP if k.startswith("LED")}
DSP_COMMANDS = {k for k in COMMAND_MAP if k.startswith("DSP")}
FILE_COMMANDS = {CMD_FILE_START, CMD_FILE_CHUNK, CMD_FILE_END}
UPDATE_COMMANDS = {CMD_VERSION_CHECK, CMD_UPDATE_START, CMD_UPDATE_WAIT}

# Commands that are handled directly by the Firmware class
SYSTEM_COMMANDS = {
    CMD_ID_ASSIGN,
    CMD_SYNC_FRAME,
    CMD_SETENC,
    CMD_NEW_SAT,
    CMD_MODE,
}

# Reverse mapping for decoding
COMMAND_REVERSE_MAP = {v: k for k, v in COMMAND_MAP.items()}
DEST_REVERSE_MAP = {v: k for k, v in DEST_MAP.items()}

# Maximum value for single-byte index (used to distinguish 1-byte vs 2-byte dest IDs)
MAX_INDEX_VALUE = 100

# Payload encoding type constants
ENCODING_RAW_TEXT = 'text'
ENCODING_NUMERIC_BYTES = 'bytes'
ENCODING_NUMERIC_WORDS = 'words'
ENCODING_FLOATS = 'floats'
ENCODING_RAW_BYTES = 'raw_bytes'


# Command-specific payload schemas
# This eliminates ambiguity in type interpretation
#
# Schema fields:
#   'type': One of the ENCODING_* constants above
#   'desc': Human-readable description
#   'count': (optional) Expected number of values for validation
PAYLOAD_SCHEMAS = {
    # Core commands
    CMD_HELLO: {'type': ENCODING_RAW_TEXT, 'desc': 'Hello message with optional text'},
    CMD_MODE: {'type': ENCODING_RAW_TEXT, 'desc': 'Operating mode: IDLE, ACTIVE, or SLEEP'},
    "ID_ASSIGN": {'type': ENCODING_RAW_TEXT, 'desc': 'Device ID string like "0100"'},
    "NEW_SAT": {'type': ENCODING_RAW_TEXT, 'desc': 'Satellite type ID like "01"'},
    "ERROR": {'type': ENCODING_RAW_TEXT, 'desc': 'Error description text'},
    "LOG": {'type': ENCODING_RAW_TEXT, 'desc': 'Log message text'},
    "SYNC_FRAME": {'type': ENCODING_FLOATS, 'desc': 'Frame sync: frame_number,time_seconds'},
    "REBOOT": {'type': ENCODING_RAW_TEXT, 'desc': 'Reboot command with optional reason text'},

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

    # File Transfer
    CMD_FILE_START: {'type': ENCODING_RAW_TEXT, 'desc': 'filename,total_size e.g. "firmware.bin,4096"'},
    CMD_FILE_CHUNK: {'type': ENCODING_RAW_BYTES, 'desc': 'raw binary chunk data'},
    CMD_FILE_END: {'type': ENCODING_RAW_TEXT, 'desc': 'SHA256 hex digest of the complete file'},

    # Firmware Update Handshake
    CMD_VERSION_CHECK: {'type': ENCODING_RAW_TEXT, 'desc': 'Firmware version string e.g. "0.4.0"'},
    CMD_UPDATE_START: {'type': ENCODING_RAW_TEXT, 'desc': 'file_count,total_bytes e.g. "5,12800"'},
    CMD_UPDATE_WAIT: {'type': ENCODING_RAW_TEXT, 'desc': 'Update in progress; retry version check later'},
}
