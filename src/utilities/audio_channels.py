# File: src/utilities/audio_channels.py
"""Audio Channel Configuration Module

Defines standard logical audio channel aliases used throughout the application.
Centralizing these definitions ensures consistency and makes it easy to
adjust the channel count.
"""

class AudioChannels:
    """
    Standard logical audio channel indices for the mixer.

    These constants define the logical channel assignments
    used by AudioManager.
    """
    CH_ATMO = 0   # Background atmosphere WAV files
    CH_SFX = 1    # Sound effects WAV files
    CH_VOICE = 2  # Voice narration WAV files
    CH_SYNTH = 3  # Synthio generated audio

    # Total mixer voices: 2 atmo + 1 voice + 1 synth + 3 sfx
    VOICE_COUNT = 7

    @classmethod
    def voice_count(cls):
        """Return the total number of mixer voices required."""
        return cls.VOICE_COUNT
