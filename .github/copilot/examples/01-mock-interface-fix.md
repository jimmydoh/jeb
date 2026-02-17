# Example 1: Fixing a Mock Interface Mismatch

## Scenario

The `AudioManager` class was updated to include a new `pause()` method, but the test mock wasn't updated. Tests are now failing.

## Initial Error

```
$ python3 tests/test_audio_manager.py

Testing audio manager initialization...
✓ Initialization test passed

Testing audio playback...
Traceback (most recent call last):
  File "tests/test_audio_manager.py", line 145, in test_playback
    manager.pause()
AttributeError: 'MockAudioManager' object has no attribute 'pause'
```

## Using the Agent

**Prompt to Copilot**:
```
@workspace /test-maintenance-agent

The test_audio_manager.py file is failing with:
AttributeError: 'MockAudioManager' object has no attribute 'pause'

The AudioManager class now has a pause() method but the mock doesn't.
Can you fix the test?
```

## Agent Response

The agent will:

1. **Analyze** the test file and identify the `MockAudioManager` class
2. **Update** the mock to include the new method:

```python
class MockAudioManager:
    """Mock AudioManager for testing."""
    def __init__(self):
        self.playing = False
        self.stopped = False
        self.paused = False  # NEW: Added to track pause state
        self.current_track = None
    
    def play(self, track):
        """Mock play method."""
        self.playing = True
        self.current_track = track
    
    def stop(self):
        """Mock stop method."""
        self.playing = False
        self.stopped = True
    
    def pause(self):  # NEW: Added pause method
        """Mock pause method."""
        self.paused = True
        self.playing = False
```

3. **Verify** the test passes:

```
$ python3 tests/test_audio_manager.py

Testing audio manager initialization...
✓ Initialization test passed

Testing audio playback...
✓ Playback test passed

Testing audio pause...
✓ Pause test passed

✓ All tests passed!
```

## Result

- ✅ Mock updated to match new interface
- ✅ Test passes
- ✅ Only test files modified (no source code changes)

## Commit Message

```
Fix test_audio_manager mock for new pause() method

- Added pause() method to MockAudioManager
- Added paused attribute to track pause state
- Tests now pass after AudioManager interface update
```

---

## Key Takeaways

1. **Agent identifies interface mismatches** between mocks and real classes
2. **Agent preserves test behavior** while updating mocks
3. **Agent follows repository patterns** for mock structure
4. **Agent verifies fixes** by ensuring tests pass
5. **No source code modified** - only test files changed
