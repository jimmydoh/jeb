# Web-Based Field Service Configurator

## Overview

The Web-Based Field Service Configurator provides a browser-based interface for configuring and monitoring JEB systems without requiring physical access to the SD card. This feature is particularly useful for "field service" scenarios where technicians need to quickly adjust settings, view logs, or trigger updates remotely.

## Features

### 1. Configuration Management
- **Global Settings**: Edit WiFi credentials, OTA update URLs, debug mode, and other system-wide settings
- **Mode Settings**: Configure individual game mode settings (difficulty, game modes, etc.)
- **Persistent Storage**: All changes are saved to `config.json` and survive reboots

### 2. File Management
- **File Browser**: Navigate SD card filesystem
- **File Download**: Download files from the device to your computer
- **File Upload**: Upload new files or update existing ones
- **Security**: Directory traversal protection prevents access to unauthorized paths

### 3. System Monitoring
- **System Status**: View WiFi connection, IP address, debug mode, uptime, and memory usage
- **Logs**: View ring buffer of system log messages with timestamps
- **Console Output**: Access console output for debugging (if console buffer is configured)

### 4. Field Service Actions
- **OTA Update Trigger**: Manually trigger an over-the-air firmware update
- **Debug Mode Toggle**: Enable/disable debug logging on the fly
- **Satellite Reordering**: Reconfigure satellite ID ordering

## Setup

### 1. Dependencies

The web server requires the following CircuitPython libraries:
- `wifi` (built-in)
- `socketpool` (built-in)
- `adafruit_httpserver` (install via circup or manually)

Install using circup:
```bash
circup install adafruit_httpserver
```

### 2. Configuration

Add the following settings to your `config.json`:

```json
{
  "wifi_ssid": "YourWiFiNetwork",
  "wifi_password": "YourWiFiPassword",
  "web_server_enabled": true,
  "web_server_port": 80
}
```

**Configuration Options:**
- `wifi_ssid`: WiFi network name (required)
- `wifi_password`: WiFi password (required)
- `web_server_enabled`: Enable/disable the web server (default: `false`)
- `web_server_port`: HTTP port to listen on (default: `80`)

### 3. Starting the Web Server

The web server automatically starts with the main application when `web_server_enabled` is `true` in the configuration. It runs concurrently with the main JEB application using asyncio.

```python
# In code.py, the web server is automatically initialized:
if config.get("web_server_enabled", False):
    web_server = WebServerManager(config)
    # Server starts alongside main app
```

## Usage

### Accessing the Web Interface

1. Ensure the device is connected to WiFi
2. Find the device's IP address (shown on startup or in console output)
3. Open a web browser and navigate to: `http://<device-ip-address>`

Example: `http://192.168.1.100`

### Web Interface Tabs

#### System Status
Displays real-time system information:
- WiFi SSID and IP address
- Debug mode status
- System uptime
- Free memory

#### Configuration
Edit global configuration settings:
- WiFi credentials
- OTA update URL
- Debug mode toggle
- Other system settings

Changes are saved to `config.json` and persist across reboots.

#### Mode Settings
Configure individual game mode settings:
- Difficulty levels (Easy, Normal, Hard, Insane)
- Game mode variants (Classic, Reverse, Blind)
- Other mode-specific options

#### File Browser
Navigate and manage files on the SD card:
- Navigate directories
- Download files
- Upload new files
- View file sizes

#### Logs
View system log messages:
- Timestamped log entries
- Ring buffer (keeps last 1000 messages)
- Auto-scroll to latest messages

#### Console
View console output:
- Real-time console messages
- Useful for debugging
- Requires console buffer configuration

#### Actions
Field service operations:
- **Trigger OTA Update**: Schedules firmware update on next boot
- **Toggle Debug Mode**: Enable/disable debug logging immediately
- **Reorder Satellites**: Change satellite ID priority (if configured)

## API Reference

The web server exposes a RESTful JSON API:

### Configuration Endpoints

#### Get Global Configuration
```http
GET /api/config/global
```
Returns the current global configuration as JSON.

#### Update Global Configuration
```http
POST /api/config/global
Content-Type: application/json

{
  "wifi_ssid": "NewNetwork",
  "wifi_password": "NewPassword",
  "debug_mode": true
}
```
Updates global configuration. Critical fields (`role`, `type_id`) are protected.

#### Get Mode Settings
```http
GET /api/config/modes
```
Returns configuration for all game modes.

#### Update Mode Settings
```http
POST /api/config/modes
Content-Type: application/json

{
  "mode_id": "SIMON",
  "settings": {
    "difficulty": "HARD",
    "mode": "REVERSE"
  }
}
```

### File Management Endpoints

#### List Directory
```http
GET /api/files?path=/sd
```
Returns list of files and directories at the specified path.

#### Download File
```http
GET /api/files/download?path=/sd/config.json
```
Downloads the specified file.

#### Upload File
```http
POST /api/files/upload?path=/sd&filename=newfile.txt
Content-Type: application/octet-stream

[file content]
```
Uploads a file to the specified path.

### Monitoring Endpoints

