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

from utilities.logger import JEBLogger

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

    def __init__(self, config, wifi_manager, console_buffer=None, power_manager=None, satellite_manager=None):
        """
        Initialize the web server manager.

        Args:
            config (dict): Configuration dictionary
            wifi_manager (WiFiManager): REQUIRED: Shared WiFiManager instance for managing WiFi connectivity.
            console_buffer (object): Optional console buffer for output capture
            power_manager (PowerManager): Optional PowerManager for live telemetry
            satellite_manager (SatelliteNetworkManager): Optional SatelliteNetworkManager for link telemetry
        """
        if wifi_manager is None:
            JEBLogger.warning("WEBS", "No WiFiManager provided - WebServerManager cannot start")
            raise RuntimeError("No WiFiManager provided")

        self.config = config
        self.port = config.get("web_server_port", 80)
        self.enabled = config.get("web_server_enabled", False)
        self.wifi_manager = wifi_manager

        self.console_buffer = console_buffer
        self.power_manager = power_manager
        self.satellite_manager = satellite_manager

        self.server = None
        self.pool = None
        self.connected = False
        self.logs = []  # Ring buffer for log messages
        self.max_logs = self.DEFAULT_MAX_LOGS  # Maximum log entries to keep

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
                        with open(filepath, "rb") as f:
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

                with open(filepath, "wb") as f:
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
            """Return mode settings from data manager."""
            try:
                # Load mode settings from data manager if available
                # For now, return example structure showing available modes
                modes_data = {
                    "SIMON": {
                        "settings": [
                            {"key": "mode", "label": "MODE", "options": ["CLASSIC", "REVERSE", "BLIND"], "default": "CLASSIC"},
                            {"key": "difficulty", "label": "DIFF", "options": ["EASY", "NORMAL", "HARD", "INSANE"], "default": "NORMAL"}
                        ],
                        "current": {
                            "mode": "CLASSIC",
                            "difficulty": "NORMAL"
                        }
                    },
                    # Add more modes as needed
                }

                return Response(request, json.dumps(modes_data),
                              content_type="application/json")
            except Exception as e:
                return Response(request, f'{{"error": "{str(e)}"}}',
                              content_type="application/json", status=500)

        # API: Update mode settings
        @self.server.route("/api/config/modes", POST)
        def update_mode_settings(request: Request):
            """Update settings for a specific mode."""
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

                # Save settings (would integrate with DataManager in actual implementation)
                self.log(f"Mode settings updated for {mode_id}")

                return Response(request, '{"status": "success"}',
                              content_type="application/json")
            except Exception as e:
                self.log(f"Error updating mode settings: {e}")
                return Response(request, f'{{"error": "{str(e)}"}}',
                              content_type="application/json", status=500)

        # API: Get logs
        @self.server.route("/api/logs", GET)
        def get_logs(request: Request):
            """Return recent log messages."""
            return Response(request, json.dumps(self.logs),
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

        # API: Trigger OTA update
        @self.server.route("/api/actions/ota-update", POST)
        def trigger_ota_update(request: Request):
            """Trigger a manual OTA update."""
            try:
                # Set update flag
                try:
                    with open("/sd/UPDATE_FLAG.txt", "w") as f:
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

        # API: Real-time telemetry via Server-Sent Events (SSE)
        @self.server.route("/api/telemetry/stream", GET)
        def telemetry_stream(request: Request):
            """Stream live power and satellite telemetry as Server-Sent Events.

            Yields one JSON data event per second containing:
            - power: voltage readings from PowerManager (bus, logic, LED rails)
            - satellites: link state for each satellite in SatelliteNetworkManager
            - ts: monotonic timestamp

            SSE comment lines (': keepalive') are sent between data events to
            maintain the connection without flooding the client.
            """
            power_manager = self.power_manager
            satellite_manager = self.satellite_manager

            def sse_generator():
                # Emit the first event immediately by pre-dating the last emit time
                last_emit = time.monotonic() - 1.0
                while True:
                    now = time.monotonic()
                    if now - last_emit >= 1.0:
                        power_data = {}
                        if power_manager is not None:
                            try:
                                power_data = power_manager.status
                            except Exception:
                                pass

                        sat_data = {}
                        if satellite_manager is not None:
                            try:
                                for sid, sat in satellite_manager.satellites.items():
                                    sat_data[sid] = {"active": sat.is_active}
                            except Exception:
                                pass

                        payload = json.dumps({
                            "power": power_data,
                            "satellites": sat_data,
                            "ts": now,
                        })
                        last_emit = now
                        yield f"data: {payload}\n\n"
                    else:
                        # SSE comment used as keepalive between data events.
                        # Each yield returns control to adafruit_httpserver's poll()
                        # which sleeps ~10ms before calling next(), so CPU impact
                        # is minimal and no additional sleep is required here.
                        yield ": keepalive\n\n"

            return Response(
                request,
                sse_generator(),
                content_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

    def _save_config(self):
        """Save configuration to config.json."""
        try:
            with open("config.json", "w") as f:
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
                with open(html_path, "r") as test_f:
                    pass  # File exists, proceed

                def html_generator(filepath, chunk_size=None):
                    """Generator that yields HTML file chunks to save RAM."""
                    if chunk_size is None:
                        chunk_size = self.CHUNK_SIZE
                    with open(filepath, "r") as f:
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
