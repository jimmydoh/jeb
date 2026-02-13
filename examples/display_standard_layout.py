"""Example demonstrating the standard layout system.

This example shows how to use the new three-zone standard layout
(Header/Main/Footer) in a mode.
"""

import asyncio
import gc
from src.modes.base import BaseMode

class StandardLayoutExample(BaseMode):
    """Example mode using the standard three-zone layout."""
    
    METADATA = {
        "id": "STANDARD_LAYOUT_EXAMPLE",
        "name": "Standard Layout Demo",
        "icon": "DEBUG",
        "requires": ["CORE"],
        "settings": []
    }
    
    def __init__(self, core):
        super().__init__(core, name="STANDARD LAYOUT", description="Demo of standard layout")
        self.counter = 0
    
    async def enter(self):
        """Set up the standard layout on mode entry."""
        # Switch to standard three-zone layout
        self.core.display.use_standard_layout()
        
        # Set initial header content (system stats, mode name)
        self.core.display.update_header("MODE: DEMO")
        
        # Set main zone content (primary mode information)
        self.core.display.update_status("Standard Layout", "Initializing...")
        
        # Set footer content (logs, messages)
        self.core.display.update_footer("System ready")
        
        await asyncio.sleep(1)
    
    async def run(self):
        """Demonstrate updating all three zones during operation."""
        
        # Main loop: update zones periodically
        for i in range(10):
            # Update main zone with mode-specific content
            self.core.display.update_status(
                f"Counter: {i}",
                "Press button to exit"
            )
            
            # Update header with system stats
            ram_free = gc.mem_free() / 1024 if hasattr(gc, 'mem_free') else 0
            self.core.display.update_header(f"RAM: {ram_free:.0f}KB")
            
            # Update footer with log-style messages
            if i % 3 == 0:
                self.core.display.update_footer(f"Checkpoint {i//3 + 1}")
            elif i % 3 == 1:
                self.core.display.update_footer("Processing...")
            else:
                self.core.display.update_footer("Status: OK")
            
            await asyncio.sleep(0.5)
            
            # Check for button press to exit
            if await self.core.hid.check_button("SELECT"):
                break
        
        # Final message
        self.core.display.update_status("Complete!", "")
        self.core.display.update_footer("Exiting...")
        await asyncio.sleep(1)
        
        return "COMPLETE"
    
    async def exit(self):
        """Clean up on mode exit."""
        self.core.display.update_status("", "")
        await asyncio.sleep(0.1)


# Example usage in a standalone script:
if __name__ == "__main__":
    # This would typically be called from the main mode manager
    # For demonstration purposes only
    
    print("Standard Layout Example")
    print("=" * 40)
    print()
    print("This mode demonstrates the standard three-zone layout:")
    print("  - Header: System stats and mode name")
    print("  - Main: Primary mode content")
    print("  - Footer: Logs and messages")
    print()
    print("Layout structure:")
    print("  ┌────────────────────────────┐")
    print("  │ HEADER (RAM, Mode name)    │")
    print("  ├────────────────────────────┤")
    print("  │                            │")
    print("  │ MAIN (Counter, Status)     │")
    print("  │                            │")
    print("  ├────────────────────────────┤")
    print("  │ FOOTER (Logs, Messages)    │")
    print("  └────────────────────────────┘")
