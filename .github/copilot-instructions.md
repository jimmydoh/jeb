# GitHub Copilot Instructions for JEB Project

## Project Overview

**JEB (JADNET Electronics Box)** is a sophisticated embedded control system built on the Raspberry Pi Pico 2 (RP2350) platform, designed with industrial-grade safety features and modular expandability. The system features a master-satellite architecture where a central CORE unit orchestrates multiple satellite modules through a custom communication protocol over RJ45 daisy-chain connections.

### Key Characteristics
- **Safety-first embedded system** with hardware watchdog, UVLO, and MOSFET firewalls
- **Master-satellite architecture** using UART communication over RJ45
- **Modular plug-and-play** satellite expansion with automatic detection
- **Rich user interface** with OLED displays, LED matrices, audio feedback, and custom input controls
- **Production-ready async architecture** with comprehensive error handling

## Technology Stack

### Primary Language & Runtime
- **CircuitPython 10.x+** for embedded firmware (source code in `src/`)
- **Python 3.11+** for testing and development tools
- **Platform**: Raspberry Pi Pico 2 (RP2350) microcontroller

### Key Libraries & Dependencies
- **asyncio** - Asynchronous event-driven architecture
- **board, digitalio, busio** - CircuitPython hardware abstraction
- **audiocore, synthio** - Audio synthesis and playback
- **adafruit_httpserver** - Web-based configurator (Pico 2W)
- **pytest, pytest-asyncio** - Testing framework

### Hardware Interfaces
- I2C (displays, I/O expanders)
- SPI (NeoPixels, microSD)
- UART (satellite communication)
- I2S (audio output)
- ADC (power monitoring)

## Development Environment

### Source Code Location
- **Firmware**: `src/` directory (runs on Pico 2 with CircuitPython)
- **Tests**: `tests/` directory (runs on development machine with Python 3.11+)
- **Examples**: `examples/` directory (configuration templates, scripts)
- **Documentation**: `docs/` directory (technical documentation)

### Running the Project
1. Flash CircuitPython 10.x+ to Raspberry Pi Pico 2
2. Copy `src/` contents to `CIRCUITPY` drive
3. Copy `config.json` to `CIRCUITPY` drive
4. System boots automatically, runs `code.py` as entrypoint

### Testing
- **Unit tests**: Run with `python3 tests/test_*.py` or `pytest`
- **Integration tests**: Require multiple test files or fixtures
- **Performance benchmarks**: `tests/performance_*.py`
- **Coverage report**: See `TEST_COVERAGE_REPORT.md`

### CI/CD
- GitHub Actions workflows in `.github/workflows/`
- Automated testing on push and PR
- Test results visible in Actions tab

## Architecture & Code Organization

### Mode-Based State Machine
- All interactive modes inherit from `BaseMode` (`src/modes/base.py`)
- Modes handle UI, user input, and state transitions
- Examples: `main_menu.py`, `game_mode.py`, `industrial_startup.py`

### Manager Pattern
Specialized managers in `src/managers/`:
- **HIDManager** - User input (buttons, encoders, keypads)
- **DisplayManager** - OLED and segment displays
- **MatrixManager** / **LEDManager** - NeoPixel control
- **AudioManager** / **SynthManager** - Sound effects and synthesis
- **PowerManager** - ADC monitoring, UVLO protection
- **SatelliteNetworkManager** - UART communication with satellites
- **RelayManager** - Message routing between satellites

### Transport Layer Abstraction
- **BaseTransport** - Abstract interface for communication
- **UARTTransport** - Serial communication implementation
- COBS encoding for packet framing
- Protocol specification in `docs/TRANSPORT_ABSTRACTION.md`

### Configuration
- `config.json` in root - system configuration
- JSON format with wifi, debug, and unit-specific settings
- Examples: `examples/config-example-core.json`, `examples/config-example-sat-01.json`

## Coding Standards & Conventions

