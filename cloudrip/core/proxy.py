"""SOCKS proxy support for DNS queries."""

import socket
import threading
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional
from urllib.parse import urlparse

import socks


class ProxyType(Enum):
    """Supported proxy types."""

    SOCKS4 = socks.SOCKS4
    SOCKS5 = socks.SOCKS5


@dataclass
class ProxyConfig:
    """Proxy configuration."""

    type: ProxyType
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None

    @classmethod
    def from_url(cls, url: str) -> "ProxyConfig":
        """Parse proxy URL.

        Formats:
            socks4://host:port
            socks5://host:port
            socks5://user:pass@host:port
        """
        parsed = urlparse(url)

        scheme = parsed.scheme.lower()
        if scheme == "socks4":
            proxy_type = ProxyType.SOCKS4
        elif scheme in ("socks5", "socks"):
            proxy_type = ProxyType.SOCKS5
        else:
            raise ValueError(f"Unsupported proxy scheme: {scheme}")

        host = parsed.hostname
        if not host:
            raise ValueError("Invalid proxy URL: missing host")

        port = parsed.port
        if not port:
            port = 1080  # Default SOCKS port

        return cls(
            type=proxy_type,
            host=host,
            port=port,
            username=parsed.username,
            password=parsed.password,
        )

    def to_tuple(self) -> tuple:
        """Convert to socks.set_default_proxy args."""
        return (
            self.type.value,
            self.host,
            self.port,
            True,  # rdns
            self.username,
            self.password,
        )


class ProxyManager:
    """Manages SOCKS proxies with rotation support."""

    def __init__(self, proxies: Optional[List[str]] = None, rotate: bool = True):
        """Initialize proxy manager.

        Args:
            proxies: List of proxy URLs (socks5://host:port)
            rotate: Whether to rotate between proxies
        """
        self._proxies: List[ProxyConfig] = []
        self._current_index = 0
        self._lock = threading.Lock()
        self._rotate = rotate
        self._original_socket = socket.socket

        if proxies:
            for url in proxies:
                try:
                    self._proxies.append(ProxyConfig.from_url(url))
                except ValueError:
                    pass  # bad url, skip it

    @property
    def has_proxies(self) -> bool:
        """Check if any proxies are configured."""
        return len(self._proxies) > 0

    @property
    def proxy_count(self) -> int:
        """Get number of configured proxies."""
        return len(self._proxies)

    def get_next_proxy(self) -> Optional[ProxyConfig]:
        """Get the next proxy in rotation.

        Returns:
            ProxyConfig or None if no proxies configured
        """
        if not self._proxies:
            return None

        with self._lock:
            proxy = self._proxies[self._current_index]
            if self._rotate:
                self._current_index = (self._current_index + 1) % len(self._proxies)
            return proxy

    def create_socket(self) -> socket.socket:
        """Create a SOCKS-wrapped socket.

        Returns:
            Socket configured with proxy or regular socket
        """
        proxy = self.get_next_proxy()

        if proxy is None:
            return self._original_socket(socket.AF_INET, socket.SOCK_STREAM)

        sock = socks.socksocket(socket.AF_INET, socket.SOCK_STREAM)
        sock.set_proxy(
            proxy.type.value,
            proxy.host,
            proxy.port,
            rdns=True,
            username=proxy.username,
            password=proxy.password,
        )
        return sock

    def activate_global(self) -> None:
        """Activate proxy globally (patches socket module).

        Warning: This affects all socket connections in the process.
        """
        if not self._proxies:
            return

        proxy = self._proxies[0]
        socks.set_default_proxy(*proxy.to_tuple())
        socket.socket = socks.socksocket

    def deactivate_global(self) -> None:
        """Deactivate global proxy patching."""
        socks.set_default_proxy()
        socket.socket = self._original_socket


def parse_proxy_list(proxy_string: str) -> List[str]:
    """Parse comma-separated proxy list.

    Args:
        proxy_string: Comma-separated proxy URLs

    Returns:
        List of proxy URLs
    """
    if not proxy_string:
        return []

    proxies = []
    for proxy in proxy_string.split(","):
        proxy = proxy.strip()
        if proxy:
            proxies.append(proxy)
    return proxies
