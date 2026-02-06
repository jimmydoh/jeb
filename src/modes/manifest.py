"""Mode Manifest - Central registry for all available modes.

This manifest defines all modes available in the system and their requirements.
The core_manager uses this to dynamically load and execute modes without
needing to maintain hardcoded references to individual mode classes.

Note: MainMenu is not included in this registry as it's always used directly
by core_manager and doesn't need dynamic loading.
"""

# Import all mode classes (except MainMenu to avoid circular import)
from .industrial_startup import IndustrialStartup
from .jebris import JEBris
from .safe_cracker import SafeCracker
from .simon import Simon


# Mode Registry
# Each entry maps a mode key to its class, requirements, and UI metadata
MODE_REGISTRY = {
    # Core Box Games - Always available
    "JEBRIS": {
        "class": JEBris,
        "requires_satellite": None,
        "name": "JEBRIS",
        "icon": "JEBRIS",
        "settings": [
            {
                "key": "difficulty",
                "label": "SPEED",
                "options": ["EASY", "NORMAL", "HARD", "INSANE"],
                "default": "NORMAL"
            },
            {
                "key": "music",
                "label": "MUSIC",
                "options": ["ON", "OFF"],
                "default": "ON"
            }
        ],
    },
    "SIMON": {
        "class": Simon,
        "requires_satellite": None,
        "name": "SIMON",
        "icon": "SIMON",
        "settings": [
            {
                "key": "mode",
                "label": "MODE",
                "options": ["CLASSIC", "REVERSE", "BLIND"],
                "default": "CLASSIC"
            },
            {
                "key": "difficulty",
                "label": "DIFF",
                "options": ["EASY", "NORMAL", "HARD", "INSANE"],
                "default": "NORMAL"
            }
        ],
    },
    "SAFE": {
        "class": SafeCracker,
        "requires_satellite": None,
        "name": "SAFE CRACKER",
        "icon": "SAFE",
        "settings": [],  # No settings for Safe Cracker yet
    },
    
    # Industrial Satellite Games - Requires Industrial satellite
    "IND": {
        "class": IndustrialStartup,
        "requires_satellite": "INDUSTRIAL",  # Requires sat_type_name == "INDUSTRIAL"
        "name": "INDUSTRIAL",
        "icon": "IND",
        "settings": [],
    },
}


def get_mode_class(mode_key):
    """Get the mode class for a given mode key.
    
    Args:
        mode_key (str): The mode identifier (e.g., "JEBRIS", "IND")
        
    Returns:
        class: The mode class, or None if not found
    """
    mode_info = MODE_REGISTRY.get(mode_key)
    if mode_info:
        return mode_info["class"]
    return None


def get_required_satellite(mode_key):
    """Get the required satellite type for a given mode.
    
    Args:
        mode_key (str): The mode identifier
        
    Returns:
        str: The required satellite type name, or None if no satellite required
    """
    mode_info = MODE_REGISTRY.get(mode_key)
    if mode_info:
        return mode_info["requires_satellite"]
    return None


def is_mode_available(mode_key, satellites):
    """Check if a mode is available based on connected satellites.
    
    Args:
        mode_key (str): The mode identifier
        satellites (dict): Dictionary of connected satellites {sid: satellite_obj}
        
    Returns:
        bool: True if mode is available, False otherwise
    """
    required_sat_type = get_required_satellite(mode_key)
    
    # Mode doesn't require a satellite - always available
    if required_sat_type is None:
        return True
    
    # Check if any connected satellite matches the required type
    for sat in satellites.values():
        if sat.sat_type_name == required_sat_type:
            return True
    
    return False


def get_available_modes(satellites):
    """Get a list of all available mode keys based on connected satellites.
    
    Args:
        satellites (dict): Dictionary of connected satellites {sid: satellite_obj}
        
    Returns:
        list: List of available mode keys
    """
    available = []
    for mode_key in MODE_REGISTRY:
        if is_mode_available(mode_key, satellites):
            available.append(mode_key)
    return available
