# File: src/utilities/pins.py
"""Centralized Pin Map for JEB Project"""
import board

DIVIDER_MULTIPLIER_20V = 1 / 0.1263  # ≈7.919
DIVIDER_MULTIPLIER_5V = 1 / 0.5      # = 2.0

class CoreProfile:
    """Hardware profile for the Master Core."""

    @classmethod
    def load(cls):
        class Expander:
            BUTTON_A = 0
            BUTTON_B = 1
            BUTTON_C = 2
            BUTTON_D = 3

        p = {
            "UART_TX": getattr(board, "GP0", None),
            "UART_RX": getattr(board, "GP1", None),
            "ENCODER_1_A": getattr(board, "GP2", None),
            "ENCODER_1_B": getattr(board, "GP3", None),
            "I2C_SDA": getattr(board, "GP4", None),
            "I2C_SCL": getattr(board, "GP5", None),
            "LED_CONTROL": getattr(board, "GP6", None),
            "ESTOP_DETECT": getattr(board, "GP7", None),
            "BUZZER": getattr(board, "GP10", None),
            "EXPANDER_INT": getattr(board, "GP11", None),
            "ENCODER_PUSH": getattr(board, "GP12", None),
            "MOSFET_CONTROL": getattr(board, "GP14", None),
            "SATBUS_DETECT": getattr(board, "GP15", None),
            "SPI_MISO": getattr(board, "GP16", None),
            "SPI_CS": getattr(board, "GP17", None),
            "SPI_SCK": getattr(board, "GP18", None),
            "SPI_MOSI": getattr(board, "GP19", None),
            "I2S_SCK": getattr(board, "GP20", None),
            "I2S_WS": getattr(board, "GP21", None),
            "I2S_SD": getattr(board, "GP22", None),
            "ADC_SENSE_A": getattr(board, "GP26", None),
            "ADC_SENSE_B": getattr(board, "GP27", None),
            "ADC_SENSE_C": getattr(board, "GP28", None),
            "ADC_SENSE_D": getattr(board, "GP29", None),
        }

        # Helper arrays
        p["ENCODER_1"] = [p["ENCODER_1_A"], p["ENCODER_1_B"], p["ENCODER_PUSH"]]
        p["ENCODERS"] = [p["ENCODER_1"]]
        p["SENSE_PINS"] = [p["ADC_SENSE_A"], p["ADC_SENSE_B"], p["ADC_SENSE_C"], p["ADC_SENSE_D"]]

        p["ADC_CONFIG"] = {
            "chip_type": "NATIVE",
            "address": None,
            "channels": [
                {"name": "input_20v", "pin": p["ADC_SENSE_A"], "multiplier": DIVIDER_MULTIPLIER_20V},
                {"name": "satbus_20v", "pin": p["ADC_SENSE_B"], "multiplier": DIVIDER_MULTIPLIER_20V},
                {"name": "main_5v", "pin": p["ADC_SENSE_C"], "multiplier": DIVIDER_MULTIPLIER_5V},
                {"name": "led_5v", "pin": p["ADC_SENSE_D"], "multiplier": DIVIDER_MULTIPLIER_5V},
            ]
        }

        p["I2C_ADDRESSES"] = {"OLED": 0x3C, "EXPANDER": 0x20}

        p["EXPANDER_CONFIGS"] = [
            {
                "chip": "MCP23008",
                "address": p["I2C_ADDRESSES"]["EXPANDER"],
                "int_pin": p["EXPANDER_INT"],
                "latching": [],
                "momentary": [],
                "buttons": [Expander.BUTTON_A, Expander.BUTTON_B, Expander.BUTTON_C, Expander.BUTTON_D]
            }
        ]

        return p


