# File: src/modes/power_telemetry.py
"""Live Power Telemetry Mode for the Admin Menu.

Provides real-time ADC voltage readings and short-term waveform graphs
for all configured power rails, accessed via the Admin Menu.
"""

import asyncio

from .utility_mode import UtilityMode


class PowerTelemetryMode(UtilityMode):
    """Admin mode for visualising live power-rail telemetry.

    Displays real-time voltage (and current, where available) for every
    configured :class:`~utilities.power_bus.PowerBus`, with an optional
    rolling waveform graph rendered on the OLED using the existing
    :meth:`~managers.display_manager.DisplayManager.show_waveform` helper.

    Controls
    --------
    * **Encoder rotate**          – cycle through available power buses.
    * **Encoder tap**             – toggle between text readout and waveform view.
    * **Button B long press (2 s)** – exit back to Admin Menu / Dashboard.
    """

    #: Number of voltage samples kept per rail for the waveform graph.
    HISTORY_SIZE = 128
    #: Seconds between ADC samples (0.5 s ≈ 2 samples/sec, filling 128px in ~64 s).
    SAMPLE_INTERVAL = 0.5

    def __init__(self, core):
        super().__init__(
            core,
            name="PWR TELEMETRY",
            description="Live power rail telemetry",
            timeout=None,
        )
        # Rolling voltage history keyed by bus name
        self._histories = {}
        self._view = "TEXT"  # "TEXT" | "WAVE"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_buses(self):
        """Return the :attr:`~managers.power_manager.PowerManager.buses` dict.

        Returns an empty dict when the power manager is unavailable or has
        not been configured with any buses (e.g. dummy / test environment).
        """
        return getattr(self.core.power, "buses", {}) or {}

    def _sample_voltages(self):
        """Poll every bus and append the latest voltage to its history buffer."""
        for name, bus in self._get_buses().items():
            bus.update()
            history = self._histories.setdefault(name, [])
            history.append(bus.v_now)
            if len(history) > self.HISTORY_SIZE:
                history.pop(0)

    def _normalize(self, history):
        """Map a list of voltage samples to the [0.0, 1.0] range.

        The range is auto-scaled to the min and max observed within the
        rolling window so the waveform fills the screen regardless of the
        absolute voltage level.  A flat-line signal is centred at 0.5.
        """
        if not history:
            return []
        v_min = min(history)
        v_max = max(history)
        span = v_max - v_min
        if span < 0.01:
            # Nearly flat — centre on screen
            return [0.5] * len(history)
        return [(v - v_min) / span for v in history]

    def _render_text(self, bus_names, bus_idx):
        """Render the standard-layout text readout for the current bus."""
        name = bus_names[bus_idx % len(bus_names)]
        bus = self._get_buses().get(name)
        if bus is None:
            return

        status_str = bus.get_status_string()
        v_str = f"{bus.v_now:.2f}V"
        if bus.has_current and bus.i_now is not None:
            v_str += f" {bus.i_now:.0f}mA"

        self.core.display.use_standard_layout()
        self.core.display.update_header("PWR TELEMETRY")
        self.core.display.update_status(name.upper(), f"{v_str} [{status_str}]")
        self.core.display.update_footer("Tap=wave  Enc=cycle  W=exit")

    def _render_wave(self, bus_names, bus_idx):
        """Render the rolling waveform graph for the current bus."""
        name = bus_names[bus_idx % len(bus_names)]
        history = self._histories.get(name, [])
        samples = self._normalize(history)

        # Pad left with midpoint when the buffer is not yet full
        if len(samples) < self.HISTORY_SIZE:
            samples = [0.5] * (self.HISTORY_SIZE - len(samples)) + samples

        self.core.display.show_waveform(samples)

    # ------------------------------------------------------------------
    # Main run loop
    # ------------------------------------------------------------------

    async def run(self):
        """Run the Power Telemetry mode."""
        buses = self._get_buses()

        if not buses:
            # No power buses — inform the operator and exit gracefully
            self.core.display.use_standard_layout()
            self.core.display.update_header("PWR TELEMETRY")
            self.core.display.update_status("NO BUSES", "No power buses found")
            self.core.display.update_footer("Hold 'W' to exit")
            await asyncio.sleep(3)
            self.core.mode = "DASHBOARD"
            return "NO_BUSES"

        bus_names = list(buses.keys())
        bus_idx = 0
        self._view = "TEXT"
        last_sample_time = 0.0

        self.core.hid.flush()
        self.core.hid.reset_encoder(0)
        last_enc_pos = 0

        # Collect an initial sample so the display is not blank on first render
        self._sample_voltages()
        self._render_text(bus_names, bus_idx)

        import time

        while True:
            now = time.monotonic()

            # --- Periodic ADC sampling ---
            new_sample = False
            if now - last_sample_time >= self.SAMPLE_INTERVAL:
                self._sample_voltages()
                last_sample_time = now
                new_sample = True

            # --- Read HID inputs ---
            curr_enc = self.core.hid.encoder_position()
            enc_diff = curr_enc - last_enc_pos
            enc_tap = self.core.hid.is_encoder_button_pressed(action="tap")
            btn_b_long = self.core.hid.is_button_pressed(1, action="hold", duration=2000)

            needs_render = new_sample  # re-render whenever new data arrives

            # Encoder rotation → cycle buses
            if enc_diff != 0:
                self.touch()
                bus_idx = (bus_idx + enc_diff) % len(bus_names)
                last_enc_pos = curr_enc
                needs_render = True
                await self.core.audio.play(
                    "audio/menu/tick.wav", self.core.audio.CH_SFX, level=0.6
                )

            # Encoder tap → toggle text / waveform view
            if enc_tap:
                self.touch()
                self._view = "WAVE" if self._view == "TEXT" else "TEXT"
                needs_render = True
                await self.core.audio.play(
                    "audio/menu/tick.wav", self.core.audio.CH_SFX, level=0.6
                )

            # Button B long → exit
            if btn_b_long:
                self.core.mode = "DASHBOARD"
                await self.core.audio.play(
                    "audio/menu/close.wav", self.core.audio.CH_SFX, level=0.8
                )
                return "EXIT"

            # --- Render ---
            if needs_render:
                if self._view == "TEXT":
                    self._render_text(bus_names, bus_idx)
                else:
                    self._render_wave(bus_names, bus_idx)

            await asyncio.sleep(0.05)
