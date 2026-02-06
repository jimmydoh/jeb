# Adding New Modes to JEB

This guide explains how to add new modes to the JEB system using the dynamic mode manifest.

## Overview

The JEB system uses a centralized mode manifest (`src/modes/manifest.py`) to manage all available modes. This eliminates the need to modify `core_manager.py` each time a new mode is added.

## Steps to Add a New Mode

### 1. Create Your Mode Class

Create a new Python file in `src/modes/` for your mode (e.g., `my_new_game.py`):

```python
from .game_mode import GameMode  # or .utility_mode, or .base

class MyNewGame(GameMode):
    """Description of your new game."""
    
    def __init__(self, core):
        super().__init__(core, "MY NEW GAME", "Game description")
        # Initialize your game...
    
    async def run(self):
        """Your game logic here."""
        # Implement your game...
        pass
```

### 2. Add to the Manifest

Edit `src/modes/manifest.py` and:

#### Add the import:
```python
from .my_new_game import MyNewGame
```

#### Add an entry to `MODE_REGISTRY`:
```python
MODE_REGISTRY = {
    # ... existing entries ...
    
    "MYNEWGAME": {
        "class": MyNewGame,
        "requires_satellite": None,  # or "INDUSTRIAL", "FUTURE_SAT_TYPE", etc.
        "name": "MY NEW GAME",
        "icon": "MYNEWGAME",  # Icon name for LED matrix display
        "settings": [
            {
                "key": "difficulty",
                "label": "DIFF",
                "options": ["EASY", "NORMAL", "HARD"],
                "default": "NORMAL"
            },
            # Add more settings as needed...
        ],
    },
}
```

### 3. Export from modes package (Optional)

If you want the mode class to be directly importable from the `modes` package, edit `src/modes/__init__.py`:

```python
from .my_new_game import MyNewGame

__all__ = [
    # ... existing exports ...
    "MyNewGame",
]
```

### 4. That's it!

Your mode will now automatically:
- Appear in the main menu when its requirements are met
- Be accessible through the manifest's dynamic loading system
- Show/hide based on connected satellite requirements

## Mode Registry Fields

### Required Fields

- **`class`**: The Python class for your mode
- **`requires_satellite`**: Satellite type name required (e.g., "INDUSTRIAL"), or `None` if always available
- **`name`**: Human-readable name displayed in UI
- **`icon`**: Icon name for LED matrix display
- **`settings`**: List of configurable settings (can be empty list `[]`)

### Settings Structure

Each setting in the `settings` list should have:

```python
{
    "key": "setting_name",      # Internal key for data storage
    "label": "DISPLAY LABEL",   # Label shown in UI (keep short)
    "options": ["OPT1", "OPT2"], # List of available options
    "default": "OPT1"            # Default value
}
```

## Satellite Requirements

### Always Available Modes
Set `requires_satellite` to `None`:
```python
"requires_satellite": None,
```

### Satellite-Dependent Modes
Set `requires_satellite` to the satellite type name (from `sat_type_name`):
```python
"requires_satellite": "INDUSTRIAL",
```

The mode will only appear in the menu when a satellite of that type is connected.

## Examples

### Simple Core-Only Game
```python
"SIMPLE_GAME": {
    "class": SimpleGame,
    "requires_satellite": None,
    "name": "SIMPLE GAME",
    "icon": "GAME",
    "settings": [],
},
```

### Industrial Satellite Game
```python
"FACTORY_GAME": {
    "class": FactoryGame,
    "requires_satellite": "INDUSTRIAL",
    "name": "FACTORY",
    "icon": "FACTORY",
    "settings": [
        {
            "key": "speed",
            "label": "SPEED",
            "options": ["SLOW", "FAST"],
            "default": "FAST"
        }
    ],
},
```

## Testing Your Mode

1. Syntax check: `python3 -m py_compile src/modes/my_new_game.py`
2. Test manifest: `python3 tests/test_manifest.py`
3. Deploy to hardware and test in the main menu

## Benefits of This System

- **No core_manager.py edits**: Add modes without touching core system code
- **Automatic satellite detection**: Modes show/hide based on connected hardware
- **Centralized configuration**: All mode metadata in one place
- **Easy maintenance**: Simple to add, remove, or modify modes
- **Type safety**: Manifest enforces consistent structure for all modes
