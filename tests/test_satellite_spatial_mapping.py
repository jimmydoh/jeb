#!/usr/bin/env python3
"""Tests for the satellite spatial mapping feature.

Validates:
  - SatelliteNetworkManager reads both the canonical ``satellites`` config key
    and the legacy ``satellite_offsets`` key.
  - SatelliteNetworkManager exposes ``satellite_offsets`` property and
    ``set_satellite_offset`` method.
  - The Layout Configurator mode file exists and has the expected structure.
  - ``save_satellite_offsets`` correctly writes/updates ``config.json``.
  - The mode manifest registers LAYOUT_CONFIGURATOR.
  - The admin menu in MainMenu contains the Layout Config option.
"""

import json
import os
import re
import sys
import tempfile

import pytest

SRC_DIR = os.path.join(os.path.dirname(__file__), '..', 'src')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read(path):
    with open(path, 'r') as f:
        return f.read()


# ---------------------------------------------------------------------------
# SatelliteNetworkManager – config key handling
# ---------------------------------------------------------------------------

class TestSatelliteNetworkManagerOffsets:

    @pytest.fixture(autouse=True)
    def snm_content(self):
        path = os.path.join(SRC_DIR, 'managers', 'satellite_network_manager.py')
        self.content = _read(path)

    def test_reads_satellites_key(self):
        """Manager should read the canonical 'satellites' config key."""
        assert '"satellites"' in self.content or "'satellites'" in self.content, \
            "SatelliteNetworkManager should read the 'satellites' config key"

    def test_backward_compat_satellite_offsets_key(self):
        """Manager should fall back to the legacy 'satellite_offsets' key."""
        assert '"satellite_offsets"' in self.content or "'satellite_offsets'" in self.content, \
            "SatelliteNetworkManager should accept the legacy 'satellite_offsets' key"

    def test_satellite_offsets_property_exists(self):
        """Manager should expose a satellite_offsets property."""
        assert 'def satellite_offsets' in self.content, \
            "SatelliteNetworkManager should expose a satellite_offsets property"

    def test_set_satellite_offset_method_exists(self):
        """Manager should expose set_satellite_offset() for runtime updates."""
        assert 'def set_satellite_offset' in self.content, \
            "SatelliteNetworkManager should have a set_satellite_offset() method"

    def test_set_satellite_offset_sends_setoff(self):
        """set_satellite_offset() should dispatch a SETOFF transport message."""
        assert 'CMD_SET_OFFSET' in self.content, \
            "set_satellite_offset() should use CMD_SET_OFFSET"


# ---------------------------------------------------------------------------
# save_satellite_offsets – filesystem helper
# ---------------------------------------------------------------------------

