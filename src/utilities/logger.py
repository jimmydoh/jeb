"""
Logging utilities for the JEB project.
"""

import time
import sys

class LogLevel:
    """
    Log levels for categorizing log messages.
    """
    DEBUG = 0
    INFO = 1
    NOTE = 2
    WARNING = 3
    ERROR = 4

class JEBLogger:
    """Centralized, memory-efficient logger for CircuitPython."""

    # Global Configuration
    LEVEL = LogLevel.INFO
    SOURCE = "CORE"  # Default source tag for log messages
    PRINT_TO_CONSOLE = True
    WRITE_TO_FILE = False
    LOG_FILE_PATH = "/jeb_syslog.txt"

    # Terminal Color Codes (Makes console debugging much easier)
    COLORS = {
        LogLevel.DEBUG: "\033[90m",    # Gray
        LogLevel.INFO: "\033[94m",     # Blue
        LogLevel.NOTE: "\033[96m",     # Cyan
        LogLevel.WARNING: "\033[93m",  # Yellow
        LogLevel.ERROR: "\033[91m",    # Red
        "RESET": "\033[0m"
    }

    LEVEL_TAGS = {
        LogLevel.DEBUG: "DBUG",
        LogLevel.INFO: "INFO",
        LogLevel.NOTE: "NOTE",  # Optional level for important info that isn't a warning
        LogLevel.WARNING: "WARN",
        LogLevel.ERROR: "!ERR"
    }

    @classmethod
    def set_level(cls, level):
        cls.LEVEL = level

    @classmethod
    def enable_file_logging(cls, enable=True):
        """Note: Requires storage.remount() in boot.py to work on actual hardware!"""
        cls.WRITE_TO_FILE = enable

    @classmethod
    def _get_timestamp(cls):
        """Returns fixed-width uptime stamp."""
        return f"{time.monotonic():>8.3f}"

    @classmethod
    def _log(cls, level, module_tag, message, source_tag=None, file_override=None):
        """Core routing method."""
        if level < cls.LEVEL:
            return

        if source_tag is None:
            source_tag = cls.SOURCE

        timestamp = cls._get_timestamp()
        lvl_tag = cls.LEVEL_TAGS[level]

        # Format: [ 123.456] [INF] [UART_MGR] Handshake successful
        formatted_msg = f"[{timestamp}][{lvl_tag:<4}][{source_tag:<4}][{module_tag:<4}] {message}"

        if cls.PRINT_TO_CONSOLE:
            # Wrap in color codes for the terminal
            color = cls.COLORS[level]
            reset = cls.COLORS["RESET"]
            print(f"{color}{formatted_msg}{reset}")

        if cls.WRITE_TO_FILE or file_override:
            target_file = file_override if file_override else cls.LOG_FILE_PATH
            try:
                # Open, append, and close immediately to ensure data is written
                # and memory is freed, protecting against unexpected power loss.
                with open(target_file, "a") as f:
                    f.write(formatted_msg + "\n")
            except OSError as e:
                # Catch Read-Only filesystem errors silently so they don't crash the program
                if cls.PRINT_TO_CONSOLE:
                    print(f"{cls.COLORS[LogLevel.ERROR]}Logger OS Error: {e}{cls.COLORS['RESET']}")

    # Convenience Wrappers
    @classmethod
    def debug(cls, tag, msg, src=None, file=None):
        cls._log(LogLevel.DEBUG, tag, msg, source_tag=src, file_override=file)

    @classmethod
    def info(cls, tag, msg, src=None, file=None):
        cls._log(LogLevel.INFO, tag, msg, source_tag=src, file_override=file)

    @classmethod
    def note(cls, tag, msg, src=None, file=None):
        cls._log(LogLevel.NOTE, tag, msg, source_tag=src, file_override=file)

    @classmethod
    def warning(cls, tag, msg, src=None, file=None):
        cls._log(LogLevel.WARNING, tag, msg, source_tag=src, file_override=file)

    @classmethod
    def error(cls, tag, msg, src=None, file=None):
        cls._log(LogLevel.ERROR, tag, msg, source_tag=src, file_override=file)
