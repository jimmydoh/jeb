# Quick Start: Test Specialist

Get started with the Test Specialist in 5 minutes.

## What is it?

A specialized GitHub Copilot agent that:
- ✅ Fixes broken unit tests
- ✅ Expands test coverage
- ✅ Reports source code bugs (without modifying source)
- ❌ Never modifies source code in `src/`

## Prerequisites

- GitHub Copilot subscription
- GitHub Copilot Chat enabled in your IDE

## Basic Usage

### 1. Activate the Agent

In GitHub Copilot Chat, type:
```
@workspace /test-specialist
```

### 2. Ask for Help

**Example 1: Fix a failing test**
```
@workspace /test-specialist

Fix test_audio_manager.py - it's failing with:
AttributeError: 'MockAudioManager' object has no attribute 'pause'
```

**Example 2: Create new tests**
```
@workspace /test-specialist

Create tests for managers/led_manager.py - it currently has 0% coverage
```

**Example 3: Handle a source bug**
```
@workspace /test-specialist

test_updater.py is failing because updater.py has a memory bug.
Should we fix it or open an issue?
```

## Common Scenarios

### Scenario A: CI Tests Failed

1. Copy error from CI logs
2. Ask the agent:
   ```
   The CI workflow failed with:
   [paste error here]

   Can you fix this?
   ```
3. Review and commit the fix

### Scenario B: Adding Coverage

1. Check `TEST_COVERAGE_REPORT.md` for gaps
2. Ask the agent:
   ```
   Create comprehensive tests for [module_name].py
   ```
3. Review generated tests
4. Run tests to verify they pass

### Scenario C: Flaky Tests

1. Identify the flaky test
2. Ask the agent:
   ```
   test_[name].py is flaky - it passes/fails randomly.
   Can you make it deterministic?
   ```
3. Test the fix multiple times

## What the Agent Does

### ✅ WILL DO
- Modify files in `tests/` directory
- Create new test files
- Update mocks to match interfaces
- Fix async synchronization issues
- Open GitHub issues for source bugs

### ❌ WON'T DO
- Modify files in `src/` directory
- Fix source code bugs directly
- Change production code
- Modify application logic

## Tips for Success

1. **Be specific** in your requests
   - ❌ "Fix tests"
   - ✅ "Fix test_audio.py - missing pause() mock method"

2. **Provide context**
   - Include error messages
   - Mention recent changes
   - Explain expected behavior

3. **Verify results**
   - Review the agent's changes
   - Run tests to confirm they pass
   - Check only test files were modified

4. **Learn the patterns**
   - Study the examples in `examples/`
   - Understand CircuitPython mocking
   - Master async test patterns

## Next Steps

- 📖 Read the [full usage guide](USAGE.md)
- 📝 Review [examples](examples/)
- 🔧 Try fixing a real test
- 📈 Expand coverage for a module

## Need Help?

- Check [USAGE.md](USAGE.md) for detailed instructions
- Review [examples/](examples/) for common scenarios
- Read [test-maintenance-agent.md](test-maintenance-agent.md) for agent details

---

**Ready to start? Try this:**
```
@workspace /test-specialist

Show me what you can help with for testing in this repository.
```
