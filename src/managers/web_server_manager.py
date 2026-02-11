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
    
    def connect_wifi(self, timeout=30):
        """
        Connect to WiFi network.
        
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
            
            # Wait for connection
            while not wifi.radio.connected and (time.monotonic() - start_time) < timeout:
                time.sleep(0.5)
            
            if wifi.radio.connected:
                print(f"✓ Connected! IP: {wifi.radio.ipv4_address}")
                self.connected = True
                self.pool = socketpool.SocketPool(wifi.radio)
                return True
            else:
                print("✗ Connection timeout")
                return False
                
        except Exception as e:
            print(f"WiFi connection error: {e}")
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
                
                # Update config (validate critical fields)
                for key, value in data.items():
                    if key not in ["role", "type_id"]:  # Protect critical fields
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
            """Download a file from the SD card."""
            try:
                path = request.query_params.get("path")
                if not path:
                    return Response(request, '{"error": "Path required"}', 
                                  content_type="application/json", status=400)
                
                # Security: Prevent directory traversal
                if ".." in path:
                    return Response(request, '{"error": "Invalid path"}', 
                                  content_type="application/json", status=400)
                
                # Read file
                with open(path, "rb") as f:
                    content = f.read()
                
                filename = path.split("/")[-1]
                return Response(request, content, 
                              content_type="application/octet-stream",
                              headers={"Content-Disposition": f"attachment; filename={filename}"})
            except Exception as e:
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
                with open("/sd/UPDATE_FLAG.txt", "w") as f:
                    f.write("UPDATE_REQUESTED\n")
                
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
        """Generate the main HTML configuration page."""
        return """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JEB Field Service Configurator</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            background: #1a1a1a;
            color: #e0e0e0;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        h1 {
            color: #4CAF50;
            margin-bottom: 30px;
            font-size: 2em;
        }
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            border-bottom: 2px solid #333;
        }
        .tab {
            padding: 10px 20px;
            background: #2a2a2a;
            border: none;
            color: #e0e0e0;
            cursor: pointer;
            border-radius: 5px 5px 0 0;
        }
        .tab.active {
            background: #4CAF50;
            color: white;
        }
        .tab-content {
            display: none;
            padding: 20px;
            background: #2a2a2a;
            border-radius: 0 5px 5px 5px;
        }
        .tab-content.active {
            display: block;
        }
        .form-group {
            margin-bottom: 15px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            color: #b0b0b0;
        }
        input, textarea, select {
            width: 100%;
            padding: 8px;
            background: #1a1a1a;
            border: 1px solid #444;
            color: #e0e0e0;
            border-radius: 3px;
        }
        button {
            padding: 10px 20px;
            background: #4CAF50;
            color: white;
            border: none;
            border-radius: 3px;
            cursor: pointer;
            margin-right: 10px;
        }
        button:hover {
            background: #45a049;
        }
        button.secondary {
            background: #666;
        }
        button.secondary:hover {
            background: #555;
        }
        .status {
            margin-top: 10px;
            padding: 10px;
            border-radius: 3px;
        }
        .status.success {
            background: #2d5016;
            color: #90EE90;
        }
        .status.error {
            background: #501616;
            color: #ffcccb;
        }
        .file-list {
            list-style: none;
        }
        .file-item {
            padding: 8px;
            background: #1a1a1a;
            margin-bottom: 5px;
            border-radius: 3px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .file-item:hover {
            background: #333;
        }
        .log-viewer {
            background: #1a1a1a;
            padding: 10px;
            height: 400px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            border: 1px solid #444;
            border-radius: 3px;
        }
        .info-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .info-card {
            background: #1a1a1a;
            padding: 15px;
            border-radius: 5px;
            border: 1px solid #444;
        }
        .info-card h3 {
            color: #4CAF50;
            margin-bottom: 10px;
            font-size: 0.9em;
        }
        .info-card .value {
            font-size: 1.5em;
            color: #e0e0e0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔧 JEB Field Service Configurator</h1>
        
        <div class="tabs">
            <button class="tab active" onclick="showTab('system')">System Status</button>
            <button class="tab" onclick="showTab('config')">Configuration</button>
            <button class="tab" onclick="showTab('files')">File Browser</button>
            <button class="tab" onclick="showTab('logs')">Logs</button>
            <button class="tab" onclick="showTab('console')">Console</button>
            <button class="tab" onclick="showTab('actions')">Actions</button>
        </div>
        
        <div id="system" class="tab-content active">
            <h2>System Status</h2>
            <div class="info-grid" id="systemStatus"></div>
            <button onclick="loadSystemStatus()">Refresh Status</button>
        </div>
        
        <div id="config" class="tab-content">
            <h2>Global Configuration</h2>
            <form id="configForm">
                <div class="form-group">
                    <label>WiFi SSID:</label>
                    <input type="text" name="wifi_ssid" id="wifi_ssid">
                </div>
                <div class="form-group">
                    <label>WiFi Password:</label>
                    <input type="password" name="wifi_password" id="wifi_password">
                </div>
                <div class="form-group">
                    <label>Update URL:</label>
                    <input type="text" name="update_url" id="update_url">
                </div>
                <div class="form-group">
                    <label>Debug Mode:</label>
                    <select name="debug_mode" id="debug_mode">
                        <option value="false">Disabled</option>
                        <option value="true">Enabled</option>
                    </select>
                </div>
                <button type="button" onclick="loadConfig()">Load Current Config</button>
                <button type="button" onclick="saveConfig()">Save Configuration</button>
            </form>
            <div id="configStatus" class="status" style="display:none;"></div>
        </div>
        
        <div id="files" class="tab-content">
            <h2>File Browser</h2>
            <div>
                <label>Current Path: <span id="currentPath">/sd</span></label>
                <button onclick="loadFiles()">Refresh</button>
            </div>
            <ul class="file-list" id="fileList"></ul>
        </div>
        
        <div id="logs" class="tab-content">
            <h2>System Logs</h2>
            <button onclick="loadLogs()">Refresh Logs</button>
            <div class="log-viewer" id="logViewer"></div>
        </div>
        
        <div id="console" class="tab-content">
            <h2>Console Output</h2>
            <button onclick="loadConsole()">Refresh Console</button>
            <div class="log-viewer" id="consoleViewer"></div>
        </div>
        
        <div id="actions" class="tab-content">
            <h2>Field Service Actions</h2>
            <div class="form-group">
                <button onclick="triggerOTAUpdate()">Trigger OTA Update</button>
                <p style="color: #b0b0b0; margin-top: 5px;">Device will update on next boot</p>
            </div>
            <div class="form-group">
                <button onclick="toggleDebugMode()">Toggle Debug Mode</button>
                <p style="color: #b0b0b0; margin-top: 5px;">Enable/disable debug logging</p>
            </div>
            <div id="actionStatus" class="status" style="display:none;"></div>
        </div>
    </div>
    
    <script>
        let currentPath = '/sd';
        
        function showTab(tabName) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById(tabName).classList.add('active');
            
            // Auto-load content for some tabs
            if (tabName === 'system') loadSystemStatus();
            if (tabName === 'files') loadFiles();
            if (tabName === 'logs') loadLogs();
        }
        
        async function loadSystemStatus() {
            try {
                const response = await fetch('/api/system/status');
                const data = await response.json();
                
                const html = `
                    <div class="info-card">
                        <h3>WiFi SSID</h3>
                        <div class="value">${data.wifi_ssid}</div>
                    </div>
                    <div class="info-card">
                        <h3>IP Address</h3>
                        <div class="value">${data.ip_address}</div>
                    </div>
                    <div class="info-card">
                        <h3>Debug Mode</h3>
                        <div class="value">${data.debug_mode ? 'ON' : 'OFF'}</div>
                    </div>
                    <div class="info-card">
                        <h3>Uptime</h3>
                        <div class="value">${Math.floor(data.uptime)}s</div>
                    </div>
                    <div class="info-card">
                        <h3>Free Memory</h3>
                        <div class="value">${Math.floor(data.free_memory / 1024)}KB</div>
                    </div>
                `;
                document.getElementById('systemStatus').innerHTML = html;
            } catch (error) {
                showStatus('systemStatus', 'Error loading status: ' + error, 'error');
            }
        }
        
        async function loadConfig() {
            try {
                const response = await fetch('/api/config/global');
                const config = await response.json();
                
                document.getElementById('wifi_ssid').value = config.wifi_ssid || '';
                document.getElementById('wifi_password').value = config.wifi_password || '';
                document.getElementById('update_url').value = config.update_url || '';
                document.getElementById('debug_mode').value = config.debug_mode ? 'true' : 'false';
                
                showStatus('configStatus', 'Configuration loaded', 'success');
            } catch (error) {
                showStatus('configStatus', 'Error loading config: ' + error, 'error');
            }
        }
        
        async function saveConfig() {
            try {
                const config = {
                    wifi_ssid: document.getElementById('wifi_ssid').value,
                    wifi_password: document.getElementById('wifi_password').value,
                    update_url: document.getElementById('update_url').value,
                    debug_mode: document.getElementById('debug_mode').value === 'true'
                };
                
                const response = await fetch('/api/config/global', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(config)
                });
                
                if (response.ok) {
                    showStatus('configStatus', 'Configuration saved successfully', 'success');
                } else {
                    showStatus('configStatus', 'Error saving configuration', 'error');
                }
            } catch (error) {
                showStatus('configStatus', 'Error: ' + error, 'error');
            }
        }
        
        async function loadFiles() {
            try {
                const response = await fetch(`/api/files?path=${encodeURIComponent(currentPath)}`);
                const data = await response.json();
                
                const fileList = document.getElementById('fileList');
                fileList.innerHTML = '';
                
                // Add parent directory link if not at root
                if (currentPath !== '/sd' && currentPath !== '/') {
                    const li = document.createElement('li');
                    li.className = 'file-item';
                    li.innerHTML = `
                        <span>📁 ..</span>
                        <button class="secondary" onclick="navigateUp()">Up</button>
                    `;
                    fileList.appendChild(li);
                }
                
                // Add files and directories
                data.items.forEach(item => {
                    const li = document.createElement('li');
                    li.className = 'file-item';
                    const icon = item.is_dir ? '📁' : '📄';
                    const size = item.is_dir ? '' : ` (${formatSize(item.size)})`;
                    
                    li.innerHTML = `
                        <span>${icon} ${item.name}${size}</span>
                        <div>
                            ${item.is_dir ? 
                                `<button class="secondary" onclick="navigateTo('${item.path}')">Open</button>` :
                                `<button class="secondary" onclick="downloadFile('${item.path}')">Download</button>`
                            }
                        </div>
                    `;
                    fileList.appendChild(li);
                });
                
                document.getElementById('currentPath').textContent = currentPath;
            } catch (error) {
                console.error('Error loading files:', error);
            }
        }
        
        function navigateTo(path) {
            currentPath = path;
            loadFiles();
        }
        
        function navigateUp() {
            const parts = currentPath.split('/');
            parts.pop();
            currentPath = parts.join('/') || '/';
            loadFiles();
        }
        
        function downloadFile(path) {
            window.location.href = `/api/files/download?path=${encodeURIComponent(path)}`;
        }
        
        function formatSize(bytes) {
            if (bytes < 1024) return bytes + ' B';
            if (bytes < 1024 * 1024) return Math.floor(bytes / 1024) + ' KB';
            return Math.floor(bytes / (1024 * 1024)) + ' MB';
        }
        
        async function loadLogs() {
            try {
                const response = await fetch('/api/logs');
                const logs = await response.json();
                
                const logViewer = document.getElementById('logViewer');
                logViewer.innerHTML = logs.map(log => 
                    `[${Math.floor(log.time)}s] ${log.message}`
                ).join('<br>');
                
                // Scroll to bottom
                logViewer.scrollTop = logViewer.scrollHeight;
            } catch (error) {
                document.getElementById('logViewer').innerHTML = 'Error loading logs: ' + error;
            }
        }
        
        async function loadConsole() {
            try {
                const response = await fetch('/api/console');
                const data = await response.json();
                
                document.getElementById('consoleViewer').innerHTML = data.output.replace(/\\n/g, '<br>');
            } catch (error) {
                document.getElementById('consoleViewer').innerHTML = 'Error loading console: ' + error;
            }
        }
        
        async function triggerOTAUpdate() {
            if (!confirm('Trigger OTA update? Device will update on next boot.')) return;
            
            try {
                const response = await fetch('/api/actions/ota-update', { method: 'POST' });
                const data = await response.json();
                
                if (response.ok) {
                    showStatus('actionStatus', 'OTA update scheduled for next boot', 'success');
                } else {
                    showStatus('actionStatus', 'Error: ' + data.error, 'error');
                }
            } catch (error) {
                showStatus('actionStatus', 'Error: ' + error, 'error');
            }
        }
        
        async function toggleDebugMode() {
            try {
                const response = await fetch('/api/actions/toggle-debug', { method: 'POST' });
                const data = await response.json();
                
                if (response.ok) {
                    showStatus('actionStatus', 'Debug mode toggled successfully', 'success');
                    loadSystemStatus();  // Refresh status
                } else {
                    showStatus('actionStatus', 'Error: ' + data.error, 'error');
                }
            } catch (error) {
                showStatus('actionStatus', 'Error: ' + error, 'error');
            }
        }
        
        function showStatus(elementId, message, type) {
            const status = document.getElementById(elementId);
            status.textContent = message;
            status.className = 'status ' + type;
            status.style.display = 'block';
            setTimeout(() => {
                status.style.display = 'none';
            }, 5000);
        }
        
        // Auto-load initial data
        loadSystemStatus();
    </script>
</body>
</html>
"""
    
    async def start(self):
        """Start the web server."""
        if not self.enabled:
            print("Web server disabled in config")
            return
        
        print("\n" + "="*50)
        print("   JEB Web Server Manager")
        print("="*50)
        
        # Connect to WiFi
        if not self.connect_wifi():
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
            
            # Server loop
            while True:
                try:
                    self.server.poll()
                    await asyncio.sleep(0.01)
                except Exception as e:
                    print(f"Server error: {e}")
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
