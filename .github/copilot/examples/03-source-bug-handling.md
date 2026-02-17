# Example 3: Handling Source Code Bugs

## Scenario

A test reveals a memory bug in the `Updater` class. The test is correct, but the source code has a bug that needs to be fixed by a maintainer (not the test agent).

## Initial Error

```
$ python3 tests/test_updater.py

Testing firmware update download...
Traceback (most recent call last):
  File "tests/test_updater.py", line 156, in test_download_large_file
    updater.download_firmware("https://example.com/firmware.bin")
  File "src/managers/updater.py", line 78, in download_firmware
    buffer = bytearray(content_length)
MemoryError: Unable to allocate 524288 bytes
```

## Using the Agent

**Prompt to Copilot**:
```
@workspace /test-maintenance-agent

test_updater.py::test_download_large_file is failing with MemoryError.

The test tries to download a 500KB firmware file, but the updater.py
code tries to allocate the entire file in memory at once (line 78).

This is a bug in the source code - it should download in chunks.
What should we do?
```

## Agent Response

The agent will:

1. **Analyze** the test and source code
2. **Identify** this is a source code bug (not a test issue)
3. **STOP** - Does NOT modify source code
4. **Create** a GitHub issue with detailed information:

### Issue Created: #45

```markdown
# Updater crashes when downloading files > 100KB

## Failed Tests
- `tests/test_updater.py::test_download_large_file` (line 145-165)

## Root Cause

In `src/managers/updater.py`, line 78:

```python
def download_firmware(self, url):
    response = requests.get(url)
    content_length = int(response.headers.get('content-length', 0))
    buffer = bytearray(content_length)  # ← PROBLEM: Allocates entire file
    buffer[:] = response.content
    return buffer
```

The `download_firmware()` method attempts to allocate a buffer equal to the
entire file size. For large firmware files (>100KB), this causes MemoryError
on CircuitPython devices with limited RAM.

## Expected Behavior

Firmware files should be downloaded in chunks and written to storage
incrementally to avoid memory exhaustion.

## Actual Behavior

Application crashes with MemoryError when attempting to download files
larger than ~100KB.

## Suggested Fix

Implement chunked download with streaming:

```python
CHUNK_SIZE = 4096  # 4KB chunks

def download_firmware(self, url):
    response = requests.get(url, stream=True)
    
    with open('/tmp/firmware.bin', 'wb') as f:
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            if chunk:
                f.write(chunk)
    
    return '/tmp/firmware.bin'
```

Alternatively, use a fixed-size buffer and write directly to filesystem:

```python
def download_firmware(self, url, output_path):
    response = requests.get(url, stream=True)
    buffer = bytearray(4096)  # Fixed 4KB buffer
    
    with open(output_path, 'wb') as f:
        while True:
            bytes_read = response.readinto(buffer)
            if bytes_read == 0:
                break
            f.write(buffer[:bytes_read])
```

## Test References

The failing test is in `tests/test_updater.py:145-165`:

```python
def test_download_large_file():
    """Test downloading large firmware files."""
    updater = Updater()
    
    # Simulate 500KB firmware file
    mock_response.content = b'x' * 500000
    mock_response.headers = {'content-length': '500000'}
    
    # This should work but currently crashes
    result = updater.download_firmware("https://example.com/firmware.bin")
    assert result is not None
```

## Priority

**High** - This affects OTA firmware updates, a critical feature.

## Labels

- `bug`
- `priority: high`
- `component: updater`
- `memory`

## Related Files

- `src/managers/updater.py` (line 78)
- `tests/test_updater.py` (line 145-165)
- `docs/OTA_UPDATE.md` (OTA update documentation)
```

5. **Mark the test** to skip until bug is fixed:

```python
import pytest

@pytest.mark.skip(reason="Source bug - see issue #45")
def test_download_large_file():
    """Test downloading large firmware files.
    
    Note: This test is skipped pending fix for issue #45.
    The updater currently crashes with MemoryError for large files.
    """
    updater = Updater()
    
    # Simulate 500KB firmware file
    mock_response.content = b'x' * 500000
    mock_response.headers = {'content-length': '500000'}
    
    result = updater.download_firmware("https://example.com/firmware.bin")
    assert result is not None
```

6. **Commit** the test change:

```
$ git diff tests/test_updater.py
```

## Result

- ✅ Issue created with comprehensive bug report
- ✅ Test marked to skip (prevents CI failures)
- ✅ Source code NOT modified (respects constraints)
- ✅ Maintainers have clear action items
- ✅ Test will be re-enabled after bug fix

## Commit Message

```
Skip test_download_large_file pending bug fix (issue #45)

- Marked test as @pytest.mark.skip
- Created issue #45 for memory bug in updater.py
- Test will be re-enabled after chunked download is implemented
- Added note explaining why test is skipped
```

---

## What Happens Next

1. **Maintainer reviews issue #45**
2. **Maintainer fixes bug** in `src/managers/updater.py`
3. **Maintainer removes skip decorator** from test
4. **Test passes** with fixed source code
5. **Coverage restored** to 100%

## Follow-Up (After Bug Fix)

When the bug is fixed, use the agent again:

```
@workspace /test-maintenance-agent

Issue #45 has been fixed. Can you re-enable the test_download_large_file
test and verify it passes?
```

Agent will:
1. Remove `@pytest.mark.skip` decorator
2. Run the test to verify it passes
3. Commit the change

---

## Key Takeaways

1. **Agent identifies source bugs** vs test bugs
2. **Agent NEVER modifies source code** directly
3. **Agent creates detailed issue reports** for maintainers
4. **Agent marks tests appropriately** to prevent CI failures
5. **Agent provides actionable suggestions** for fixing bugs
6. **Clear separation** between test maintenance and source code fixes
