"""Tests for the proxy module."""

import socket
from unittest.mock import MagicMock, patch

import pytest
import socks

from cloudrip.core.proxy import (
    ProxyConfig,
    ProxyManager,
    ProxyType,
    parse_proxy_list,
)


class TestProxyType:
    """Tests for ProxyType enum."""

    def test_socks4_value(self):
        """Test SOCKS4 value."""
        assert ProxyType.SOCKS4.value == socks.SOCKS4

    def test_socks5_value(self):
        """Test SOCKS5 value."""
        assert ProxyType.SOCKS5.value == socks.SOCKS5


class TestProxyConfig:
    """Tests for ProxyConfig dataclass."""

    def test_from_url_socks5_basic(self):
        """Test parsing basic SOCKS5 URL."""
        config = ProxyConfig.from_url("socks5://127.0.0.1:1080")
        assert config.type == ProxyType.SOCKS5
        assert config.host == "127.0.0.1"
        assert config.port == 1080
        assert config.username is None
        assert config.password is None

    def test_from_url_socks4_basic(self):
        """Test parsing basic SOCKS4 URL."""
        config = ProxyConfig.from_url("socks4://192.168.1.1:9050")
        assert config.type == ProxyType.SOCKS4
        assert config.host == "192.168.1.1"
        assert config.port == 9050

    def test_from_url_socks_alias(self):
        """Test 'socks' scheme is treated as SOCKS5."""
        config = ProxyConfig.from_url("socks://localhost:1080")
        assert config.type == ProxyType.SOCKS5

    def test_from_url_with_auth(self):
        """Test parsing URL with authentication."""
        config = ProxyConfig.from_url("socks5://user:pass@proxy.example.com:1080")
        assert config.type == ProxyType.SOCKS5
        assert config.host == "proxy.example.com"
        assert config.port == 1080
        assert config.username == "user"
        assert config.password == "pass"

    def test_from_url_default_port(self):
        """Test default port when not specified."""
        config = ProxyConfig.from_url("socks5://localhost")
        assert config.port == 1080

    def test_from_url_unsupported_scheme(self):
        """Test unsupported scheme raises error."""
        with pytest.raises(ValueError) as exc_info:
            ProxyConfig.from_url("http://localhost:8080")
        assert "Unsupported proxy scheme" in str(exc_info.value)

    def test_from_url_missing_host(self):
        """Test missing host raises error."""
        with pytest.raises(ValueError) as exc_info:
            ProxyConfig.from_url("socks5://:1080")
        assert "missing host" in str(exc_info.value)

    def test_to_tuple(self):
        """Test conversion to tuple for socks library."""
        config = ProxyConfig(
            type=ProxyType.SOCKS5,
            host="localhost",
            port=1080,
            username="user",
            password="pass",
        )
        result = config.to_tuple()
        assert result == (socks.SOCKS5, "localhost", 1080, True, "user", "pass")

    def test_to_tuple_no_auth(self):
        """Test tuple without authentication."""
        config = ProxyConfig(
            type=ProxyType.SOCKS4,
            host="127.0.0.1",
            port=9050,
        )
        result = config.to_tuple()
        assert result == (socks.SOCKS4, "127.0.0.1", 9050, True, None, None)


