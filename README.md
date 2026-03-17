# 🚀 JEB - JADNET Electronics Box

> *A modular, safety-focused embedded control system for industrial and interactive applications*

[![CircuitPython](https://img.shields.io/badge/CircuitPython-10.x+-blueviolet.svg)](https://circuitpython.org/)
[![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi%20Pico%202-c51a4a.svg)](https://www.raspberrypi.com/products/raspberry-pi-pico-2/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [System Architecture](#-system-architecture)
- [Hardware Components](#-hardware-components)
- [Getting Started](#-getting-started)
- [Configuration](#-configuration)
- [Project Structure](#-project-structure)
- [Safety Features](#-safety-features)
- [Development](#-development)
- [Documentation](#-documentation)
- [License](#-license)

---

## 🌟 Overview

**JEB (JADNET Electronics Box)** is a sophisticated embedded control system built on the Raspberry Pi Pico 2 platform, designed with industrial-grade safety features and modular expandability. The system features a master-satellite architecture where a central CORE unit orchestrates multiple satellite modules through a custom communication protocol over RJ45 daisy-chain connections.

### What Makes JEB Special?

- **🛡️ Safety-First Design**: Hardware watchdog timers, undervoltage lockout (UVLO), and MOSFET firewalls
- **🔌 Modular Architecture**: Plug-and-play satellite expansion via RJ45 daisy-chaining with automatic detection
- **⚡ Power Management**: Intelligent power distribution with high-side switching and multi-rail buck converters
- **🎮 Rich User Interface**: OLED displays, LED matrices, audio feedback, rotary encoders, and custom input controls
- **🔧 Production-Ready**: Async event-driven architecture with comprehensive error handling and recovery

---

## ✨ Key Features

### Core System
- **Robust Power Distribution**: USB-C PD 20V input with separate 5V/2.5A logic and 5V/5A LED buck converters
- **Advanced Sensing**: Four-channel ADC monitoring for voltage rails (20V raw/bus, 5V logic/LED)
- **Over-The-Air Updates**: Wi-Fi-based firmware updates via manifest synchronization (Pico 2W)
- **Web-Based Configurator**: Browser-based field service interface for remote configuration, file management, and system monitoring
- **Rich I/O**:
  - 128x64 OLED display (I2C)
  - 8x8 NeoPixel matrix (GlowBit 64) with support for arbitrary matrix configurations (dual, quad, strips, custom)
  - I2S audio amplifier support
  - SD card storage
  - Rotary encoder with button
  - Four programmable buttons via I/O expander
- **Safety Systems**:
  - MOSFET firewall with boot protection
  - Watchdog timer (8s timeout)
  - Software UVLO (< 18V blocks startup)
- **Gameplay Features**:
  - E-Stop button for interactive gameplay mechanics

### Satellite System
- **Modular Design**: Chainable satellite units for distributed control
- **Industrial I/O**:
  - Dual HT16K33 14-segment LED displays (combined 8-character output)
  - 3x3 matrix keypad (9 keys)
  - 8x small latching toggles + 1x guarded latching toggle + 1x key switch + 1x 3-position rotary switch + 1x momentary toggle + 1x execute button
  - 9x NeoPixel status indicators (one per toggle)
  - Rotary encoder with button
- **Smart Power Management**:
  - Brownout detection with automatic LED dimming
  - Short circuit protection with emergency kill
  - Hot-plug detection and link-loss protection
- **Communication**: Full-duplex UART daisy-chain with message relay capability

---

## 🏗️ System Architecture

### Hardware Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          CORE UNIT (Master)                     │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ USB-C PD 20V → Fuse → Caps → Buck Converters            │   │
│  │                    ↓                                      │   │
│  │          ┌─────────────────────┐                         │   │
│  │          │   MOSFET FIREWALL   │                         │   │
│  │          │  (High-Side Switch) │                         │   │
│  │          └─────────────────────┘                         │   │
│  │                    ↓                                      │   │
│  │   Raspberry Pi Pico 2 (RP2350) + UI Components          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                        │ RJ45                                    │
│                        │ (UART + Power)                          │
└────────────────────────┼─────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│                    SATELLITE 01 (Industrial)                     │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 20V Input → Polyfuse → Buck 5V/1A → Pico 2 + Displays   │   │
│  │                    ↓                                      │   │
│  │          ┌─────────────────────┐                         │   │
│  │          │   MOSFET SWITCH     │                         │   │
│  │          │  (Downstream Power) │                         │   │
│  │          └─────────────────────┘                         │   │
│  └──────────────────────────────────────────────────────────┘   │
│                        │ RJ45                                    │
│                        │ (UART + Power)                          │
└────────────────────────┼─────────────────────────────────────────┘
                         │
                         ↓
                   (More Satellites...)
```

### Software Architecture

The system uses an **asynchronous event-driven architecture** built on CircuitPython's `asyncio`:

- **Mode-Based State Machine**: Inherit from `BaseMode` for consistent UI/UX
- **Manager Pattern**: Specialized managers handle HID inputs, UART communications, and device control
- **Global State Management**: Centralized state with async task coordination
- **Watchdog Integration**: Automatic system recovery on hangs or crashes

---

## 🔧 Hardware Components

### CORE Unit (Type 00) - Master Controller

#### Power System
- **Input**: USB-C PD 20V (with 3A blade fuse and 1000µF capacitor)
- **Logic Rail**: 5V/2.5A buck converter (Pico 2, OLED, peripherals)
- **LED Rail**: 5V/5A buck converter (GlowBit matrix - isolated to prevent ADC noise)
- **Protection**: IRF5305 P-Channel MOSFET with 2N3904 NPN driver + 100kΩ pull-down

#### Sensing & Monitoring
- **ADC Channels** (with 3.3V Zener clamps):
  - GP26: 20V Raw Input (47kΩ/6.8kΩ divider)
  - GP27: 20V Bus Output (47kΩ/6.8kΩ divider)
  - GP28: 5V Logic Rail (10kΩ/10kΩ divider)
  - GP29: 5V LED Rail (10kΩ/10kΩ divider)

#### User Interface
- **Display**: SSD1306 128x64 OLED (I2C, requires 4.7kΩ pull-ups)
- **LEDs**: GlowBit 64 (8x8 NeoPixel matrix)
- **Audio**: I2S 3W Class D amplifier with 4Ω transducer
- **Input**: Rotary encoder + 4 face buttons (via MCP23008 I/O expander)
- **Storage**: MicroSD card via SPI

#### Communication
- **RJ45 Port** (T568-B standard):
  - UART TX/RX (GP0/GP1) with 1kΩ series resistors for ESD protection
  - Satellite detection (GP15, active low)
  - 20V power distribution (post-MOSFET)
  - Star-ground topology (split power/signal ground)

### Satellite 01 (Type 01) - Industrial I/O Module

#### Power System
- **Input**: 20V DC via RJ45 (pins 7 & 8)
- **Protection**: SS54 Schottky diode (reverse polarity) + 1.0A polyfuse
- **Local Buck**: 5V/1A converter for Pico 2 and peripherals
- **Downstream Control**: P-Channel MOSFET high-side switch

#### User Interface
- **Displays**: Dual HT16K33 14-segment LED displays (I2C addresses 0x70, 0x71) — combined 8-character output
- **Keypad**: 3x3 matrix keypad (9 keys; rows GP16-18, cols GP19-21)
- **Switches**:
  - 8x small latching toggles (2 rows of 4, via MCP23008 Expander 1)
  - 1x guarded latching toggle (heavy-action with safety cover)
  - 1x 2-position key switch
  - 1x 3-position rotary switch
  - 1x (On-Off-On) momentary toggle
  - 1x large execute/panic button
- **Encoder**: Incremental rotary encoder with push button
- **LEDs**: 9x NeoPixels (one per latching toggle + guarded toggle, indices 0–8); hardware provisions for up to 3 additional NeoPixel strips

#### Communication
- **Dual UART**:
  - Upstream (GP0/GP1): Communicates with Core/previous satellite
  - Downstream (GP8/GP9): Relays to next satellite in chain
- **Detection**: Automatic upstream/downstream device sensing

---

## 🚀 Getting Started

### Prerequisites

1. **Hardware**:
   - Raspberry Pi Pico 2 (RP2350)
   - USB-C cable for programming
   - 20V power supply (for production use)
   - Required peripherals based on your unit type

2. **Software**:
   - CircuitPython 10.x or later ([Download](https://circuitpython.org/board/raspberry_pi_pico_2/))
   - Code editor (VS Code, Thonny, etc.)

### Installation

1. **Flash CircuitPython** to your Pico 2:
   ```bash
   # Hold BOOTSEL button while plugging in USB
   # Drag and drop the .uf2 file to the RPI-RP2 drive
   ```

2. **Clone this repository**:
   ```bash
   git clone https://github.com/jimmydoh/jeb.git
   cd jeb
   ```

3. **Copy files to Pico**:
   ```bash
   # Copy the entire 'src' directory contents to the CIRCUITPY drive root
   cp -r src/* /path/to/CIRCUITPY/
   ```

4. **Configure your device**:
   ```bash
   # For CORE unit:
   cp examples/config-example-core.json /path/to/CIRCUITPY/config.json

   # For Satellite 01:
   cp examples/config-example-sat-01.json /path/to/CIRCUITPY/config.json
   ```

5. **Reset your Pico** - The device will boot and start the appropriate application

### First Boot

The system will:
1. Execute `boot.py` to safely initialize MOSFET control (prevents power glitches)
2. Load configuration from `config.json`
3. Enable hardware watchdog timer (8s timeout)
4. Launch the appropriate manager based on role (CORE or SAT)
5. Enter the main async event loop

---

## ⚙️ Configuration

The system is configured via `config.json` in the root directory:

### Core Unit Configuration
```json
{
    "role": "CORE",
    "type_id": "00",
    "type_name": "CORE",
    "mount_sd_card": false,
    "debug_mode": false,
    "test_mode": false
}
```

### Satellite Configuration
```json
{
    "role": "SAT",
    "type_id": "01",
    "type_name": "INDUSTRIAL",
    "mount_sd_card": false,
    "debug_mode": false,
    "test_mode": false
}
```

### Configuration Options

| Parameter | Type | Description |
|-----------|------|-------------|
| `role` | string | Device role: `"CORE"` (master) or `"SAT"` (satellite) |
| `type_id` | string | Device type identifier: `"00"` (core), `"01"` (industrial satellite) |
| `type_name` | string | Human-readable device name |
| `mount_sd_card` | boolean | Enable SD card mounting at boot (requires SD card hardware) |
| `debug_mode` | boolean | Enable verbose debug output |
| `test_mode` | boolean | Run console manager in test/diagnostic mode |
| `log_level` | string | Log verbosity: `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"` |
| `uart_baudrate` | integer | UART communication speed (default: `921600`) |
| `uart_buffer_size` | integer | UART RX buffer size in bytes (default: `4096`) |
| `led_brightness` | float | Global LED brightness 0.0–1.0 (default: `0.3`) |
| `web_server_enabled` | boolean | Enable the web-based configurator (Pico 2W) |
| `web_server_port` | integer | Web server port (default: `8080`) |
| `wifi_ssid` | string | WiFi network name (Pico 2W, for OTA/web features) |
| `wifi_password` | string | WiFi password |
| `update_url` | string | OTA firmware update server base URL |
| `root_data_dir` | string | Root directory for persistent data (default: `"/sd/"`) |
| `hardware_features` | object | Selectively disable hardware subsystems (audio, display, matrix, leds, buzzer, power, segment, hid) |
| `resource_monitor` | object | Resource monitoring settings (`enabled`, `interval_seconds`) |
| `satellites` | object | Per-satellite configuration (e.g., display offset overrides) |

---

## 📁 Project Structure

```
jeb/
├── src/
│   ├── boot.py                    # Hardware safety initialization (runs before code.py)
│   ├── code.py                    # Main entry point and application loader
│   ├── config.json                # Device configuration
│   ├── updater.py                 # Over-The-Air (OTA) firmware update system (Pico 2W)
│   │
│   ├── core/                      # CORE unit implementation
│   │   ├── __init__.py
│   │   └── core_manager.py        # Main CORE controller
│   │
│   ├── satellites/                # Satellite unit implementations
│   │   ├── __init__.py
│   │   ├── base_firmware.py       # Base satellite firmware class
│   │   ├── base_driver.py         # Base satellite driver class
│   │   ├── sat_01_driver.py       # Satellite 01 hardware driver
│   │   └── sat_01_firmware.py     # Satellite 01 firmware
│   │
│   ├── modes/                     # Mode system (UI/UX states) — 50+ game and visualization modes
│   │   ├── base.py                # BaseMode class for inheritance
│   │   ├── manifest.py            # Mode manifest/registry
│   │   ├── main_menu.py           # Main menu / dashboard
│   │   ├── game_mode.py           # Base game mode class
│   │   ├── utility_mode.py        # System utilities
│   │   ├── debug.py               # Debug/diagnostic mode
│   │   ├── global_settings.py     # Global settings mode
│   │   ├── layout_configurator.py # Display layout configurator
│   │   ├── power_telemetry.py     # Power monitoring mode
│   │   ├── zero_player.py         # Zero-player menu
│   │   ├── industrial_startup.py  # Industrial satellite startup sequence
│   │   │
│   │   ├── # --- CORE Game Modes ---
│   │   ├── simon.py               # Simon Says
│   │   ├── jebris.py              # Tetris-style game
│   │   ├── safe_cracker.py        # Safe cracking puzzle
│   │   ├── pong.py                # Mini Pong
│   │   ├── cyber_snake.py         # Cyber Snake
│   │   ├── astro_breaker.py       # Astro Breaker (Breakout)
│   │   ├── trench_run.py          # Trench Run
│   │   ├── lunar_salvage.py       # Lunar Salvage
│   │   ├── data_flow.py           # Data Flow puzzle
│   │   ├── virtual_pet.py         # Virtual Pet
│   │   ├── groovebox.py           # JEB-808 Groovebox (music sequencer)
│   │   ├── abyssal_rover.py       # Abyssal Rover maze game
│   │   │
│   │   ├── # --- CORE+INDUSTRIAL Game Modes ---
│   │   ├── abyssal_ping.py        # Abyssal Ping (sonar)
│   │   ├── artillery_command.py   # Artillery Command
│   │   ├── bunker_defuse.py       # Bunker Defuse (asymmetric co-op)
│   │   ├── defcon_commander.py    # DEFCON Commander
│   │   ├── enigma_byte.py         # Enigma Byte cipher
│   │   ├── flux_scavenger.py      # Flux Scavenger
│   │   ├── iron_canopy.py         # Iron Canopy
│   │   ├── magnetic_containment.py # Magnetic Containment
│   │   ├── maglev_express.py      # Maglev Express
│   │   ├── mecha_forge.py         # Mecha Forge
│   │   ├── numbers_station.py     # Numbers Station
│   │   ├── orbital_docking.py     # Orbital Docking
│   │   ├── orbital_strike.py      # Orbital Strike
│   │   ├── pipeline_overload.py   # Pipeline Overload
│   │   ├── seismic_stabilizer.py  # Seismic Stabilizer
│   │   ├── vanguard_override.py   # Vanguard Override (shmup)
│   │   ├── frequency_hunter.py    # Frequency Hunter
│   │   ├── rhythm_mode.py         # Rhythm mode
│   │   │
│   │   └── # --- Zero-Player / Visualizations ---
│   │       ├── boids.py           # Boid flocking simulation
│   │       ├── bouncing_sprite.py # Bouncing sprite physics
│   │       ├── conways_life.py    # Conway's Game of Life
│   │       ├── digital_rain.py    # Digital rain effect
│   │       ├── emoji_reveal.py    # Emoji reveal puzzle
│   │       ├── falling_sand.py    # Falling sand simulation
│   │       ├── langtons_ant.py    # Langton's Ant
│   │       ├── lava_lamp.py       # Lava lamp animation
│   │       ├── lissajous.py       # Lissajous curves
│   │       ├── lorenz_attractor.py # Lorenz attractor
│   │       ├── perlin_flow.py     # Perlin noise vector flow
│   │       ├── plasma.py          # Plasma effect
│   │       ├── reaction_diffusion.py # Gray-Scott reaction diffusion
│   │       ├── sorting_visualizer.py # Sorting algorithm visualizer
│   │       ├── starfield.py       # 3D starfield
│   │       ├── wireworld.py       # Wireworld cellular automaton
│   │       └── wolfram_automata.py # Wolfram 1D cellular automata
│   │
│   ├── managers/                  # System managers
│   │   ├── __init__.py
│   │   ├── adc_manager.py         # I2C ADC (ADS1115) and native ADC management
│   │   ├── audio_manager.py       # I2S audio system management
│   │   ├── base_pixel_manager.py  # Base class for pixel-based displays
│   │   ├── buzzer_manager.py      # PWM buzzer control
│   │   ├── console_manager.py     # Serial console management
│   │   ├── data_manager.py        # Data storage and management
│   │   ├── display_manager.py     # OLED display control
│   │   ├── global_animation_controller.py  # Centralized animation coordination
│   │   ├── hid_manager.py         # Human Interface Device handling
│   │   ├── led_manager.py         # LED control
│   │   ├── matrix_manager.py      # LED matrix control (8×8 to 16×16+)
│   │   ├── power_manager.py       # Power system monitoring
│   │   ├── relay_manager.py       # UART message relay
│   │   ├── render_manager.py      # LED rendering coordination and frame sync
│   │   ├── resource_manager.py    # System resource tracking
│   │   ├── satellite_network_manager.py  # Satellite network coordination
│   │   ├── segment_manager.py     # 14-segment display control
│   │   ├── synth_manager.py       # Audio synthesis
│   │   ├── watchdog_manager.py    # Hardware watchdog timer
│   │   ├── web_server_manager.py  # Web-based configurator
│   │   └── wifi_manager.py        # WiFi connectivity (Pico 2W)
│   │
│   ├── transport/                 # Communication transport layer
│   │   ├── __init__.py
│   │   ├── base_transport.py      # Abstract transport base class
│   │   ├── file_transfer.py       # File transfer protocol
│   │   ├── message.py             # Message structure definitions
│   │   ├── protocol.py            # Protocol definitions and command mappings
│   │   └── uart_transport.py      # UART transport implementation
│   │
│   ├── utilities/                 # Helper modules
│   │   ├── __init__.py
│   │   ├── audio_analyzer.py      # Audio analysis utilities
│   │   ├── audio_channels.py      # Audio channel management
│   │   ├── cobs.py                # COBS encoding/decoding
│   │   ├── context.py             # Global context management
│   │   ├── crc.py                 # CRC calculations
│   │   ├── icons.py               # Icon definitions for display
│   │   ├── jeb_pixel.py           # Custom pixel class
│   │   ├── logger.py              # Logging system
│   │   ├── matrix_animations.py   # Reusable LED matrix animations
│   │   ├── mcp_keys.py            # MCP23008 key mappings
│   │   ├── palette.py             # Color palette definitions
│   │   ├── payload_parser.py      # Binary payload parsing
│   │   ├── pins.py                # Pin definitions per firmware type
│   │   ├── power_bus.py           # Power bus management
│   │   ├── synth_registry.py      # Synthesis pattern registry
│   │   └── tones.py               # Musical tone definitions
│   │
│   └── dummies/                   # Hardware stub implementations for disabled features
│
├── docs/                          # Documentation
│   ├── hardware-core.md           # CORE hardware specifications
│   ├── hardware-sat-01.md         # Satellite 01 specifications
│   ├── ADC_MANAGER_EXTENSION.md   # ADC Manager edge cases and extensibility
│   ├── ADC_MANAGER_INTEGRATION.md # ADC Manager integration examples
│   ├── BINARY_PROTOCOL.md         # Binary protocol specification
│   ├── CRC_IMPLEMENTATION.md      # CRC implementation details
│   ├── DISPLAY_LAYOUT_QUICK_REFERENCE.md  # Display layout quick reference
│   ├── DISPLAY_LAYOUT_SYSTEM.md   # Display layout system documentation
│   ├── DISPLAY_LAYOUT_VISUAL_GUIDE.md     # Display layout visual guide
│   ├── DISPLAY_MANAGER_REDESIGN_SUMMARY.md  # DisplayManager redesign summary
│   ├── EMULATOR_ADC_TESTING.md    # ADC emulator testing guide
│   ├── INDUSTRIAL_STARTUP_16x16.md  # Industrial startup 16×16 matrix
│   ├── LED_RENDERING.md           # LED rendering optimization and frame sync
│   ├── MATRIX_ARBITRARY_CONFIGURATIONS.md  # Arbitrary matrix configuration support
│   ├── OPTIMIZATION_SUMMARY.md    # Performance optimizations and improvements
│   ├── OTA_UPDATE.md              # Over-The-Air firmware update system
│   ├── PAYLOAD_ENCODING.md        # Payload encoding documentation
│   ├── SATELLITE_DEV.md           # Satellite development guide
│   ├── SYNTHIO_IMPLEMENTATION.md  # Audio synthesis implementation
│   ├── TRANSPORT_ABSTRACTION.md   # Transport layer abstraction
│   ├── TUPLE_MUTABILITY_ANALYSIS.md  # Tuple/list mutability analysis
│   └── WEB_CONFIGURATOR.md        # Web-based field service configurator
│
├── examples/                      # Example configurations and scripts
│   ├── config-example-core.json   # CORE config template
│   ├── config-example-sat-01.json # Satellite config template
│   ├── display_custom_layout.py   # Custom display layout demo
│   ├── display_standard_layout.py # Standard display layout demo
│   ├── download_mpy_files.py      # Script for downloading/verifying compiled MPY files
│   └── example_test_web_server.py # Web server integration example
│
├── tests/                         # Test suite (Python/pytest)
│   ├── test_*.py                  # Unit and integration tests
│   └── performance_*.py           # Performance benchmarks
│
├── .gitignore                     # Git ignore patterns
├── LICENSE                        # MIT License
├── README.md                      # This file
├── TEST_COVERAGE_REPORT.md        # Test coverage report and unit test summary
└── VERSION                        # Current version identifier for builds
```

---

## 🛡️ Safety Features

JEB incorporates multiple layers of safety protection:

### Hardware Protection

1. **MOSFET Firewall**
   - High-side P-Channel MOSFET (IRF5305) with NPN driver
   - 100kΩ pull-down ensures OFF state during boot/float conditions
   - Prevents power delivery during undefined MCU states

2. **Electrical Protection**
   - 3A blade fuse on input power
   - 3.3V Zener diodes on all ADC inputs
   - 1kΩ series resistors on UART lines (ESD/hot-swap protection)
   - SS54 Schottky diodes for reverse polarity protection (satellites)
   - Polyfuses for overcurrent protection

3. **Grounding Strategy**
   - Star topology split-ground configuration
   - Separate power (22AWG) and signal (28AWG) ground returns
   - Copper busbar for high-current returns

### Software Protection

1. **Watchdog Timer**
   - 8-second hardware watchdog
   - Automatic system reset on hangs
   - Fed regularly by async event loop

2. **Undervoltage Lockout (UVLO)**
   - Blocks system startup if input < 18.0V
   - Prevents brownout conditions and unstable operation

3. **Link Protection** (Satellites)
   - Automatic power cutoff on cable disconnect
   - Brownout detection with automatic load reduction
   - Short circuit watchdog with emergency kill

4. **Error Recovery**
   - Comprehensive exception handling
   - Automatic supervisor reload on critical crashes
   - Graceful degradation on subsystem failures

---

## 🔨 Development

### Test Mode

Enable test mode in `config.json` to run system tests without full hardware:

```json
{
    "test_mode": true
}
```

This runs diagnostic tests and validation routines for the system components.

### Testing

The project includes a comprehensive test suite in the `tests/` directory with unit tests, integration tests, and performance benchmarks. Tests are written for Python/pytest and can be run on development machines:

- Unit tests for individual components (managers, utilities, transport layer)
- Integration tests for multi-component interactions
- Performance benchmarks for critical paths (brightness calculations, payload encoding)
- Hardware-specific tests for satellite communication and protocol validation

**Test Specialist**: The repository includes a custom GitHub Copilot agent specifically designed for test repair and coverage expansion. See [`.github/copilot/`](.github/copilot/) for:
- Automated repair of failing or flaky unit tests
- Expansion of test coverage for untested modules
- Issue creation for source code bugs (without modifying source code)
- Best practices and examples for testing CircuitPython applications

For usage instructions and examples, see [`.github/copilot/USAGE.md`](.github/copilot/USAGE.md).

### Development Roadmap

**CORE Unit:**
- [ ] Advanced error logging for satellite communications
- [ ] Matrix animations (non-blocking, per-pixel and fill modes)
- [ ] Matrix-based progress indicators
- [ ] Victory and boot animations
- [ ] Power integrity testing under various loads
- [ ] Voltage calibration system

**Satellite 01:**
- [ ] Power monitoring via ADC
- [ ] Power protection for downstream satellites
- [ ] Async task optimization
- [ ] Configuration commands from master
- [ ] UART buffering and flow control
- [ ] Multi-satellite chain testing

### Automated Builds

The repository includes a GitHub Action workflow that automatically compiles Python source files to MicroPython bytecode (`.mpy` files) for faster loading and reduced memory usage. The workflow:

- Uses CircuitPython-specific `mpy-cross` executable for compilation
- Compiles all Python files in `src/` (except boot.py and code.py)
- Copies boot.py and code.py as-is (not compiled)
- Generates a `manifest.json` with file paths and SHA256 hashes
- Generates a lightweight `version.json` for quick version checks
- Automatically determines version from VERSION file, git tags, or git history
- Uploads compiled files as GitHub Actions artifacts
- Creates release archives when tags are pushed

**Version Management:** Update the `VERSION` file in the repository root to specify the build version, or use git tags for releases.

For details, see [.github/workflows/README.md](.github/workflows/README.md).

### Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Follow the existing code style
4. Test thoroughly with hardware
5. Submit a pull request

---

## 📚 Documentation

Detailed hardware and implementation documentation is available in the `docs/` directory:

- **[hardware-core.md](docs/hardware-core.md)**: Complete CORE unit specifications, GPIO mapping, and schematics
- **[hardware-sat-01.md](docs/hardware-sat-01.md)**: Industrial Satellite specifications and pinout
- **[ADC_MANAGER_EXTENSION.md](docs/ADC_MANAGER_EXTENSION.md)**: ADC Manager edge cases and extensibility guide
- **[ADC_MANAGER_INTEGRATION.md](docs/ADC_MANAGER_INTEGRATION.md)**: ADC Manager integration examples for voltage monitoring
- **[BINARY_PROTOCOL.md](docs/BINARY_PROTOCOL.md)**: Binary protocol specification and message format
- **[CRC_IMPLEMENTATION.md](docs/CRC_IMPLEMENTATION.md)**: CRC implementation and validation details
- **[DISPLAY_LAYOUT_QUICK_REFERENCE.md](docs/DISPLAY_LAYOUT_QUICK_REFERENCE.md)**: Quick reference for display layout APIs
- **[DISPLAY_LAYOUT_SYSTEM.md](docs/DISPLAY_LAYOUT_SYSTEM.md)**: Three-zone display layout system (Legacy/Standard/Custom modes)
- **[DISPLAY_LAYOUT_VISUAL_GUIDE.md](docs/DISPLAY_LAYOUT_VISUAL_GUIDE.md)**: Visual guide to display layout zones
- **[DISPLAY_MANAGER_REDESIGN_SUMMARY.md](docs/DISPLAY_MANAGER_REDESIGN_SUMMARY.md)**: DisplayManager redesign implementation summary
- **[EMULATOR_ADC_TESTING.md](docs/EMULATOR_ADC_TESTING.md)**: ADC testing guide for brownout and voltage simulation
- **[INDUSTRIAL_STARTUP_16x16.md](docs/INDUSTRIAL_STARTUP_16x16.md)**: Industrial startup mode 16×16 matrix investigation
- **[LED_RENDERING.md](docs/LED_RENDERING.md)**: LED rendering optimization, frame sync, and animation architecture
- **[MATRIX_ARBITRARY_CONFIGURATIONS.md](docs/MATRIX_ARBITRARY_CONFIGURATIONS.md)**: Arbitrary matrix configuration support for dual, quad, and custom LED matrix layouts
- **[OPTIMIZATION_SUMMARY.md](docs/OPTIMIZATION_SUMMARY.md)**: Transport layer performance optimizations
- **[OTA_UPDATE.md](docs/OTA_UPDATE.md)**: Over-The-Air firmware update system (Pico 2W)
- **[PAYLOAD_ENCODING.md](docs/PAYLOAD_ENCODING.md)**: Payload encoding type safety documentation
- **[SATELLITE_DEV.md](docs/SATELLITE_DEV.md)**: Guide for creating new satellite firmware classes
- **[SYNTHIO_IMPLEMENTATION.md](docs/SYNTHIO_IMPLEMENTATION.md)**: Audio synthesis system implementation
- **[TRANSPORT_ABSTRACTION.md](docs/TRANSPORT_ABSTRACTION.md)**: Transport layer abstraction design
- **[TUPLE_MUTABILITY_ANALYSIS.md](docs/TUPLE_MUTABILITY_ANALYSIS.md)**: Tuple vs list mutability analysis for payloads
- **[WEB_CONFIGURATOR.md](docs/WEB_CONFIGURATOR.md)**: Web-based field service configurator with remote configuration and monitoring

Additional resources:

- **[TEST_COVERAGE_REPORT.md](TEST_COVERAGE_REPORT.md)**: Comprehensive test coverage analysis and unit test summary
- **[.github/workflows/README.md](.github/workflows/README.md)**: GitHub Actions workflows for automated builds and testing

---

## 📞 Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Check existing documentation in the `docs/` folder
- Review hardware specifications for wiring and setup

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🎯 Design Philosophy

JEB was designed with these core principles:

1. **Safety First**: Multiple redundant protection layers prevent hardware damage and unsafe conditions
2. **Modularity**: Plug-and-play satellite architecture allows flexible system expansion
3. **Reliability**: Watchdog timers, error recovery, and graceful degradation ensure continuous operation
4. **Real-World Ready**: Industrial-grade hardware design with proper ESD protection, grounding, and power management
5. **Developer Friendly**: Clean async architecture with comprehensive documentation

---

<div align="center">

**Built with ❤️ for robust, safe, and expandable embedded control systems**

*JEB - JADNET Electronics Box*

</div>
