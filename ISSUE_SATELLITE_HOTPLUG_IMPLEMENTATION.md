# Issue: Implement Satellite Hotplug Behavior (Remove Mode Abortion on Topology Changes)

## Summary
Tests have been written in `tests/test_satellite_hotplug.py` that verify satellite hotplug behavior. However, the source code has not yet been modified to pass these tests. This issue documents the required source code changes.

## Failed Tests
Currently, 7 out of 10 tests in `test_satellite_hotplug.py` are FAILING because the source code has not been updated:

- ✅ `test_satellite_network_manager_abort_event_stored` - PASSES
- ✅ `test_satellite_network_manager_display_updates_present` - PASSES  
- ✅ (1 more minor test passes)
- ❌ `test_satellite_network_manager_no_abort_on_hello` - FAILS
- ❌ `test_satellite_network_manager_no_abort_on_link_restored` - FAILS
- ❌ `test_satellite_network_manager_no_abort_on_link_lost` - FAILS
- ❌ `test_main_menu_last_sat_keys_initialization` - FAILS
- ❌ `test_main_menu_curr_sat_keys_computation` - FAILS
- ❌ `test_main_menu_topology_change_detection` - FAILS
- ❌ `test_main_menu_selected_game_idx_clamping` - FAILS

## Root Cause
The current implementation calls `abort_event.set()` whenever satellite topology changes (connect/disconnect/reconnect), which forcefully terminates running game modes. This is problematic for hot-pluggable satellite scenarios.

## Required Source Code Changes

### 1. `src/managers/satellite_network_manager.py`

#### Change 1: Remove `abort_event.set()` from `_handle_hello_command` (Line ~189)

**Current Code:**
```python
async def _handle_hello_command(self, sid, val):
    """Handle HELLO command from satellite..."""
    if sid in self.satellites:
        self.satellites[sid].update_heartbeat()
    else:
        # ... satellite initialization code ...
        self.satellites[sid].update_heartbeat(increment=2000)
        self.abort_event.set()  # ← REMOVE THIS LINE
    self.display.update_status("NEW SAT", f"{sid} sent HELLO {val}.")
    JEBLogger.info("NETM", f"New sat {sid} TYPE-{val} via HELLO.")
```

**Required Change:**
Remove the line `self.abort_event.set()` - new satellite connections should NOT abort running modes.

**Reason:** When a new satellite connects during gameplay, the mode should continue running and gracefully handle the new satellite becoming available.

---

#### Change 2: Remove `abort_event.set()` from link-restored section in `monitor_satellites` (Line ~293)

**Current Code:**
```python
async def monitor_satellites(self, heartbeat_callback=None):
    """Background task to monitor satellite health..."""
    while True:
        # ...
        for sid, sat in self.satellites.items():
            if sat.is_active:
                if sat.was_offline:
                    # Satellite is online now but was detected as offline
                    JEBLogger.info("NETM", f"Link restored with {sid}. Marking as active.")
                    self.display.update_status(f"LINK RESTORED", f"ID: {sid}")
                    self.abort_event.set()  # ← REMOVE THIS LINE
                    self._spawn_audio_task(...)
                    sat.was_offline = False
```

**Required Change:**
Remove the line `self.abort_event.set()` - satellite reconnections should NOT abort running modes.

**Reason:** When a satellite reconnects after temporary disconnection, the mode should continue and re-integrate the satellite.

---

#### Change 3: Remove `abort_event.set()` from link-lost section in `monitor_satellites` (Line ~307)

**Current Code:**
```python
                if ticks_diff(now, sat.last_seen) > 5000:
                    # Satellite has not been seen for over 5 seconds, mark as offline
                    JEBLogger.warning("NETM", f"Link lost with {sid}. Marking as offline.")
                    sat.is_active = False
                    sat.was_offline = True
                    self.display.update_status(f"LINK LOST", f"ID: {sid}")
                    self.abort_event.set()  # ← REMOVE THIS LINE
                    self._spawn_audio_task(...)
```

**Required Change:**
Remove the line `self.abort_event.set()` - satellite disconnections should NOT abort running modes.

**Reason:** When a satellite disconnects, the mode should continue running and gracefully handle the missing satellite (e.g., disable features that require it).

---

### 2. `src/modes/main_menu.py`

#### Change 1: Initialize `last_sat_keys` before main loop (Line ~93)

**Current Code:**
```python
async def run(self):
    """Main Menu for selecting modes."""
    # ... initialization code ...
    
    # Data Variables
    menu_items = self._build_menu_items()
    selected_game_idx = 0
    selected_setting_idx = 0
    
    # Render Tracking (Prevents unnecessary screen updates)  # ← INSERT NEW CODE HERE
    self.core.display.use_standard_layout()
```

**Required Addition:**
Add satellite topology tracking initialization:
```python
    # Data Variables
    menu_items = self._build_menu_items()
    selected_game_idx = 0
    selected_setting_idx = 0
    
    # Satellite topology tracking for hot-plug detection
    last_sat_keys = frozenset(self.core.satellites.keys())
    
    # Render Tracking (Prevents unnecessary screen updates)
    self.core.display.use_standard_layout()
```

---

#### Change 2: Add topology change detection in main loop (Line ~127)

**Current Code:**
```python
        while True:
            # ... input gathering code ...
            
            # --- GLOBAL TIMEOUT CHECK ---
            if self.is_timed_out and self.state != "DASHBOARD":
                # ... timeout handling ...
                needs_render = True
            
            # =========================================  # ← INSERT NEW CODE HERE
            # 2. PROCESS STATE & LOGIC
            # =========================================
```

**Required Addition:**
Add satellite topology change detection:
```python
            # --- GLOBAL TIMEOUT CHECK ---
            if self.is_timed_out and self.state != "DASHBOARD":
                # ... timeout handling ...
                needs_render = True
            
            # --- SATELLITE TOPOLOGY CHECK ---
            # Detect hot-plugged satellites and refresh menu items in-place
            curr_sat_keys = frozenset(self.core.satellites.keys())
            if curr_sat_keys != last_sat_keys:
                last_sat_keys = curr_sat_keys
                menu_items = self._build_menu_items()
                if menu_items and selected_game_idx >= len(menu_items):
                    selected_game_idx = len(menu_items) - 1
                needs_render = True
            
            # =========================================
            # 2. PROCESS STATE & LOGIC
            # =========================================
```

**Reason:** This detects when satellites are added/removed and rebuilds the menu to show/hide games based on new hardware availability. It also clamps the selected index to prevent crashes.

---

## Expected Behavior After Implementation

After making these changes:

1. **New satellite connections** will be detected and integrated WITHOUT aborting running modes
2. **Satellite disconnections** will be handled gracefully WITHOUT aborting running modes
3. **Satellite reconnections** will restore functionality WITHOUT aborting running modes
4. **Main menu** will dynamically update available games when satellites are hot-plugged
5. User will still see visual/audio feedback for topology changes (NEW SAT, LINK LOST, LINK RESTORED)
6. `abort_event` remains stored in SatelliteNetworkManager for backward compatibility

## Test References
See `tests/test_satellite_hotplug.py` for complete test coverage of this behavior.

Run tests with:
```bash
python3 -m pytest tests/test_satellite_hotplug.py -v
```

## Priority
**HIGH** - These tests were written based on requirements. Source code must be updated to pass tests.

## Implementation Steps
1. Apply changes to `src/managers/satellite_network_manager.py` (remove 3 lines)
2. Apply changes to `src/modes/main_menu.py` (add ~10 lines)
3. Run tests to verify: `python3 tests/test_satellite_hotplug.py`
4. All 10 tests should PASS after implementation