### Python Style
- **Follow CircuitPython patterns** for embedded code
- **Type hints encouraged** but not required (CircuitPython limitations)
- **Docstrings** for public classes and methods
- **Error handling**: Use try/except, graceful degradation

### Async Patterns
- Use `asyncio.create_task()` for concurrent operations
- Use `await` for I/O operations
- Feed watchdog regularly in long-running loops
- Clean up tasks on mode exit

### Hardware Abstractions
- **Mock hardware** in tests (don't import real CircuitPython modules)
- Use manager pattern for hardware access
- Centralize hardware initialization in managers
- Handle hardware failures gracefully

### Naming Conventions
- **Classes**: PascalCase (e.g., `AudioManager`, `BaseMode`)
- **Functions/Methods**: snake_case (e.g., `play_sound`, `update_display`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `MAX_SATELLITES`, `UART_BAUDRATE`)
- **Private members**: Leading underscore (e.g., `_internal_state`)

### File Organization
```
src/
├── code.py                 # Main entrypoint
├── updater.py              # OTA firmware updates
├── modes/                  # Application modes
├── managers/               # Hardware/system managers
├── satellites/             # Satellite firmware and drivers
├── transport/              # Communication layer
└── utilities/              # Utility functions

tests/
├── test_*.py               # Unit tests (one per module)
└── performance_*.py        # Performance benchmarks

docs/
├── *.md                    # Technical documentation
```

## Testing Practices

### Test Structure
- **One test file per module**: `src/managers/audio_manager.py` → `tests/test_audio_manager.py`
- **Mock CircuitPython modules**: Create mock objects for hardware
- **Standalone tests**: Most tests can run with `python3 test_file.py`
- **pytest compatibility**: Tests also work with `pytest` runner

### Mocking Strategy
```python
# Example mock for CircuitPython hardware
class MockBoard:
    """Mock board module for testing."""
    def __init__(self):
        self.GP0 = "GP0"
        self.GP1 = "GP1"
        # ... other pins

class MockAudioManager:
    """Mock AudioManager for testing."""
    def __init__(self):
        self.playing = False
        self.current_track = None

    def play(self, track):
        self.playing = True
        self.current_track = track
```

### Async Testing
- Use `asyncio.run()` for async tests
- Or use `@pytest.mark.asyncio` decorator
- Mock async methods as needed
- Test concurrent behavior with `asyncio.gather()`

### Test Coverage Goals
- **Core utilities**: 100% coverage target
- **Managers**: 80%+ coverage target
- **Modes**: 60%+ coverage target (UI-heavy)
- See `TEST_COVERAGE_REPORT.md` for current status

## Common Workflows & Tasks

### Adding a New Manager
1. Create `src/managers/new_manager.py` inheriting from appropriate base
2. Implement required methods (init, update, cleanup)
3. Add manager to context in `src/code.py`
4. Create `tests/test_new_manager.py` with mocks
5. Document in README.md if user-facing

### Adding a New Mode
1. Create `src/modes/new_mode.py` inheriting from `BaseMode`
2. Implement `enter()`, `exit()`, `run()` methods
3. Register mode in mode manager
4. Create tests for mode logic
5. Add documentation to relevant docs

### Fixing Failing Tests
1. Run test locally: `python3 tests/test_file.py`
2. Analyze error message and stack trace
3. Update test mocks if interface changed
4. If source bug, open issue (don't modify source in test PRs)
5. Verify fix: run test again

### Adding Test Coverage
1. Check `TEST_COVERAGE_REPORT.md` for gaps
2. Create new test file following naming convention
3. Write comprehensive tests (happy path + edge cases)
4. Run tests to verify they pass
5. Update `TEST_COVERAGE_REPORT.md` with new coverage

### OTA Updates (Pico 2W only)
1. Update version in manifest file
2. Generate MPY files: `mpy-cross source.py`
3. Upload to update server
4. Device downloads manifest, checks versions, updates files
5. See `docs/OTA_UPDATE.md` for details

## Important Constraints & Gotchas

### Memory Constraints
- **Limited RAM**: Pico 2 has 520KB total, CircuitPython uses significant portion
- **Avoid large allocations**: Use generators, streaming, chunked processing
- **Free memory explicitly**: Use `gc.collect()` after large allocations
- **Audio files**: Keep WAV files small, use mono/8-bit when possible

### CircuitPython Limitations
- **No threading**: Use `asyncio` for concurrency
- **Limited stdlib**: Many Python features unavailable
- **Slow imports**: Minimize imports, use MPY compiled files
- **No numpy/scipy**: Implement algorithms from scratch

### Hardware Timing
- **Watchdog**: Must be fed every 5 seconds (async tasks should complete quickly)
- **UART timing**: 115200 baud, ensure proper async handling
- **NeoPixel updates**: ~30µs per pixel, batch updates
- **ADC settling**: Allow time between channel switches

### Safety Features (DO NOT DISABLE)
- **UVLO check**: System refuses to boot below 18V input
- **Watchdog timer**: Must be fed regularly, prevents hangs
- **MOSFET firewall**: Protects downstream satellites from faults
- **Polarity protection**: Schottky diodes prevent reverse voltage damage

### Test-Only Modification Policy
When working on tests:
- ✅ **ALLOWED**: Modify files in `tests/` directory
- ✅ **ALLOWED**: Update test mocks to match interfaces
- ✅ **ALLOWED**: Add new test files
- ❌ **FORBIDDEN**: Modify source code in `src/` to fix failing tests
- ❌ **FORBIDDEN**: Change application logic to make tests pass

If tests reveal source code bugs, open a GitHub issue with details instead of fixing directly.

## Custom Agents

### Test Specialist
- **Purpose**: Automated test repair and coverage expansion
- **Activate**: `@workspace /test-specialist`
- **Capabilities**: Fix failing tests, create new tests, update mocks
- **Constraint**: NEVER modifies source code, only test files
- **Documentation**: See `.github/copilot/USAGE.md` for detailed guide

### Usage Example
```
@workspace /test-specialist

Fix test_audio_manager.py - MockAudioManager is missing the pause() method
that was added to the real AudioManager class.
```

## Additional Resources

### Internal Documentation
- **README.md** - Project overview and getting started
- **TEST_COVERAGE_REPORT.md** - Current test coverage analysis
- **docs/** - Technical documentation for subsystems:
  - `TRANSPORT_ABSTRACTION.md` - Communication protocol
  - `OTA_UPDATE.md` - Firmware update system
  - `WEB_CONFIGURATOR.md` - Field service web interface
  - `PAYLOAD_ENCODING.md` - Data encoding specification
  - `SYNTHIO_IMPLEMENTATION.md` - Audio synthesis details

### External Resources
- [CircuitPython Documentation](https://docs.circuitpython.org/)
- [Raspberry Pi Pico 2 Documentation](https://www.raspberrypi.com/documentation/microcontrollers/pico-series.html)
- [Adafruit Learning Guides](https://learn.adafruit.com/category/circuitpython)

## Quick Reference

### Common Commands
```bash
# Run specific test
python3 tests/test_audio_manager.py

# Run all tests with pytest
pytest tests/

# Run performance benchmarks
python3 tests/performance_cobs.py

# Check test coverage (if pytest-cov installed)
pytest --cov=src tests/
```

### File Paths (Always use absolute paths in code)
- Config: `/config.json` on CIRCUITPY drive
- Logs: `/logs/` directory
- Audio: `/audio/` directory
- SD card: `/sd/` mount point

### Debug Mode
Enable in `config.json`:
```json
{
    "debug_mode": true
}
```
Provides verbose logging and diagnostic output.

---

**Last Updated**: 2026-02-18

For questions or clarifications, refer to the documentation in `docs/` or ask the repository maintainer.
