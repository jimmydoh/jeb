#!/usr/bin/env python3
"""
Example script to download and verify MPY files using the manifest.

This script demonstrates how to:
1. Download the manifest.json from GitHub Actions artifacts
2. Download individual .mpy files
3. Verify file integrity using SHA256 hashes
4. Copy files to a CircuitPython device

Usage:
    python download_mpy_files.py [--verify] [--output-dir OUTPUT_DIR]

Note: This is an example script. You'll need to modify it to work with your
specific GitHub Actions artifact download method.
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path


def calculate_sha256(filepath):
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def verify_file(filepath, expected_hash):
    """Verify a file's SHA256 hash matches the expected value."""
    actual_hash = calculate_sha256(filepath)
    return actual_hash == expected_hash


def load_manifest(manifest_path):
    """Load the manifest.json file."""
    with open(manifest_path, 'r') as f:
        return json.load(f)


def verify_all_files(mpy_dir, manifest):
    """Verify all files in the directory match the manifest."""
    print("Verifying files...")
    success_count = 0
    fail_count = 0
    
    for file_info in manifest['files']:
        filepath = os.path.join(mpy_dir, file_info['path'])
        
        if not os.path.exists(filepath):
            print(f"  ✗ Missing: {file_info['path']}")
            fail_count += 1
            continue
        
        if verify_file(filepath, file_info['sha256']):
            print(f"  ✓ Verified: {file_info['path']}")
            success_count += 1
        else:
            print(f"  ✗ Hash mismatch: {file_info['path']}")
            fail_count += 1
    
    print()
    print(f"Verification complete: {success_count} verified, {fail_count} failed")
    return fail_count == 0


def copy_to_circuitpy(source_dir, circuitpy_mount="/media/CIRCUITPY"):
    """Copy files to a CircuitPython device."""
    if not os.path.exists(circuitpy_mount):
        print(f"Error: CircuitPython device not found at {circuitpy_mount}")
        return False
    
    print(f"Copying files to {circuitpy_mount}...")
    
    for root, dirs, files in os.walk(source_dir):
        for file in files:
            if file.endswith('.mpy'):
                src_path = os.path.join(root, file)
                rel_path = os.path.relpath(src_path, source_dir)
                dst_path = os.path.join(circuitpy_mount, rel_path)
                
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                
                # Copy file
                import shutil
                shutil.copy2(src_path, dst_path)
                print(f"  ✓ Copied: {rel_path}")
    
    print("Copy complete!")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Download and verify MPY files from manifest"
    )
    parser.add_argument(
        '--verify',
        action='store_true',
        help='Verify all files against manifest hashes'
    )
    parser.add_argument(
        '--output-dir',
        default='./mpy',
        help='Directory containing the mpy files (default: ./mpy)'
    )
    parser.add_argument(
        '--manifest',
        default='./manifest.json',
        help='Path to manifest.json (default: ./manifest.json)'
    )
    parser.add_argument(
        '--copy-to-circuitpy',
        metavar='MOUNT_PATH',
        help='Copy files to CircuitPython device at the specified mount path'
    )
    
    args = parser.parse_args()
    
    # Check if manifest exists
    if not os.path.exists(args.manifest):
        print(f"Error: Manifest not found at {args.manifest}")
        print()
        print("To use this script:")
        print("1. Download the 'manifest' and 'mpy-files' artifacts from GitHub Actions")
        print("2. Extract them to the current directory")
        print("3. Run this script with --verify to verify file integrity")
        sys.exit(1)
    
    # Load manifest
    manifest = load_manifest(args.manifest)
    print(f"Loaded manifest version {manifest['version']}")
    print(f"Build timestamp: {manifest['build_timestamp']}")
    print(f"Total files: {len(manifest['files'])}")
    print()
    
    # Verify files if requested
    if args.verify:
        if not verify_all_files(args.output_dir, manifest):
            sys.exit(1)
    
    # Copy to CircuitPython if requested
    if args.copy_to_circuitpy:
        if not copy_to_circuitpy(args.output_dir, args.copy_to_circuitpy):
            sys.exit(1)
    
    print("Done!")


if __name__ == '__main__':
    main()
