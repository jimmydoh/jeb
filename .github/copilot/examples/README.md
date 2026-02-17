# Test Maintenance Agent Examples

This directory contains practical examples demonstrating how to use the Test Maintenance Agent for common testing scenarios.

## Available Examples

### [Example 1: Fixing a Mock Interface Mismatch](01-mock-interface-fix.md)
**Scenario**: Source code interface changed but test mock wasn't updated  
**Solution**: Update mock to match new interface  
**Key Skills**: Mock updating, interface matching, test repair

### [Example 2: Creating Tests for an Untested Module](02-create-new-tests.md)
**Scenario**: Module has 0% test coverage  
**Solution**: Create comprehensive test file with mocks  
**Key Skills**: Test scaffolding, hardware mocking, coverage expansion

### [Example 3: Handling Source Code Bugs](03-source-bug-handling.md)
**Scenario**: Test reveals a bug in source code  
**Solution**: Open issue instead of modifying source code  
**Key Skills**: Bug detection, issue creation, test skipping

### [Example 4: Fixing Flaky Async Tests](04-flaky-async-tests.md)
**Scenario**: Async test passes/fails intermittently  
**Solution**: Fix async synchronization and race conditions  
**Key Skills**: Async patterns, race condition detection, test stability

---

## Example Categories

### Test Repair
- Example 1: Mock Interface Mismatch
- Example 4: Flaky Async Tests

### Coverage Expansion  
- Example 2: Creating New Tests

### Bug Reporting
- Example 3: Source Code Bugs

---

## How to Use These Examples

1. **Read the scenario** to understand the problem
2. **Review the prompt** to see how to ask the agent
3. **Study the agent's response** to learn the solution pattern
4. **Apply the pattern** to your own testing challenges

---

## Quick Reference

### When Mocks Need Updating
→ See [Example 1](01-mock-interface-fix.md)

### When Module Has No Tests
→ See [Example 2](02-create-new-tests.md)

### When Test Reveals Source Bug
→ See [Example 3](03-source-bug-handling.md)

### When Tests Are Flaky
→ See [Example 4](04-flaky-async-tests.md)

---

## Contributing New Examples

Have a great example of using the Test Maintenance Agent? Add it here!

1. Create a new file: `05-your-example.md`
2. Follow the format of existing examples:
   - **Scenario**: What's the problem?
   - **Using the Agent**: What prompt to use?
   - **Agent Response**: What does the agent do?
   - **Result**: What's the outcome?
   - **Key Takeaways**: What did we learn?
3. Update this README with your new example
4. Submit a pull request

---

## Common Patterns

### Asking the Agent

**Be specific**:
```
❌ "Fix the tests"
✅ "Fix test_audio_manager.py - MockAudioManager is missing pause() method"
```

**Provide context**:
```
❌ "Tests are failing"
✅ "test_matrix.py fails with: AttributeError: 'MockMatrix' object has no attribute 'brightness'"
```

**Include error messages**:
```
✅ "CI failed with: MemoryError: Unable to allocate 524288 bytes"
```

### Verifying Agent Work

After the agent makes changes:

1. ✅ **Review the diff** - Check what files were modified
2. ✅ **Run tests locally** - Verify they pass
3. ✅ **Check boundaries** - Ensure only test files changed
4. ✅ **Assess quality** - Make sure tests are meaningful, not just passing

---

## Tips for Success

1. **Start with simple requests** to build familiarity
2. **Provide complete error messages** for better diagnosis
3. **Ask the agent to explain** its reasoning if unclear
4. **Verify fixes work** before committing
5. **Learn the patterns** to better understand testing

---

## Support

Questions about these examples?
- Check the main [USAGE.md](../USAGE.md) guide
- Review the [agent configuration](../test-maintenance-agent.md)
- Open an issue in the repository

---

**Happy Testing! 🧪**