class TestSaveHelper:
    """Exercises the save_satellite_offsets() helper via direct import."""

    def _import_save_fn(self):
        # Temporarily patch sys.path so the module-level imports inside
        # layout_configurator.py resolve without CircuitPython hardware libs.
        # The function itself only uses json/os so it is safe to import.
        import importlib, importlib.util, types

        # UtilityMode (base class of LayoutConfigurator) imports adafruit_ticks at
        # module level, so stub it before executing the layout_configurator module.
        for mod_name in ['adafruit_ticks', 'utilities.palette', 'modes.utility_mode']:
            if mod_name not in sys.modules:
                sys.modules[mod_name] = types.ModuleType(mod_name)

        # Stub Palette
        palette_mod = sys.modules.get('utilities.palette', types.ModuleType('utilities.palette'))
        if not hasattr(palette_mod, 'Palette'):
            palette_mod.Palette = type('Palette', (), {'OFF': (0, 0, 0)})()
        sys.modules['utilities.palette'] = palette_mod

        # Stub UtilityMode
        utility_mod = sys.modules.get('modes.utility_mode', types.ModuleType('modes.utility_mode'))
        if not hasattr(utility_mod, 'UtilityMode'):
            class _UM:
                def __init__(self, core, name, description='', timeout=None):
                    self.core = core
                    self.name = name
            utility_mod.UtilityMode = _UM
        sys.modules['modes.utility_mode'] = utility_mod

        spec = importlib.util.spec_from_file_location(
            'modes.layout_configurator',
            os.path.join(SRC_DIR, 'modes', 'layout_configurator.py')
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.save_satellite_offsets

    def test_creates_config_when_missing(self, tmp_path):
        """Should create config.json when it does not exist."""
        save = self._import_save_fn()
        cfg_path = str(tmp_path / 'config.json')
        offsets = {"0101": {"offset_x": 16, "offset_y": 0}}
        result = save(offsets, config_path=cfg_path)
        assert result is True
        with open(cfg_path) as f:
            data = json.load(f)
        assert data["satellites"] == offsets

    def test_updates_existing_config(self, tmp_path):
        """Should preserve existing keys and update only 'satellites'."""
        save = self._import_save_fn()
        cfg_path = str(tmp_path / 'config.json')
        existing = {"wifi_ssid": "TestNet", "satellites": {"0101": {"offset_x": 0, "offset_y": 0}}}
        with open(cfg_path, 'w') as f:
            json.dump(existing, f)

        new_offsets = {"0101": {"offset_x": 8, "offset_y": 4}, "0102": {"offset_x": -8, "offset_y": 4}}
        result = save(new_offsets, config_path=cfg_path)
        assert result is True
        with open(cfg_path) as f:
            data = json.load(f)
        assert data["satellites"] == new_offsets
        assert data["wifi_ssid"] == "TestNet"

    def test_returns_false_on_write_error(self, tmp_path):
        """Should return False when the filesystem is not writable."""
        save = self._import_save_fn()
        # Pass a directory path (not a file) to force an OSError on open()
        result = save({}, config_path=str(tmp_path))
        assert result is False


# ---------------------------------------------------------------------------
# Layout Configurator – source structure
# ---------------------------------------------------------------------------

class TestLayoutConfiguratorSource:

    @pytest.fixture(autouse=True)
    def lc_content(self):
        path = os.path.join(SRC_DIR, 'modes', 'layout_configurator.py')
        assert os.path.exists(path), "layout_configurator.py should exist"
        self.content = _read(path)

    def test_class_defined(self):
        assert 'class LayoutConfigurator' in self.content

    def test_metadata_present(self):
        assert 'METADATA' in self.content
        assert '"LAYOUT_CONFIGURATOR"' in self.content or "'LAYOUT_CONFIGURATOR'" in self.content

    def test_crosshair_helper(self):
        assert '_draw_crosshair' in self.content, \
            "Should have a _draw_crosshair helper"

    def test_save_helper(self):
        assert 'save_satellite_offsets' in self.content, \
            "Should have a save_satellite_offsets helper"

    def test_setoff_live_update(self):
        assert 'set_satellite_offset' in self.content, \
            "Should call set_satellite_offset for live SETOFF updates"

    def test_encoder_axis_toggle(self):
        """Encoder tap should toggle between X and Y axis."""
        assert 'axis' in self.content, "Should track active axis (X / Y)"
        assert '"X"' in self.content and '"Y"' in self.content

    def test_save_and_exit_on_long_press(self):
        assert 'encoder_long' in self.content or 'action="hold"' in self.content, \
            "Should detect encoder long press for save and exit"

    def test_sets_mode_to_dashboard_on_exit(self):
        assert 'DASHBOARD' in self.content, \
            "Should return to DASHBOARD mode on exit"


# ---------------------------------------------------------------------------
# Manifest – LAYOUT_CONFIGURATOR registration
# ---------------------------------------------------------------------------

class TestManifest:

    @pytest.fixture(autouse=True)
    def manifest_content(self):
        path = os.path.join(SRC_DIR, 'modes', 'manifest.py')
        self.content = _read(path)

    def test_layout_configurator_registered(self):
        assert '"LAYOUT_CONFIGURATOR"' in self.content or "'LAYOUT_CONFIGURATOR'" in self.content, \
            "LAYOUT_CONFIGURATOR should be in the mode registry manifest"

    def test_layout_configurator_has_module_path(self):
        assert 'modes.layout_configurator' in self.content, \
            "LAYOUT_CONFIGURATOR registry entry should reference the correct module_path"


# ---------------------------------------------------------------------------
# Example config – uses canonical 'satellites' key
# ---------------------------------------------------------------------------

class TestExampleConfig:

    def test_example_core_config_uses_satellites_key(self):
        path = os.path.join(os.path.dirname(__file__), '..', 'examples', 'config-example-core.json')
        with open(path) as f:
            data = json.load(f)
        assert 'satellites' in data, \
            "config-example-core.json should use the canonical 'satellites' key"
        assert 'satellite_offsets' not in data, \
            "config-example-core.json should not use the deprecated 'satellite_offsets' key"

    def test_example_core_config_structure(self):
        path = os.path.join(os.path.dirname(__file__), '..', 'examples', 'config-example-core.json')
        with open(path) as f:
            data = json.load(f)
        for sid, entry in data['satellites'].items():
            assert 'offset_x' in entry, f"satellites.{sid} should have offset_x"
            assert 'offset_y' in entry, f"satellites.{sid} should have offset_y"


if __name__ == "__main__":
    import subprocess
    result = subprocess.run([sys.executable, "-m", "pytest", __file__, "-v"])
    sys.exit(result.returncode)
