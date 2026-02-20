# Example 4: Fixing Flaky Async Tests

## Scenario

An async test for the `SatelliteNetworkManager` passes most of the time but occasionally fails with timeout errors. This is a classic "flaky test" that needs to be made deterministic.

## Initial Problem

```
$ python3 tests/test_satellite_network_manager.py

Testing satellite network initialization...
✓ Initialization test passed

Testing concurrent message handling...
✗ FAIL - Test timeout after 5 seconds

# Run again...
$ python3 tests/test_satellite_network_manager.py
✓ All tests passed!

# Run again...
$ python3 tests/test_satellite_network_manager.py
✗ FAIL - Test timeout after 5 seconds
```

## Using the Agent

**Prompt to Copilot**:
```
@workspace /test-specialist

test_satellite_network_manager.py::test_concurrent_messages is flaky.
It fails about 30% of the time with timeout errors.

The test creates multiple async tasks but might not be waiting for all
of them to complete. Can you make this test deterministic?
```

## Agent Response

The agent will:

1. **Analyze** the test code to find the race condition:

```python
# BEFORE (flaky version)
@pytest.mark.asyncio
async def test_concurrent_messages():
    """Test handling concurrent satellite messages."""
    print("\nTesting concurrent message handling...")

    manager = SatelliteNetworkManager()

    # Create multiple concurrent tasks
    task1 = asyncio.create_task(manager.send_message(sat_id=1, msg="Hello"))
    task2 = asyncio.create_task(manager.send_message(sat_id=2, msg="World"))
    task3 = asyncio.create_task(manager.process_incoming())

    # Wait for first task only (BUG: other tasks might not complete)
    result1 = await task1

    assert result1 == "OK", "Message 1 should send successfully"
    print("✓ Concurrent message test passed")
```

**Problem identified**: Only `task1` is awaited. `task2` and `task3` may not complete before assertions run.

2. **Fix** the race condition using proper synchronization:

```python
# AFTER (deterministic version)
@pytest.mark.asyncio
async def test_concurrent_messages():
    """Test handling concurrent satellite messages."""
    print("\nTesting concurrent message handling...")

    manager = SatelliteNetworkManager()

    # Create multiple concurrent tasks
    task1 = asyncio.create_task(manager.send_message(sat_id=1, msg="Hello"))
    task2 = asyncio.create_task(manager.send_message(sat_id=2, msg="World"))
    task3 = asyncio.create_task(manager.process_incoming())

    # Wait for ALL tasks to complete
    results = await asyncio.gather(task1, task2, task3)

    # Now safe to assert - all tasks completed
    assert results[0] == "OK", "Message 1 should send successfully"
    assert results[1] == "OK", "Message 2 should send successfully"
    assert results[2] is not None, "Process task should complete"

    print("✓ Concurrent message test passed")
```

3. **Add timeout protection** to prevent infinite hangs:

```python
@pytest.mark.asyncio
async def test_concurrent_messages():
    """Test handling concurrent satellite messages."""
    print("\nTesting concurrent message handling...")

    manager = SatelliteNetworkManager()

    # Create multiple concurrent tasks
    task1 = asyncio.create_task(manager.send_message(sat_id=1, msg="Hello"))
    task2 = asyncio.create_task(manager.send_message(sat_id=2, msg="World"))
    task3 = asyncio.create_task(manager.process_incoming())

    # Wait for ALL tasks with timeout protection
    try:
        results = await asyncio.wait_for(
            asyncio.gather(task1, task2, task3),
            timeout=2.0  # Fail fast if tasks hang
        )
    except asyncio.TimeoutError:
        assert False, "Tasks did not complete within 2 seconds"

    # Now safe to assert - all tasks completed
    assert results[0] == "OK", "Message 1 should send successfully"
    assert results[1] == "OK", "Message 2 should send successfully"
    assert results[2] is not None, "Process task should complete"

    print("✓ Concurrent message test passed")
```

4. **Test the fix** multiple times to verify stability:

```bash
$ for i in {1..20}; do
    echo "Run $i:"
    python3 tests/test_satellite_network_manager.py || exit 1
done

Run 1:
✓ All tests passed!
Run 2:
✓ All tests passed!
Run 3:
✓ All tests passed!
...
Run 20:
✓ All tests passed!

All 20 runs passed! Test is now stable.
```

## Additional Improvements

The agent might also suggest:

### 1. Mock Time-Dependent Operations

```python
# Instead of actual delays
await asyncio.sleep(0.5)

# Use mock time
with mock.patch('asyncio.sleep'):
    await manager.operation()
```

### 2. Add Explicit Synchronization Points

```python
# Add event to signal when ready
ready_event = asyncio.Event()

async def operation():
    await setup()
    ready_event.set()  # Signal ready
    await work()

# In test
await ready_event.wait()  # Wait for setup
assert manager.is_ready
```

### 3. Cleanup After Tests

```python
@pytest.mark.asyncio
async def test_concurrent_messages():
    """Test handling concurrent satellite messages."""
    manager = SatelliteNetworkManager()

    try:
        # Test code here
        tasks = [...]
        results = await asyncio.gather(*tasks)
        assert ...
    finally:
        # Cleanup: Cancel any remaining tasks
        await manager.shutdown()

        # Wait for background tasks to clean up
        await asyncio.sleep(0.1)
```

## Result

- ✅ Test is now deterministic (100% pass rate)
- ✅ Proper async synchronization with `asyncio.gather()`
- ✅ Timeout protection prevents infinite hangs
- ✅ Clear error messages when timeout occurs
- ✅ No changes to source code

## Commit Message

```
Fix flaky test_concurrent_messages with proper async synchronization

- Use asyncio.gather() to wait for all tasks, not just first one
- Add timeout protection (2 seconds) to fail fast if tasks hang
- Verify all task results before assertions
- Test now passes consistently (verified with 20 runs)

Fixes intermittent timeout failures in CI.
```

---

## Common Async Test Patterns

### Pattern 1: Wait for All Tasks

```python
# ✅ Correct
results = await asyncio.gather(task1, task2, task3)

# ❌ Wrong (race condition)
result1 = await task1
# task2 and task3 might not be done!
```

### Pattern 2: Timeout Protection

```python
# ✅ Correct
try:
    result = await asyncio.wait_for(operation(), timeout=2.0)
except asyncio.TimeoutError:
    assert False, "Operation timed out"

# ❌ Wrong (might hang forever)
result = await operation()
```

### Pattern 3: Event Synchronization

```python
# ✅ Correct
ready = asyncio.Event()
async def worker():
    await setup()
    ready.set()

await ready.wait()  # Wait for signal

# ❌ Wrong (race condition)
asyncio.create_task(worker())
await asyncio.sleep(0.1)  # Hope it's ready?
```

### Pattern 4: Proper Cleanup

```python
# ✅ Correct
try:
    await test_operation()
finally:
    await manager.cleanup()

# ❌ Wrong (leaves tasks running)
await test_operation()
# cleanup might not happen
```

---

## Key Takeaways

1. **Flaky tests are often async synchronization issues**
2. **Use `asyncio.gather()` to wait for all tasks**
3. **Add timeouts to prevent infinite hangs**
4. **Test fixes multiple times to verify stability**
5. **Mock time-dependent operations** when possible
6. **Always cleanup** async resources in `finally` blocks
