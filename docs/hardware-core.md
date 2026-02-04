# PROJECT: JEB - JADNET Electronics Box - CORE COMMAND UNIT (MASTER)
**VERSION:** 2.2 - 2026-02-01
**MCU:** Raspberry Pi Pico 2 (RP2350)
**OS:** CircuitPython 10.x+
**Architecture:** Asynchronous Global State with Mode Inheritance

---

## *** PHYSICAL HARDWARE ARCHITECTURE ***

### ⚡ INPUT POWER & BUCK DISTRIBUTION
* **PROTECTION:** USB-C PD 20V Input -> 3A Blade Fuse -> 1000uF 35V Electrolytic Cap.
* **LOGIC RAIL:** 20V Input -> 5V/2.5A Buck -> Powers Pico 2, OLED, and Piezo.
* **LED RAIL:** 20V Input -> 5V/5A Buck -> Powers GlowBit 64 Matrix.
* **RULE:** Logic and LED bucks are physically separated to prevent Matrix noise from inducing jitter in the Pico's ADC readings.

### 🛡️ MOSFET FIREWALL (HIGH-SIDE SWITCH)
* **MAIN SWITCH:** IRF5305 P-Channel MOSFET.
* **NPN DRIVER:** 2N3904 Transistor.
* **TRIGGER:** Pico GP14 -> 1kΩ Resistor -> 2N3904 Base.
* **GATE DIVIDER:** 10kΩ Pull-up (20V to Gate) + 10kΩ Limiter (Gate to 2N3904 Collector).
* **HARDENING:** **100kΩ Pull-down resistor** added to 2N3904 Base to ensure the MOSFET remains strictly OFF during MCU boot-up or floating pin states.

### 📊 SENSE BOARD (CONDITIONING & UVLO)
* **20V RAILS (RAW & BUS):** 47k / 6.8k Resistor Divider -> 3.3V Zener Diode + 0.1uF Cap -> GP26/GP27.
* **5V RAILS (LOGIC & LED):** 10k / 10k Resistor Divider -> 3.3V Zener Diode + 0.1uF Cap -> GP28/GP29.
* **SAFETY GATE:** Software implementation (UVLO) halts startup if RAW Input < 18.0V.
* **RULE:** Zener "stripe" (cathode) must face the Pico pins to clamp overvoltage at 3.3V.

### 🔌 BORDER CONTROL (RJ45 JUNCTION & GROUNDING)
* **TOPOLOGY:** Split-Ground "Star" Configuration.
* **DRAIN (BUSBAR):** Thick 22AWG wire for high-current satellite returns to Copper Busbar.
* **REFERENCE (PICO):** Thin 28AWG wire for zero-ohm logic signaling to Pico GND.
* **PROTECTION:** **1kΩ Series Resistors** added to UART TX/RX lines (GP0/GP1) to buffer against hot-swap spikes and ESD.

---

## *** COMMUNICATION & PINOUT (JADNET 2.2 STD) ***

### UART VIA RJ45 (T568-B CABLE)
1.  **White Orange:** SENSE (GP15, pulls to GND via Pin 2 bridge on satellite).
2.  **Orange:** SENSE GND (Logic Ground Rail).
3.  **White Green:** UART TX (GP0 via 1kΩ).
4.  **Blue:** GND (Logic Ground Rail).
5.  **White Blue:** UART RX (GP1 via 1kΩ).
6.  **Green:** GND (Logic Ground Rail).
7.  **White Brown:** 20V VCC (POST-MOSFET - Drain).
8.  **Brown:** 20V VCC (POST-MOSFET - Drain).

---

## *** UI/UX COMPONENTS ***

* **OLED:** 128x64 I2C SSD1306. **Requires 4.7kΩ external pull-ups** on SDA/SCL.
* **MATRIX:** GlowBit 64 (8x8 NeoPixel Matrix).
* **AUDIO 1:** I2S 3W Class D Amp -> 4-ohm Transducer/Exciter.
* **PLANNED AUDIO 2:** Passive Piezo Buzzer (GP TBD via 100Ω) for hardware alerts/diagnostics.
* **ENCODER:** Absolute Position tracking (handled by Satellite-side interrupts).

---

## *** GPIO MAPPING ***

| Pin | Function | Logic |
| :--- | :--- | :--- |
| **GP0** | UART TX | 115200 Baud (via 1kΩ) |
| **GP1** | UART RX | 115200 Baud (via 1kΩ) |
| **GP2** | Rotary Encoder A | |
| **GP3** | Rotary Encoder B | |
| **GP4** | I2C SDA | Requires 4.7kΩ Pull-ups |
| **GP5** | I2C SCL | Requires 4.7kΩ Pull-ups |
| **GP6** | GlowBit Matrix Control | |
| **GP7** | E-Stop Input | Active Low (Normally Closed to GND) |
| **GP8** | SPARE | |
| **GP9** | SPARE | |
| **GP10**| Button A | Face Buttons (Active Low) |
| **GP11**| Button B | Face Buttons (Active Low) |
| **GP12**| Button C | Face Buttons (Active Low) |
| **GP13**| Button D | Face Buttons (Active Low) |
| **GP14**| MOSFET Enable | High = ON (NPN Base) |
| **GP15**| Sat Detect | Active Low (Link Sense) |
| **GP16**| SPI MISO | Planned |
| **GP17**| SPI CS | Planned |
| **GP18**| SPI SCK | Planned |
| **GP19**| SPI MOSI | Planned |
| **GP20**| I2S Audio SCK | |
| **GP21**| I2S Audio WS | |
| **GP22**| I2S Audio SD | |
| **GP23**| Internal Pico | Power |
| **GP24**| Internal Pico | VBUS Sense |
| **GP25**| Encoder Push Button | |
| **GP26**| ADC0 | Sense - 20V Raw Input (47k/6.8k) |
| **GP27**| ADC1 | Sense - 20V Bus Output (47k/6.8k) |
| **GP28**| ADC2 | Sense - 5V Logic Rail (10k/10k) |
| **GP29**| ADC3 | Sense - 5V LED Rail (10k/10k) |

---

## *** PROTECTION STRATEGY ***

1.  **Hardware Lockout:** 100kΩ resistor prevents MOSFET from opening during boot.
2.  **Electrical Buffer:** 1kΩ resistors protect UART pins from cable faults.
3.  **Voltage Clamp:** Zener diodes on all ADC inputs prevent >3.3V exposure.
4.  **Software UVLO:** Blocking logic prevents system initialization under 18V.
5.  **Async E-Stop:** Dedicated 100Hz monitoring task ensures sub-20ms shutdown response.
