"""
ota_updater.py - Interactive Over-The-Air (OTA) Update Mode

This mode provides a dedicated UI for the user to trigger Wi-Fi updates,
handle read-only USB states, and repair SD card assets.
It completely replaces the old standalone updater.py script.
"""

import asyncio
import json
import os
import hashlib
import time
import microcontroller

from .utility_mode import UtilityMode


class UpdaterError(Exception):
    """Custom exception for updater errors."""
    pass


class AsyncOTAEngine:
    """Handles the raw network and filesystem operations for the update."""

    def __init__(self, update_url, wifi_manager):
        self.update_url = update_url.rstrip("/")
        self.wifi_manager = wifi_manager
        self.manifest = None
        self.remote_version = None
        self.http_session = None
        self.download_dir = "/sd/update"

    def is_core_writable(self):
        """Hardware check to see if USB is locking the internal flash."""
        try:
            with open('/.fs_test', 'w') as f:
                f.write('1')
            os.remove('/.fs_test')
            return True
        except OSError:
            return False

    async def connect(self):
        if not self.wifi_manager.connect(timeout=30):
            raise UpdaterError("Wi-Fi connection failed")
        self.http_session = self.wifi_manager.create_http_session()
        if not self.http_session:
            raise UpdaterError("Failed to create HTTP session")

    def disconnect(self):
        self.wifi_manager.disconnect()

    def get_local_version(self):
        try:
            with open("version.json", "r") as f:
                return json.load(f)
        except OSError:
            return None

    def write_local_version(self):
        if not self.manifest: return
        try:
            v_info = {
                "version": self.manifest["version"],
                "file_count": len(self.manifest["files"])
            }
            with open("version.json", "w") as f:
                json.dump(v_info, f)
        except OSError:
            pass

    async def fetch_manifest(self):
        """Fetches remote version and then full manifest if valid."""
        v_url = f"{self.update_url}/version.json"
        response = None
        try:
            response = self.http_session.get(v_url, timeout=10)
            if response.status_code != 200:
                raise UpdaterError("Failed to fetch version.json")
            self.remote_version = response.json()
        finally:
            if response: response.close()

        m_url = f"{self.update_url}/manifest.json"
        response = None
        try:
            response = self.http_session.get(m_url, timeout=10)
            if response.status_code != 200:
                raise UpdaterError("Failed to fetch manifest.json")
            self.manifest = response.json()
        finally:
            if response: response.close()

    async def verify_files(self, sd_only=False):
        """Compares local hashes to the manifest."""
        files_to_update = []
        for f_info in self.manifest["files"]:
            action = f_info.get("action", "update")
            dest = f_info.get("destination", f"/{f_info['path']}")
            expected_hash = f_info["sha256"]

            if action == "ignore_if_frozen":
                continue
            if sd_only and not dest.startswith("/sd/"):
                continue

            local_hash = None
            try:
                h = hashlib.sha256()
                with open(dest, "rb") as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        h.update(chunk)
                local_hash = h.hexdigest()
            except OSError:
                pass # File missing

            if local_hash != expected_hash:
                files_to_update.append(f_info)

            await asyncio.sleep(0) # Yield so system doesn't hang on large SD card scans

        return files_to_update

    def check_disk_space(self, files_to_update):
        """Calculates exact net-change for internal flash overwrites."""
        staging_needed = int(sum(f.get("size", 0) for f in files_to_update) * 1.1)
        try:
            sd_stat = os.statvfs("/sd")
            if (sd_stat[0] * sd_stat[3]) < staging_needed:
                raise UpdaterError("Insufficient SD staging space")
        except OSError:
            pass

        flash_net_change = 0
        for f in files_to_update:
            dest = f.get("destination", f"/{f['path']}")
            if not dest.startswith("/sd/"):
                try:
                    current_size = os.stat(dest)[6]
                except OSError:
                    current_size = 0
                flash_net_change += (f.get("size", 0) - current_size)

        flash_needed = max(0, flash_net_change) + 8192
        try:
            flash_stat = os.statvfs("/")
            if (flash_stat[0] * flash_stat[3]) < flash_needed:
                raise UpdaterError("Insufficient internal flash space")
        except OSError:
            pass

    async def download_file(self, file_info, progress_cb):
        download_path = file_info["download_path"]
        local_path = f"{self.download_dir}/{file_info['path']}"
        file_url = f"{self.update_url}/{self.remote_version['version']}/{download_path}"

        # Ensure dir
        d_dir = os.path.dirname(local_path)
        if d_dir:
            try: os.makedirs(d_dir)
            except OSError: pass

        response = None
        try:
            response = self.http_session.get(file_url, timeout=30)
            if response.status_code != 200:
                raise UpdaterError(f"HTTP {response.status_code} on {download_path}")

            hasher = hashlib.sha256()
            downloaded = 0
            with open(local_path, "wb") as f:
                for chunk in response.iter_content(1024):
                    if not chunk: continue
                    f.write(chunk)
                    hasher.update(chunk)
                    downloaded += len(chunk)
                    progress_cb(downloaded)
                    await asyncio.sleep(0) # Keep UI alive during big downloads!

            if hasher.hexdigest() != file_info["sha256"]:
                raise UpdaterError("Hash mismatch after download")
        finally:
            if response: response.close()

    async def install_file(self, file_info):
        src = f"{self.download_dir}/{file_info['path']}"
        dest = file_info.get("destination", f"/{file_info['path']}")

        d_dir = os.path.dirname(dest)
        if d_dir and d_dir not in ["", "/", "/sd"]:
            try: os.makedirs(d_dir)
            except OSError: pass

        with open(src, "rb") as s, open(dest, "wb") as d:
            while True:
                chunk = s.read(4096)
                if not chunk: break
                d.write(chunk)
                await asyncio.sleep(0) # Keep UI alive

        try: os.remove(src)
        except OSError: pass


