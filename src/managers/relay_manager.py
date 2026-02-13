# File: src/managers/relay_manager.py
"""Manages relay outputs for gameplay feedback and ambience purposes."""

import asyncio
import time
import random
from utilities.payload_parser import parse_values, get_int, get_float, get_str

class RelayManager:
    """
    Manages relay outputs for purely aesthetic gameplay feedback and ambience.
    Similar to LED management but for physical relays with no load expectations.
    """
    
    def __init__(self, relay_pins):
        """
        Initialize the relay manager with a list of digital output pins.
        
        Args:
            relay_pins: List of digitalio.DigitalInOut objects configured as outputs
        """
        self.relays = relay_pins
        self.num_relays = len(relay_pins)
        self.relay_states = [False] * self.num_relays  # Track current state
        self._led_slave_map = {}  # Maps relay_idx -> (led_manager, led_idx)
        self._active_tasks = []  # Track running animation tasks
        
        # Initialize all relays to OFF state
        for relay in self.relays:
            relay.value = False
    
    def get_state(self, index):
        """Get the current state of a specific relay."""
        if 0 <= index < self.num_relays:
            return self.relay_states[index]
        return False
    
    def set_relay(self, index, state):
        """
        Set a specific relay to ON or OFF.
        
        Args:
            index: Relay index (or -1 for all relays)
            state: True for ON, False for OFF
        """
        targets = range(self.num_relays) if index < 0 or index >= self.num_relays else [index]
        for i in targets:
            self.relays[i].value = state
            self.relay_states[i] = state
    
    async def trigger_relay(self, index, duration=0.1, cycles=1):
        """
        Trigger a relay with on/off cycles.
        
        Args:
            index: Relay index (or -1 for all relays)
            duration: Duration for each on or off phase in seconds
            cycles: Number of on/off cycles to perform
        """
        targets = range(self.num_relays) if index < 0 or index >= self.num_relays else [index]
        for _ in range(cycles):
            for i in targets:
                self.relays[i].value = True
                self.relay_states[i] = True
            await asyncio.sleep(duration)
            for i in targets:
                self.relays[i].value = False
                self.relay_states[i] = False
            if _ < cycles - 1:  # Add pause between cycles (except after last cycle)
                await asyncio.sleep(duration)
    
    async def trigger_simultaneous(self, indices=None, duration=0.1, cycles=1):
        """
        Trigger multiple relays simultaneously.
        
        Args:
            indices: List of relay indices (None for all relays)
            duration: Duration for each on or off phase in seconds
            cycles: Number of on/off cycles to perform
        """
        targets = indices if indices is not None else list(range(self.num_relays))
        for _ in range(cycles):
            # Turn all ON
            for i in targets:
                if 0 <= i < self.num_relays:
                    self.relays[i].value = True
                    self.relay_states[i] = True
            await asyncio.sleep(duration)
            # Turn all OFF
            for i in targets:
                if 0 <= i < self.num_relays:
                    self.relays[i].value = False
                    self.relay_states[i] = False
            if _ < cycles - 1:
                await asyncio.sleep(duration)
    
    async def trigger_progressive(self, indices=None, duration=0.1, delay=0.05, cycles=1):
        """
        Trigger relays progressively (one after another).
        
        Args:
            indices: List of relay indices (None for all relays)
            duration: Duration each relay stays on in seconds
            delay: Delay between each relay activation in seconds
            cycles: Number of times to repeat the sequence
        """
        targets = indices if indices is not None else list(range(self.num_relays))
        for _ in range(cycles):
            for i in targets:
                if 0 <= i < self.num_relays:
                    self.relays[i].value = True
                    self.relay_states[i] = True
                    await asyncio.sleep(delay)
            await asyncio.sleep(duration - delay)  # Hold all on
            # Turn all OFF
            for i in targets:
                if 0 <= i < self.num_relays:
                    self.relays[i].value = False
                    self.relay_states[i] = False
            if _ < cycles - 1:
                await asyncio.sleep(duration)
    
    async def trigger_random(self, indices=None, duration=0.1, timeframe=1.0, cycles=1):
        """
        Trigger relays in random order within a timeframe.
        
        Args:
            indices: List of relay indices (None for all relays)
            duration: Duration each relay stays on in seconds
            timeframe: Total time window for random activation in seconds
            cycles: Number of times to repeat the sequence
        """
        targets = indices if indices is not None else list(range(self.num_relays))
        for _ in range(cycles):
            # Create random activation times within timeframe
            activation_times = []
            for i in targets:
                if 0 <= i < self.num_relays:
                    activation_times.append((random.random() * timeframe, i))
            activation_times.sort()  # Sort by time
            
            start_time = time.monotonic()
            for activation_time, i in activation_times:
                # Wait until activation time
                wait_time = activation_time - (time.monotonic() - start_time)
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                self.relays[i].value = True
                self.relay_states[i] = True
            
            # Keep all on for duration
            await asyncio.sleep(duration)
            
            # Turn all OFF
            for i in targets:
                if 0 <= i < self.num_relays:
                    self.relays[i].value = False
                    self.relay_states[i] = False
            
            if _ < cycles - 1:
                await asyncio.sleep(duration)
    
    def slave_to_led(self, relay_index, led_manager, led_index):
        """
        Slave a relay to follow the state of a specific LED.
        
        Args:
            relay_index: Index of the relay to control
            led_manager: LEDManager instance to read from
            led_index: Index of the LED to follow
        """
        if 0 <= relay_index < self.num_relays:
            self._led_slave_map[relay_index] = (led_manager, led_index)
    
    def unslave_relay(self, relay_index):
        """
        Remove LED slaving from a relay.
        
        Args:
            relay_index: Index of the relay to unslave
        """
        if relay_index in self._led_slave_map:
            del self._led_slave_map[relay_index]
    
    async def update_slaved_relays(self):
        """
        Update all slaved relays based on their corresponding LED states.
        This should be called periodically from a background task.
        """
        for relay_idx, (led_manager, led_idx) in self._led_slave_map.items():
            if 0 <= relay_idx < self.num_relays:
                # Check if LED is effectively "on" (any non-zero color value)
                if hasattr(led_manager, 'pixels') and led_idx < len(led_manager.pixels):
                    led_color = led_manager.pixels[led_idx]
                    led_is_on = any(c > 0 for c in led_color) if led_color else False
                    self.relays[relay_idx].value = led_is_on
                    self.relay_states[relay_idx] = led_is_on
    
    async def slave_update_loop(self):
        """Background task to continuously update slaved relays."""
        while True:
            if self._led_slave_map:
                await self.update_slaved_relays()
            await asyncio.sleep(0.05)  # Update at ~20Hz
    
    def clear(self):
        """Turn off all relays and clear all slaved mappings."""
        for i in range(self.num_relays):
            self.relays[i].value = False
            self.relay_states[i] = False
        self._led_slave_map.clear()
        # Cancel all active tasks
        for task in self._active_tasks:
            if not task.done():
                task.cancel()
        self._active_tasks.clear()
    
    async def apply_command(self, cmd, val):
        """
        Parses and executes a raw protocol command.
        Handles both text (CSV string) and binary (Tuple) payloads.
        """
        # Robustly handle val whether it's a string, bytes, or tuple
        if isinstance(val, (list, tuple)):
            values = val
        else:
            values = parse_values(val)
        
        # RELAY commands
        if cmd == "RELAY":
            # RELAY,<index>,<state>
            idx_raw = get_str(values, 0)
            target_indices = range(self.num_relays) if idx_raw == "ALL" else [get_int(values, 0)]
            state = bool(get_int(values, 1, 0))
            for i in target_indices:
                self.set_relay(i, state)
        
        elif cmd == "RELAYTRIG":
            # RELAYTRIG,<index>,<duration>,<cycles>
            idx_raw = get_str(values, 0)
            target_indices = range(self.num_relays) if idx_raw == "ALL" else [get_int(values, 0)]
            duration = get_float(values, 1, 0.1)
            cycles = get_int(values, 2, 1)
            for i in target_indices:
                await self.trigger_relay(i, duration=duration, cycles=cycles)
        
        elif cmd == "RELAYSIMUL":
            # RELAYSIMUL,ALL or index,duration,cycles
            idx_raw = get_str(values, 0)
            if idx_raw == "ALL":
                indices = None
            else:
                # Single index - parse remaining values as additional indices up to duration/cycles
                indices = []
                for i in range(len(values) - 2):
                    try:
                        indices.append(get_int(values, i))
                    except:
                        break
            duration = get_float(values, len(values)-2, 0.1)
            cycles = get_int(values, len(values)-1, 1)
            await self.trigger_simultaneous(indices=indices, duration=duration, cycles=cycles)
        
        elif cmd == "RELAYPROG":
            # RELAYPROG,ALL or index,duration,delay,cycles
            idx_raw = get_str(values, 0)
            if idx_raw == "ALL":
                indices = None
            else:
                # Parse indices up to the last 3 values (duration, delay, cycles)
                indices = []
                for i in range(len(values) - 3):
                    try:
                        indices.append(get_int(values, i))
                    except:
                        break
            duration = get_float(values, len(values)-3, 0.1)
            delay = get_float(values, len(values)-2, 0.05)
            cycles = get_int(values, len(values)-1, 1)
            await self.trigger_progressive(indices=indices, duration=duration, delay=delay, cycles=cycles)
        
        elif cmd == "RELAYRAND":
            # RELAYRAND,ALL or index,duration,timeframe,cycles
            idx_raw = get_str(values, 0)
            if idx_raw == "ALL":
                indices = None
            else:
                # Parse indices up to the last 3 values (duration, timeframe, cycles)
                indices = []
                for i in range(len(values) - 3):
                    try:
                        indices.append(get_int(values, i))
                    except:
                        break
            duration = get_float(values, len(values)-3, 0.1)
            timeframe = get_float(values, len(values)-2, 1.0)
            cycles = get_int(values, len(values)-1, 1)
            await self.trigger_random(indices=indices, duration=duration, timeframe=timeframe, cycles=cycles)
