# PROJECT: JEB - JADNET Electronics Box - INDUSTRIAL SATELLITE (SLAVE)
**VERSION:** 0.1 - 2024-06-05
**MCU:** Raspberry Pi Pico 2 (RP2350)
**OS:** CircuitPython 9.x+
**Type:** "01" (Industrial Expansion)

---

## *** PHYSICAL HARDWARE ARCHITECTURE ***

### ⚡ INPUT POWER & DISTRIBUTION
* **INPUT SOURCE:** 20V DC via RJ45 Pins 7 & 8 (Upstream).
* **PROTECTION:** * **SS54 Schottky Diode:** Prevents reverse polarity if Core is mis-plugged into the Output port.
    * **1.0A Polyfuse:** Protects local circuitry from overcurrent.
* **LOCAL BUCK:** 20V to 5V/1A DC-DC Converter. Powers the Pico 2, dual HT16K33 displays, and NeoPixels.
* **DOWNSTREAM PASS-THROUGH:** * Power is gated via a **High-Side Switch** (P-Channel MOSFET) controlled by the Pico.
    * Logic ensures power is only sent downstream if a valid satellite is detected.

### 🛡️ PORT LOGIC & SENSE
* **UPSTREAM PORT (IN):** Pins 1 & 2 are **Physically Bridged** to local GND. This allows the Core (or previous satellite) to detect this unit's presence.
* **DOWNSTREAM PORT (OUT):** Pins 1 & 2 are wired as **Input (GP15)** with an internal Pull-Up.
    * *Logic:* If GP15 is pulled LOW, a downstream device is plugged in.
* **GROUNDING:** Star topology. Local 5V return and RJ45 Power GND (Pins 3, 6, 8) meet at a central local point.

---

## *** COMMUNICATION & PINOUT (JADNET STD) ***

### UART DAISY-CHAIN
The Satellite acts as a repeater. It processes messages addressed to its ID and blindly relays others.
* **UART_UP (GP0/GP1):** Communicates with the Master (or previous Satellite).
* **UART_DOWN (GP4/GP5):** Communicates with the next Satellite in the chain.

### RJ45 PINOUT (T568-B)
1.  **White Orange:** SENSE (GP15 on Downstream side, Bridged to GND on Upstream side).
2.  **Orange:** SENSE GND.
3.  **White Green:** UART TX/RX (Upstream GP0 / Downstream GP1).
4.  **Blue:** GND.
5.  **White Blue:** UART TX/RX (Upstream GP1 / Downstream GP0).
6.  **Green:** GND.
7.  **White Brown:** 20V VCC (Pass-through).
8.  **Brown:** 20V VCC (Pass-through).

---

## *** UI/UX COMPONENTS ***

* **DISPLAYS:** Dual 14-Segment LED Displays (HT16K33).
    * **Address:** 0x70 (Right), 0x71 (Left).
    * **Protocol:** I2C (GP2/GP3).
* **INPUTS:**
    * **Keypad:** 4x3 Matrix (Rows: GP7-10, Cols: GP11-13).
    * **Toggles:** 4x Latching Toggles (GP20-23) with internal Pull-Ups.
    * **Momentary:** 1x (On-Off-On) Toggle (GP24 Up / GP25 Down).
    * **Rotary:** Incremental Encoder (GP17/18) + Push Button (GP19).
* **FEEDBACK:** 6x NeoPixels (GP6). Asynchronous animation engine.

---

## *** GPIO MAPPING ***

| Pin | Function | Description |
| :--- | :--- | :--- |
| **GP0** | UART_UP RX | Receive from Upstream |
| **GP1** | UART_UP TX | Transmit to Upstream |
| **GP2** | Encoder A | Rotary Encoder Phase A |
| **GP3** | Encoder B | Rotary Encoder Phase B |
| **GP4** | I2C SDA | Main Bus (Displays, Expander) |
| **GP5** | I2C SCL | Main Bus (Displays, Expander) |
| **GP6** | LED Data | NeoPixel Control Line |
| **GP7** | SPARE | |
| **GP8** | UART_DOWN TX | Transmit to Downstream |
| **GP9** | UART_DOWN RX | Receive from Downstream |
| **GP10**| Buzzer | PWM Audio (Piezo) |
| **GP11**| Expander INT | MCP23008 Interrupt (Active Low) |
| **GP12**| SPARE | |
| **GP13**| SPARE | |
| **GP14**| MOSFET Control | High = Downstream Power ON |
| **GP15**| Sat Detect | Active Low (Downstream Sense) |
| **GP16**| Keypad Row 1 | Matrix Row |
| **GP17**| Keypad Row 2 | Matrix Row |
| **GP18**| Keypad Row 3 | Matrix Row |
| **GP19**| Keypad Col 1 | Matrix Col |
| **GP20**| Keypad Col 2 | Matrix Col |
| **GP21**| Keypad Col 3 | Matrix Col |
| **GP22**| SPARE | |
| **GP23**| Internal | Power Supply Mode (Pico Std) |
| **GP24**| Internal | VBUS Sense (Pico Std) |
| **GP25**| Encoder Push | Rotary Encoder Button |
| **GP26** | ADC0 | Sense - 20V Input (Pre-MOSFET) [47k/6.8k] |
| **GP27** | ADC1 | Sense - 20V Bus (Post-MOSFET) [47k/6.8k] |
| **GP28** | ADC2 | Sense - 5V Logic Rail [10k/10k] |
| **GP29**| SPARE | |

### **EXPANDER MAPPING (MCP23008 at 0x20)**

| Pin | Function | Description |
| :--- | :--- | :--- |
| **GP0** | Latching 1 | Toggle Switch (Active Low) |
| **GP1** | Latching 2 | Toggle Switch (Active Low) |
| **GP2** | Latching 3 | Toggle Switch (Active Low) |
| **GP3** | Latching 4 | Toggle Switch (Active Low) |
| **GP4** | Momentary Up | Toggle 5 Direction Up |
| **GP5** | Momentary Dn | Toggle 5 Direction Down |
| **GP6** | SPARE | |
| **GP7** | SPARE | |

---

## *** PROTECTION STRATEGY ***

1.  **Brownout Detection:**
    * Monitors **GP28 (5V Rail)**. If voltage dips < 4.7V, LEDs dim automatically to save power.
    * Monitors **GP26 (Input)**. If Upstream < 18.0V, Downstream power is denied.
2.  **Short Circuit Watchdog:**
    * Monitors **GP27 (Downstream Bus)**. If voltage drops < 17.0V while enabled, the system triggers an **Emergency Kill** (GP14 Low) to isolate the fault.
3.  **Link Loss Kill-Switch:**
    * If **GP15 (Detect)** goes HIGH (cable unplugged), power is immediately cut to prevent exposed live pins on the output port.
