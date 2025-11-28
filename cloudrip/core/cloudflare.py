"""Cloudflare IP range management."""

from ipaddress import (
    AddressValueError,
    IPv4Address,
    IPv4Network,
    IPv6Address,
    IPv6Network,
)

import requests


class CloudflareIPRanges:
    """Manages Cloudflare IP ranges (IPv4 + IPv6) with dynamic fetching."""

    API_URL_V4 = "https://www.cloudflare.com/ips-v4"
    API_URL_V6 = "https://www.cloudflare.com/ips-v6"

    FALLBACK_V4 = [
        "103.21.244.0/22",
        "103.22.200.0/22",
        "103.31.4.0/22",
        "104.16.0.0/13",
        "104.24.0.0/14",
        "108.162.192.0/18",
        "131.0.72.0/22",
        "141.101.64.0/18",
        "162.158.0.0/15",
        "172.64.0.0/13",
        "173.245.48.0/20",
        "188.114.96.0/20",
        "190.93.240.0/20",
        "197.234.240.0/22",
        "198.41.128.0/17",
    ]

    FALLBACK_V6 = [
        "2400:cb00::/32",
        "2606:4700::/32",
        "2803:f800::/32",
        "2405:b500::/32",
        "2405:8100::/32",
        "2a06:98c0::/29",
        "2c0f:f248::/32",
    ]

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self._networks_v4: list[IPv4Network] = []
        self._networks_v6: list[IPv6Network] = []
        self._loaded = False
        self._used_fallback_v4 = False
        self._used_fallback_v6 = False

    def load(self) -> tuple[bool, bool]:
        """Load Cloudflare IP ranges. Returns (v4_from_api, v6_from_api)."""
        ranges_v4 = self._fetch_from_api(self.API_URL_V4)
        ranges_v6 = self._fetch_from_api(self.API_URL_V6)

        if ranges_v4:
            self._networks_v4 = [IPv4Network(cidr) for cidr in ranges_v4]
            self._used_fallback_v4 = False
        else:
            self._networks_v4 = [IPv4Network(cidr) for cidr in self.FALLBACK_V4]
            self._used_fallback_v4 = True

        if ranges_v6:
            self._networks_v6 = [IPv6Network(cidr) for cidr in ranges_v6]
            self._used_fallback_v6 = False
        else:
            self._networks_v6 = [IPv6Network(cidr) for cidr in self.FALLBACK_V6]
            self._used_fallback_v6 = True

        self._loaded = True
        return (not self._used_fallback_v4, not self._used_fallback_v6)

    def _fetch_from_api(self, url: str) -> list[str]:
        """Fetch IP ranges from Cloudflare's public endpoint."""
        try:
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            return [
                line.strip()
                for line in response.text.strip().split("\n")
                if line.strip()
            ]
        except requests.RequestException:
            return []

    def is_cloudflare_ip(self, ip: str) -> bool:
        """Check if an IP address (v4 or v6) belongs to Cloudflare."""
        if not self._loaded:
            self.load()

        try:
            v4_addr = IPv4Address(ip)
            return any(v4_addr in network for network in self._networks_v4)
        except AddressValueError:
            pass

        try:
            v6_addr = IPv6Address(ip)
            return any(v6_addr in network for network in self._networks_v6)
        except AddressValueError:
            pass

        return False

    @property
    def used_fallback(self) -> tuple[bool, bool]:
        """Returns (used_fallback_v4, used_fallback_v6)."""
        return (self._used_fallback_v4, self._used_fallback_v6)

    @property
    def range_count(self) -> tuple[int, int]:
        """Returns (v4_count, v6_count)."""
        return (len(self._networks_v4), len(self._networks_v6))

    @property
    def is_loaded(self) -> bool:
        """Check if ranges have been loaded."""
        return self._loaded
