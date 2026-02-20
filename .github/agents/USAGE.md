# Using the Test Specialist

This guide explains how to use the custom GitHub Copilot Test Specialist to repair failing tests and expand test coverage for the JEB project.

## Overview

The Test Specialist is a specialized GitHub Copilot agent configured to:
- Fix broken or flaky unit tests
- Expand test coverage by creating new tests
- Report source code bugs (without modifying source code)
- Maintain the test suite health

## Prerequisites

- GitHub Copilot subscription (Individual, Business, or Enterprise)
- Access to the JEB repository
- GitHub Copilot Chat extension in your IDE (VS Code, Visual Studio, etc.)

## Quick Start

### 1. Activate the Agent

In GitHub Copilot Chat, reference the agent with:

```
@workspace /test-specialist
```

Or simply start your message with context about tests:

```
The test_audio_manager.py tests are failing. Can you help fix them?
```

### 2. Common Use Cases

#### Repair a Failing Test

```
@workspace /test-specialist

The test_audio_manager.py::test_preload test is failing with:
AttributeError: 'MockAudioManager' object has no attribute 'pause'

Can you fix this test?
```

The agent will:
1. Analyze the test file
2. Identify the mock needs updating
3. Add the missing `pause()` method to the mock
4. Verify the test passes

#### Expand Test Coverage

```
@workspace /test-specialist

According to TEST_COVERAGE_REPORT.md, the led_manager.py module has no tests.
Can you create tests for it?
```

The agent will:
1. Review the source module (`src/managers/led_manager.py`)
2. Create a new test file (`tests/test_led_manager.py`)
3. Write comprehensive tests with appropriate mocks
4. Run tests to verify they pass

#### Analyze Test Failures from CI

```
@workspace /test-specialist

The CI workflow is failing. The unit-tests.yml workflow shows:
- test_matrix_manager.py failed
- test_protocol.py failed

Can you investigate and fix these?
```

The agent will:
1. Review the failing tests
2. Determine root causes
3. Fix test-related issues or open issues for source bugs
4. Verify fixes work

## Agent Capabilities

### ✅ What the Agent CAN Do

- **Modify test files** in the `tests/` directory
- **Create new test files** following repository patterns
- **Update mocks** to match changed interfaces
- **Adjust assertions** when behavior changes intentionally
- **Fix test logic** errors
- **Add missing test cases** for untested code paths
- **Update test infrastructure** (pytest configs, helpers)
- **Open issues** for source code bugs

### ❌ What the Agent CANNOT Do

- **Modify source code** in `src/` directory
- **Fix source code bugs** directly
- **Change application logic** or business rules
- **Modify production code** files

## Detailed Usage Examples

### Example 1: Fixing a Mock Interface Mismatch

**Scenario**: The AudioManager class added a new `pause()` method, but the test mock doesn't have it.

**Prompt**:
```
@workspace /test-specialist

Fix the failing test in test_audio_manager.py. The error is:
AttributeError: 'MockAudioManager' object has no attribute 'pause'
```

**What the Agent Does**:
1. Opens `tests/test_audio_manager.py`
2. Finds the `MockAudioManager` class
3. Adds the `pause()` method:
   ```python
   def pause(self):
       """Mock pause."""
       self.paused = True
   ```
4. Adds `self.paused = False` to `__init__`
5. Runs the test to verify it passes

**Result**: Test passes, mock updated to match new interface.

---

### Example 2: Creating Tests for an Untested Module

**Scenario**: `managers/display_manager.py` has no tests (0% coverage).

**Prompt**:
```
@workspace /test-specialist

Create comprehensive tests for display_manager.py. It's a manager class
that controls a 7-segment display. Focus on:
- Initialization
- Setting display text
- Clearing the display
- Error handling for invalid input
```

**What the Agent Does**:
1. Reviews `src/managers/display_manager.py` to understand the API
2. Creates `tests/test_display_manager.py`
3. Implements mocks for CircuitPython hardware (board, digitalio)
4. Writes 8-10 test cases:
   - `test_initialization()`
   - `test_set_text()`
   - `test_clear()`
   - `test_brightness_control()`
   - `test_invalid_text_length()`
   - etc.
