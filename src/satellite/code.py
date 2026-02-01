"""
PROJECT: JEB - JADNET Electronics Box - INDUSTRIAL SATELLITE (SLAVE)
VERSION: 0.1 - 2024-06-05
MCU: Raspberry Pi Pico 2 (RP2350)
OS: CircuitPython
TYPE: "01" (Industrial)

*** PHYSICAL HARDWARE ARCHITECTURE ***
--- SUB-CIRCUIT MANIFESTS (SATELLITE) ---
POWER ENTRY & PROTECTION
- INBOUND: 20V via RJ45 Pins 7 & 8 -> 5A Schottky Diode (SS54) -> 1A Polyfuse -> Local Buck.
- LOCAL BUCK: 20V to 5V/1A Converter for local Pico, Displays, and NeoPixels.
- REVERSE PROTECTION: Schottky diode prevents back-feeding 20V if Core is mis-plugged into OUT port.
PORT LOGIC & SENSE
- INBOUND PORT (UPSTREAM): Pins 1 & 2 PHYSICALLY BRIDGED to local GND.
- OUTBOUND PORT (DOWNSTREAM): Pins 1 & 2 wired as INPUT (GP Sense) with Pull-Up (Mirror of Master).
- SAFETY: Power only flows to downstream ports if a bridge is detected on Pins 1/2.
GROUNDING
- STAR POINT: Local 5V return and RJ45 Power GND (3, 6, 8) meet at a local central point.

--- COMMUNICATION ---
UART Daisy-Chain via RJ45 (Bypassing via Software).
 - UART_UP (GP0/GP1): Connected to Master/Previous Sat.
 - UART_DOWN (GP4/GP5): Connected to Next Sat.

--- RJ45 PINOUT AND T568-B CABLE (JADNET STD) ---
1 White Orange: SENSE (GP14, tied to 2 on Downstream Satellite)
2 Orange:       SENSE GND (GND Bus, tied to 1 on Downstream Satellite)
3 White Green:  UART TX/RX (GP0 on Upstream to GP1 on Downstream)
4 Blue:         GND
5 White Blue:   UART TX/RX (GP1 on Upstream to GP0 on Downstream)
6 Green:        GND
7 White Brown:  20V VCC (POST-MOSFET)
8 Brown:        20V VCC (POST-MOSFET)

--- UI/UX COMPONENTS ---
DISPLAYS: Dual 14-Segment I2C (HT16K33) - 0x70 Right, 0x71 Left.
INPUTS: 4x Latching Toggles (GP10-13), 2x Momentary Toggles (GP16-17).
ROTARY: Encoder (GP18-19) + Push Button (GP20).
KEYPAD: 4x3 Matrix Keypad (GP7-13 rows/cols shared).
FEEDBACK: 6x NeoPixels (Independent async animation engine).

--- GPIO MAPPING ---
GP0: UART_UP TX to Upstream (115200 Baud).
GP1: UART_UP RX from Upstream (115200 Baud).
GP2: I2C SCL for Displays (HT16K33).
GP3: I2C SDA for Displays (HT16K33).
GP4: UART_DOWN TX to Downstream (115200 Baud).
GP5: UART_DOWN RX from Downstream (115200 Baud).
GP6: NeoPixel Data line (6x Pixels).
GP7-GP10: Keypad Row Pins (4x).
GP11-GP13: Keypad Column Pins (3x).
TODO GP14: Sat-Power Enable (Logic High -> 2N3904 Base -> MOSFET ON).
GP17: Rotary Encoder A.
GP18: Rotary Encoder B.
GP19: Rotary Encoder Button.
GP20-GP23: Latching Toggle Inputs (4x).
GP24: Momentary Toggle 1 - UP.
GP25: Momentary Toggle 1 - DOWN.
TODO GP26 (ADC0): Sense - 20V Input (Pre-MOSFET) [Divider: 47k/6.8k].
TODO GP27 (ADC1): Sense - 20V Downstream Bus (Post-MOSFET) [Divider: 47k/6.8k].
TODO GP28 (ADC2): Sense - 5V Logic Rail [Divider: 10k/10k].


--- LOCAL LOGIC FEATURES ---
Dynamic ID Assignment: Satellites auto-increment index on boot (e.g., 0101, 0102).
Async LED/DSP: Local multitasking for animations (Breathing, Strobes, Marquee).
Heartbeat: Sends 10Hz status packet to Master (STATUS|btn,toggles,momentary,key,enc).

--- PROTECTION STRATEGY ---
1.0A Polyfuse on 5V Local Supply.

--- TODO ---
Implement power monitoring via ADC.
Implement power protection for downstream satellites.
Implement advanced LED animations (Breathing, Strobe).
Add error handling for UART communication.
Optimize async tasks for responsiveness.
Implement configuration commands from Master.
UART Buffering and flow control.
Keypad debouncing improvements.
Test with multiple chained satellites.
Add LED flashing animations for triggering.
Prevent cancellation of global animations from individual LED commands.
"""

import asyncio

from managers import SatManager

MY_TYPE = "01"  # Industrial Satellite
sat = SatManager(MY_TYPE)

asyncio.run(sat.start())
