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
- **Rich I/O**: 
  - 128x64 OLED display (I2C)
  - 8x8 NeoPixel matrix (GlowBit 64)
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
  - Dual 14-segment LED displays
  - 4x3 matrix keypad
  - 4x latching toggle switches
  - 6x NeoPixel indicators
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
- **Displays**: Dual HT16K33 14-segment LED displays (I2C addresses 0x70, 0x71)
- **Keypad**: 4x3 matrix (rows GP7-10, cols GP11-13)
- **Switches**: 4x latching toggles + 1x (On-Off-On) momentary
- **Encoder**: Incremental rotary encoder with push button
- **LEDs**: 6x NeoPixels with async animation engine

#### Communication
- **Dual UART**: 
  - Upstream (GP0/GP1): Communicates with Core/previous satellite
  - Downstream (GP4/GP5): Relays to next satellite in chain
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
| `test_mode` | boolean | Run in test mode (loads `TestManager` instead of production app) |

---

## 📁 Project Structure

```
jeb/
├── src/
│   ├── boot.py                    # Hardware safety initialization (runs before code.py)
│   ├── code.py                    # Main entry point and application loader
│   ├── config.json                # Device configuration
│   ├── protocol.py                # Protocol definitions and command mappings
│   │
│   ├── core/                      # CORE unit implementation
│   │   ├── __init__.py
│   │   └── core_manager.py        # Main CORE controller
│   │
│   ├── satellites/                # Satellite unit implementations
│   │   ├── __init__.py
│   │   ├── base.py                # Base satellite class
│   │   ├── sat_01_driver.py       # Satellite 01 hardware driver
│   │   └── sat_01_firmware.py     # Satellite 01 firmware
│   │
│   ├── modes/                     # Mode system (UI/UX states)
│   │   ├── base.py                # BaseMode class for inheritance
│   │   ├── main_menu.py           # Main menu mode
│   │   ├── game_mode.py           # Interactive game modes
│   │   ├── debug.py               # Debug/diagnostic mode
│   │   ├── utility_mode.py        # System utilities
│   │   ├── industrial_startup.py  # Industrial satellite startup sequence
│   │   ├── jebris.py              # Tetris-style game mode
│   │   ├── safe_cracker.py        # Safe cracking game mode
│   │   ├── simon.py               # Simon Says game mode
│   │   └── manifest.py            # Mode manifest/registry
│   │
│   ├── managers/                  # System managers
│   │   ├── __init__.py
│   │   ├── hid_manager.py         # Human Interface Device handling
│   │   ├── uart_manager.py        # UART communication handler
│   │   ├── audio_manager.py       # Audio system management
│   │   ├── buzzer_manager.py      # Buzzer control
│   │   ├── console_manager.py     # Serial console management
│   │   ├── data_manager.py        # Data storage and management
│   │   ├── display_manager.py     # OLED display control
│   │   ├── led_manager.py         # LED control
│   │   ├── matrix_manager.py      # LED matrix control
│   │   ├── power_manager.py       # Power system monitoring
│   │   ├── satellite_network_manager.py  # Satellite network coordination
│   │   ├── segment_manager.py     # 14-segment display control
│   │   ├── synth_manager.py       # Audio synthesis
│   │   ├── base_pixel_manager.py  # Base class for pixel-based displays
│   │   └── ring_buffer.py         # Ring buffer utility
│   │
│   ├── transport/                 # Communication transport layer
│   │   ├── __init__.py
│   │   ├── base_transport.py      # Abstract transport base class
│   │   ├── message.py             # Message structure definitions
│   │   └── uart_transport.py      # UART transport implementation
│   │
│   └── utilities/                 # Helper modules
│       ├── __init__.py
│       ├── cobs.py                # COBS encoding/decoding
│       ├── context.py             # Global context management
│       ├── crc.py                 # CRC calculations
│       ├── icons.py               # Icon definitions for display
│       ├── jeb_pixel.py           # Custom pixel class
│       ├── mcp_keys.py            # MCP23008 key mappings
│       ├── palette.py             # Color palette definitions
│       ├── payload_parser.py      # Binary payload parsing
│       ├── pins.py                # Pin definitions
│       ├── synth_registry.py      # Synthesis pattern registry
│       └── tones.py               # Musical tone definitions
│
├── docs/                          # Documentation
│   ├── hardware-core.md           # CORE hardware specifications
│   ├── hardware-sat-01.md         # Satellite 01 specifications
│   ├── BINARY_PROTOCOL.md         # Binary protocol specification
│   ├── CRC_IMPLEMENTATION.md      # CRC implementation details
│   ├── PAYLOAD_ENCODING.md        # Payload encoding documentation
│   ├── SYNTHIO_IMPLEMENTATION.md  # Audio synthesis implementation
│   └── TRANSPORT_ABSTRACTION.md   # Transport layer abstraction
│
├── examples/                      # Example configurations
│   ├── config-example-core.json   # CORE config template
│   └── config-example-sat-01.json # Satellite config template
│
├── tests/                         # Test suite (Python/pytest)
│   ├── test_*.py                  # Unit and integration tests
│   └── performance_*.py           # Performance benchmarks
│
├── .gitignore                     # Git ignore patterns
├── LICENSE                        # MIT License
├── TEST_COVERAGE_REPORT.md        # Test coverage report
└── README.md                      # This file
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
- **[BINARY_PROTOCOL.md](docs/BINARY_PROTOCOL.md)**: Binary protocol specification and message format
- **[CRC_IMPLEMENTATION.md](docs/CRC_IMPLEMENTATION.md)**: CRC implementation and validation details
- **[PAYLOAD_ENCODING.md](docs/PAYLOAD_ENCODING.md)**: Payload encoding and decoding documentation
- **[TRANSPORT_ABSTRACTION.md](docs/TRANSPORT_ABSTRACTION.md)**: Transport layer abstraction design
- **[SYNTHIO_IMPLEMENTATION.md](docs/SYNTHIO_IMPLEMENTATION.md)**: Audio synthesis system implementation

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
