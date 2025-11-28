"""Tests for cloudrip.core.cloudflare."""

from unittest.mock import MagicMock, patch

import pytest

from cloudrip.core.cloudflare import CloudflareIPRanges


class TestCloudflareIPRanges:
    """Tests for CloudflareIPRanges class."""

    def test_init_defaults(self):
        """Test initialization with default values."""
        ranges = CloudflareIPRanges()
        assert ranges.timeout == 10
        assert ranges._loaded is False
        assert ranges._networks_v4 == []
        assert ranges._networks_v6 == []

    def test_init_custom_timeout(self):
        """Test initialization with custom timeout."""
        ranges = CloudflareIPRanges(timeout=30)
        assert ranges.timeout == 30

    def test_load_with_fallback(self):
        """Test load falls back when API is unreachable."""
        ranges = CloudflareIPRanges()
        with patch.object(ranges, "_fetch_from_api", return_value=[]):
            v4_api, v6_api = ranges.load()

        assert v4_api is False
        assert v6_api is False
        assert ranges._loaded is True
        assert len(ranges._networks_v4) == len(CloudflareIPRanges.FALLBACK_V4)
        assert len(ranges._networks_v6) == len(CloudflareIPRanges.FALLBACK_V6)

    def test_load_with_api_success(self):
        """Test load uses API data when available."""
        ranges = CloudflareIPRanges()

        def mock_fetch(url):
            if "v4" in url:
                return ["103.21.244.0/22", "104.16.0.0/13"]
            return ["2400:cb00::/32"]

        with patch.object(ranges, "_fetch_from_api", side_effect=mock_fetch):
            v4_api, v6_api = ranges.load()

        assert v4_api is True
        assert v6_api is True
        assert len(ranges._networks_v4) == 2
        assert len(ranges._networks_v6) == 1

    def test_is_cloudflare_ip_v4_true(self, cf_ranges):
        """Test IPv4 detection for Cloudflare IP."""
        # 104.16.0.0/13 includes 104.16.x.x
        assert cf_ranges.is_cloudflare_ip("104.16.1.1") is True

    def test_is_cloudflare_ip_v4_false(self, cf_ranges):
        """Test IPv4 detection for non-Cloudflare IP."""
        assert cf_ranges.is_cloudflare_ip("192.168.1.1") is False
        assert cf_ranges.is_cloudflare_ip("8.8.8.8") is False

    def test_is_cloudflare_ip_v6_true(self, cf_ranges):
        """Test IPv6 detection for Cloudflare IP."""
        # 2606:4700::/32 includes 2606:4700::x
        assert cf_ranges.is_cloudflare_ip("2606:4700::1") is True

    def test_is_cloudflare_ip_v6_false(self, cf_ranges):
        """Test IPv6 detection for non-Cloudflare IP."""
        assert cf_ranges.is_cloudflare_ip("2001:db8::1") is False

    def test_is_cloudflare_ip_invalid(self, cf_ranges):
        """Test with invalid IP address."""
        assert cf_ranges.is_cloudflare_ip("not-an-ip") is False
        assert cf_ranges.is_cloudflare_ip("") is False

    def test_is_cloudflare_ip_auto_loads(self):
        """Test is_cloudflare_ip loads ranges if not loaded."""
        ranges = CloudflareIPRanges()
        with patch.object(ranges, "_fetch_from_api", return_value=[]):
            # Should trigger load()
            result = ranges.is_cloudflare_ip("104.16.1.1")
            assert ranges._loaded is True

    def test_used_fallback_property(self, cf_ranges):
        """Test used_fallback property."""
        v4_fallback, v6_fallback = cf_ranges.used_fallback
        assert v4_fallback is True
        assert v6_fallback is True

    def test_range_count_property(self, cf_ranges):
        """Test range_count property."""
        v4_count, v6_count = cf_ranges.range_count
        assert v4_count == len(CloudflareIPRanges.FALLBACK_V4)
        assert v6_count == len(CloudflareIPRanges.FALLBACK_V6)

    def test_is_loaded_property(self, cf_ranges):
        """Test is_loaded property."""
        assert cf_ranges.is_loaded is True

        new_ranges = CloudflareIPRanges()
        assert new_ranges.is_loaded is False

    def test_fetch_from_api_success(self):
        """Test _fetch_from_api with successful response."""
        ranges = CloudflareIPRanges()

        mock_response = MagicMock()
        mock_response.text = "103.21.244.0/22\n104.16.0.0/13\n"
        mock_response.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_response):
            result = ranges._fetch_from_api("http://test.com")

        assert result == ["103.21.244.0/22", "104.16.0.0/13"]

    def test_fetch_from_api_failure(self):
        """Test _fetch_from_api with network error."""
        import requests as req

        ranges = CloudflareIPRanges()

        with patch("requests.get", side_effect=req.RequestException("Network error")):
            result = ranges._fetch_from_api("http://test.com")

        assert result == []

    def test_api_urls(self):
        """Test API URL constants are set."""
        assert CloudflareIPRanges.API_URL_V4 == "https://www.cloudflare.com/ips-v4"
        assert CloudflareIPRanges.API_URL_V6 == "https://www.cloudflare.com/ips-v6"

    def test_fallback_ranges_not_empty(self):
        """Test fallback ranges are defined."""
        assert len(CloudflareIPRanges.FALLBACK_V4) > 0
        assert len(CloudflareIPRanges.FALLBACK_V6) > 0