class Sat01Profile:
    """Hardware profile for the Industrial / Bunker Satellite."""

    @classmethod
    def load(cls):
        class Expander1:
            LATCHING_1 = 0
            LATCHING_2 = 1
            LATCHING_3 = 2
            LATCHING_4 = 3
            LATCHING_5 = 4
            LATCHING_6 = 5
            LATCHING_7 = 6
            LATCHING_8 = 7

        class Expander2:
            MOMENTARY_1_UP = 0
            MOMENTARY_1_DOWN = 1
            LATCHING_GUARD_1 = 2
            KEY_SWITCH_POS_1 = 3
            KEY_SWITCH_POS_2 = 4
            KEY_SWITCH_POS_3 = 5
            BIG_RED_BUTTON = 6

        p = {
            # --- 1. PHYSICAL PINS ---
            "UART_RX": getattr(board, "GP0", None),
            "UART_TX": getattr(board, "GP1", None),
            "ENCODER_1_A": getattr(board, "GP2", None),
            "ENCODER_1_B": getattr(board, "GP3", None),
            "I2C_SDA": getattr(board, "GP4", None),
            "I2C_SCL": getattr(board, "GP5", None),
            "LED_CONTROL": getattr(board, "GP6", None),
            "UART_DOWN_TX": getattr(board, "GP8", None),
            "UART_DOWN_RX": getattr(board, "GP9", None),
            "BUZZER": getattr(board, "GP10", None),
            "EXPANDER_1_INT": getattr(board, "GP11", None),
            "ENCODER_PUSH": getattr(board, "GP12", None),
            "EXPANDER_2_INT": getattr(board, "GP13", None),
            "MOSFET_CONTROL": getattr(board, "GP14", None),
            "SATBUS_DETECT": getattr(board, "GP15", None),
            "MATRIX_KEY_ROW_1": getattr(board, "GP16", None),
            "MATRIX_KEY_ROW_2": getattr(board, "GP17", None),
            "MATRIX_KEY_ROW_3": getattr(board, "GP18", None),
            "MATRIX_KEY_COL_1": getattr(board, "GP19", None),
            "MATRIX_KEY_COL_2": getattr(board, "GP20", None),
            "MATRIX_KEY_COL_3": getattr(board, "GP21", None),
            "ADC_SENSE_A": getattr(board, "GP26", None),
            "ADC_SENSE_B": getattr(board, "GP27", None),
            "ADC_SENSE_C": getattr(board, "GP28", None),

            # --- 2. LOGICAL MAPPINGS (Game Mode Semantics) ---
            # These map to the indices generated by HIDManager based on the physical arrays below.
            "SW_SILO_1": 0,
            "SW_SILO_2": 1,
            "SW_SILO_3": 2,
            "SW_ARM": 3,
            "SW_KEY": 4,          # Placeholder for new hardware
            "BTN_EXECUTE": 0,     # Placeholder for new hardware
            "SW_SILOS_ALL": [0, 1, 2],

            "LED_SILO_1": 0,
            "LED_SILO_2": 1,
            "LED_SILO_3": 2,
            "LED_ARM": 3,
        }

        # Keypad Maps for 3x3
        p["KEYPAD_MAP_3x3"] = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "*", "0", "#"]

        # Helper arrays
        p["ENCODER_1"] = [p["ENCODER_1_A"], p["ENCODER_1_B"], p["ENCODER_PUSH"]]
        p["ENCODERS"] = [p["ENCODER_1"]]
        p["MATRIX_1_ROWS"] = [p["MATRIX_KEY_ROW_1"], p["MATRIX_KEY_ROW_2"], p["MATRIX_KEY_ROW_3"]]
        p["MATRIX_1_COLS"] = [p["MATRIX_KEY_COL_1"], p["MATRIX_KEY_COL_2"], p["MATRIX_KEY_COL_3"]]
        p["MATRIX_KEYPADS"] = [(p["KEYPAD_MAP_3x3"], p["MATRIX_1_ROWS"], p["MATRIX_1_COLS"])]
        p["SENSE_PINS"] = [p["ADC_SENSE_A"], p["ADC_SENSE_B"], p["ADC_SENSE_C"]]

        p["ADC_CONFIG"] = {
            "chip_type": "NATIVE",
            "address": None,
            "channels": [
                {"name": "input_20v", "pin": p["ADC_SENSE_A"], "multiplier": DIVIDER_MULTIPLIER_20V},
                {"name": "satbus_20v", "pin": p["ADC_SENSE_B"], "multiplier": DIVIDER_MULTIPLIER_20V},
                {"name": "main_5v", "pin": p["ADC_SENSE_C"], "multiplier": DIVIDER_MULTIPLIER_5V},
            ]
        }

        p["I2C_ADDRESSES"] = {
            "SEGMENT_LEFT": 0x70,
            "SEGMENT_RIGHT": 0x71,
            "EXPANDER_1": 0x20,
            "EXPANDER_2": 0x21
        }

        p["EXPANDER_CONFIGS"] = [
            {
                "chip": "MCP23008",
                "address": p["I2C_ADDRESSES"]["EXPANDER_1"],
                "int_pin": p["EXPANDER_1_INT"],
                "latching": [
                    Expander1.LATCHING_1,
                    Expander1.LATCHING_2,
                    Expander1.LATCHING_3,
                    Expander1.LATCHING_4,
                    Expander1.LATCHING_5,
                    Expander1.LATCHING_6,
                    Expander1.LATCHING_7,
                    Expander1.LATCHING_8
                ],
                "momentary": [],
                "buttons": []
            },
            {
                "chip": "MCP23008",
                "address": p["I2C_ADDRESSES"]["EXPANDER_2"],
                "int_pin": p["EXPANDER_2_INT"],
                "latching": [Expander2.LATCHING_GUARD_1, Expander2.KEY_SWITCH_POS_1, Expander2.KEY_SWITCH_POS_2, Expander2.KEY_SWITCH_POS_3],
                "momentary": [[Expander2.MOMENTARY_1_UP, Expander2.MOMENTARY_1_DOWN]],
                "buttons": [Expander2.BIG_RED_BUTTON]
            }
        ]

        return p


class Pins:
    """Centralized Pin Map for JEB Project"""

    # Registry of available hardware profiles
    _PROFILES = {
        ("CORE", "00"): CoreProfile,
        ("SAT", "01"): Sat01Profile,
    }

    @classmethod
    def initialize(cls, profile="CORE", type_id="00"):
        """Initialize pin mappings by dynamically loading the selected profile."""
        profile_class = cls._PROFILES.get((profile, type_id))

        if not profile_class:
            print(f"❗Unknown profile/type_id for Pins: {profile}/{type_id}. No pins assigned.❗")
            return

        # Load the configuration dictionary from the specific profile
        config = profile_class.load()

        # Dynamically map all attributes to the Pins class namespace
        for key, value in config.items():
            setattr(cls, key, value)
