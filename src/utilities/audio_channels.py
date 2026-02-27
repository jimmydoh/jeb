# File: src/utilities/audio_channels.py
"""Audio Channel Configuration Module

Defines standard audio channel aliases used throughout the application.
Centralizing these definitions ensures consistency and makes it easy to
adjust the channel count.
"""

class AudioChannels:
    """Standard audio channel indices for the mixer.

    These constants define the channel assignments used by AudioManager.
    The REQUIRED_VOICE_COUNT property ensures the mixer has enough channels
    for all defined aliases.
    """
    CH_ATMO = 0   # Background atmosphere WAV files
    CH_SFX = 1    # Sound effects WAV files
    CH_VOICE = 2  # Voice narration WAV files
    CH_SYNTH = 3  # Synthio generated audio
    SFX_POOL = [1, 4, 5]  # Dedicated SFX channels

    @classmethod
    def voice_count(cls):
        """Returns the minimum number of mixer voices needed for all defined channels.

        Returns:
            int: Minimum voice_count required
        """
        return 6