class OtaUpdater(UtilityMode):
    """Admin mode UI for executing firmware updates."""

    def __init__(self, core):
        super().__init__(core, name="SYSTEM UPDATE", description="OTA Firmware Updater", timeout=None)

        # NOTE: Update this URL to point to your actual GitHub Releases structure
        self.update_url = core.config.get("update_url", "https://github.com/jimmydoh/jeb/releases/download/latest")
        self.engine = AsyncOTAEngine(self.update_url, core.wifi)

        self.core_writable = False
        self.menu_options = []
        self.selected_idx = 0

    def _render_menu(self):
        """Renders the main selection menu."""
        self.core.display.use_standard_layout()
        self.core.display.update_header("SYSTEM UPDATE")

        if not self.core_writable:
            status_text = "USB LOCK ACTIVE"
            options_text = f"[{self.menu_options[self.selected_idx]}]"
            self.core.display.update_footer("SD Assets Only | W=Exit")
        else:
            status_text = "SELECT ACTION"
            options_text = f"[{self.menu_options[self.selected_idx]}]"
            self.core.display.update_footer("Tap=Select | W=Exit")

        self.core.display.update_status(status_text, options_text)

    async def run(self):
        """Main state machine loop."""

        # 1. Hardware Permissions Check
        self.core_writable = self.engine.is_core_writable()

        if self.core_writable:
            self.menu_options = ["FULL FIRMWARE UPDATE", "REPAIR SD ASSETS", "EXIT"]
        else:
            self.menu_options = ["REPAIR SD ASSETS (ONLY)", "EXIT"]

        self.core.hid.flush()
        self.core.hid.reset_encoder(0)
        last_pos = 0

        self._render_menu()

        # 2. Menu Loop
        while True:
            curr_pos = self.core.hid.encoder_position()
            enc_diff = curr_pos - last_pos
            enc_tap = self.core.hid.is_encoder_button_pressed(action="tap")
            btn_b_long = self.core.hid.is_button_pressed(1, action="hold", duration=1500)

            if enc_diff != 0:
                self.touch()
                self.selected_idx = (self.selected_idx + enc_diff) % len(self.menu_options)
                self._render_menu()
                last_pos = curr_pos

            if btn_b_long or (enc_tap and self.menu_options[self.selected_idx] == "EXIT"):
                self.core.audio.play("audio/menu/close.wav", self.core.audio.CH_SFX)
                self.core.mode = "DASHBOARD"
                return "CANCELLED"

            if enc_tap:
                self.touch()
                self.core.audio.play("audio/menu/select.wav", self.core.audio.CH_SFX)
                selection = self.menu_options[self.selected_idx]

                if "FULL" in selection:
                    await self._perform_update(sd_only=False)
                elif "REPAIR" in selection:
                    await self._perform_update(sd_only=True)
                return "FINISHED"

            await asyncio.sleep(0.02)

    async def _perform_update(self, sd_only):
        """Executes the actual update sequence with live OLED feedback."""
        try:
            self.core.display.update_header("CONNECTING...")
            self.core.display.update_status("WIFI", "Joining Network")
            self.core.display.update_footer("")
            await self.engine.connect()

            self.core.display.update_header("CHECKING...")
            self.core.display.update_status("MANIFEST", "Fetching versions")
            await self.engine.fetch_manifest()

            # Version Check (Skip if we are just repairing SD assets)
            if not sd_only:
                local_v = self.engine.get_local_version()
                remote_v = self.engine.manifest["version"]
                if local_v and local_v.get("version") == remote_v:
                    self.core.display.update_header("UP TO DATE")
                    self.core.display.update_status(f"v{remote_v}", "No update required")
                    self.core.display.update_footer("Exiting in 3s...")
                    await asyncio.sleep(3)
                    self.core.mode = "DASHBOARD"
                    return

            self.core.display.update_header("SCANNING...")
            self.core.display.update_status("LOCAL FILES", "Calculating hashes")
            files_to_update = await self.engine.verify_files(sd_only=sd_only)

            if not files_to_update:
                self.core.display.update_header("UP TO DATE")
                self.core.display.update_status("ALL FILES MATCH", "No changes needed")
                self.core.display.update_footer("Exiting in 3s...")
                await asyncio.sleep(3)
                self.core.mode = "DASHBOARD"
                return

            self.engine.check_disk_space(files_to_update)

            # --- DOWNLOAD PHASE ---
            total_files = len(files_to_update)
            for idx, f_info in enumerate(files_to_update, 1):
                fname = f_info["path"].split("/")[-1]
                fsize = f_info["size"]

                # Setup the live progress callback
                def update_progress(downloaded_bytes):
                    pct = int((downloaded_bytes / fsize) * 100) if fsize > 0 else 100
                    self.core.display.update_header(f"DL [{idx}/{total_files}]")
                    self.core.display.update_status(fname[:16], f"{pct}% ({downloaded_bytes//1024}kb)")

                await self.engine.download_file(f_info, update_progress)

            # --- INSTALL PHASE ---
            for idx, f_info in enumerate(files_to_update, 1):
                fname = f_info["path"].split("/")[-1]
                self.core.display.update_header(f"INSTALL [{idx}/{total_files}]")
                self.core.display.update_status("WRITING TO DISK", fname[:16])
                await self.engine.install_file(f_info)

            # --- FINALIZE ---
            if not sd_only:
                self.engine.write_local_version()

            self.core.display.update_header("SUCCESS")
            self.core.display.update_status("UPDATE COMPLETE", "Rebooting...")
            self.core.audio.play("audio/menu/success.wav", self.core.audio.CH_SFX)
            await asyncio.sleep(2)
            microcontroller.reset()

        except UpdaterError as e:
            self.core.display.update_header("UPDATE FAILED")
            self.core.display.update_status("ERROR:", str(e)[:16])
            self.core.display.update_footer("Exiting in 5s...")
            self.core.audio.play("audio/menu/error.wav", self.core.audio.CH_SFX)
            await asyncio.sleep(5)
            self.core.mode = "DASHBOARD"

        finally:
            self.engine.disconnect()