class TestProxyManager:
    """Tests for ProxyManager class."""

    def test_init_no_proxies(self):
        """Test initialization with no proxies."""
        manager = ProxyManager()
        assert manager.has_proxies is False
        assert manager.proxy_count == 0

    def test_init_with_proxies(self):
        """Test initialization with proxy list."""
        proxies = ["socks5://localhost:1080", "socks5://localhost:1081"]
        manager = ProxyManager(proxies)
        assert manager.has_proxies is True
        assert manager.proxy_count == 2

    def test_init_skips_invalid_urls(self):
        """Test invalid proxy URLs are skipped."""
        proxies = ["socks5://localhost:1080", "http://invalid:8080", "bad-url"]
        manager = ProxyManager(proxies)
        assert manager.proxy_count == 1

    def test_get_next_proxy_empty(self):
        """Test get_next_proxy with no proxies."""
        manager = ProxyManager()
        assert manager.get_next_proxy() is None

    def test_get_next_proxy_single(self):
        """Test get_next_proxy with single proxy."""
        manager = ProxyManager(["socks5://localhost:1080"])
        proxy = manager.get_next_proxy()
        assert proxy is not None
        assert proxy.host == "localhost"
        assert proxy.port == 1080

    def test_get_next_proxy_rotation(self):
        """Test proxy rotation."""
        proxies = ["socks5://host1:1080", "socks5://host2:1080", "socks5://host3:1080"]
        manager = ProxyManager(proxies, rotate=True)

        # First round
        assert manager.get_next_proxy().host == "host1"
        assert manager.get_next_proxy().host == "host2"
        assert manager.get_next_proxy().host == "host3"

        # Rotation wraps around
        assert manager.get_next_proxy().host == "host1"

    def test_get_next_proxy_no_rotation(self):
        """Test without proxy rotation."""
        proxies = ["socks5://host1:1080", "socks5://host2:1080"]
        manager = ProxyManager(proxies, rotate=False)

        # Always returns first proxy
        assert manager.get_next_proxy().host == "host1"
        assert manager.get_next_proxy().host == "host1"
        assert manager.get_next_proxy().host == "host1"

    def test_create_socket_no_proxy(self):
        """Test create_socket without proxies returns regular socket."""
        manager = ProxyManager()
        sock = manager.create_socket()
        # Should be a regular socket, not a socks socket
        assert sock is not None
        sock.close()

    def test_create_socket_with_proxy(self):
        """Test create_socket with proxy returns SOCKS socket."""
        manager = ProxyManager(["socks5://localhost:1080"])
        with patch.object(socks, "socksocket") as mock_socksocket:
            mock_sock = MagicMock()
            mock_socksocket.return_value = mock_sock

            sock = manager.create_socket()

            mock_socksocket.assert_called_once_with(socket.AF_INET, socket.SOCK_STREAM)
            mock_sock.set_proxy.assert_called_once()
            assert sock == mock_sock

    def test_activate_global_no_proxies(self):
        """Test activate_global does nothing without proxies."""
        manager = ProxyManager()
        original_socket = socket.socket
        manager.activate_global()
        # Socket should not be patched
        assert socket.socket == original_socket

    def test_activate_deactivate_global(self):
        """Test activate and deactivate global proxy."""
        manager = ProxyManager(["socks5://localhost:1080"])
        original_socket = socket.socket

        with patch.object(socks, "set_default_proxy") as mock_set_proxy:
            manager.activate_global()
            mock_set_proxy.assert_called_once()

        # Deactivate
        with patch.object(socks, "set_default_proxy") as mock_set_proxy:
            manager.deactivate_global()
            mock_set_proxy.assert_called_once_with()
            # Socket should be restored
            assert socket.socket == original_socket


class TestParseProxyList:
    """Tests for parse_proxy_list function."""

    def test_empty_string(self):
        """Test empty string returns empty list."""
        assert parse_proxy_list("") == []

    def test_none_string(self):
        """Test None-like empty string."""
        assert parse_proxy_list("") == []

    def test_single_proxy(self):
        """Test single proxy URL."""
        result = parse_proxy_list("socks5://localhost:1080")
        assert result == ["socks5://localhost:1080"]

    def test_multiple_proxies(self):
        """Test comma-separated proxy URLs."""
        result = parse_proxy_list("socks5://host1:1080,socks5://host2:1080")
        assert result == ["socks5://host1:1080", "socks5://host2:1080"]

    def test_with_spaces(self):
        """Test URLs with spaces are trimmed."""
        result = parse_proxy_list("  socks5://host1:1080  ,  socks5://host2:1080  ")
        assert result == ["socks5://host1:1080", "socks5://host2:1080"]

    def test_empty_entries_skipped(self):
        """Test empty entries are skipped."""
        result = parse_proxy_list("socks5://host1:1080,,socks5://host2:1080,")
        assert result == ["socks5://host1:1080", "socks5://host2:1080"]

    def test_complex_url_with_auth(self):
        """Test URL with authentication is preserved."""
        result = parse_proxy_list("socks5://user:pass@host:1080")
        assert result == ["socks5://user:pass@host:1080"]
