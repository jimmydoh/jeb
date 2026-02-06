"""Base class for all modes."""
import asyncio

class BaseMode:
    """
    Base class for all modes.

    All mode subclasses must define a METADATA class attribute that describes
    the mode's properties and requirements. This metadata is used by the
    CoreManager for mode registration and by the main menu for displaying
    available modes and checking hardware requirements.

    METADATA Structure:
        id (str): Unique identifier for the mode (e.g., "MAIN_MENU", "SIMON")
        name (str): Human-readable display name shown in the menu
        icon (str): Icon key from the icon library for visual representation
        requires (List[str]): Hardware dependencies required to run this mode
            - "CORE": Always available (built-in hardware)
            - Other values match satellite types (e.g., "INDUSTRIAL", "AUDIO")
        settings (List[dict]): Optional configuration settings for the mode
            Each setting dict must have:
                - key (str): Internal identifier for the setting
                - label (str): Short display label
                - options (List): Available values for the setting
                - default: Default value (must be in options)

    Example METADATA:
        METADATA = {
            "id": "SIMON",
            "name": "Simon Says",
            "icon": "GAME",
            "requires": ["CORE"],
            "settings": [
                {
                    "key": "difficulty",
                    "label": "DIFF",
                    "options": ["EASY", "NORMAL", "HARD"],
                    "default": "NORMAL"
                }
            ]
        }
    
    Access Pattern:
        Modes are registered in CoreManager.modes as:
            Dict[mode_id, mode_class]
        
        To access mode metadata from a registered mode:
            meta = self.core.modes[mode_id].METADATA
            mode_name = meta["name"]
            requirements = meta["requires"]
    """

    # Default Metadata
    METADATA = {
        "id": "UNKNOWN",
        "name": "Unknown Mode",
        "icon": "DEFAULT",
        "requires": ["CORE"],
        "settings": []
    }

    def __init__(self, core, name="MODE", description=""):
        self.core = core
        self.name = name if name else self.METADATA["name"]
        self.description = description
        self.variant = "DEFAULT"

    async def enter(self):
        """Standard setup routine."""
        # 1. Hardware Reset
        self.core.matrix.clear()
        self.core.audio.stop_all()

        # 2. Input Flush (Prevent accidental clicks carrying over)
        self.core.hid.flush()

        # 3. UI Setup
        self.core.display.update_status(self.name, "LOADING...")
        await asyncio.sleep(0.1)

    async def exit(self):
        """Standard cleanup routine."""
        self.core.matrix.clear()
        self.core.audio.stop_all()
        # Reset any temporary state in the manager
        self.core.current_mode_step = 0

    async def run(self):
        """Override this method in subclasses."""
        raise NotImplementedError("Subclasses must implement the run() method.")

    async def execute(self):
        """The wrapper called by JEBManager."""
        try:
            await self.enter()
            result = await self.run()
            return result
        finally:
            await self.exit()
