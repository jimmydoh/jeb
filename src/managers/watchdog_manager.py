# File: src/managers/watchdog_manager.py
import microcontroller

class WatchdogManager:
    """
    Manages the Watchdog Timer using a 'Flag Pattern'.

    Instead of blindly feeding the dog, this manager requires all registered
    critical tasks to 'check-in' (set a flag) during their loop.
    The dog is only fed if ALL tasks have checked in since the last feed.
    """
    def __init__(self, task_names, timeout=None):
        # Initialize flags for all tasks as False
        self._flags = {name: False for name in task_names}

        # Enable the hardware watchdog if a timeout is provided
        if timeout:
            microcontroller.watchdog.timeout = timeout
            microcontroller.watchdog.mode = microcontroller.watchdog.WatchDogMode.RESET
            microcontroller.watchdog.feed()

    def register_flags(self, task_names):
        """Register additional tasks to monitor."""
        for name in task_names:
            if name not in self._flags:
                self._flags[name] = False

    def unregister_flags(self, task_names):
        """Unregister tasks that no longer need monitoring."""
        for name in task_names:
            if name in self._flags:
                del self._flags[name]

    def check_in(self, task_name):
        """Called by a task to indicate it is alive."""
        if task_name in self._flags:
            self._flags[task_name] = True

    def safe_feed(self):
        """
        Feeds the watchdog ONLY if all tasks have checked in.
        Returns True if fed, False if a task is hanging (which will eventually cause a reset).
        """
        if all(self._flags.values()):
            microcontroller.watchdog.feed()
            # Reset flags for the next cycle
            for name in self._flags:
                self._flags[name] = False
            return True
        return False
