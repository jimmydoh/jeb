# File: src/utilities/pins.py
"""Centralized Pin Map for JEB Project"""
import board

class Pins:
    """Centralized Pin Map for JEB Project"""
    @classmethod
    def initialize(cls, profile="CORE", type_id="00"):
        """Initialize pin mappings based on the selected profile."""
        if profile == "CORE" and type_id == "00":
            cls.UART_TX = getattr(board, "GP0")
            cls.UART_RX = getattr(board, "GP1")
            cls.ENCODER_1_A = getattr(board, "GP2")
            cls.ENCODER_1_B = getattr(board, "GP3")
            cls.I2C_SDA = getattr(board, "GP4")
            cls.I2C_SCL = getattr(board, "GP5")
            cls.LED_CONTROL = getattr(board, "GP6")
            cls.ESTOP_DETECT = getattr(board, "GP7")
            #SPARE GP8 (secondary UART TX)
            #SPARE GP9 (secondary UART RX)
            cls.BUZZER = getattr(board, "GP10")
            cls.EXPANDER_INT = getattr(board, "GP11")
            cls.ENCODER_PUSH = getattr(board, "GP12")
            # SPARE GP13
            cls.MOSFET_CONTROL = getattr(board, "GP14")
            cls.SATBUS_DETECT = getattr(board, "GP15")
            cls.SPI_MISO = getattr(board, "GP16")
            cls.SPI_CS = getattr(board, "GP17")
            cls.SPI_SCK = getattr(board, "GP18")
            cls.SPI_MOSI = getattr(board, "GP19")
            cls.I2S_SCK = getattr(board, "GP20")
            cls.I2S_WS  = getattr(board, "GP21")
            cls.I2S_SD  = getattr(board, "GP22")
            # GP23 - Internal Pico - Power Circuitry
            # GP24 - Internal Pico - VBUS Sense
            # GP25 - User LED
            cls.ADC_SENSE_A = getattr(board, "GP26") # Pre-MOSFET 20V Input
            cls.ADC_SENSE_B = getattr(board, "GP27") # Post-MOSFET 20V Bus
            cls.ADC_SENSE_C = getattr(board, "GP28") # 5V Logic Rail
            cls.ADC_SENSE_D = getattr(board, "GP29") # 5V LED Rail
            cls.Expander.initialize(profile=profile, type_id=type_id)
            cls.EXPANDER = cls.Expander

            # Helper arrays
            cls.ENCODER_1 = [cls.ENCODER_1_A, cls.ENCODER_1_B, cls.ENCODER_PUSH]
            cls.ENCODERS = [cls.ENCODER_1]
            cls.SENSE_PINS = [cls.ADC_SENSE_A, cls.ADC_SENSE_B, cls.ADC_SENSE_C, cls.ADC_SENSE_D]
            cls.EXPANDER_BUTTONS = [
                cls.EXPANDER.BUTTON_A,
                cls.EXPANDER.BUTTON_B,
                cls.EXPANDER.BUTTON_C,
                cls.EXPANDER.BUTTON_D
            ]

            # ADC Configuration
            # Defines which ADC to use for power sensing and role assignments
            cls.ADC_CONFIG = {
                "chip_type": "NATIVE",  # Use native analogio ADC pins
                "address": None,  # Not used for native ADC
                "channels": [
                    {"name": "input_20v", "pin": cls.ADC_SENSE_A, "multiplier": 1/0.1263},  # 20V with voltage divider
                    {"name": "satbus_20v", "pin": cls.ADC_SENSE_B, "multiplier": 1/0.1263},  # 20V with voltage divider
                    {"name": "main_5v", "pin": cls.ADC_SENSE_C, "multiplier": 1/0.5},  # 5V with voltage divider
                    {"name": "led_5v", "pin": cls.ADC_SENSE_D, "multiplier": 1/0.5},  # 5V with voltage divider
                ]
            }

            # I2C Address Map
            cls.I2C_ADDRESSES = {
                "OLED": 0x3C,
                "EXPANDER": 0x20
            }

        elif profile == "SAT" and type_id == "01":
            # INDUSTRIAL SATELLITE - Type 01
            cls.UART_RX = getattr(board, "GP0")
            cls.UART_TX = getattr(board, "GP1")
            cls.ENCODER_1_A = getattr(board, "GP2")
            cls.ENCODER_1_B = getattr(board, "GP3")
            cls.I2C_SDA = getattr(board, "GP4")
            cls.I2C_SCL = getattr(board, "GP5")
            cls.LED_CONTROL = getattr(board, "GP6")
            # SPARE GP7
            cls.UART_DOWN_TX = getattr(board, "GP8")
            cls.UART_DOWN_RX = getattr(board, "GP9")
            cls.BUZZER = getattr(board, "GP10")
            cls.EXPANDER_INT = getattr(board, "GP11")
            cls.ENCODER_PUSH = getattr(board, "GP12")
            # SPARE GP13
            cls.MOSFET_CONTROL = getattr(board, "GP14")
            cls.SATBUS_DETECT = getattr(board, "GP15")
            cls.MATRIX_KEY_ROW_1 = getattr(board, "GP16")
            cls.MATRIX_KEY_ROW_2 = getattr(board, "GP17")
            cls.MATRIX_KEY_ROW_3 = getattr(board, "GP18")
            cls.MATRIX_KEY_COL_1 = getattr(board, "GP19")
            cls.MATRIX_KEY_COL_2 = getattr(board, "GP20")
            cls.MATRIX_KEY_COL_3  = getattr(board, "GP21")
            # SPARE cls.I2S_SD  = getattr(board, "GP22")
            # GP23 - Internal Pico - Power Circuitry
            # GP24 - Internal Pico - VBUS Sense
            # GP25 - User LED
            cls.ADC_SENSE_A = getattr(board, "GP26") # Pre-MOSFET 20V Input
            cls.ADC_SENSE_B = getattr(board, "GP27") # Post-MOSFET 20V Bus
            cls.ADC_SENSE_C = getattr(board, "GP28") # 5V Main Rail
            # SPARE cls.ADC_SENSE_D = getattr(board, "GP29") # 5V LED Rail
            cls.EXPANDER = cls.Expander.initialize(profile=profile, type_id=type_id)
            cls.EXPANDER = cls.Expander

            # Keypad Maps for 3x3
            cls.KEYPAD_MAP_3x3 = [
                "1", "2", "3",
                "4", "5", "6",
                "7", "8", "9",
                "*", "0", "#"
            ]

            # Helper arrays
            cls.ENCODER_1 = [cls.ENCODER_1_A, cls.ENCODER_1_B, cls.ENCODER_PUSH]
            cls.ENCODERS = [cls.ENCODER_1]
            cls.MATRIX_1_ROWS = [cls.MATRIX_KEY_ROW_1, cls.MATRIX_KEY_ROW_2, cls.MATRIX_KEY_ROW_3]
            cls.MATRIX_1_COLS = [cls.MATRIX_KEY_COL_1, cls.MATRIX_KEY_COL_2, cls.MATRIX_KEY_COL_3]
            cls.MATRIX_KEYPADS = [(
                cls.KEYPAD_MAP_3x3,
                cls.MATRIX_1_ROWS,
                cls.MATRIX_1_COLS
            )]
            cls.SENSE_PINS = [cls.ADC_SENSE_A, cls.ADC_SENSE_B, cls.ADC_SENSE_C]
            cls.EXPANDER_LATCHING = [
                cls.EXPANDER.LATCHING_1,
                cls.EXPANDER.LATCHING_2,
                cls.EXPANDER.LATCHING_3,
                cls.EXPANDER.LATCHING_4
            ]
            cls.EXPANDER_MOMENTARY = [
                [
                    cls.EXPANDER.MOMENTARY_1_UP,
                    cls.EXPANDER.MOMENTARY_1_DOWN
                ]
            ]

            # ADC Configuration
            # Defines which ADC to use for power sensing and role assignments
            cls.ADC_CONFIG = {
                "chip_type": "NATIVE",  # Use native analogio ADC pins
                "address": None,  # Not used for native ADC
                "channels": [
                    {"name": "input_20v", "pin": cls.ADC_SENSE_A, "multiplier": 1/0.1263},  # 20V with voltage divider
                    {"name": "satbus_20v", "pin": cls.ADC_SENSE_B, "multiplier": 1/0.1263},  # 20V with voltage divider
                    {"name": "main_5v", "pin": cls.ADC_SENSE_C, "multiplier": 1/0.5},  # 5V with voltage divider
                ]
            }

            # I2C Address Map
            cls.I2C_ADDRESSES = {
                "SEGMENT_LEFT": 0x70,
                "SEGMENT_RIGHT": 0x71,
                "EXPANDER": 0x20
            }

        else:
            print(f"❗Unknown profile/type_id for Pins: {profile}/{type_id}. No pins assigned.❗")

    class Expander:
        """Pin mappings for the I/O expander (e.g., MCP23017, MCP23008)"""

        @classmethod
        def initialize(cls, profile="CORE", type_id="00"):
            """Initialize expander pin mappings based on the selected profile."""
            if profile == "CORE" and type_id == "00":
                # For CORE with Expander - Type 00 - Expander MCP23008
                cls.BUTTON_A = 0
                cls.BUTTON_B = 1
                cls.BUTTON_C = 2
                cls.BUTTON_D = 3
            elif profile == "SAT" and type_id == "01":
                # INDUSTRIAL SATELLITE - Type 01 - Expander MCP23008
                cls.LATCHING_1 = 0
                cls.LATCHING_2 = 1
                cls.LATCHING_3 = 2
                cls.LATCHING_4 = 3
                cls.MOMENTARY_1_UP = 4
                cls.MOMENTARY_1_DOWN = 5
            else:
                print(f"❗Unknown profile for Expander: {profile}/{type_id}. No pins assigned.❗")
