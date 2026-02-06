"""
updater.py - Over-The-Air (OTA) Firmware Update Module

This module handles automatic firmware updates for the Raspberry Pi Pico 2W
via Wi-Fi, using a manifest-based file synchronization approach.

Features:
- Wi-Fi connection management
- Manifest-based delta updates
- SHA256 file verification
- Safe abort on errors
- Version tracking
"""

import json
import os
import hashlib
import time

# MicroPython/CircuitPython imports
try:
    import wifi
    import socketpool
    import ssl
    import adafruit_requests
    import microcontroller
    WIFI_AVAILABLE = True
except ImportError:
    WIFI_AVAILABLE = False
    print("⚠️ Wi-Fi libraries not available - updater will not function")


class UpdaterError(Exception):
    """Custom exception for updater errors."""
    pass


class Updater:
    """
    OTA Firmware Updater for Raspberry Pi Pico 2W.
    
    This class manages the entire update process including:
    - Connecting to Wi-Fi
    - Downloading and parsing manifest
    - Verifying local files against manifest
    - Downloading only changed files
    - Writing version information
    """
    
    def __init__(self, config):
        """
        Initialize the updater with configuration.
        
        Args:
            config (dict): Configuration dictionary containing:
                - wifi_ssid: Wi-Fi network name
                - wifi_password: Wi-Fi password
                - update_url: URL to manifest.json
        """
        self.config = config
        self.wifi_ssid = config.get("wifi_ssid")
        self.wifi_password = config.get("wifi_password")
        self.update_url = config.get("update_url")
        self.manifest = None
        self.http_session = None
        
        # Validate configuration
        if not WIFI_AVAILABLE:
            raise UpdaterError("Wi-Fi libraries not available")
        
        if not all([self.wifi_ssid, self.wifi_password, self.update_url]):
            raise UpdaterError(
                "Missing required config: wifi_ssid, wifi_password, or update_url"
            )
    
    def connect_wifi(self, timeout=30):
        """
        Connect to Wi-Fi network.
        
        Args:
            timeout (int): Connection timeout in seconds
            
        Returns:
            bool: True if connected successfully
            
        Raises:
            UpdaterError: If connection fails
        """
        print(f"Connecting to Wi-Fi: {self.wifi_ssid}")
        
        try:
            # Check if already connected
            if wifi.radio.connected:
                print("Already connected to Wi-Fi")
                return True
            
            # Connect to Wi-Fi
            wifi.radio.connect(self.wifi_ssid, self.wifi_password, timeout=timeout)
            
            # Wait for connection
            start_time = time.monotonic()
            while not wifi.radio.connected and (time.monotonic() - start_time) < timeout:
                print(".", end="")
                time.sleep(1)
            print()
            
            if wifi.radio.connected:
                print(f"✓ Connected! IP: {wifi.radio.ipv4_address}")
                
                # Initialize HTTP session
                pool = socketpool.SocketPool(wifi.radio)
                self.http_session = adafruit_requests.Session(pool, ssl.create_default_context())
                return True
            else:
                raise UpdaterError("Wi-Fi connection timeout")
                
        except Exception as e:
            raise UpdaterError(f"Wi-Fi connection failed: {e}")
    
    def disconnect_wifi(self):
        """Disconnect from Wi-Fi to save power."""
        if WIFI_AVAILABLE and wifi.radio.connected:
            wifi.radio.enabled = False
            print("Wi-Fi disconnected")
    
    def fetch_manifest(self):
        """
        Download and parse the remote manifest file.
        
        Returns:
            dict: Parsed manifest dictionary
            
        Raises:
            UpdaterError: If download or parsing fails
        """
        print(f"Fetching manifest from: {self.update_url}")
        
        try:
            response = self.http_session.get(self.update_url, timeout=10)
            
            if response.status_code != 200:
                raise UpdaterError(
                    f"Failed to fetch manifest: HTTP {response.status_code}"
                )
            
            # Parse JSON
            self.manifest = response.json()
            response.close()
            
            # Validate manifest structure
            if "version" not in self.manifest or "files" not in self.manifest:
                raise UpdaterError("Invalid manifest structure")
            
            print(f"✓ Manifest fetched: version {self.manifest['version']}")
            print(f"  Files in manifest: {len(self.manifest['files'])}")
            
            return self.manifest
            
        except Exception as e:
            raise UpdaterError(f"Failed to fetch manifest: {e}")
    
    @staticmethod
    def calculate_sha256(filepath):
        """
        Calculate SHA256 hash of a file.
        
        Args:
            filepath (str): Path to file
            
        Returns:
            str: Hex-encoded SHA256 hash, or None if file doesn't exist
        """
        try:
            sha256_hash = hashlib.sha256()
            with open(filepath, "rb") as f:
                while True:
                    chunk = f.read(4096)
                    if not chunk:
                        break
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except OSError:
            return None
    
    @staticmethod
    def file_exists(filepath):
        """Check if a file exists."""
        try:
            os.stat(filepath)
            return True
        except OSError:
            return False
    
    def verify_files(self):
        """
        Compare local files with manifest to identify changes.
        
        Returns:
            tuple: (files_to_update, files_ok) lists
        """
        if not self.manifest:
            raise UpdaterError("No manifest loaded")
        
        files_to_update = []
        files_ok = []
        
        print("Verifying local files...")
        
        for file_info in self.manifest["files"]:
            path = file_info["path"]
            expected_hash = file_info["sha256"]
            
            # Calculate local hash
            local_hash = self.calculate_sha256(path)
            
            if local_hash is None:
                print(f"  ✗ Missing: {path}")
                files_to_update.append(file_info)
            elif local_hash != expected_hash:
                print(f"  ✗ Modified: {path}")
                files_to_update.append(file_info)
            else:
                files_ok.append(file_info)
        
        print(f"\n✓ Verification complete:")
        print(f"  Files OK: {len(files_ok)}")
        print(f"  Files to update: {len(files_to_update)}")
        
        return files_to_update, files_ok
    
    def download_file(self, file_info):
        """
        Download a single file from the remote server.
        
        Args:
            file_info (dict): File information from manifest
            
        Returns:
            bool: True if successful
            
        Raises:
            UpdaterError: If download fails
        """
        path = file_info["path"]
        download_path = file_info["download_path"]
        expected_hash = file_info["sha256"]
        size = file_info["size"]
        
        # Construct full URL (assuming base URL is the directory containing manifest)
        base_url = self.update_url.rsplit("/", 1)[0]
        file_url = f"{base_url}/{download_path}"
        
        print(f"Downloading: {path} ({size} bytes)")
        
        try:
            # Create directory if needed
            dir_path = path.rsplit("/", 1)[0] if "/" in path else ""
            if dir_path:
                try:
                    os.makedirs(dir_path)
                except OSError:
                    pass  # Directory already exists
            
            # Download file
            response = self.http_session.get(file_url, timeout=30)
            
            if response.status_code != 200:
                raise UpdaterError(
                    f"Failed to download {path}: HTTP {response.status_code}"
                )
            
            # Write to file
            with open(path, "wb") as f:
                f.write(response.content)
            
            response.close()
            
            # Verify hash
            actual_hash = self.calculate_sha256(path)
            if actual_hash != expected_hash:
                raise UpdaterError(
                    f"Hash mismatch for {path}: expected {expected_hash}, got {actual_hash}"
                )
            
            print(f"  ✓ Downloaded and verified: {path}")
            return True
            
        except Exception as e:
            raise UpdaterError(f"Failed to download {path}: {e}")
    
    def update_files(self, files_to_update):
        """
        Download all files that need updating.
        
        Args:
            files_to_update (list): List of file info dictionaries
            
        Returns:
            bool: True if all files updated successfully
        """
        total = len(files_to_update)
        
        if total == 0:
            print("No files need updating")
            return True
        
        print(f"\nDownloading {total} file(s)...")
        
        success_count = 0
        for i, file_info in enumerate(files_to_update, 1):
            print(f"\n[{i}/{total}] ", end="")
            try:
                self.download_file(file_info)
                success_count += 1
            except UpdaterError as e:
                print(f"  ✗ Error: {e}")
                return False
        
        print(f"\n✓ Successfully updated {success_count}/{total} files")
        return success_count == total
    
    def write_version_info(self):
        """
        Write version.json file to track current firmware version.
        
        Returns:
            bool: True if successful
        """
        if not self.manifest:
            raise UpdaterError("No manifest loaded")
        
        # Format timestamp as ISO string for JSON serialization
        try:
            current_time = time.localtime()
            update_timestamp = "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}Z".format(
                current_time[0], current_time[1], current_time[2],
                current_time[3], current_time[4], current_time[5]
            )
        except Exception:
            update_timestamp = "unknown"
        
        version_info = {
            "version": self.manifest["version"],
            "build_timestamp": self.manifest.get("build_timestamp", "unknown"),
            "update_timestamp": update_timestamp,
            "file_count": len(self.manifest["files"])
        }
        
        try:
            with open("version.json", "w") as f:
                json.dump(version_info, f)
            print(f"✓ Version info written: {version_info['version']}")
            return True
        except Exception as e:
            print(f"⚠️ Failed to write version.json: {e}")
            return False
    
    def check_current_version(self):
        """
        Check the currently installed version.
        
        Returns:
            dict: Version info, or None if not found
        """
        try:
            with open("version.json", "r") as f:
                return json.load(f)
        except OSError:
            return None
    
    def run_update(self):
        """
        Execute the complete update process.
        
        Returns:
            bool: True if update completed successfully
        """
        print("\n" + "="*50)
        print("   OTA FIRMWARE UPDATE")
        print("="*50 + "\n")
        
        try:
            # Check current version
            current_version = self.check_current_version()
            if current_version:
                print(f"Current version: {current_version.get('version', 'unknown')}")
            else:
                print("No version.json found (first boot)")
            
            # Step 1: Connect to Wi-Fi
            self.connect_wifi()
            
            # Step 2: Fetch manifest
            self.fetch_manifest()
            
            # Check if update is needed
            if current_version and current_version.get("version") == self.manifest["version"]:
                print(f"\n✓ Already up to date: {self.manifest['version']}")
                return True
            
            # Step 3: Verify files
            files_to_update, files_ok = self.verify_files()
            
            # Step 4: Update files
            if not self.update_files(files_to_update):
                raise UpdaterError("File update failed")
            
            # Step 5: Write version info
            self.write_version_info()
            
            print("\n" + "="*50)
            print("   UPDATE COMPLETE")
            print("="*50 + "\n")
            
            return True
            
        except UpdaterError as e:
            print(f"\n❌ Update failed: {e}")
            print("Aborting update - existing firmware will be used")
            return False
            
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            print("Aborting update - existing firmware will be used")
            return False
            
        finally:
            # Always disconnect Wi-Fi
            self.disconnect_wifi()
    
    def reboot(self):
        """Reboot the microcontroller."""
        print("\nRebooting...")
        time.sleep(1)
        microcontroller.reset()


def should_check_for_updates():
    """
    Determine if the system should check for updates.
    
    Returns:
        bool: True if update check is needed
    """
    # Check for update flag file
    try:
        os.stat(".update_flag")
        return True
    except OSError:
        pass
    
    # Check for missing version.json (first boot)
    try:
        os.stat("version.json")
        return False  # version.json exists, normal boot
    except OSError:
        return True  # version.json missing, first boot


def trigger_update():
    """Create update flag file to trigger update on next boot."""
    try:
        with open(".update_flag", "w") as f:
            f.write("1")
        print("Update flag created - update will run on next boot")
        return True
    except Exception as e:
        print(f"Failed to create update flag: {e}")
        return False


def clear_update_flag():
    """Remove update flag file."""
    try:
        os.remove(".update_flag")
    except OSError:
        pass  # File doesn't exist, that's fine
