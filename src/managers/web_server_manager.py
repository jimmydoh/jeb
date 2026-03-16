"""
WebServerManager - Async HTTP Server for Field Service Configuration

This manager provides a web-based interface for configuring and monitoring
the JEB system without requiring physical access to the SD card.

Features:
- Configuration editor (global and mode settings)
- File browser (upload/download SD card files)
- Console output viewer
- Log viewer
- Manual OTA update trigger
- Debug mode toggle
- Satellite reordering
- Pixel Art Studio (live LED matrix drawing canvas)
- Audio Studio (multi-channel chiptune sequence editor and .jseq export)

Dependencies:
- JEBLogger (for logging within the web server)
- WiFiManager (for managing WiFi connectivity)
- adafruit_httpserver (CircuitPython library)
- ssl (CircuitPython built-ins)
"""

import asyncio
import json
import os
import gc
import time

from adafruit_httpserver import Server, Request, Response, GET, POST

from utilities.logger import JEBLogger, LogLevel
from utilities.palette import Palette

class WebServerManager:
    """
    Async HTTP server for field service configuration and monitoring.

    This manager runs independently of CoreManager and can be loaded
    by code.py to provide web-based configuration interface.
    """

    # Class constants for memory management and chunked I/O
    CHUNK_SIZE = 1024  # Bytes to read/write at a time for file operations
    MAX_UPLOAD_SIZE_BYTES = 50 * 1024  # Maximum upload size (50KB)
    DEFAULT_MAX_LOGS = 1000  # Default maximum log entries to keep

    def __init__(self, config, wifi_manager, app=None, console_buffer=None, testing=False):
        """
        Initialize the web server manager.

        Args:
            config (dict): Configuration dictionary
            wifi_manager (WiFiManager): REQUIRED: Shared WiFiManager instance.
            app: Optional CoreManager application instance for hardware and registry access.
            console_buffer (object): Optional console buffer for output capture
        """
        if wifi_manager is None:
            JEBLogger.warning("WEBS", "No WiFiManager provided - WebServerManager cannot start")
            raise RuntimeError("No WiFiManager provided")

        JEBLogger.info("WEBS", f"[INIT] WebServerManager - port: {config.get('web_server_port', 80)}, enabled: {config.get('web_server_enabled', False)}, testing: {testing}")
        self._testing = testing

        self.config = config
        self.port = config.get("web_server_port", 80)
        self.enabled = config.get("web_server_enabled", False)
        self.wifi_manager = wifi_manager

        self.app = app
        self.console_buffer = console_buffer

        self.server = None
        self.pool = None
        self.connected = False
        self.logs = []  # Ring buffer for log messages
        self.max_logs = self.DEFAULT_MAX_LOGS

        # Enable JEBLogger ring buffer so all system logs feed the Logging tab
        JEBLogger.enable_buffer(max_entries=self.DEFAULT_MAX_LOGS)

    # --- Hardware Delegation Properties ---
    # These properties safely fetch the managers from the active app if it exists.
    # This prevents us from needing to rewrite all the API endpoints!

    @property
    def power_manager(self):
        return getattr(self.app, 'power', None) if self.app else None

    @property
    def satellite_manager(self):
        return getattr(self.app, 'sat_network', None) if self.app else None

    @property
    def matrix_manager(self):
        return getattr(self.app, 'matrix', None) if self.app else None

    @property
    def synth_manager(self):
        return getattr(self.app, 'synth', None) if self.app else None

    @property
    def hid(self):
        return getattr(self.app, 'hid', None) if self.app else None

    async def connect_wifi(self, timeout=30):
        """
        Connect to WiFi network (async, non-blocking).

        Delegates to wifi_manager if one was provided, otherwise manages
        the connection directly.

        Args:
            timeout (int): Connection timeout in seconds

        Returns:
            bool: True if connected successfully
        """
        connected = self.wifi_manager.connect(timeout)
        if connected:
            self.connected = True
            self.pool = self.wifi_manager.pool
        else:
            self.connected = False
        return connected

    def disconnect_wifi(self):
        """Disconnect from WiFi to save power."""
        self.wifi_manager.disconnect()
        self.connected = False
        return

    def _is_wifi_connected(self):
        """Check current WiFi connection status via wifi_manager or direct radio."""
        return self.wifi_manager.is_connected

    def _get_ip_address(self):
        """Get current IP address string via wifi_manager or direct radio."""
        return str(self.wifi_manager.ip_address)

    def log(self, message):
        """Add a message to the log buffer."""
        timestamp = time.monotonic()
        self.logs.append({"time": timestamp, "message": message})

        # Trim log buffer if too large
        if len(self.logs) > self.max_logs:
            self.logs = self.logs[-self.max_logs:]

    def _sanitize_path(self, base_path, user_path):
        """
        Sanitize a user-provided path to prevent directory traversal attacks.

        This function normalizes paths using string manipulation instead of
        os.path.normpath, which is not available in CircuitPython.

        Args:
            base_path (str): The base directory path (e.g., "/sd")
            user_path (str): The user-provided path to sanitize

        Returns:
            str: The sanitized absolute path within base_path
        """
        # If user_path starts with base_path, extract the relative part
        if user_path.startswith(base_path + "/"):
            # Extract relative path after base_path
            relative_path = user_path[len(base_path) + 1:]
            parts = relative_path.split("/")
        elif user_path == base_path:
            # User path is exactly the base path
            return base_path
        elif user_path.startswith("/"):
            # Absolute path that doesn't start with base_path is a security violation
            # Return base_path to deny access outside the allowed directory
            return base_path
        else:
            # Relative path - will be appended to base_path
            parts = user_path.split("/")

        clean_parts = []

        # Process each part
        for part in parts:
            # Skip empty parts and current directory references
            if part == "" or part == ".":
                continue
            # Handle parent directory references
            if part == "..":
                # Only pop if there are parts to pop (prevent going above base)
                if clean_parts:
                    clean_parts.pop()
            else:
                # Add normal directory/file name
                clean_parts.append(part)

        # Construct the sanitized path
        if clean_parts:
            sanitized = base_path + "/" + "/".join(clean_parts)
        else:
            sanitized = base_path

        # Final validation: ensure the sanitized path doesn't escape the base directory
        # This is a defense-in-depth measure to catch any edge cases
        if not sanitized.startswith(base_path):
            return base_path

        return sanitized

    def setup_routes(self):
        """Setup HTTP routes for the web server."""

        # Serve main HTML page
        @self.server.route("/", GET)
        def index(request: Request):
            """Serve the main configuration page."""
            html = self._generate_html_page()
            return Response(request, html, content_type="text/html")

        # API: Get global config
        @self.server.route("/api/config/global", GET)
        def get_global_config(request: Request):
            """Return global configuration as JSON."""
            return Response(request, json.dumps(self.config), content_type="application/json")

        # API: Update global config
        @self.server.route("/api/config/global", POST)
        def update_global_config(request: Request):
            """Update global configuration."""
            try:
                data = request.json()
                if not data:
                    return Response(request, '{"error": "Invalid JSON"}',
                                  content_type="application/json", status=400)

                # Validate and update config (protect critical fields)
                protected_fields = ["role", "type_id"]
                valid_boolean_fields = ["debug_mode", "test_mode", "web_server_enabled", "mount_sd_card"]
                valid_int_fields = ["web_server_port", "uart_baudrate", "uart_buffer_size"]

                for key, value in data.items():
                    # Skip protected fields
                    if key in protected_fields:
                        continue

                    # Validate boolean fields
                    if key in valid_boolean_fields:
                        if not isinstance(value, bool):
                            return Response(request, f'{{"error": "{key} must be boolean"}}',
                                          content_type="application/json", status=400)

                    # Validate integer fields
                    if key in valid_int_fields:
                        if not isinstance(value, int) or value < 0:
                            return Response(request, f'{{"error": "{key} must be positive integer"}}',
                                          content_type="application/json", status=400)
                        # Validate port range
                        if key == "web_server_port" and (value < 1 or value > 65535):
                            return Response(request, '{"error": "Invalid port number (1-65535)"}',
                                          content_type="application/json", status=400)

                    # Update config
                    self.config[key] = value

                # Save config to file
                self._save_config()
                self.log(f"Global config updated")

                return Response(request, '{"status": "success"}',
                              content_type="application/json")
            except Exception as e:
                self.log(f"Error updating config: {e}")
                return Response(request, f'{{"error": "{str(e)}"}}',
                              content_type="application/json", status=500)

        # API: List files
        @self.server.route("/api/files", GET)
        def list_files(request: Request):
            """List files in a directory."""
            try:
                path = request.query_params.get("path", "/sd")
                files = self._list_directory(path)
                return Response(request, json.dumps(files),
                              content_type="application/json")
            except Exception as e:
                return Response(request, f'{{"error": "{str(e)}"}}',
                              content_type="application/json", status=500)

        # API: Download file
        @self.server.route("/api/files/download", GET)
        def download_file(request: Request):
            """Download a file from the SD card using chunked reading."""
            try:
                path = request.query_params.get("path")
                if not path:
                    return Response(request, '{"error": "Path required"}',
                                  content_type="application/json", status=400)

                # Security: Prevent directory traversal and validate path
                # Normalize path and ensure it's within allowed directories
                normalized_path = self._sanitize_path("/sd", path)

                # Defense-in-depth: Verify sanitized path is within allowed directories
                # _sanitize_path already ensures this, but we check again for safety
                if not (normalized_path.startswith("/sd/") or normalized_path == "/sd"):
                    return Response(request, '{"error": "Invalid path - access denied"}',
                                  content_type="application/json", status=400)

                # Create a generator function to read file in chunks
                def file_generator(filepath, chunk_size=None):
                    """Generator that yields file chunks to avoid loading entire file in RAM."""
                    if chunk_size is None:
                        chunk_size = self.CHUNK_SIZE
                    try:
                        with open(filepath, "rb", encoding="utf-8") as f:
                            while True:
                                chunk = f.read(chunk_size)
                                if not chunk:
                                    break
                                yield chunk
                    except Exception as e:
                        print(f"Error reading file {filepath}: {e}")

                filename = normalized_path.split("/")[-1]

                # Return response with generator for chunked transfer
                return Response(request, file_generator(normalized_path),
                              content_type="application/octet-stream",
                              headers={"Content-Disposition": f"attachment; filename={filename}"})
            except Exception as e:
                return Response(request, f'{{"error": "{str(e)}"}}',
                              content_type="application/json", status=500)

        # API: Upload file (Note: CircuitPython HTTP server may need chunked upload)
        @self.server.route("/api/files/upload", POST)
        def upload_file(request: Request):
            """Upload a file to the SD card with chunked streaming to prevent MemoryError."""
            try:
                # Get target path and filename from query params
                path = request.query_params.get("path", "/sd")
                filename = request.query_params.get("filename")

                if not filename:
                    return Response(request, '{"error": "Filename required"}',
                                  content_type="application/json", status=400)

                # Security: Prevent directory traversal and validate paths
                normalized_path = self._sanitize_path("/sd", path)

                # For filename, we just need to remove any path components
                # and ensure it doesn't contain directory traversal
                # First check for path separators in the original filename
                if "/" in filename or "\\" in filename:
                    return Response(request, '{"error": "Invalid filename - path separators not allowed"}',
                                  content_type="application/json", status=400)

                # Check for directory traversal attempts (exact match)
                if filename == ".." or filename == ".":
                    return Response(request, '{"error": "Invalid filename - directory references not allowed"}',
                                  content_type="application/json", status=400)

                # Strip whitespace and check for empty filename
                clean_filename = filename.strip()
                if clean_filename == "":
                    return Response(request, '{"error": "Filename cannot be empty"}',
                                  content_type="application/json", status=400)

                # Defense-in-depth: Verify sanitized path is within SD card
                # _sanitize_path already ensures this, but we check again for safety
                if not (normalized_path.startswith("/sd/") or normalized_path == "/sd"):
                    return Response(request, '{"error": "Invalid path - must be within /sd"}',
                                  content_type="application/json", status=400)

                # Get content length from headers to validate size before reading
                # Avoid calling request.body which loads everything into memory at once
                content_length = 0
                if hasattr(request, 'headers') and request.headers:
                    content_length = int(request.headers.get('Content-Length', 0))
                elif hasattr(request, 'content_length'):
                    content_length = request.content_length

                # Check available memory and validate upload size
                free_mem = gc.mem_free()
                max_upload_size = min(self.MAX_UPLOAD_SIZE_BYTES, free_mem // 2)  # Max 50KB or half of free RAM

                if content_length > max_upload_size:
                    return Response(request,
                                  f'{{"error": "File too large. Max size: {max_upload_size} bytes. Free RAM: {free_mem} bytes"}}',
                                  content_type="application/json", status=413)

                # Stream file content directly to SD card in chunks to avoid MemoryError
                # This bypasses request.body which would load everything into RAM at once
                filepath = f"{normalized_path}/{clean_filename}"
                bytes_written = 0
                upload_method = "unknown"

                with open(filepath, "wb", encoding="utf-8") as f:
                    # Try to use streaming interface if available
                    # First, check for request.stream (newer adafruit_httpserver versions)
                    if hasattr(request, 'stream') and request.stream:
                        upload_method = "stream"
                        while True:
                            chunk = request.stream.read(self.CHUNK_SIZE)
                            if not chunk:
                                break
                            f.write(chunk)
                            bytes_written += len(chunk)
                    # Fallback: Try to access underlying socket directly
                    # NOTE: Accessing _socket is a workaround for older adafruit_httpserver versions
                    # that don't expose a streaming API. This may break with library updates.
                    elif hasattr(request, '_socket') and request._socket:
                        upload_method = "socket"
                        self.log("⚠️ Using _socket fallback for chunked upload (consider updating adafruit_httpserver)")
                        remaining = content_length
                        while remaining > 0:
                            chunk_size = min(self.CHUNK_SIZE, remaining)
                            chunk = request._socket.recv(chunk_size)
                            if not chunk:
                                break
                            f.write(chunk)
                            bytes_written += len(chunk)
                            remaining -= len(chunk)
                    # Last resort fallback: use request.body (original behavior)
                    # WARNING: This loads entire file into RAM and may cause MemoryError
                    else:
                        upload_method = "body"
                        self.log("⚠️ Falling back to request.body - may cause MemoryError for large files")
                        content = request.body
                        for i in range(0, len(content), self.CHUNK_SIZE):
                            f.write(content[i:i+self.CHUNK_SIZE])
                        bytes_written = len(content)

                self.log(f"File uploaded: {filepath} ({bytes_written} bytes, method: {upload_method})")
                return Response(request, f'{{"status": "success", "path": "{filepath}", "size": {bytes_written}}}',
                              content_type="application/json")
            except MemoryError:
                gc.collect()  # Try to free memory
                return Response(request,
                              '{"error": "MemoryError: File too large for available RAM"}',
                              content_type="application/json", status=507)
            except Exception as e:
                self.log(f"Error uploading file: {e}")
                return Response(request, f'{{"error": "{str(e)}"}}',
                              content_type="application/json", status=500)

        # API: Get mode settings
        @self.server.route("/api/config/modes", GET)
        def get_mode_settings(request: Request):
            """Return mode settings from the registry with current values from DataManager."""
            try:
                # Resolve mode registry: prefer live app registry, fall back to manifest import
                mode_registry = None
                if self.app is not None and hasattr(self.app, 'mode_registry'):
                    mode_registry = self.app.mode_registry
                else:
                    try:
                        from modes.manifest import MODE_REGISTRY
                        mode_registry = MODE_REGISTRY
                    except ImportError:
                        return Response(request, '{"error": "Mode registry not available"}',
                                      content_type="application/json", status=503)

                # Resolve DataManager if available
                data_mgr = None
                if self.app is not None and hasattr(self.app, 'data'):
                    data_mgr = self.app.data

                modes_data = {}
                for mode_id, meta in mode_registry.items():
                    settings = meta.get("settings", [])
                    if not settings:
                        continue
                    current = {}
                    for s in settings:
                        if data_mgr is not None:
                            current[s["key"]] = data_mgr.get_setting(mode_id, s["key"], s["default"])
                        else:
                            current[s["key"]] = s["default"]
                    modes_data[mode_id] = {
                        "settings": settings,
                        "current": current,
                    }

                return Response(request, json.dumps(modes_data),
                              content_type="application/json")
            except Exception as e:
                return Response(request, f'{{"error": "{str(e)}"}}',
                              content_type="application/json", status=500)

        # API: Update mode settings
        @self.server.route("/api/config/modes", POST)
        def update_mode_settings(request: Request):
            """Update settings for a specific mode and persist to DataManager."""
            try:
                data = request.json()
                if not data:
                    return Response(request, '{"error": "Invalid JSON"}',
                                  content_type="application/json", status=400)

                mode_id = data.get("mode_id")
                settings = data.get("settings")

                if not mode_id or not settings:
                    return Response(request, '{"error": "mode_id and settings required"}',
                                  content_type="application/json", status=400)

                if self.app is None or not hasattr(self.app, 'data'):
                    return Response(request, '{"error": "DataManager not available"}',
                                  content_type="application/json", status=503)

                for key, value in settings.items():
                    self.app.data.set_setting(mode_id, key, value)

                self.log(f"Mode settings updated for {mode_id}")

                return Response(request, '{"status": "success"}',
                              content_type="application/json")
            except Exception as e:
                self.log(f"Error updating mode settings: {e}")
                return Response(request, f'{{"error": "{str(e)}"}}',
                              content_type="application/json", status=500)

        # API: Get full mode list from manifest with playable status
        @self.server.route("/api/modes", GET)
        def get_modes(request: Request):
            """Return all game modes from the registry with settings and playable status.

            Playable status is determined by comparing each mode's ``requires``
            list against the hardware that is currently connected (CORE is always
            present; satellite types are checked via the satellite_manager).
            """
            try:
                # Resolve mode registry: prefer live app registry, fall back to manifest import
                mode_registry = None
                if self.app is not None and hasattr(self.app, 'mode_registry'):
                    mode_registry = self.app.mode_registry
                else:
                    try:
                        from modes.manifest import MODE_REGISTRY
                        mode_registry = MODE_REGISTRY
                    except ImportError:
                        return Response(request, '{"error": "Mode registry not available"}',
                                      content_type="application/json", status=503)

                # Determine connected hardware
                connected_hardware = ["CORE"]
                if self.satellite_manager is not None:
                    try:
                        for sat in self.satellite_manager.satellites.values():
                            if getattr(sat, 'is_active', False):
                                sat_type = getattr(sat, 'sat_type_name', '')
                                if sat_type and sat_type not in connected_hardware:
                                    connected_hardware.append(sat_type)
                    except Exception:
                        pass

                # Game menu categories only (exclude admin/system menus)
                # Resolve DataManager if available; reload from disk to ensure fresh data
                data_mgr = None
                if self.app is not None and hasattr(self.app, 'data'):
                    data_mgr = self.app.data
                    if hasattr(data_mgr, 'reload'):
                        try:
                            data_mgr.reload()
                        except Exception:
                            pass

                game_menus = {"CORE", "EXP1", "ZERO_PLAYER"}
                modes = []
                for mode_id, meta in mode_registry.items():
                    if meta.get("menu") not in game_menus:
                        continue
                    requires = meta.get("requires", [])
                    playable = all(hw in connected_hardware for hw in requires)
                    settings = meta.get("settings", [])
                    current = {}
                    for s in settings:
                        if data_mgr is not None:
                            current[s["key"]] = data_mgr.get_setting(mode_id, s["key"], s["default"])
                        else:
                            current[s["key"]] = s["default"]
                    modes.append({
                        "id": meta["id"],
                        "name": meta.get("name", meta["id"]),
                        "menu": meta.get("menu", ""),
                        "order": meta.get("order", 9999),
                        "requires": requires,
                        "optional": meta.get("optional", []),
                        "has_tutorial": meta.get("has_tutorial", False),
                        "playable": playable,
                        "settings": settings,
                        "current": current,
                    })

                # Sort: menu category, then order, then name
                menu_order = {"CORE": 0, "ZERO_PLAYER": 1, "EXP1": 2}
                _unknown_menu_order = len(menu_order)
                modes.sort(key=lambda m: (menu_order.get(m["menu"], _unknown_menu_order), m["order"], m["name"]))

                return Response(request, json.dumps({
                    "connected_hardware": connected_hardware,
                    "modes": modes,
                }), content_type="application/json")
            except Exception as e:
                self.log(f"Error getting modes: {e}")
                return Response(request, f'{{"error": "{str(e)}"}}',
                              content_type="application/json", status=500)

        # API: Get logs
        @self.server.route("/api/logs", GET)
        def get_logs(request: Request):
            """Return JEBLogger ring buffer, optionally filtered.

            Query parameters:
                level  (int) – minimum LogLevel value (0=DEBUG … 5=ERROR)
                search (str) – case-insensitive substring filter
            """
            try:
                level_param = request.query_params.get("level")
                search_param = request.query_params.get("search", "").strip()

                level_filter = None
                if level_param is not None:
                    try:
                        level_filter = int(level_param)
                    except (ValueError, TypeError):
                        pass

                entries = JEBLogger.get_buffer(
                    level=level_filter,
                    search=search_param if search_param else None,
                )
                return Response(request, json.dumps(entries),
                              content_type="application/json")
            except Exception as e:
                return Response(request, f'{{"error": "{str(e)}"}}',
                              content_type="application/json", status=500)

        # API: Clear log buffer
        @self.server.route("/api/logs/clear", POST)
        def clear_logs(request: Request):
            """Clear the JEBLogger ring buffer."""
            JEBLogger.clear_buffer()
            return Response(request, '{"status": "cleared"}',
                          content_type="application/json")

        # API: Get console output
        @self.server.route("/api/console", GET)
        def get_console(request: Request):
            """Return recent console output."""
            if self.console_buffer:
                output = self.console_buffer.get_output()
            else:
                output = "Console buffer not available"

            return Response(request, json.dumps({"output": output}),
                          content_type="application/json")

        # API: Send input to the console manager
        @self.server.route("/api/console/input", POST)
        def post_console_input(request: Request):
            """Inject a line of text into the ConsoleManager input queue."""
            try:
                if self.console_buffer is None:
                    return Response(request, '{"error": "Console not available"}',
                                  content_type="application/json", status=503)

                # 1. Grab the raw body
                raw_body = request.body.decode('utf-8').strip()
                line = ""

                # 2. Try parsing it as JSON {"input": "..."} first
                if raw_body.startswith("{"):
                    try:
                        data = json.loads(raw_body)
                        line = str(data.get("input", "")).strip()
                    except Exception:
                        pass
                else:
                    # 3. Not JSON – treat the raw body as the input directly
                    line = raw_body

                if not line:
                    return Response(request, '{"error": "No input provided"}',
                                  content_type="application/json", status=400)

                # 4. Push to the queue!
                self.console_buffer.input_queue.append(line)
                self.log(f"Web Console Input Received: '{line}'") # Added to logs tab for debugging

                return Response(request, '{"status": "queued"}',
                              content_type="application/json")

            except Exception as e:
                self.log(f"Web Console Input Error: {e}")
                return Response(request, f'{{"error": "{str(e)}"}}',
                              content_type="application/json", status=500)

        # API: Trigger OTA update
        @self.server.route("/api/actions/ota-update", POST)
        def trigger_ota_update(request: Request):
            """Trigger a manual OTA update."""
            try:
                # Set update flag
                try:
                    with open("/sd/UPDATE_FLAG.txt", "w", encoding="utf-8") as f:
                        f.write("UPDATE_REQUESTED\n")
                except OSError as e:
                    # Provide more specific error message
                    if e.errno == 30:  # Read-only filesystem
                        error_msg = "SD card is read-only"
                    elif e.errno == 28:  # No space left on device
                        error_msg = "SD card is full"
                    else:
                        error_msg = f"Failed to write update flag: {e}"
                    return Response(request, f'{{"error": "{error_msg}"}}',
                                  content_type="application/json", status=500)

                self.log("OTA update triggered - device will update on next boot")
                return Response(request, '{"status": "update_scheduled"}',
                              content_type="application/json")
            except Exception as e:
                return Response(request, f'{{"error": "{str(e)}"}}',
                              content_type="application/json", status=500)

        # API: Toggle debug mode
        @self.server.route("/api/actions/toggle-debug", POST)
        def toggle_debug(request: Request):
            """Toggle debug mode."""
            try:
                self.config["debug_mode"] = not self.config.get("debug_mode", False)
                self._save_config()

                status = "enabled" if self.config["debug_mode"] else "disabled"
                self.log(f"Debug mode {status}")

                return Response(request, f'{{"status": "debug_{status}"}}',
                              content_type="application/json")
            except Exception as e:
                return Response(request, f'{{"error": "{str(e)}"}}',
                              content_type="application/json", status=500)

        # API: Reorder satellites
        @self.server.route("/api/actions/reorder-satellites", POST)
        def reorder_satellites(request: Request):
            """Reorder satellite IDs in configuration."""
            try:
                data = request.json()
                if not data:
                    return Response(request, '{"error": "Invalid JSON"}',
                                  content_type="application/json", status=400)

                satellite_order = data.get("order")
                if not satellite_order or not isinstance(satellite_order, list):
                    return Response(request, '{"error": "order array required"}',
                                  content_type="application/json", status=400)

                # Save new satellite order to config
                self.config["satellite_order"] = satellite_order
                self._save_config()

                self.log(f"Satellite order updated: {satellite_order}")
                return Response(request, '{"status": "success"}',
                              content_type="application/json")
            except Exception as e:
                self.log(f"Error reordering satellites: {e}")
                return Response(request, f'{{"error": "{str(e)}"}}',
                              content_type="application/json", status=500)

        # API: Launch a mode on the device
        @self.server.route("/api/actions/launch-mode", POST)
        def launch_mode(request: Request):
            """Launch a specific game mode on the device.

            Uses the same console-override mechanism as ConsoleManager to
            request a mode transition from outside the main game loop.

            JSON body fields:
                mode_id  (str): The mode registry ID to launch (e.g. 'SIMON').
                tutorial (bool, optional): When true, launch the tutorial variant.
            """
            try:
                data = request.json()
                if not data:
                    return Response(request, '{"error": "Invalid JSON"}',
                                  content_type="application/json", status=400)

                mode_id = data.get("mode_id")
                if not mode_id:
                    return Response(request, '{"error": "mode_id required"}',
                                  content_type="application/json", status=400)

                if self.app is None:
                    return Response(request, '{"error": "No app instance available"}',
                                  content_type="application/json", status=503)

                # Request tutorial variant if asked
                tutorial = data.get("tutorial", False)
                self.app._pending_mode_variant = "TUTORIAL" if tutorial else None

                # Set high-priority console override (same as ConsoleManager)
                self.app.console_override_mode = mode_id

                # Interrupt the currently running mode so the app loop transitions
                if hasattr(self.app, 'active_mode') and self.app.active_mode:
                    self.app.active_mode._exit_requested = True
                    if hasattr(self.app, 'active_mode_task') and self.app.active_mode_task:
                        self.app.active_mode_task.cancel()

                self.log(f"Mode launch requested: {mode_id} (tutorial={tutorial})")
                return Response(request, f'{{"status": "launching", "mode_id": "{mode_id}"}}',
                              content_type="application/json")
            except Exception as e:
                self.log(f"Error launching mode: {e}")
                return Response(request, f'{{"error": "{str(e)}"}}',
                              content_type="application/json", status=500)

        # API: Get system status
        @self.server.route("/api/system/status", GET)
        def get_system_status(request: Request):
            """Return system status information."""
            try:
                status = {
                    "wifi_ssid": self.wifi_manager.ssid,
                    "ip_address": self._get_ip_address(),
                    "debug_mode": self.config.get("debug_mode", False),
                    "uptime": time.monotonic(),
                    "free_memory": gc.mem_free(),
                }
                return Response(request, json.dumps(status),
                              content_type="application/json")
            except Exception as e:
                return Response(request, f'{{"error": "{str(e)}"}}',
                              content_type="application/json", status=500)

        # API: Real-time telemetry via standard AJAX polling
        @self.server.route("/api/telemetry/status", GET)
        def telemetry_status(request: Request):
            """Return current power and satellite telemetry as a single JSON response."""
            try:
                power_data = {}
                if self.power_manager is not None:
                    try:
                        # 1. Trigger a fresh hardware read across all buses
                        _ = self.power_manager.status

                        # 2. Extract the actual voltage floats for the Web UI
                        for name, bus in self.power_manager.buses.items():
                            if bus.v_now is not None:
                                power_data[name] = bus.v_now
                    except Exception:
                        pass

                sat_data = {}
                if self.satellite_manager is not None:
                    try:
                        for sid, sat in self.satellite_manager.satellites.items():
                            sat_data[sid] = {"active": sat.is_active}
                    except Exception:
                        pass

                system_data = {
                    "sleeping": self.app._sleeping if hasattr(self.app, "_sleeping") else False
                }

                payload = json.dumps({
                    "power": power_data,
                    "satellites": sat_data,
                    "system": system_data,
                    "ts": time.monotonic(),
                })
                return Response(request, payload, content_type="application/json")
            except Exception as e:
                return Response(request, f'{{"error": "{str(e)}"}}',
                              content_type="application/json", status=500)

        # API: Get pixel art palette
        @self.server.route("/api/pixel-art/palette", GET)
        def get_pixel_art_palette(request: Request):
            """Return the color palette as JSON for use in the pixel art studio."""
            try:
                palette_data = {}
                for idx in sorted(Palette.LIBRARY.keys()):
                    color = Palette.LIBRARY[idx]
                    palette_data[str(idx)] = {
                        "name": color.name,
                        "r": color.r,
                        "g": color.g,
                        "b": color.b,
                    }
                return Response(request, json.dumps(palette_data),
                              content_type="application/json")
            except Exception as e:
                return Response(request, f'{{"error": "{str(e)}"}}',
                              content_type="application/json", status=500)

        # API: Preview pixel art on the live LED matrix
        @self.server.route("/api/pixel-art/preview", POST)
        def preview_pixel_art(request: Request):
            """Draw pixel art on the live LED matrix for real-time preview."""
            try:
                data = request.json()
                if not data:
                    return Response(request, '{"error": "Invalid JSON"}',
                                  content_type="application/json", status=400)

                pixels = data.get("pixels")
                if not pixels or len(pixels) != 256:
                    return Response(request, '{"error": "pixels must be an array of 256 values"}',
                                  content_type="application/json", status=400)

                for v in pixels:
                    if not isinstance(v, int) or v < 0 or v > 255:
                        return Response(request, '{"error": "pixel values must be integers 0-255"}',
                                      content_type="application/json", status=400)

                if self.matrix_manager is None:
                    return Response(request, '{"status": "no_matrix", "message": "Matrix manager not available"}',
                                  content_type="application/json")

                # Clear matrix and draw each pixel
                self.matrix_manager.clear()
                for y in range(16):
                    for x in range(16):
                        val = pixels[y * 16 + x]
                        if val != 0:
                            color = Palette.LIBRARY.get(val)
                            if color:
                                self.matrix_manager.draw_pixel(x, y, color)

                self.log("Pixel art preview updated on matrix")
                return Response(request, '{"status": "success"}',
                              content_type="application/json")
            except Exception as e:
                return Response(request, f'{{"error": "{str(e)}"}}',
                              content_type="application/json", status=500)

        # API: Save pixel art as a .bin icon file
        @self.server.route("/api/pixel-art/save", POST)
        def save_pixel_art(request: Request):
            """Save pixel art as a .bin file to /sd/icons/."""
            try:
                data = request.json()
                if not data:
                    return Response(request, '{"error": "Invalid JSON"}',
                                  content_type="application/json", status=400)

                name = data.get("name", "").strip()
                pixels = data.get("pixels")

                if not name:
                    return Response(request, '{"error": "name is required"}',
                                  content_type="application/json", status=400)

                # Validate name: letters, numbers, and underscores only
                valid_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
                if not all(c in valid_chars for c in name):
                    return Response(request, '{"error": "name must contain only letters, numbers, and underscores"}',
                                  content_type="application/json", status=400)

                if not pixels or len(pixels) != 256:
                    return Response(request, '{"error": "pixels must be an array of 256 values"}',
                                  content_type="application/json", status=400)

                for v in pixels:
                    if not isinstance(v, int) or v < 0 or v > 255:
                        return Response(request, '{"error": "pixel values must be integers 0-255"}',
                                      content_type="application/json", status=400)

                filepath = f"/sd/icons/{name.lower()}.bin"

                if not self._testing:
                    # Ensure /sd/icons/ directory exists
                    try:
                        os.mkdir("/sd/icons")
                    except OSError:
                        pass  # Directory already exists

                    with open(filepath, "wb", encoding="utf-8") as f:
                        f.write(bytes(pixels))

                self.log(f"Pixel art saved: {filepath}")
                return Response(request, f'{{"status": "success", "path": "{filepath}"}}',
                              content_type="application/json")
            except Exception as e:
                return Response(request, f'{{"error": "{str(e)}"}}',
                              content_type="application/json", status=500)

        # API: Live preview of a multichannel synth sequence
        @self.server.route("/api/synth/preview", POST)
        def preview_synth(request: Request):
            """Play a multichannel sequence on the synth engine for live preview."""
            try:
                data = request.json()
                if not data:
                    return Response(request, '{"error": "Invalid JSON"}',
                                  content_type="application/json", status=400)

                channels = data.get("channels")
                if not channels or not isinstance(channels, list) or len(channels) == 0:
                    return Response(request, '{"error": "channels array required"}',
                                  content_type="application/json", status=400)

                if len(channels) > 4:
                    return Response(request, '{"error": "maximum 4 channels allowed"}',
                                  content_type="application/json", status=400)

                bpm = data.get("bpm", 120)
                if not isinstance(bpm, int) or bpm < 20 or bpm > 300:
                    return Response(request, '{"error": "bpm must be an integer between 20 and 300"}',
                                  content_type="application/json", status=400)

                channel_dicts = []
                for ch in channels:
                    if not isinstance(ch, dict):
                        return Response(request, '{"error": "each channel must be an object"}',
                                      content_type="application/json", status=400)
                    sequence = ch.get("sequence")
                    if not sequence or not isinstance(sequence, list):
                        return Response(request, '{"error": "each channel must have a sequence array"}',
                                      content_type="application/json", status=400)
                    patch_name = ch.get("patch", "SELECT")
                    channel_dicts.append({
                        'bpm': bpm,
                        'patch': patch_name,
                        'sequence': sequence,
                    })

                if self.synth_manager is None:
                    return Response(request, '{"status": "no_synth", "message": "Synth manager not available"}',
                                  content_type="application/json")

                self.synth_manager.preview_channels(channel_dicts)
                self.log("Synth preview started")
                return Response(request, '{"status": "success"}',
                              content_type="application/json")
            except Exception as e:
                return Response(request, f'{{"error": "{str(e)}"}}',
                              content_type="application/json", status=500)

        # API: Save a .jseq sequence file to /sd/sequences/
        @self.server.route("/api/synth/save", POST)
        def save_synth_sequence(request: Request):
            """Save a .jseq binary sequence file to /sd/sequences/."""
            try:
                name = request.query_params.get("name", "").strip()
                if not name:
                    return Response(request, '{"error": "name query parameter required"}',
                                  content_type="application/json", status=400)

                valid_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
                if not all(c in valid_chars for c in name):
                    return Response(request, '{"error": "name must contain only letters, numbers, and underscores"}',
                                  content_type="application/json", status=400)

                body = request.body
                if not body or len(body) < 8:
                    return Response(request, '{"error": "request body must contain .jseq binary data (minimum 8 bytes)"}',
                                  content_type="application/json", status=400)

                if body[:4] != b'JSEQ':
                    return Response(request, '{"error": "invalid .jseq file: missing JSEQ magic bytes"}',
                                  content_type="application/json", status=400)

                filepath = f"/sd/sequences/{name.lower()}.jseq"

                if not self._testing:
                    try:
                        os.mkdir("/sd/sequences")
                    except OSError:
                        pass  # Directory already exists

                    with open(filepath, "wb") as f:
                        f.write(body)

                self.log(f"Synth sequence saved: {filepath}")
                return Response(request, f'{{"status": "success", "path": "{filepath}"}}',
                              content_type="application/json")
            except Exception as e:
                return Response(request, f'{{"error": "{str(e)}"}}',
                              content_type="application/json", status=500)

        # API: Stop any currently playing synth sequence
        @self.server.route("/api/synth/stop", POST)
        def stop_synth(request: Request):
            """Stop any currently playing synth sequence or preview."""
            try:
                if self.synth_manager is None:
                    return Response(request, '{"status": "no_synth"}',
                                  content_type="application/json")
                self.synth_manager.stop_chiptune()
                self.log("Synth playback stopped")
                return Response(request, '{"status": "stopped"}',
                              content_type="application/json")
            except Exception as e:
                return Response(request, f'{{"error": "{str(e)}"}}',
                              content_type="application/json", status=500)

        # API: Remote HID state override (web-based interaction)
        @self.server.route("/api/hid/update", POST)
        def update_hid_state(request: Request):
            """Inject virtual HID state changes via web dashboard using override mode.

            Accepts a JSON body with an optional 'sid' field and one or more HID state
            fields. When 'sid' is 'CORE' or omitted, the command targets the core
            HIDManager. Otherwise the command is routed to the matching satellite's
            HIDManager so both core and satellite inputs can be driven remotely.

            All writes use override=True so they bypass the monitor_only guard and
            do not get clobbered by the next hardware-poll cycle.

            JSON fields:
                sid (str, optional): Target unit ID. 'CORE' or omitted = core HID.
                buttons (str, optional): Button states string (e.g. '010').
                latching_toggles (str, optional): Latching toggle states string (e.g. '10110').
                momentary_toggles (str, optional): Momentary toggle states string (e.g. 'CUC').
                encoders (str, optional): Encoder positions string (e.g. '0:25:123').
                encoder_buttons (str, optional): Encoder button states string (e.g. '1').
            """
            try:
                data = request.json()
                if not data:
                    return Response(request, '{"error": "Invalid JSON"}',
                                  content_type="application/json", status=400)

                sid = data.get("sid", "CORE")
                buttons = data.get("buttons")
                latching_toggles = data.get("latching_toggles")
                momentary_toggles = data.get("momentary_toggles")
                encoders = data.get("encoders")
                encoder_buttons = data.get("encoder_buttons")

                if not any([buttons, latching_toggles, momentary_toggles, encoders, encoder_buttons]):
                    return Response(request, '{"error": "No HID fields provided"}',
                                  content_type="application/json", status=400)

                # Resolve the target HIDManager
                if sid == "CORE" or sid is None:
                    target_hid = self.hid
                else:
                    if self.satellite_manager is None:
                        return Response(request, '{"error": "No satellite manager available"}',
                                      content_type="application/json", status=503)
                    sat = self.satellite_manager.satellites.get(sid)
                    if sat is None:
                        return Response(request, f'{{"error": "Satellite {sid} not found"}}',
                                      content_type="application/json", status=404)
                    target_hid = sat.hid

                if target_hid is None:
                    return Response(request, '{"status": "no_hid"}',
                                  content_type="application/json")

                # Apply overrides - each _sw_set_* method accepts override=True to
                # bypass the monitor_only guard and properly timestamp the interaction.
                dirty = False
                if buttons is not None:
                    if target_hid._sw_set_buttons(buttons, override=True):
                        dirty = True
                if latching_toggles is not None:
                    if target_hid._sw_set_latching_toggles(latching_toggles, override=True):
                        dirty = True
                if momentary_toggles is not None:
                    if target_hid._sw_set_momentary_toggles(momentary_toggles, override=True):
                        dirty = True
                if encoders is not None:
                    if target_hid._sw_set_encoders(encoders, override=True):
                        dirty = True
                if encoder_buttons is not None:
                    if target_hid._sw_set_encoder_buttons(encoder_buttons, override=True):
                        dirty = True

                self.log(f"HID override applied to {sid}: buttons={buttons} latching={latching_toggles} momentary={momentary_toggles} encoders={encoders} enc_btns={encoder_buttons}")
                status = "success" if dirty else "no_change"
                return Response(request, f'{{"status": "{status}"}}',
                              content_type="application/json")
            except Exception as e:
                return Response(request, f'{{"error": "{str(e)}"}}',
                              content_type="application/json", status=500)

        # --- SYSTEM ACTIONS ---

        @self.server.route("/api/action/reboot", POST)
        def action_reboot(request: Request):
            """Trigger a soft reboot of the Master Controller."""
            self.log("Web requested system reboot.")
            import supervisor
            import asyncio

            # Spawn a background task to reboot after 1 second
            # This allows the HTTP 200 OK response to successfully reach the browser first!
            async def delayed_reboot():
                await asyncio.sleep(1)
                supervisor.reload()

            asyncio.create_task(delayed_reboot())
            return Response(request, '{"status": "rebooting"}', content_type="application/json")

        @self.server.route("/api/action/sleep", POST)
        def action_sleep(request: Request):
            """Toggle the low-power sleep state."""
            if not self.app:
                return Response(request, '{"error": "App not available"}', status=503)
            try:
                data = json.loads(request.body)
                sleep_req = data.get("sleep", True)

                if sleep_req:
                    asyncio.create_task(self.app._enter_sleep())
                    self.log("Web forced system SLEEP.")
                else:
                    asyncio.create_task(self.app._wake_system())
                    self.log("Web forced system WAKE.")

                return Response(request, '{"status": "ok"}', content_type="application/json")
            except Exception as e:
                return Response(request, f'{{"error": "{str(e)}"}}', status=500, content_type="application/json")

        @self.server.route("/api/action/led", POST)
        def action_led(request: Request):
            """Apply an animation state to specific LEDs."""
            if not self.app or not self.app.leds:
                return Response(request, '{"error": "LED Manager not available"}', status=503)
            try:
                data = json.loads(request.body)
                idx = int(data.get("index", -1))
                hex_color = data.get("color", "#00FFFF")
                anim = data.get("anim", "SOLID")
                speed = float(data.get("speed", 1.0))

                # Parse hex to RGB tuple
                hex_color = hex_color.lstrip('#')
                r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

                # Apply to the button LED manager
                self.app.leds.set_led(idx, color=(r,g,b), anim_mode=anim, speed=speed)
                self.log(f"Web set LED {idx} -> {anim} @ {speed}x")

                return Response(request, '{"status": "ok"}', content_type="application/json")
            except Exception as e:
                return Response(request, f'{{"error": "{str(e)}"}}', status=500, content_type="application/json")

    def _save_config(self):
        """Save configuration to config.json."""
        if self._testing:
            return
        try:
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(self.config, f)
            print("Configuration saved to config.json")
        except Exception as e:
            print(f"Error saving config: {e}")
            raise

    def _list_directory(self, path):
        """List files and directories at the given path."""
        try:
            items = []
            for item in os.listdir(path):
                full_path = f"{path}/{item}" if path != "/" else f"/{item}"
                try:
                    stat = os.stat(full_path)
                    # Check if it's a directory (S_IFDIR = 0x4000)
                    is_dir = (stat[0] & 0x4000) != 0
                    items.append({
                        "name": item,
                        "path": full_path,
                        "is_dir": is_dir,
                        "size": stat[6] if not is_dir else 0
                    })
                except OSError:
                    pass  # Skip inaccessible items

            return {"path": path, "items": items}
        except Exception as e:
            raise RuntimeError(f"Error listing directory: {e}")

    def _generate_html_page(self):
        """Load and stream the main HTML configuration page from file."""
        # Try to load from SD card first, then fall back to local filesystem
        html_paths = ["/sd/www/index.html", "www/index.html", "src/www/index.html"]

        for html_path in html_paths:
            try:
                # Check if file exists before creating generator
                with open(html_path, "r", encoding="utf-8") as test_f:
                    pass  # File exists, proceed

                def html_generator(filepath, chunk_size=None):
                    """Generator that yields HTML file chunks to save RAM."""
                    if chunk_size is None:
                        chunk_size = self.CHUNK_SIZE
                    with open(filepath, "r", encoding="utf-8") as f:
                        while True:
                            chunk = f.read(chunk_size)
                            if not chunk:
                                break
                            yield chunk

                # Return generator for chunked streaming
                return html_generator(html_path)
            except OSError:
                continue

        # Fallback: Return minimal error page if HTML file not found
        return """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>JEB Field Service - Error</title>
    <style>
        body { font-family: Arial; background: #1a1a1a; color: #e0e0e0; padding: 40px; text-align: center; }
        h1 { color: #ff6b6b; }
    </style>
</head>
<body>
    <h1>Configuration Error</h1>
    <p>HTML interface file not found. Please ensure index.html is present in:</p>
    <ul style="list-style: none;">
        <li>/sd/www/index.html</li>
        <li>www/index.html</li>
        <li>src/www/index.html</li>
    </ul>
</body>
</html>"""

    async def start(self):
        """Start the web server."""
        if not self.enabled:
            print("Web server disabled in config")
            return

        print("\n" + "="*50)
        print("   JEB Web Server Manager")
        print("="*50)

        # Connect to WiFi
        if not await self.connect_wifi():
            print("Failed to connect to WiFi - web server not started")
            return

        try:
            # Create server
            self.server = Server(self.pool, "/static", debug=True)

            # Setup routes
            self.setup_routes()

            # Start server
            self.server.start(self._get_ip_address(), self.port)

            print(f"\n✓ Web server started!")
            print(f"  URL: http://{self._get_ip_address()}")
            print(f"  Port: {self.port}")
            print("\nWeb server running... Press Ctrl+C to stop")

            self.log("Web server started")

            # Server loop with WiFi reconnection
            while True:
                try:
                    # Check WiFi connection status
                    if not self._is_wifi_connected():
                        print("WiFi disconnected! Attempting to reconnect...")
                        self.connected = False
                        self.log("WiFi connection lost")

                        # Try to reconnect
                        if await self.connect_wifi():
                            print("WiFi reconnected successfully")
                            self.log("WiFi reconnected")
                            # Recreate server with new socket pool
                            self.server.stop()
                            self.server = Server(self.pool, "/static", debug=True)
                            self.setup_routes()
                            self.server.start(self._get_ip_address(), self.port)
                        else:
                            print("WiFi reconnection failed, retrying in 5 seconds...")
                            await asyncio.sleep(5)
                            continue

                    # Poll server only when WiFi is connected
                    self.server.poll()
                    await asyncio.sleep(0.01)
                except Exception as e:
                    print(f"Server error: {e}")
                    self.log(f"Server error: {e}")
                    await asyncio.sleep(1)

        except KeyboardInterrupt:
            print("\nShutting down web server...")
            self.log("Web server stopped")
        except Exception as e:
            print(f"Web server error: {e}")
            self.log(f"Web server error: {e}")
        finally:
            self.disconnect_wifi()

    async def stop(self):
        """Stop the web server."""
        if self.server:
            self.server.stop()
        self.disconnect_wifi()
        print("Web server stopped")