#### Get System Status
```http
GET /api/system/status
```
Returns system status including WiFi, memory, uptime, etc.

#### Get Logs
```http
GET /api/logs
```
Returns recent log messages as JSON array.

#### Get Console Output
```http
GET /api/console
```
Returns recent console output.

### Action Endpoints

#### Trigger OTA Update
```http
POST /api/actions/ota-update
```
Schedules an OTA update for next boot.

#### Toggle Debug Mode
```http
POST /api/actions/toggle-debug
```
Toggles debug mode on/off immediately.

#### Reorder Satellites
```http
POST /api/actions/reorder-satellites
Content-Type: application/json

{
  "order": [1, 3, 2]
}
```

## Security Considerations

### Implemented Security Features

1. **Directory Traversal Protection**: Prevents `..` in file paths
2. **Protected Fields**: Critical config fields (`role`, `type_id`) cannot be modified
3. **Input Validation**: All user inputs are validated before processing
4. **Read-Only Operations**: Most endpoints are read-only by default

### Security Best Practices

1. **Network Security**: Use a secure WiFi network with strong encryption
2. **Change Default Credentials**: Update WiFi password after setup
3. **Limited Exposure**: Only enable web server when needed for field service
4. **Monitor Access**: Check logs regularly for unexpected access patterns

### Future Security Enhancements

Consider implementing these additional security features:
- Basic authentication (username/password)
- HTTPS/TLS encryption
- CSRF token protection
- Rate limiting
- Session management
- IP whitelist/blacklist

## Performance Considerations

### Memory Usage
- The web server uses approximately 15-20KB of RAM when running
- HTML page is generated dynamically (22KB)
- Log buffer limited to 1000 entries (configurable)

### CPU Impact
- Minimal impact on main application
- Async polling every 10ms
- WiFi operations may cause brief delays

### Network Traffic
- HTML page: ~22KB initial load
- API responses: typically <1KB
- File downloads: varies by file size

## Troubleshooting

### Web Server Won't Start

1. **Check WiFi Credentials**: Verify `wifi_ssid` and `wifi_password` in config.json
2. **Verify Dependencies**: Ensure `adafruit_httpserver` is installed
3. **Check Enable Flag**: Confirm `web_server_enabled: true` in config.json
4. **View Console Output**: Look for error messages during startup

### Cannot Access Web Interface

1. **Find IP Address**: Check console output for assigned IP
2. **Network Connectivity**: Ensure device and computer are on same network
3. **Firewall**: Check for firewall blocking port 80
4. **WiFi Signal**: Verify strong WiFi signal strength

### Configuration Changes Not Saving

1. **SD Card**: Ensure SD card is mounted and writable
2. **File Permissions**: Check config.json file permissions
3. **Disk Space**: Verify sufficient free space on SD card

### File Upload Fails

1. **File Size**: Large files may exceed memory limits
2. **Path Validation**: Ensure valid path without `..`
3. **SD Card**: Verify SD card is writable
4. **Memory**: Check available free memory

## Example Integration

### Standalone Web Server Mode

Run only the web server without the main application:

```python
import asyncio
from managers import WebServerManager

config = {
    "wifi_ssid": "MyNetwork",
    "wifi_password": "MyPassword",
    "web_server_enabled": True,
    "web_server_port": 80
}

web_server = WebServerManager(config)
asyncio.run(web_server.start())
```

### With Main Application

The web server runs concurrently with CoreManager:

```python
async def run_both():
    """Run both the main app and web server concurrently."""
    app_task = asyncio.create_task(app.start())
    web_task = asyncio.create_task(web_server.start())
    await asyncio.gather(app_task, web_task)

asyncio.run(run_both())
```

## Architecture

### Class Structure

```python
class WebServerManager:
    def __init__(self, config, console_buffer=None)
    def connect_wifi(self, timeout=30) -> bool
    def disconnect_wifi(self)
    def log(self, message)
    def setup_routes(self)
    async def start(self)
    async def stop(self)
```

### Request Flow

1. Browser sends HTTP request
2. `adafruit_httpserver` receives request
3. Route handler processes request
4. Handler performs operation (read/write config, etc.)
5. Response sent back to browser as JSON or HTML

### Concurrency Model

The web server uses CircuitPython's `asyncio` for concurrent operation:
- Main application runs in one async task
- Web server runs in another async task
- Both share the same event loop
- Non-blocking I/O ensures responsive operation

## Testing

Unit tests are available at `tests/test_web_server_manager.py`:

```bash
# Run unit tests
python3 tests/test_web_server_manager.py

# Run example/demo
python3 examples/test_web_server.py
```

Test coverage includes:
- Initialization and configuration
- WiFi connection management
- Log buffer operations
- Directory listing
- Configuration save/load
- HTML generation
- Route registration
- Invalid input handling

## References

- [adafruit_httpserver documentation](https://docs.circuitpython.org/projects/httpserver/en/latest/)
- [CircuitPython WiFi Guide](https://learn.adafruit.com/circuitpython-essentials/circuitpython-wifi)
- [OTA Update Documentation](OTA_UPDATE.md)
