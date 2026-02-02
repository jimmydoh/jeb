""""""
import asyncio

class BaseMode:
    """Base class for all modes."""
    def __init__(self, jeb, name="MODE", description=""):
        self.jeb = jeb
        self.name = name
        self.description = description

    async def enter(self):
        """Standard setup routine."""
        # 1. Hardware Reset
        self.jeb.matrix.clear()
        self.jeb.audio.stop_all()

        # 2. Input Flush (Prevent accidental clicks carrying over)
        self.jeb.hid.flush()

        # 3. UI Setup
        self.jeb.display.update_status(self.name, "LOADING...")
        await asyncio.sleep(0.1)

    async def exit(self):
        """Standard cleanup routine."""
        self.jeb.matrix.clear()
        self.jeb.audio.stop_all()
        # Reset any temporary state in the manager
        self.jeb.current_mode_step = 0

    async def run(self):
        """Override this method in subclasses."""
        pass

    async def execute(self):
        """The wrapper called by JEBManager."""
        try:
            await self.enter()
            result = await self.run()
            return result
        finally:
            await self.exit()
