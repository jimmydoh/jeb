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
  "update_url": "https://your-server.com",
  ... other config ...
}
```

**Important Notes**: 
- Always use HTTPS for `update_url` to prevent man-in-the-middle attacks
- `update_url` should be the base URL (not including manifest.json)
- SD card must be mounted for OTA updates (files stage to `/sd/update/`)

## Server File Structure

The update server should host files in this structure:

```
https://your-server.com/
├── version.json         (tiny file checked first)
├── manifest.json        (full manifest)
└── 0.1.0/              (version folder)
    └── mpy/
        ├── boot.mpy
        ├── code.mpy
        └── ...
```

### version.json (Checked First)

Small file (~200 bytes) checked first to determine if an update is needed:

```json
{
  "version": "0.1.0",
  "build_timestamp": "2026-02-06T11:33:14Z",
  "file_count": 42,
  "total_size": 125840
}
```

## Manifest Format

The manifest is a JSON file at `{update_url}/manifest.json` that defines the complete firmware state:

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
  - **download_path**: Remote path for download (relative to version folder)
  - **sha256**: SHA256 hash for verification
  - **size**: File size in bytes

### File Download URLs

Files are downloaded from: `{update_url}/{version}/{download_path}`

Example: `https://your-server.com/0.1.0/mpy/boot.mpy`

## Filesystem Permissions

The OTA system uses CircuitPython's filesystem permissions to safely manage updates:

### Normal Mode (Default)
- **Code Access**: Read-only (`storage.remount("/", readonly=True)`)
  - Running CircuitPython code cannot write to the filesystem
  - Prevents accidental file modifications by application code
- **USB Access**: Writable (USB mass storage enabled)
  - Host computer can read and write files via USB
  - Users can manually edit `config.json` or create `.update_flag`
  
**Important**: In CircuitPython, `readonly=True` only restricts code access, not USB access. This is by design and allows manual file management while protecting against code errors.

### Update Mode
- **Code Access**: Writable (`storage.remount("/", readonly=False)`)
  - Updater can download and install firmware files
  - Can write `version.json` and clear `.update_flag`
- **USB Access**: Disabled (`storage.disable_usb_drive()`)
  - Prevents host computer from interfering during update
  - Ensures atomic updates without USB interference

## Update Process

### 1. First Boot Detection

On first boot, the system:
1. `boot.py` initializes SD card at `/sd`
2. Detects missing `version.json`
3. Mounts filesystem as writable
4. Disables USB mass storage
5. Triggers update check

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
├─────────────────┤
│ 1. Init SD card │
│ 2. Check update │
│    flag/version │
│ 3. Toggle perms │
└────────┬────────┘
         │
┌────────▼────────┐
│ Main (code.py)  │
└────────┬────────┘
         │
         ├─→ SD mounted?
         │   └─ No: Skip update
         │
