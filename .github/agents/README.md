# GitHub Copilot Custom Agents

This directory contains custom GitHub Copilot agents for the JEB project.

## Available Agents

### Test Specialist

**Purpose**: Automated repair of failing unit tests and expansion of test coverage.

**Files**:
- `test-maintenance-agent.md` - Agent configuration and instructions
- `USAGE.md` - User guide for maintainers and contributors

**Key Features**:
- ✅ Fix broken or flaky unit tests
- ✅ Create new tests for untested modules
- ✅ Update mocks when interfaces change
- ✅ Identify and report source code bugs (without modifying source)
- ❌ Never modifies source code in `src/` directory

**Quick Start**:
```
@workspace /test-specialist

Fix the failing tests in test_audio_manager.py
```

**Documentation**: See [USAGE.md](USAGE.md) for detailed examples and workflows.

---

## How Custom Agents Work

GitHub Copilot agents are specialized AI assistants configured with:
1. **Domain knowledge** - Understanding of the project structure and patterns
2. **Specific constraints** - Rules about what the agent can/cannot do
3. **Best practices** - Guidelines for high-quality outputs
4. **Context awareness** - Knowledge of testing frameworks, CI/CD, etc.

Agents are invoked in GitHub Copilot Chat using `@workspace /agent-name` or by providing relevant context in your questions.

---

## Agent Configuration Format

Each agent is defined in a Markdown file with:
- **Agent description** - What the agent does
- **Core responsibilities** - Primary tasks
- **Critical constraints** - Hard limits on agent behavior
- **Technical context** - Technology stack, patterns, tools
- **Best practices** - Quality guidelines
- **Examples** - Sample workflows and scenarios

---

## Adding New Agents

To create a new custom agent:

1. **Create agent file**: `<agent-name>.md` in this directory
2. **Define agent instructions**: Follow the format in `test-maintenance-agent.md`
3. **Test the agent**: Verify it behaves as expected
4. **Document usage**: Add examples and common workflows
5. **Update this README**: Add the new agent to the list above

---

## Agent Best Practices

### For Agent Creators

- ✅ Be specific about what the agent CAN and CANNOT do
- ✅ Provide clear examples and workflows
- ✅ Include technical context (frameworks, tools, patterns)
- ✅ Define boundaries and safety constraints
- ✅ Document edge cases and error scenarios

### For Agent Users

- ✅ Be specific in your requests
- ✅ Provide relevant context (error messages, logs, etc.)
- ✅ Review and verify agent outputs
- ✅ Report issues with agent behavior
- ✅ Share successful workflows with the team

---

## Maintenance

### Updating Agents

When project patterns or tools change:
1. Update the agent configuration file
2. Test with example scenarios
3. Update USAGE.md with new patterns
4. Notify team of changes

### Monitoring Agent Performance

Track:
- Success rate of agent suggestions
- Types of requests that work well
- Types of requests that fail
- User feedback and pain points

---

## Resources

### Internal
- [Test Coverage Report](../../TEST_COVERAGE_REPORT.md)
- [GitHub Workflows](../workflows/)
- [Test Files](../../tests/)

### External
- [GitHub Copilot Documentation](https://docs.github.com/copilot)
- [GitHub Copilot Chat](https://docs.github.com/copilot/using-github-copilot/asking-github-copilot-questions-in-your-ide)

---

## Support

Questions or issues with custom agents?
1. Check the agent's USAGE.md file
2. Review the agent configuration file
3. Open an issue in the repository

---

**Last Updated**: 2026-02-17
