"""Base class for all modes."""
import asyncio

from utilities.logger import JEBLogger

class BaseMode:
    """
    Base class for all modes.

    Access Pattern:
        Modes are registered in CoreManager.modes as:
            Dict[mode_id, mode_class]

        To access mode metadata from a registered mode:
            meta = self.core.modes[mode_id].METADATA
            mode_name = meta["name"]
            requirements = meta["requires"]
    """

    def __init__(self, core, name="MODE", description="", exitable=True):
        self.core = core
        self.name = name
        self.description = description
        self.variant = "DEFAULT"
        self.exitable = exitable

    async def enter(self):
        """Standard setup routine."""
        JEBLogger.info("MODE", f"Entering mode: {self.name}")
        await self.core.clean_slate()  # Reset state before starting the mode
        self.core.display.update_status(self.name, "LOADING...")
        await asyncio.sleep(0.1)

    async def exit(self):
        """Standard cleanup routine."""
        JEBLogger.info("MODE", f"Exiting mode: {self.name}")
        await self.core.clean_slate()  # Reset state and cancel tasks
        self.core.current_mode_step = 0

    async def run(self):
        """Override this method in subclasses."""
        raise NotImplementedError("Subclasses must implement the run() method.")

    async def run_tutorial(self):
        """Override this method in subclasses."""
        raise NotImplementedError("Subclasses must implement the run_tutorial() method.")

    async def _monitor_exit(self, main_task):
        """
        Monitors for a global exit command (long press Button 3)
        to gracefully abort the mode.
        """
        try:
            # Continue checking as long as the main mode task is running
            while not main_task.done():
                # Check if Button 3 has been held for 3 seconds
                if self.core.hid.is_button_pressed(3, long=True, duration=3000):
                    # Cancel the main running task
                    main_task.cancel()
                    break

                # Yield control back to the event loop
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            # It's expected that this task gets cancelled when run() finishes normally
            pass

    async def execute(self):
        """The wrapper called by JEBManager."""
        monitor_task = None
        try:
            await self.enter()

            if getattr(self, "variant", None) == "TUTORIAL" and self.__class__.run_tutorial is not BaseMode.run_tutorial:
                JEBLogger.info("MODE", f"Running tutorial variant of mode: {self.name}")
                run_task = asyncio.create_task(self.run_tutorial())
            else:
                JEBLogger.info("MODE", f"Running main variant of mode: {self.name}")
                run_task = asyncio.create_task(self.run())

            if self.exitable:
                JEBLogger.info("MODE", f"Starting exit monitor for mode: {self.name}")
                monitor_task = asyncio.create_task(self._monitor_exit(run_task))
            try:
                # Await the main mode task
                JEBLogger.info("MODE", f"Awaiting main task for mode: {self.name}")
                result = await run_task
            except asyncio.CancelledError:
                # Handle _monitor_exit cancelling the run task
                result = "EXIT"
            return result
        finally:
            # Cancel the monitor task and await it to ensure proper cleanup
            if monitor_task is not None and not monitor_task.done():
                monitor_task.cancel()
                try:
                    await monitor_task
                except asyncio.CancelledError:
                    pass
            await self.exit()
