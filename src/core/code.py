"""
PROJECT: JEB - JADNET Electronics Box - CORE COMMAND UNIT (MASTER)
VERSION: 0.1 - 2024-06-05
MCU: Raspberry Pi Pico 2 (RP2350)
OS: CircuitPython

*** PHYSICAL HARDWARE ARCHITECTURE ***
--- SUB-CIRCUIT MANIFESTS (MASTER) ---
INPUT POWER & BUCK DISTRIBUTION
- PROTECTION: USB-C PD 20V Input -> 3A Blade Fuse -> 1000uF 35V Electrolytic Cap.
- LOGIC RAIL: 20V Input -> 5V/2.5A Buck -> Powers Pico 2, OLED, and I2S Amp.
- LED RAIL: 20V Input -> 5V/5A Buck -> Powers GlowBit 64 Matrix.
MOSFET FIREWALL (HIGH-SIDE SWITCH)
- MAIN SWITCH: IRF5305 P-Channel MOSFET.
- NPN DRIVER: 2N3904 Transistor.
- TRIGGER: Pico GP14 -> 1k Ohm Resistor -> 2N3904 Base.
- GATE DIVIDER: 10k Ohm Pull-up (20V to Gate) + 10k Ohm Limiter (Gate to 2N3904 Collector).
- SAFETY: Vgs limited to 10V; Default state is OFF.
SENSE BOARD (PROTECTION & CONDITIONING)
- 20V RAILS (RAW & BUS): 47k / 6.8k Resistor Divider -> 3.3V Zener Diode + 0.1uF Cap -> GP26/GP27.
- 5V RAILS (LOGIC & LED): 10k / 10k Resistor Divider -> 3.3V Zener Diode + 0.1uF Cap -> GP28/GP29.
- RULE: Zener "stripe" (cathode) must face the Pico pins to clamp overvoltage.
BORDER CONTROL GROUNDING (RJ45 JUNCTION)
- JUNCTION: Solder pad/terminal block immediately adjacent to RJ45 jack.
- INPUTS: RJ45 Pins 3, 6 (Power Return) and Pin 2 (Sense GND) tied together.
- DRAIN (BUSBAR): Thick 22AWG wire from junction to Copper Busbar.
- REFERENCE (PICO): Thin 28AWG wire from junction to Pico GND.
- RULE: NO RESISTORS on the Pico reference path to ensure zero-ohm signaling.
CALIBRATION & PERSISTENCE (TODO - FUTURE)
- STORAGE: /calibration.json (Flash-based NVM).
- CALIBRATION: Hold GP22 (Button D) at boot to enable Pico WRITE access via boot.py.

--- COMMUNICATION ---
UART via RJ45
 - UART (GP0/GP1): Connected to First Sat in chain.

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
DISPLAY 1: 128x64 I2C OLED (System status & narrative).
DISPLAY 2: GlowBit 64 (8x8 NeoPixel Matrix) - Game HUD & Progress.
INPUTS:
 - 4x Arcade Buttons (A, B, C, D)
 - 1x E-Stop (Big Red Button)
 - 1x Rotary Encoder w/ Push Button
AUDIO: I2S 3W Class D Amp -> 8-ohm Inducer.

--- GPIO MAPPING ---
GP0: UART TX to Satellite Chain (115200 Baud).
GP1: UART RX from Satellite Chain (115200 Baud).
GP4: GlowBit 64 Data line (NeoPixel).
GP7: E-Stop Input (Active Low).
GP8 & GP9: I2C OLED (SDA, SCL).
GP14: Sat Power Enable (Logic High -> 2N3904 Base -> MOSFET ON).
GP15: Sat Connection Sense (RJ45 Pin 7/8) (Active Low).
GP16, GP17, GP18: I2S Audio (BCLK, LRCLK, DATA).
GP19, GP20, GP21, GP22: Face Buttons A, B, C, D (Active Low).
GP23 & GP24: Rotary Encoder (A, B).
GP25: Rotary Encoder Push Button (Active Low).
GP26 (ADC0): Sense - 20V Input (Pre-MOSFET) [Divider: 47k/6.8k].
GP27 (ADC1): Sense - 20V Downstream Bus (Post-MOSFET) [Divider: 47k/6.8k].
GP28 (ADC2): Sense - 5V Logic Rail [Divider: 10k/10k].
GP29 (ADC3): Sense - 5V LED Rail [Divider: 10k/10k].

--- PROTECTION STRATEGY ---
3.3V Zener diodes + 0.1uF caps on all ADC pins.
3A Blade fuse on 20v Input power
2.5A Blade fuse on

--- TODO LIST ---
Implement advanced error logging for satellite communications.
Add LED breathing animations, non blocking.
Replace neobar progress with matrix-based version.
Replace simon game visuals with matrix-based version.
Replace bracketing phase visuals with matrix-based version.
Victory animation on matrix.
Boot animation on matrix.
Check power integrity during various load conditions.
boot.py for file handling.
calibration.json for voltage calibration values.
"""
import asyncio

from managers import JEBManager

jeb = JEBManager()

asyncio.run(jeb.start())
