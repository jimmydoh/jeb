# PROJECT: JEB - JADNET Electronics Box - INDUSTRIAL SATELLITE (SLAVE)
**VERSION:** 0.2 - 2026-02-23
**MCU:** Raspberry Pi Pico 2 (RP2350)
**OS:** CircuitPython 10.x+
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
* **UART_DOWN (GP8/GP9):** Communicates with the next Satellite in the chain.

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

* **DISPLAYS:** 1x 8-Character 14-Segment LED Display driven via **Dual HT16K33 Backpacks**.
    * **Address Left:** 0x70. **Address Right:** 0x71.
    * **Protocol:** I2C (GP4/GP5).
* **INPUTS:**
    * **Small Latching Toggles:** 8x Latching Toggles arranged in **2 rows of 4** (via Expander 1, pins 0–7).
    * **Guarded Latching Toggle:** 1x Heavy-action toggle with safety guard / **Master Arm** (Expander 2, pin 2).
    * **Key Switch:** 1x 2-Position Key Switch / **Secure State Toggle** (Expander 2, pin 3).
    * **Rotary Switch:** 1x 3-Position Rotary Switch / **Mode Selection / Power Routing** (Expander 2, pins 4–5).
    * **Momentary Toggle:** 1x On-Off-On Momentary Toggle / **Dual-direction momentary action** (Expander 2, pins 0–1).
    * **Execute Button:** 1x Large-format Single Momentary Button / **Panic or Execute** (Expander 2, pin 6).
    * **Keypad:** 9-digit 3x3 Matrix Keypad (Rows: GP16–18, Cols: GP19–21).
    * **Rotary Encoder:** Incremental Encoder (GP2/GP3) + Integrated Push Button (GP12).
    * **Dual MCP23008 Expanders:** Address 0x20 (INT: GP11) and 0x21 (INT: GP13) to accommodate all additional inputs.
* **FEEDBACK:**
    * **Status LEDs:** Individual NeoPixels (GP6) adjacent to each of the 8 small latching toggles and the guarded toggle (indices 0–8).
    * **LED Strips (TBD):** Provisions for up to **three 1×8 NeoPixel strips** for directional feedback / animations (e.g. left/right indicator, power gauges, progress bar).

---

## *** GPIO MAPPING ***

| Pin | Function | Description |
| :--- | :--- | :--- |
| **GP0** | UART_UP RX | Receive from Upstream |
| **GP1** | UART_UP TX | Transmit to Upstream |
| **GP2** | Encoder A | Rotary Encoder Phase A |
| **GP3** | Encoder B | Rotary Encoder Phase B |
| **GP4** | I2C SDA | Main Bus (Displays, Expanders) |
| **GP5** | I2C SCL | Main Bus (Displays, Expanders) |
| **GP6** | LED Data | NeoPixel Control Line |
| **GP7** | SPARE | |
| **GP8** | UART_DOWN TX | Transmit to Downstream |
| **GP9** | UART_DOWN RX | Receive from Downstream |
| **GP10**| Buzzer | PWM Audio (Piezo) |
| **GP11**| Expander 1 INT | MCP23008 #1 Interrupt (Active Low) |
| **GP12**| Encoder Push | Rotary Encoder Integrated Push Button |
| **GP13**| Expander 2 INT | MCP23008 #2 Interrupt (Active Low) |
| **GP14**| MOSFET Control | High = Downstream Power ON |
| **GP15**| Sat Detect | Active Low (Downstream Sense) |
| **GP16**| Keypad Row 1 | 3×3 Matrix Row |
| **GP17**| Keypad Row 2 | 3×3 Matrix Row |
| **GP18**| Keypad Row 3 | 3×3 Matrix Row |
| **GP19**| Keypad Col 1 | 3×3 Matrix Col |
| **GP20**| Keypad Col 2 | 3×3 Matrix Col |
| **GP21**| Keypad Col 3 | 3×3 Matrix Col |
| **GP22**| SPARE | |
| **GP23**| Internal | Power Supply Mode (Pico Std) |
| **GP24**| Internal | VBUS Sense (Pico Std) |
| **GP25**| SPARE | |
| **GP26** | ADC0 | Sense - 20V Input (Pre-MOSFET) [47k/6.8k] |
| **GP27** | ADC1 | Sense - 20V Bus (Post-MOSFET) [47k/6.8k] |
| **GP28** | ADC2 | Sense - 5V Logic Rail [10k/10k] |
| **GP29**| SPARE | |

### **EXPANDER 1 MAPPING (MCP23008 at 0x20, INT: GP11)**
*8x Small Latching Toggles arranged in 2 rows of 4.*

| Pin | Function | Description |
| :--- | :--- | :--- |
| **GP0** | Small Toggle 1 | Row 1, Position 1 (Active Low) |
| **GP1** | Small Toggle 2 | Row 1, Position 2 (Active Low) |
| **GP2** | Small Toggle 3 | Row 1, Position 3 (Active Low) |
| **GP3** | Small Toggle 4 | Row 1, Position 4 (Active Low) |
| **GP4** | Small Toggle 5 | Row 2, Position 1 (Active Low) |
| **GP5** | Small Toggle 6 | Row 2, Position 2 (Active Low) |
| **GP6** | Small Toggle 7 | Row 2, Position 3 (Active Low) |
| **GP7** | Small Toggle 8 | Row 2, Position 4 (Active Low) |

### **EXPANDER 2 MAPPING (MCP23008 at 0x21, INT: GP13)**
*Guarded toggle, key switch, rotary switch, momentary toggle, and execute button.*

| Pin | Function | Description |
| :--- | :--- | :--- |
| **GP0** | Momentary Toggle UP | On-Off-On Toggle — UP direction (Active Low) |
| **GP1** | Momentary Toggle DOWN | On-Off-On Toggle — DOWN direction (Active Low) |
| **GP2** | Guarded Latching Toggle | Heavy action / Master Arm (Active Low) |
| **GP3** | Key Switch | 2-Position Key Switch — Secure State ON (Active Low) |
| **GP4** | Rotary Switch A | 3-Position Rotary — Position A / Mode A (Active Low) |
| **GP5** | Rotary Switch B | 3-Position Rotary — Position B / Mode B (Active Low) |
| **GP6** | Execute Button | Large-format Momentary / Panic or Execute (Active Low) |
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