5. Runs tests to verify they pass
6. Updates `TEST_COVERAGE_REPORT.md` to reflect new coverage

**Result**: New test file with comprehensive coverage, documented in coverage report.

---

### Example 3: Handling Source Code Bugs

**Scenario**: A test reveals a bug in the source code.

**Prompt**:
```
@workspace /test-specialist

test_updater.py::test_download_large_file is failing because the
updater crashes with MemoryError for files > 100KB. What should we do?
```

**What the Agent Does**:
1. Analyzes the test and source code
2. Identifies the bug in `src/managers/updater.py` (no size check before reading)
3. **Does NOT modify source code**
4. Opens a GitHub issue:
   ```markdown
   Title: Updater crashes when downloading files > 100KB

   ## Failed Tests
   - tests/test_updater.py::test_download_large_file

   ## Root Cause
   In src/managers/updater.py, line 78:
   - The download() method reads entire file into memory
   - No check for file size before allocating buffer

   ## Expected Behavior
   Files > 100KB should be downloaded in chunks

   ## Actual Behavior
   MemoryError raised when attempting to allocate large buffer

   ## Suggested Fix
   Implement chunked download:
   ```python
   CHUNK_SIZE = 4096
   while True:
       chunk = response.read(CHUNK_SIZE)
       if not chunk:
           break
       file.write(chunk)
   ```

   ## Test References
   See tests/test_updater.py:145-160
   ```
5. Marks the test with skip decorator:
   ```python
   @pytest.mark.skip(reason="Source bug - see issue #45")
   def test_download_large_file():
       ...
   ```

**Result**: Issue opened for maintainers to fix source code, test marked to skip until fixed.

---

### Example 4: Fixing Flaky Async Tests

**Scenario**: An async test sometimes passes, sometimes fails.

**Prompt**:
```
@workspace /test-specialist

test_satellite_network_manager.py::test_concurrent_messages is flaky.
It fails about 30% of the time with timeout errors. Can you make it more stable?
```

**What the Agent Does**:
1. Analyzes the async test
2. Identifies race condition: test doesn't await all tasks
3. Fixes the synchronization:
   ```python
   # Before
   task1 = asyncio.create_task(manager.send_message(msg1))
   task2 = asyncio.create_task(manager.send_message(msg2))
   result = await task1

   # After
   task1 = asyncio.create_task(manager.send_message(msg1))
   task2 = asyncio.create_task(manager.send_message(msg2))
   results = await asyncio.gather(task1, task2)
   ```
4. Runs test multiple times to verify stability

**Result**: Test is now deterministic and passes consistently.

---

## Working with CI/CD

### Triggering Test Runs

Tests automatically run on:
- Push to `main` branch
- Pull requests
- Manual trigger via GitHub Actions UI

### Viewing Test Results

1. Go to the repository's Actions tab
2. Click on the "Unit Tests" workflow
3. View logs for failed tests
4. Copy error messages to share with the agent

### Example CI Integration Workflow

```
1. Developer pushes code
2. CI runs → tests fail
3. Developer copies error from CI logs
4. Developer asks agent: "Fix failing tests from CI: [paste error]"
5. Agent fixes tests
6. Developer commits and pushes
7. CI runs again → tests pass ✓
```

---

## Advanced Features

### Batch Test Repairs

Fix multiple failing tests at once:

```
@workspace /test-specialist

CI shows 5 tests failing:
1. test_audio_manager.py::test_preload
2. test_audio_manager.py::test_play
3. test_matrix_manager.py::test_brightness
4. test_protocol.py::test_parse_command
5. test_uart_transport.py::test_send_message

All seem related to a recent refactor. Can you fix them all?
```

### Coverage Analysis

Get a coverage report and recommendations:

```
@workspace /test-specialist

Analyze current test coverage and recommend:
1. Top 3 modules that need tests most urgently
2. Specific test cases we're missing for existing test files
3. Overall coverage improvement strategy
```

### Test Performance Analysis

Optimize slow tests:

```
@workspace /test-specialist

The test_integration_performance.py file takes 45 seconds to run.
Can you identify slow tests and suggest optimizations (without changing behavior)?
```

---

## Best Practices

### 1. Be Specific in Your Requests

❌ **Vague**: "Fix the tests"
✅ **Specific**: "Fix test_audio_manager.py - MockAudioManager is missing the pause() method"

