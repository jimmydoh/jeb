"""
WiFiManager - Centralised WiFi Connectivity Management

This manager centralises all WiFi control and status for the JEB system.

It is only instantiated when WiFi credentials are present in the config,
and only imports WiFi-related modules when connect() is first called.
It is designed to be passed to the Updater and WebServerManager to provide
shared connectivity lifecycle management.
"""

from utilities.logger import JEBLogger

class WiFiManager:
    """
    Centralised WiFi Manager for the JEB system.

    Only instantiated when SSID and password are present in config.
    WiFi-related modules (wifi, socketpool, ssl, adafruit_requests) are
    imported lazily on the first connect() call to avoid import errors on
    non-wireless hardware.

    Maintains connectivity status and lifecycle, and can be shared between
    the Updater and WebServerManager.
    """

    def __init__(self, config):
        """
        Initialize WiFiManager with configuration.

        Args:
            config (dict): Configuration dictionary containing:
                - wifi_ssid: Wi-Fi network name
                - wifi_password: Wi-Fi password
        """
        self.ssid = config.get("wifi_ssid", "")
        self.password = config.get("wifi_password", "")

        JEBLogger.info("WIFI", f"[INIT] WiFiManager - wifi_ssid: {self.ssid}, wifi_password: {'***' if self.password else ''}")

        self.online_callers = set()  # Track which callers want WiFi online

        # Lazily populated when connect() is called
        self._wifi = None
        self._socketpool = None
        self._pool = None

    @property
    def is_connected(self):
        """Return True if currently connected to WiFi."""
        if self._wifi is not None:
            return bool(self._wifi.radio.connected)
        return False

    @property
    def ip_address(self):
        """Return the current IP address, or None if not connected."""
        if self.is_connected:
            JEBLogger.debug("WIFI", f"Current WiFi IP address: {self._wifi.radio.ipv4_address}")
            return self._wifi.radio.ipv4_address
        return None

    @property
    def pool(self):
        """Return the socket pool, or None if not connected."""
        return self._pool

    def connect(self, timeout=30, caller=None):
        """
        Connect to the configured WiFi network.

        WiFi-related modules are imported on the first call. Subsequent
        calls reuse the already-imported modules.

        Args:
            timeout (int): Connection timeout in seconds

        Returns:
            bool: True if connected (or already connected) successfully,
                  False on failure or if WiFi modules are unavailable.
        """
        # Lazy import of WiFi modules
        if self._wifi is None:
            try:
                import wifi as _wifi
                import socketpool as _socketpool
                self._wifi = _wifi
                self._socketpool = _socketpool
            except ImportError:
                JEBLogger.error("WIFI", "WiFi modules not available")
                return False

        # Already connected - ensure pool exists
        if self._wifi.radio.connected:
            if self._pool is None:
                self._pool = self._socketpool.SocketPool(self._wifi.radio)
            JEBLogger.info("WIFI", f"Already connected to WiFi. IP: {self._wifi.radio.ipv4_address}")
            # The caller thinks we are online
            if caller and caller not in self.online_callers:
                self.online_callers.add(caller)
            return True

        import time
        try:
            JEBLogger.info("WIFI", f"Connecting to WiFi: {self.ssid}")
            self._wifi.radio.connect(self.ssid, self.password, timeout=timeout)

            start = time.monotonic()
            while not self._wifi.radio.connected and (time.monotonic() - start) < timeout:
                time.sleep(0.5)

            if self._wifi.radio.connected:
                self._pool = self._socketpool.SocketPool(self._wifi.radio)
                JEBLogger.info("WIFI", f"✓ Connected! IP: {self._wifi.radio.ipv4_address}")
                # The caller thinks we are online
                if caller and caller not in self.online_callers:
                    self.online_callers.add(caller)
                return True
            else:
                JEBLogger.error("WIFI", "✗ WiFi connection timeout")
                # The caller DOES NOT think we are online
                if caller and caller in self.online_callers:
                    self.online_callers.remove(caller)
                return False

        except Exception as e:
            JEBLogger.error("WIFI", f"WiFi connection error: {e}")
            # The caller DOES NOT think we are online
            if caller and caller in self.online_callers:
                self.online_callers.remove(caller)
            return False

    def disconnect(self, caller=None):
        """
        Disconnect from WiFi and release the socket pool.

        Safe to call even if not currently connected.
        """
        # The caller no longer thinks we are online
        if caller and caller in self.online_callers:
            self.online_callers.remove(caller)

        if self._wifi is not None and self._wifi.radio.connected:
            try:
                # Only actually disconnect if no other callers want to be online
                if self.online_callers:
                    JEBLogger.info("WIFI", f"Not disconnecting WiFi, still needed by: {self.online_callers}")
                    return
                # Disconnect and clean up
                self._wifi.radio.enabled = False
                JEBLogger.info("WIFI", "WiFi disconnected")
                self._pool = None
            except Exception as e:
                JEBLogger.error("WIFI", f"Error disconnecting WiFi: {e}")
        else:
            JEBLogger.info("WIFI", "WiFi already disconnected")

    def create_http_session(self):
        """
        Create and return an adafruit_requests HTTP session using the current
        socket pool.

        Returns:
            adafruit_requests.Session or None if unavailable (not connected,
            or required libraries missing).
        """
        if not self.is_connected or self._pool is None:
            return None
        try:
            import ssl
            import adafruit_requests
            return adafruit_requests.Session(self._pool, ssl.create_default_context())
        except ImportError:
            JEBLogger.error("WIFI", "adafruit_requests or ssl not available")
            return None
