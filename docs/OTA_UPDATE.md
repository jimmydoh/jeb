# OTA Firmware Update System

## Overview

The JEB system implements a robust Over-The-Air (OTA) firmware update mechanism for the Raspberry Pi Pico 2W. This allows wireless firmware updates without physical USB access, using a manifest-based file synchronization approach.

## Architecture

### Key Components

1. **`src/updater.py`**: Core update module handling:
   - Wi-Fi connectivity
   - Manifest download and parsing
   - File verification (SHA256)
   - Delta updates (only changed files)
   - Error handling and safe rollback

2. **`src/boot.py`**: Boot-time detection and filesystem control:
   - Detects first boot or update flag
   - Toggles filesystem permissions
   - Controls USB mass storage access

3. **`src/code.py`**: Integration point:
   - Checks for update requirements
   - Triggers updater before main application
   - Handles update failures gracefully

## Configuration

Add the following fields to your `config.json`:

```json
{
  "wifi_ssid": "YOUR_WIFI_SSID",
  "wifi_password": "YOUR_WIFI_PASSWORD",
  "update_url": "https://your-server.com/manifest.json",
  ... other config ...
}
```

**Security Note**: Always use HTTPS for `update_url` to prevent man-in-the-middle attacks.

## Manifest Format

The manifest is a JSON file hosted on your server that defines the desired firmware state:

```json
{
  "version": "0.1.0",
  "build_timestamp": "2026-02-06T11:33:14Z",
  "files": [
    {
      "path": "boot.mpy",
      "download_path": "mpy/boot.mpy",
      "sha256": "c2dde4b80967920d03184350367707da580f607bb11de98782ac660c0eb2c7fe",
      "size": 240
    },
    {
      "path": "code.mpy",
      "download_path": "mpy/code.mpy",
      "sha256": "70e957c544a38a8f021c3de993993b165a924a4f690943f885c0a3ddda32ccc7",
      "size": 2561
    }
  ]
}
```

### Manifest Fields

- **version**: Semantic version string
- **build_timestamp**: ISO 8601 UTC timestamp
- **files**: Array of file objects:
  - **path**: Target path on device (relative to root)
  - **download_path**: Remote path for download (relative to manifest URL)
  - **sha256**: SHA256 hash for verification
  - **size**: File size in bytes

## Update Process

### 1. First Boot Detection

On first boot, the system:
1. Detects missing `version.json`
2. Mounts filesystem as writable
3. Disables USB mass storage
4. Triggers update check

### 2. Update Flag

To trigger an update on an existing installation, create `.update_flag`:

```python
from updater import trigger_update
trigger_update()
# Reboot to apply
```

### 3. Update Flow

```
┌─────────────────┐
│  Boot (boot.py) │
└────────┬────────┘
         │
         ├─→ Check for version.json
         │   or .update_flag
         │
         ├─→ Update needed?
         │   ├─ Yes: Mount writable, disable USB
         │   └─ No:  Mount read-only, enable USB
         │
┌────────▼────────┐
│ Main (code.py)  │
└────────┬────────┘
         │
         ├─→ Update mode detected?
         │   └─ Yes: Run updater
         │
┌────────▼────────┐
│    Updater      │
├─────────────────┤
│ 1. Connect WiFi │
│ 2. Fetch Manifest│
│ 3. Verify Files │
│ 4. Download Δ   │
│ 5. Write version.json│
│ 6. Reboot       │
└─────────────────┘
```

### 4. File Verification

The updater compares local files against the manifest:

1. Calculate SHA256 of local file
2. Compare with manifest hash
3. If missing or mismatch → download
4. If match → skip (already up to date)

### 5. Delta Updates

Only files that are missing or changed are downloaded, reducing:
- Download time
- Network usage
- Flash write cycles

### 6. Safety Features

- **Graceful Abort**: If Wi-Fi fails or manifest is unreachable, boot existing firmware
- **Hash Verification**: Each downloaded file is verified against SHA256
- **Atomic Writes**: Files are written completely before verification
- **USB Lockout**: USB mass storage disabled during update to prevent corruption
- **Version Tracking**: `version.json` records successful updates

## Version Tracking

After a successful update, `version.json` is created/updated:

```json
{
  "version": "0.1.0",
  "build_timestamp": "2026-02-06T11:33:14Z",
  "update_timestamp": "2026-02-06T20:15:30Z",
  "file_count": 42
}
```