### 2. Provide Context

Include:
- Error messages from test runs
- Which tests are failing
- Recent changes that might have caused failures
- Expected vs. actual behavior

### 3. Verify Agent Changes

After the agent makes changes:
1. Review the modifications
2. Run tests locally to confirm they pass
3. Check that only test files were modified (not source code)
4. Verify test quality (not just making tests pass incorrectly)

### 4. Document Coverage Improvements

When adding new tests, ask the agent to:
- Update `TEST_COVERAGE_REPORT.md`
- Document the test cases added
- Note the coverage improvement

### 5. Use for Learning

Ask the agent to explain:
- Why a test failed
- How mocking works for CircuitPython modules
- Best practices for async test patterns
- How to structure new test files

---

## Troubleshooting

### Agent Suggests Modifying Source Code

**Problem**: Agent wants to fix a bug in `src/` directory.

**Solution**: Remind the agent:
```
Please don't modify source code. Open an issue instead to report the bug.
```

### Agent's Fix Doesn't Work

**Problem**: Test still fails after agent's fix.

**Solution**: Provide more context:
```
The fix didn't work. Here's the new error message:
[paste error]

Can you try a different approach?
```

### Agent Creates Tests That Are Too Simple

**Problem**: Tests don't adequately cover the module.

**Solution**: Request more comprehensive tests:
```
These tests are a good start, but please add:
- Edge case tests (empty input, None values, boundary conditions)
- Error handling tests
- Async behavior tests (if applicable)
```

### Not Sure How to Use the Agent

**Problem**: Unsure what to ask or how to phrase requests.

**Solution**: Start with:
```
@workspace /test-specialist

I need help with testing in the JEB project. Can you:
1. Explain what you can help with
2. Show me examples of common requests
3. Suggest what tests I should focus on next
```

---

## Integration with Development Workflow

### Typical Development Cycle with Agent

```
┌─────────────────────────────────┐
│  1. Write/modify source code    │
└─────────┬───────────────────────┘
          │
          ▼
┌─────────────────────────────────┐
│  2. Run tests locally           │
└─────────┬───────────────────────┘
          │
          ▼
┌─────────────────────────────────┐
│  3. Tests fail?                 │
│     ├─ Yes → Ask agent to fix   │
│     └─ No  → Commit & push      │
└─────────┬───────────────────────┘
          │
          ▼
┌─────────────────────────────────┐
│  4. CI runs tests               │
└─────────┬───────────────────────┘
          │
          ▼
┌─────────────────────────────────┐
│  5. CI fails?                   │
│     ├─ Yes → Share logs w/agent │
│     └─ No  → Done! ✓            │
└─────────────────────────────────┘
```

### Pre-Commit Checklist

Before committing:
- [ ] Run tests locally
- [ ] Fix any failures (or ask agent for help)
- [ ] Add new tests for new features (or ask agent to create them)
- [ ] Verify test coverage is maintained or improved
- [ ] Update TEST_COVERAGE_REPORT.md if adding new tests

---

## Additional Resources

### Repository Documentation
- `TEST_COVERAGE_REPORT.md` - Current coverage status and gaps
- `.github/workflows/unit-tests.yml` - CI test runner configuration
- `tests/README.md` - Test suite overview (if exists)

### Example Test Files (Good Patterns)
- `tests/test_cobs.py` - Simple standalone tests
- `tests/test_audio_manager.py` - Complex mocking example
- `tests/test_mode_base.py` - Async test patterns

### External Resources
- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [CircuitPython](https://docs.circuitpython.org/) - Understanding what we're mocking

---

## Support

If you encounter issues with the Test Specialist:

1. **Check this guide** for common solutions
2. **Review agent configuration** in `.github/copilot/test-specialist.md`
3. **Ask the agent directly** about its capabilities
4. **Open an issue** in the repository for agent behavior problems

---

## Summary

The Test Specialist is your automated assistant for:
- 🔧 Keeping tests healthy
- 📈 Expanding coverage
- 🐛 Reporting bugs
- ⚡ Accelerating development

Use it frequently, trust but verify its changes, and enjoy more time coding instead of fixing tests!

**Happy Testing! 🎉**
