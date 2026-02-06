# File: /src/utilities/context.py

class HardwareContext:
    """
    A class to hold references to hardware components such as audio, matrix, hid, and leds.
    This allows for easy access to these components throughout the application.
    """
    def __init__(self, hid=None, audio=None, matrix=None, leds=None):
        self.audio = audio
        self.matrix = matrix
        self.hid = hid
        self.leds = leds
