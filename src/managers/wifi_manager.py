"""
WiFiManager - Centralised WiFi Connectivity Management

This manager centralises all WiFi control and status for the JEB system.

It is only instantiated when WiFi credentials are present in the config,
and only imports WiFi-related modules when connect() is first called.
It is designed to be passed to the Updater and WebServerManager to provide
shared connectivity lifecycle management.
"""


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
            return self._wifi.radio.ipv4_address
        return None

    @property
    def pool(self):
        """Return the socket pool, or None if not connected."""
        return self._pool

    def connect(self, timeout=30):
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
                print("WiFi modules not available")
                return False

        # Already connected - ensure pool exists
        if self._wifi.radio.connected:
            if self._pool is None:
                self._pool = self._socketpool.SocketPool(self._wifi.radio)
            print(f"Already connected to WiFi. IP: {self._wifi.radio.ipv4_address}")
            return True

        import time
        try:
            print(f"Connecting to WiFi: {self.ssid}")
            self._wifi.radio.connect(self.ssid, self.password, timeout=timeout)

            start = time.monotonic()
            while not self._wifi.radio.connected and (time.monotonic() - start) < timeout:
                time.sleep(0.5)

            if self._wifi.radio.connected:
                self._pool = self._socketpool.SocketPool(self._wifi.radio)
                print(f"✓ Connected! IP: {self._wifi.radio.ipv4_address}")
                return True
            else:
                print("✗ WiFi connection timeout")
                return False

        except Exception as e:
            print(f"WiFi connection error: {e}")
            return False

    def disconnect(self):
        """
        Disconnect from WiFi and release the socket pool.

        Safe to call even if not currently connected.
        """
        if self._wifi is not None and self._wifi.radio.connected:
            try:
                self._wifi.radio.enabled = False
                print("WiFi disconnected")
            except Exception as e:
                print(f"Error disconnecting WiFi: {e}")
        self._pool = None

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
            print("adafruit_requests or ssl not available")
            return None
