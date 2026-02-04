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
| **GP0** | UART TX | Transmit to Satellite Bus |
| **GP1** | UART RX | Receive from Satellite Bus |
| **GP2** | Encoder A | Rotary Encoder Phase A |
| **GP3** | Encoder B | Rotary Encoder Phase B |
| **GP4** | I2C SDA | Main Bus (OLED, Expander) |
| **GP5** | I2C SCL | Main Bus (OLED, Expander) |
| **GP6** | LED Data | NeoPixel Control Line |
| **GP7** | E-Stop Detect | Active Low (Safety Cut-off) |
| **GP8** | SPARE | |
| **GP9** | SPARE | |
| **GP10**| Buzzer | PWM Audio (Piezo) |
| **GP11**| Expander INT | MCP23008 Interrupt (Active Low) |
| **GP12**| SPARE | |
| **GP13**| SPARE | |
| **GP14**| MOSFET Control | High = Power ON |
| **GP15**| Sat Detect | Active Low (Link Sense) |
| **GP16**| SPI MISO | SD Card |
| **GP17**| SPI CS | SD Card |
| **GP18**| SPI SCK | SD Card |
| **GP19**| SPI MOSI | SD Card |
| **GP20**| I2S SCK | Audio Amp Bit Clock |
| **GP21**| I2S WS | Audio Amp Word Select |
| **GP22**| I2S SD | Audio Amp Data |
| **GP23**| Internal | Power Supply Mode (Pico Std) |
| **GP24**| Internal | VBUS Sense (Pico Std) |
| **GP25**| Encoder Push | Rotary Encoder Button |
| **GP26**| ADC0 | Sense - 20V Raw Input (47k/6.8k) |
| **GP27**| ADC1 | Sense - 20V Bus Output (47k/6.8k) |
| **GP28**| ADC2 | Sense - 5V Logic Rail (10k/10k) |
| **GP29**| ADC3 | Sense - 5V LED Rail (10k/10k) |

### **EXPANDER MAPPING (MCP23008 at 0x20)**

| Pin | Function | Logic |
| :--- | :--- | :--- |
| **GP0** | Button A | Face Button (Active Low) |
| **GP1** | Button B | Face Button (Active Low) |
| **GP2** | Button C | Face Button (Active Low) |
| **GP3** | Button D | Face Button (Active Low) |
| **GP4** | SPARE | |
| **GP5** | SPARE | |
| **GP6** | SPARE | |
| **GP7** | SPARE | |

---

## *** PROTECTION STRATEGY ***

1.  **Hardware Lockout:** 100kΩ resistor prevents MOSFET from opening during boot.
2.  **Electrical Buffer:** 1kΩ resistors protect UART pins from cable faults.
3.  **Voltage Clamp:** Zener diodes on all ADC inputs prevent >3.3V exposure.
4.  **Software UVLO:** Blocking logic prevents system initialization under 18V.
5.  **Async E-Stop:** Dedicated 100Hz monitoring task ensures sub-20ms shutdown response.