## Error Handling

### Connection Failures

If Wi-Fi connection fails:
- Update aborts after 30-second timeout
- Device continues with existing firmware
- Error logged to console

### Manifest Download Failures

If manifest cannot be fetched:
- Update aborts
- Device continues with existing firmware
- Check `update_url` configuration

### File Download Failures

If a file download fails:
- Update aborts (doesn't proceed with partial update)
- Device continues with existing firmware
- Retry on next boot (update flag remains)

### Hash Mismatch

If downloaded file hash doesn't match manifest:
- File is rejected
- Update aborts
- Prevents corrupted firmware

## CI/CD Integration

The GitHub Actions workflow automatically generates manifests:

```yaml
# .github/workflows/build-mpy.yml
- name: Generate manifest.json and version.json
  run: |
    python3 << 'EOF'
    # ... manifest generation code ...
    EOF
```

Artifacts are uploaded and can be deployed to your update server.

## Testing

Run the updater test suite:

```bash
python3 tests/test_updater.py
```

Test coverage includes:
- File existence checks
- SHA256 calculation
- Config validation
- Update detection logic
- Version tracking
- Mock Wi-Fi operations

## Best Practices

1. **Always use HTTPS** for update URLs
2. **Test updates** in a staging environment first
3. **Monitor update failures** and investigate patterns
4. **Keep manifests immutable** - use versioned URLs
5. **Maintain update server availability** for critical deployments
6. **Document version changes** for troubleshooting
7. **Consider rollback strategy** for failed updates

## Troubleshooting

### Update Not Triggering

**Symptom**: Device doesn't check for updates

**Checks**:
- Is `wifi_ssid` and `update_url` configured in `config.json`?
- Does `version.json` exist? (delete to trigger first boot)
- Is `.update_flag` present? (create to force update)

### Wi-Fi Connection Fails

**Symptom**: "Wi-Fi connection failed" error

**Checks**:
- Verify SSID and password in `config.json`
- Check Wi-Fi signal strength
- Ensure Pico 2W is in range
- Try connecting to Wi-Fi manually

### Manifest Not Found

**Symptom**: "Failed to fetch manifest: HTTP 404"

**Checks**:
- Verify `update_url` is correct and accessible
- Check manifest file exists on server
- Test URL in web browser
- Ensure HTTPS certificate is valid

### Hash Mismatch

**Symptom**: "Hash mismatch for {file}"

**Checks**:
- Verify manifest hashes are correct
- Re-generate manifest from clean build
- Check for file corruption on server
- Ensure no proxies are modifying content

## Security Considerations

1. **Use HTTPS**: Prevents man-in-the-middle attacks
2. **Verify Hashes**: SHA256 ensures file integrity
3. **Atomic Updates**: Partial updates are rejected
4. **Access Control**: Secure your update server
5. **Certificate Validation**: Ensure SSL certificates are valid
6. **Network Segmentation**: Consider separate network for updates

## Future Enhancements

Potential improvements for future versions:

- [ ] Signed manifests for authenticity verification
- [ ] Incremental file patches (binary diff)
- [ ] Multi-server fallback for reliability
- [ ] Update scheduling (time windows)
- [ ] Bandwidth throttling
- [ ] Progress callbacks for UI feedback
- [ ] Automatic rollback on boot failures

## Dependencies

Required CircuitPython libraries:
- `wifi` - Wi-Fi connectivity
- `socketpool` - Network socket operations
- `ssl` - HTTPS support
- `adafruit_requests` - HTTP client
- `hashlib` - SHA256 hashing (built-in)

## API Reference

### Updater Class

```python
from updater import Updater

config = {
    "wifi_ssid": "MyNetwork",
    "wifi_password": "password123",
    "update_url": "https://example.com/manifest.json"
}

updater = Updater(config)
success = updater.run_update()

if success:
    updater.reboot()
```

### Helper Functions

```python
from updater import (
    should_check_for_updates,
    trigger_update,
    clear_update_flag
)

# Check if update is needed
if should_check_for_updates():
    # ... run update ...

# Trigger update on next boot
trigger_update()

# Clear update flag
clear_update_flag()
```

## License

This OTA update system is part of the JEB project and is licensed under the MIT License.