┌────────▼────────┐
│    Updater      │
├─────────────────┤
│ 1. Connect WiFi │
│ 2. Fetch        │
│    version.json │
│ 3. Version      │
│    changed?     │
│    └─ No: Exit  │
│ 4. Fetch full   │
│    manifest     │
│ 5. Verify files │
│ 6. Download to  │
│    /sd/update/  │
│ 7. Install from │
│    SD to flash  │
│ 8. Write        │
│    version.json │
│ 9. Reboot       │
└─────────────────┘
```

### 4. Version Check Optimization

The updater first downloads a tiny `version.json` (~200 bytes) to check if an update is needed:

1. Compare remote version with local version
2. If versions match → skip update (saves bandwidth)
3. If versions differ → download full manifest and update

### 5. File Download and Staging

Files are downloaded to SD card staging area then installed to flash:

1. Download to `/sd/update/{path}`
2. Verify SHA256 hash
3. Copy from `/sd/update/{path}` to `/{path}` (internal flash)
4. Verify SHA256 hash again after installation
5. Create subdirectories as needed (e.g., `lib/`, `managers/`)

**Important**: Files are now automatically installed from SD staging to internal flash during the update process. The flash is writable because `boot.py` has already unlocked it in update mode.

### 6. File Verification

The updater compares local files against the manifest:

1. Calculate SHA256 of local file
2. Compare with manifest hash
3. If missing or mismatch → download
4. If match → skip (already up to date)

### 7. Delta Updates

Only files that are missing or changed are downloaded, reducing:
- Download time
- Network usage
- Flash write cycles

### 8. Safety Features

- **Graceful Abort**: If Wi-Fi fails or manifest is unreachable, boot existing firmware
- **Hash Verification**: Each downloaded file is verified against SHA256
- **Atomic Writes**: Files are written completely before verification
- **USB Lockout**: USB mass storage disabled during update to prevent corruption
- **Version Tracking**: `version.json` records successful updates
- **SD Card Required**: Updates require SD card for staging (flash is read-only)
- **Update Flag Persistence**: Failed updates preserve flag for automatic retry on next boot
- **Zombie Prevention**: Only clears update flag on successful completion (prevents devices with partially updated firmware from becoming unrecoverable)

### 9. Update Flag and Retry Logic

The system uses an intelligent flag management strategy to prevent devices from becoming unrecoverable after partial updates:

**Flag Cleared (No Retry):**
- Update completed successfully
- SD card not mounted (cannot proceed)
- Wi-Fi credentials missing (cannot proceed)

**Flag Preserved (Automatic Retry):**
- Update failed during download
- Update failed during installation
- Fatal error/exception occurred
- Power loss or crash during update

**Recovery Scenario:**
```
1. Update starts, downloads 5 of 10 files
2. Power loss occurs during file installation
3. Device reboots with mix of old and new firmware files
4. boot.py detects preserved update flag
5. Mounts filesystem as writable
6. Updater automatically retries the full update
7. All files are re-downloaded and installed (overwrites partial state)
8. Update completes successfully, flag cleared
9. Device reboots into consistent new firmware
```

This prevents the scenario where a device has inconsistent firmware (mix of old and new files) with no way to self-heal.

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
- **Update flag preserved** - automatic retry on next boot
- Device continues with existing firmware
- Error logged to console

### Manifest Download Failures

If manifest cannot be fetched:
- Update aborts
- **Update flag preserved** - automatic retry on next boot
- Device continues with existing firmware
- Check `update_url` configuration

### File Download Failures

If a file download fails:
- Update aborts (doesn't proceed with partial update)
- **Update flag preserved** - automatic retry on next boot
- Device continues with existing firmware
- Next boot will retry the complete update

### Installation Failures

If file installation to flash fails:
- Installation aborts immediately
- **Update flag preserved** - automatic retry on next boot
- Already-installed files remain on flash
- Next boot will retry the complete update (overwrites partial files)

### Hash Mismatch

If downloaded file hash doesn't match manifest:
- File is rejected
- Update aborts
- **Update flag preserved** - automatic retry on next boot
- Prevents corrupted firmware from being installed

### Power Loss During Update

If power is lost during update:
- **Update flag preserved** automatically
- On next boot, device detects flag and retries
- Complete update process runs again
- Device self-heals from partial/corrupted state

**Note**: Only successful completion of the entire update process clears the flag and prevents retry.

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
import os

# Check if SD card is mounted (do not import boot.py)
def is_sd_mounted():
    try:
        return 'sd' in os.listdir('/')
    except OSError:
        return False

SD_MOUNTED = is_sd_mounted()

config = {
    "wifi_ssid": "MyNetwork",
    "wifi_password": "password123",
    "update_url": "https://example.com"  # Base URL, not manifest.json
}

# SD card must be mounted
updater = Updater(config, sd_mounted=SD_MOUNTED)
success = updater.run_update()

if success:
    updater.reboot()
```

**Important**: Do not import `boot.py` in your code as it will cause re-execution. Instead, check the filesystem state directly using `os.listdir('/')`.

### Update Process Methods

```python
# Step-by-step update process
updater.connect_wifi()                        # Connect to Wi-Fi
updater.fetch_remote_version()                # Fetch version.json (small file)
updater.fetch_manifest()                      # Fetch full manifest if needed
files_to_update, _ = updater.verify_files()   # Compare with local
updater.update_files(files_to_update)         # Download to /sd/update/
updater.install_files(files_to_update)        # Install from SD to flash
updater.write_version_info()                  # Write version.json
updater.reboot()                              # Reboot to apply
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
