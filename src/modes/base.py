"""Base class for all modes."""
import asyncio

class BaseMode:
    """Base class for all modes."""
    def __init__(self, core, name="MODE", description=""):
        self.core = core
        self.name = name
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
