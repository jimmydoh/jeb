import os
import json
import shutil
import time

def find_circuitpy_drive():
    """Scans Windows drives for the CIRCUITPY volume."""
    print("Scanning for CIRCUITPY drive...")
    for drive_letter in "DEFGHIJKLMNPQRSTUVWXYZ":
        drive = f"{drive_letter}:\\"
        if os.path.exists(drive) and os.path.exists(os.path.join(drive, "boot_out.txt")):
            # Simple heuristic: boot_out.txt is almost always present on CircuitPython
            print(f"  ✓ Found CIRCUITPY at {drive}")
            return drive
    return None

def main():
    print("="*50)
    print(" JEB Master Bootstrapper (Windows)")
    print("="*50)

    # 1. Locate Manifest
    if not os.path.exists("manifest.json"):
        print("❌ Error: manifest.json not found!")
        print("Please run this script from the folder containing your extracted release.")
        time.sleep(3)
        return

    with open("manifest.json", "r") as f:
        manifest = json.load(f)

    print(f"Loaded manifest version: {manifest.get('version', 'unknown')}")

    # 2. Locate Drives
    circuitpy_drive = find_circuitpy_drive()
    if not circuitpy_drive:
        circuitpy_drive = input("Could not auto-detect CIRCUITPY. Enter drive letter (e.g., E:\\): ").strip().upper()
        if not circuitpy_drive.endswith(":\\"):
            circuitpy_drive += ":\\"

    sd_drive = input("\nEnter SD Card drive letter (e.g., F:\\) or press Enter to skip SD files: ").strip().upper()
    if sd_drive and not sd_drive.endswith(":\\"):
        sd_drive += ":\\"

    # 3. Process Files
    print("\nStarting file transfer...")
    copied_count = 0
    ignored_count = 0
    error_count = 0

    for file_info in manifest.get("files", []):
        action = file_info.get("action", "update")
        dest_rule = file_info.get("destination", "")
        source_path = file_info.get("download_path", "")

        # Skip frozen files
        if action == "ignore_if_frozen":
            ignored_count += 1
            continue

        if not os.path.exists(source_path):
            print(f"  ❌ Missing source: {source_path}")
            error_count += 1
            continue

        # Route to the correct physical drive
        if dest_rule.startswith("/sd/"):
            if not sd_drive:
                continue # User skipped SD card
            # Strip '/sd/' and prepend Windows drive letter
            rel_dest = dest_rule[4:]
            target_path = os.path.join(sd_drive, rel_dest.replace("/", "\\"))
        else:
            # Strip leading '/' and prepend CircuitPy drive letter
            rel_dest = dest_rule.lstrip("/")
            target_path = os.path.join(circuitpy_drive, rel_dest.replace("/", "\\"))

        # Create directories and copy
        try:
            target_dir = os.path.dirname(target_path)
            if target_dir:
                os.makedirs(target_dir, exist_ok=True)

            shutil.copy2(source_path, target_path)
            print(f"  ✓ Copied -> {target_path}")
            copied_count += 1
        except Exception as e:
            print(f"  ❌ Failed to copy {source_path}: {e}")
            error_count += 1

    print("\n" + "="*50)
    print(f" Bootstrap Complete")
    print(f" Copied:  {copied_count}")
    print(f" Ignored: {ignored_count} (Frozen OS files)")
    print(f" Errors:  {error_count}")
    print("="*50)

if __name__ == "__main__":
    main()
