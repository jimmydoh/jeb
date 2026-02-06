# Build MPY Files Workflow

This GitHub Action workflow compiles Python source files from the `src/` directory into MicroPython bytecode (`.mpy` files) using `mpy-cross` and generates a manifest file with download paths and checksums.

## Overview

The workflow:
1. Compiles all Python files in `src/` to `.mpy` bytecode format
2. Generates a `manifest.json` with file metadata (paths, SHA256 hashes, sizes)
3. Uploads artifacts for download
4. Creates release archives when tags are pushed

## Triggers

The workflow runs on:
- Push to `main` or `develop` branches (when `src/**/*.py` files change)
- Pull requests (when `src/**/*.py` files change)
- Manual trigger via `workflow_dispatch`

## Outputs

### 1. MPY Files Artifact

All successfully compiled `.mpy` files are uploaded as an artifact named `mpy-files`:
- Retention: 90 days
- Structure: Mirrors the `src/` directory structure
- Location: `build/mpy/`

### 2. Manifest Artifact

A `manifest.json` file containing metadata about all compiled files:

```json
{
  "version": "1.0.0",
  "build_timestamp": "2026-02-06T10:46:02Z",
  "files": [
    {
      "path": "boot.mpy",
      "download_path": "mpy/boot.mpy",
      "sha256": "c2dde4b80967920d03184350367707da580f607bb11de98782ac660c0eb2c7fe",
      "size": 240
    },
    ...
  ]
}
```

Fields:
- `path`: Relative path within the mpy directory
- `download_path`: Path for downloading from artifacts
- `sha256`: SHA256 hash for integrity verification
- `size`: File size in bytes

A lightweight `version.json` file is also included for quick version checks (~112 bytes):

```json
{
  "version": "1.0.0",
  "build_timestamp": "2026-02-06T11:06:01Z",
  "file_count": 51,
  "total_size": 84353
}
```

This file is ideal for checking if a new build is available without downloading the full manifest.

### 3. Release Archives (on tag push)

When a tag is pushed, the workflow also creates:
- `mpy-files.tar.gz` - Compressed tar archive
- `mpy-files.zip` - ZIP archive

## Using the Compiled Files

### Download from GitHub Actions

1. Go to the Actions tab in the repository
2. Select the workflow run
3. Download the `mpy-files` or `manifest` artifacts

### Using the Manifest

The manifest can be used to:
- Verify file integrity using SHA256 hashes
- Generate download scripts
- Track version changes
- Implement over-the-air (OTA) updates for CircuitPython devices

### Example: Verifying a File

```python
import hashlib
import json

with open('manifest.json') as f:
    manifest = json.load(f)

def verify_file(filepath):
    # Get expected hash from manifest
    for file_info in manifest['files']:
        if file_info['path'] == filepath:
            expected_hash = file_info['sha256']
            break
    
    # Calculate actual hash
    sha256_hash = hashlib.sha256()
    with open(f"mpy/{filepath}", "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    actual_hash = sha256_hash.hexdigest()
    
    return actual_hash == expected_hash

# Verify a file
if verify_file('boot.mpy'):
    print("File verified successfully!")
else:
    print("File verification failed!")
```

### Example Script

A complete example script for downloading and verifying MPY files is available at:
[`examples/download_mpy_files.py`](../../examples/download_mpy_files.py)

This script can:
- Verify all files against the manifest
- Copy files to a CircuitPython device
- Report any integrity issues

Usage:
```bash
# Download artifacts from GitHub Actions
# Then verify them:
python examples/download_mpy_files.py --verify --output-dir ./mpy

# Copy to CircuitPython device:
python examples/download_mpy_files.py --copy-to-circuitpy /media/CIRCUITPY
```

## Benefits of MPY Files

MPY (MicroPython bytecode) files offer several advantages:
1. **Faster Loading**: Pre-compiled bytecode loads faster than source code
2. **Memory Efficient**: Takes less memory than parsing Python source
3. **Code Protection**: Source code is not directly readable
4. **Optimization**: Bytecode is optimized for the target platform

## Compilation Process

The workflow uses `mpy-cross`, the official MicroPython cross-compiler:
- Version: Latest from PyPI (`mpy-cross` package)
- Target: Compatible with CircuitPython 10.x+
- Error Handling: Files that fail to compile are logged but don't stop the workflow

### Known Limitations

Some Python 3 syntax features may not be supported by MicroPython/CircuitPython. Files that fail to compile are:
- Logged in the workflow output
- Excluded from the manifest
- The workflow continues and succeeds if at least one file compiles

#### Current Known Issue: code.py

The `src/code.py` file currently fails to compile due to dictionary unpacking syntax on line 63:

```python
return {**default_config, **config_data}  # Merge with defaults
```

**Why it fails:** MicroPython's parser (used by mpy-cross v1.27) doesn't support the `{**dict1, **dict2}` dictionary unpacking operator that was introduced in Python 3.5. While CircuitPython 10.x runtime supports this syntax when running .py files directly, the mpy-cross compiler has not yet implemented it in its parser.

**Workaround:** This file can remain as a `.py` file on the device since CircuitPython will parse it correctly at runtime. The precompiled `.mpy` files for all other modules will still provide performance benefits. Alternatively, the code can be rewritten to use `dict.update()` or manual merging if compilation is required:

```python
# Alternative syntax that compiles:
merged_config = default_config.copy()
merged_config.update(config_data)
return merged_config
```

**Impact:** This is a minor limitation affecting only 1 of 52 files. The workflow successfully compiles 51 files (98% success rate), and the main application entry point can run as interpreted Python without significant performance impact.

## Maintenance

### Updating the Workflow

The workflow file is located at `.github/workflows/build-mpy.yml`.

To modify:
1. Edit the workflow file
2. Commit and push changes
3. The workflow will use the new configuration on the next run

### Adding New Files

New Python files added to `src/` are automatically detected and compiled. No workflow changes needed.

## Troubleshooting

### File Fails to Compile

Check the workflow logs for the specific syntax error. Common issues:
- Unsupported Python 3 syntax (e.g., some dictionary unpacking patterns)
- CircuitPython-specific syntax that's not standard Python

### Artifact Not Available

- Artifacts expire after 90 days
- Check if the workflow completed successfully
- Verify the file passed the compilation step

## Related Documentation

- [CircuitPython Documentation](https://circuitpython.org/)
- [MicroPython mpy-cross](https://docs.micropython.org/en/latest/reference/mpyfiles.html)
- [GitHub Actions Artifacts](https://docs.github.com/en/actions/using-workflows/storing-workflow-data-as-artifacts)
