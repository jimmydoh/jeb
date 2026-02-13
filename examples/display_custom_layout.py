"""Example demonstrating custom layout mode.

This example shows how to use custom layout for full display control,
useful for games or modes with specialized UI requirements.
"""

import asyncio
import displayio
import terminalio
from adafruit_display_text import label
from src.modes.base import BaseMode

class CustomLayoutExample(BaseMode):
    """Example mode using custom layout for full display control."""
    
    METADATA = {
        "id": "CUSTOM_LAYOUT_EXAMPLE",
        "name": "Custom Layout Demo",
        "icon": "GAME",
        "requires": ["CORE"],
        "settings": []
    }
    
    def __init__(self, core):
        super().__init__(core, name="CUSTOM LAYOUT", description="Demo of custom layout")
        self.score = 0
        self.custom_ui = None
    
    async def enter(self):
        """Set up custom layout on mode entry."""
        # Switch to custom layout mode for full display control
        self.core.display.use_custom_layout()
        
        # Build a custom UI group
        self.custom_ui = displayio.Group()
        
        # Title at the top
        self.title_label = label.Label(
            terminalio.FONT,
            text="CUSTOM GAME",
            x=25,
            y=8
        )
        self.custom_ui.append(self.title_label)
        
        # Score display in the middle
        self.score_label = label.Label(
            terminalio.FONT,
            text="SCORE: 0",
            x=30,
            y=28
        )
        self.custom_ui.append(self.score_label)
        
        # Status message
        self.status_label = label.Label(
            terminalio.FONT,
            text="Press button",
            x=15,
            y=48
        )
        self.custom_ui.append(self.status_label)
        
        # Set the custom content on the display
        self.core.display.set_custom_content(self.custom_ui)
        
        await asyncio.sleep(1)
    
    async def run(self):
        """Demonstrate custom UI updates during gameplay."""
        
        # Simulate a simple game loop
        for round_num in range(5):
            # Update title for current round
            self.title_label.text = f"ROUND {round_num + 1}"
            
            # Increment score
            self.score += 100 * (round_num + 1)
            self.score_label.text = f"SCORE: {self.score}"
            
            # Update status
            self.status_label.text = "Playing..."
            
            await asyncio.sleep(1)
            
            # Check for button press
            if await self.core.hid.check_button("SELECT"):
                break
        
        # Game over screen
        self.title_label.text = "GAME OVER"
        self.status_label.text = f"Final: {self.score}"
        await asyncio.sleep(2)
        
        return "COMPLETE"
    
    async def exit(self):
        """Clean up custom UI on exit."""
        # Clear custom content
        self.core.display.set_custom_content(None)
        await asyncio.sleep(0.1)


class HybridLayoutExample(BaseMode):
    """Example mode that switches between standard and custom layouts.
    
    This demonstrates that modes can switch layout modes during operation,
    though it's generally recommended to stick to one layout per mode.
    """
    
    METADATA = {
        "id": "HYBRID_LAYOUT_EXAMPLE",
        "name": "Hybrid Layout Demo",
        "icon": "DEBUG",
        "requires": ["CORE"],
        "settings": []
    }
    
    def __init__(self, core):
        super().__init__(core, name="HYBRID LAYOUT", description="Demo of switching layouts")
    
    async def enter(self):
        """Start with standard layout for menu/setup."""
        # Use standard layout for initial setup
        self.core.display.use_standard_layout()
        self.core.display.update_header("MODE: SETUP")
        self.core.display.update_status("Preparing...", "")
        self.core.display.update_footer("Loading...")
        
        await asyncio.sleep(1)
    
    async def run(self):
        """Switch to custom layout for main content, then back to standard."""
        
        # Phase 1: Standard layout (configuration)
        self.core.display.update_status("Configuration", "Press button")
        self.core.display.update_footer("Phase 1 of 2")
        await asyncio.sleep(2)
        
        # Phase 2: Switch to custom layout (gameplay/visualization)
        self.core.display.use_custom_layout()
        
        custom_group = displayio.Group()
        game_label = label.Label(
            terminalio.FONT,
            text="CUSTOM PHASE",
            x=20,
            y=32
        )
        custom_group.append(game_label)
        self.core.display.set_custom_content(custom_group)
        
        await asyncio.sleep(2)
        
        # Phase 3: Switch back to standard layout (results)
        self.core.display.use_standard_layout()
        self.core.display.update_header("RESULTS")
        self.core.display.update_status("Complete!", "")
        self.core.display.update_footer("Phase 2 of 2")
        
        await asyncio.sleep(2)
        
        return "COMPLETE"


# Example usage documentation
if __name__ == "__main__":
    print("Custom Layout Examples")
    print("=" * 40)
    print()
    print("CustomLayoutExample:")
    print("  - Demonstrates full custom UI control")
    print("  - Useful for games with bespoke graphics")
    print("  - Provides pixel-perfect positioning")
    print()
    print("HybridLayoutExample:")
    print("  - Shows switching between layout modes")
    print("  - Start with standard for menus")
    print("  - Switch to custom for gameplay")
    print("  - Return to standard for results")
    print()
    print("Best Practices:")
    print("  - Prefer standard layout for most modes")
    print("  - Use custom layout only when necessary")
    print("  - Stick to one layout mode per mode if possible")
    print("  - Clean up custom content in exit()")
