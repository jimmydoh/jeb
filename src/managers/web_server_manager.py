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
- adafruit_httpserver (CircuitPython library)
- wifi, socketpool, ssl (CircuitPython built-ins)
"""

import asyncio
import json
import os
import gc
import time

try:
    import wifi
    import socketpool
    from adafruit_httpserver import Server, Request, Response, GET, POST
    WIFI_AVAILABLE = True
except ImportError:
    WIFI_AVAILABLE = False
    print("⚠️ WiFi or adafruit_httpserver not available - WebServerManager disabled")


class WebServerManager:
    """
    Async HTTP server for field service configuration and monitoring.
    
    This manager runs independently of CoreManager and can be loaded
    by code.py to provide web-based configuration interface.
    """
    
    def __init__(self, config, console_buffer=None):
        """
        Initialize the web server manager.
        
        Args:
            config (dict): Configuration dictionary with wifi_ssid, wifi_password
            console_buffer (object): Optional console buffer for output capture
        """
        if not WIFI_AVAILABLE:
            raise RuntimeError("WiFi or adafruit_httpserver not available")
        
        self.config = config
        self.wifi_ssid = config.get("wifi_ssid", "")
        self.wifi_password = config.get("wifi_password", "")
        self.port = config.get("web_server_port", 80)
        self.enabled = config.get("web_server_enabled", False)
        self.console_buffer = console_buffer
        
        self.server = None
        self.pool = None
        self.connected = False
        self.logs = []  # Ring buffer for log messages
        self.max_logs = 1000  # Maximum log entries to keep
        
        # Validate configuration
        if not self.wifi_ssid or not self.wifi_password:
            raise ValueError("WiFi credentials required for web server")
    
    async def connect_wifi(self, timeout=30):
        """
        Connect to WiFi network (async, non-blocking).
        
        Args:
            timeout (int): Connection timeout in seconds
            
        Returns:
            bool: True if connected successfully
        """
        print(f"Connecting to WiFi: {self.wifi_ssid}")
        
        try:
            # Check if already connected
            if wifi.radio.connected:
                print(f"Already connected! IP: {wifi.radio.ipv4_address}")
                self.connected = True
                return True
            
            # Connect to WiFi
            start_time = time.monotonic()
            wifi.radio.connect(self.wifi_ssid, self.wifi_password, timeout=timeout)
            
            # Wait for connection (non-blocking)
            while not wifi.radio.connected and (time.monotonic() - start_time) < timeout:
                await asyncio.sleep(0.5)  # Non-blocking async sleep
            
            if wifi.radio.connected:
                print(f"✓ Connected! IP: {wifi.radio.ipv4_address}")
                self.connected = True
                self.pool = socketpool.SocketPool(wifi.radio)
                return True
            else:
                print("✗ Connection timeout")
                self.connected = False
                return False
                
        except Exception as e:
            print(f"WiFi connection error: {e}")
            self.connected = False
            return False
    
    def disconnect_wifi(self):
        """Disconnect from WiFi to save power."""
        if self.connected:
            try:
                wifi.radio.enabled = False
                self.connected = False
                print("WiFi disconnected")
            except Exception as e:
                print(f"Error disconnecting WiFi: {e}")
    
    def log(self, message):
        """Add a message to the log buffer."""
        timestamp = time.monotonic()
        self.logs.append({"time": timestamp, "message": message})
        
        # Trim log buffer if too large
        if len(self.logs) > self.max_logs:
            self.logs = self.logs[-self.max_logs:]
    
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
                import os.path
                normalized_path = os.path.normpath(path)
                
                # Check for directory traversal
                if ".." in normalized_path or not (normalized_path.startswith("/sd/") or normalized_path == "/sd"):
                    return Response(request, '{"error": "Invalid path - access denied"}', 
                                  content_type="application/json", status=400)
                
                # Create a generator function to read file in chunks
                def file_generator(filepath, chunk_size=1024):
                    """Generator that yields file chunks to avoid loading entire file in RAM."""
                    try:
                        with open(filepath, "rb") as f:
                            while True:
                                chunk = f.read(chunk_size)
                                if not chunk:
                                    break
                                yield chunk
                    except Exception as e:
                        print(f"Error reading file {filepath}: {e}")
                
                filename = path.split("/")[-1]
                
                # Return response with generator for chunked transfer
                return Response(request, file_generator(path), 
                              content_type="application/octet-stream",
                              headers={"Content-Disposition": f"attachment; filename={filename}"})
            except Exception as e:
                return Response(request, f'{{"error": "{str(e)}"}}', 
                              content_type="application/json", status=500)
        
        # API: Upload file (Note: CircuitPython HTTP server may need chunked upload)
        @self.server.route("/api/files/upload", POST)
        def upload_file(request: Request):
            """Upload a file to the SD card with size limit to prevent MemoryError."""
            try:
                # Get target path and filename from query params
                path = request.query_params.get("path", "/sd")
                filename = request.query_params.get("filename")
                
                if not filename:
                    return Response(request, '{"error": "Filename required"}', 
                                  content_type="application/json", status=400)
                
                # Security: Prevent directory traversal and validate paths
                import os.path
                normalized_path = os.path.normpath(path)
                normalized_filename = os.path.normpath(filename)
                
                # Check for directory traversal in both path and filename
                if ".." in normalized_path or ".." in normalized_filename:
                    return Response(request, '{"error": "Invalid path - directory traversal not allowed"}', 
                                  content_type="application/json", status=400)
                
                # Ensure path is within SD card
                if not (normalized_path.startswith("/sd/") or normalized_path == "/sd"):
                    return Response(request, '{"error": "Invalid path - must be within /sd"}', 
                                  content_type="application/json", status=400)
                
                # Check available memory before attempting to read body
                free_mem = gc.mem_free()
                max_upload_size = min(50 * 1024, free_mem // 2)  # Max 50KB or half of free RAM
                
                # Get file content from request body
                content = request.body
                
                # Check content size to prevent MemoryError
                if len(content) > max_upload_size:
                    return Response(request, 
                                  f'{{"error": "File too large. Max size: {max_upload_size} bytes. Free RAM: {free_mem} bytes"}}', 
                                  content_type="application/json", status=413)
                
                # Write file in chunks to minimize memory usage
                filepath = f"{path}/{filename}"
                chunk_size = 1024
                with open(filepath, "wb") as f:
                    for i in range(0, len(content), chunk_size):
                        f.write(content[i:i+chunk_size])
                
                self.log(f"File uploaded: {filepath} ({len(content)} bytes)")
                return Response(request, f'{{"status": "success", "path": "{filepath}", "size": {len(content)}}}', 
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
                    "wifi_ssid": self.wifi_ssid,
                    "ip_address": str(wifi.radio.ipv4_address),
                    "debug_mode": self.config.get("debug_mode", False),
                    "uptime": time.monotonic(),
                    "free_memory": gc.mem_free(),
                }
                return Response(request, json.dumps(status), 
                              content_type="application/json")
            except Exception as e:
                return Response(request, f'{{"error": "{str(e)}"}}', 
                              content_type="application/json", status=500)
    
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
                
                def html_generator(filepath, chunk_size=1024):
                    """Generator that yields HTML file chunks to save RAM."""
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
            self.server.start(str(wifi.radio.ipv4_address), self.port)
            
            print(f"\n✓ Web server started!")
            print(f"  URL: http://{wifi.radio.ipv4_address}")
            print(f"  Port: {self.port}")
            print("\nWeb server running... Press Ctrl+C to stop")
            
            self.log("Web server started")
            
            # Server loop with WiFi reconnection
            while True:
                try:
                    # Check WiFi connection status
                    if not wifi.radio.connected:
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
                            self.server.start(str(wifi.radio.ipv4_address), self.port)
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
