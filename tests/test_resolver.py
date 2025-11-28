"""Tests for cloudrip.core.resolver."""

from unittest.mock import MagicMock, patch

import dns.resolver
import pytest

from cloudrip.core.resolver import DNSResolver


class TestDNSResolver:
    """Tests for DNSResolver class."""

    def test_init_with_cf_ranges(self, mock_cf_ranges):
        """Test initialization with provided CF ranges."""
        resolver = DNSResolver(mock_cf_ranges)
        assert resolver.cf_ranges is mock_cf_ranges

    def test_init_creates_cf_ranges(self):
        """Test initialization creates CF ranges if not provided."""
        resolver = DNSResolver()
        assert resolver.cf_ranges is not None

    def test_resolve_record_a_success(self, dns_resolver):
        """Test resolving A records successfully."""
        mock_answer = MagicMock()
        mock_answer.address = "192.168.1.1"
        mock_answers = [mock_answer]

        with patch("dns.resolver.resolve", return_value=mock_answers):
            result = dns_resolver.resolve_record("test.com", "A")

        assert result == ["192.168.1.1"]

    def test_resolve_record_multiple_ips(self, dns_resolver):
        """Test resolving multiple A records."""
        mock_answers = []
        for ip in ["192.168.1.1", "192.168.1.2", "192.168.1.3"]:
            mock_answer = MagicMock()
            mock_answer.address = ip
            mock_answers.append(mock_answer)

        with patch("dns.resolver.resolve", return_value=mock_answers):
            result = dns_resolver.resolve_record("test.com", "A")

        assert len(result) == 3
        assert "192.168.1.1" in result
        assert "192.168.1.2" in result
        assert "192.168.1.3" in result

    def test_resolve_record_nxdomain(self, dns_resolver):
        """Test resolving non-existent domain."""
        with patch("dns.resolver.resolve", side_effect=dns.resolver.NXDOMAIN):
            result = dns_resolver.resolve_record("nonexistent.com", "A")

        assert result == []

    def test_resolve_record_no_answer(self, dns_resolver):
        """Test resolving domain with no answer."""
        with patch("dns.resolver.resolve", side_effect=dns.resolver.NoAnswer):
            result = dns_resolver.resolve_record("test.com", "AAAA")

        assert result == []

    def test_resolve_record_timeout(self, dns_resolver):
        """Test resolving with timeout."""
        with patch("dns.resolver.resolve", side_effect=dns.resolver.Timeout):
            result = dns_resolver.resolve_record("test.com", "A")

        assert result == []

    def test_resolve_record_no_nameservers(self, dns_resolver):
        """Test resolving with no nameservers."""
        with patch("dns.resolver.resolve", side_effect=dns.resolver.NoNameservers):
            result = dns_resolver.resolve_record("test.com", "A")

        assert result == []

    def test_resolve_record_generic_exception(self, dns_resolver):
        """Test resolving with generic exception."""
        with patch("dns.resolver.resolve", side_effect=Exception("Unknown error")):
            result = dns_resolver.resolve_record("test.com", "A")

        assert result == []

    def test_resolve_domain_found(self, dns_resolver):
        """Test resolve_domain with non-CF IPs found."""

        def mock_resolve(domain, record_type):
            mock_answer = MagicMock()
            if record_type == "A":
                mock_answer.address = "192.168.1.1"
            else:
                mock_answer.address = "2001:db8::1"
            return [mock_answer]

        with patch("dns.resolver.resolve", side_effect=mock_resolve):
            result = dns_resolver.resolve_domain("test.example.com")

        assert result.domain == "test.example.com"
        assert result.status == "found"
        assert "192.168.1.1" in result.ipv4
        assert "2001:db8::1" in result.ipv6

    def test_resolve_domain_cloudflare(self, dns_resolver):
        """Test resolve_domain with all CF IPs."""

        def mock_resolve(domain, record_type):
            mock_answer = MagicMock()
            if record_type == "A":
                mock_answer.address = "104.16.1.1"
            else:
                mock_answer.address = "2606:4700::1"
            return [mock_answer]

        with patch("dns.resolver.resolve", side_effect=mock_resolve):
            result = dns_resolver.resolve_domain("cf.example.com")

        assert result.status == "cloudflare"
        assert "104.16.1.1" in result.ipv4_cloudflare
        assert "2606:4700::1" in result.ipv6_cloudflare

    def test_resolve_domain_not_found(self, dns_resolver):
        """Test resolve_domain with no IPs found."""
        with patch("dns.resolver.resolve", side_effect=dns.resolver.NXDOMAIN):
            result = dns_resolver.resolve_domain("notfound.example.com")

        assert result.status == "not_found"
        assert result.ipv4 == []
        assert result.ipv6 == []

    def test_resolve_domain_with_base_domain(self, dns_resolver):
        """Test resolve_domain with base domain."""

        def mock_resolve(domain, record_type):
            mock_answer = MagicMock()
            mock_answer.address = "192.168.1.1"
            return [mock_answer]

        with patch("dns.resolver.resolve", side_effect=mock_resolve):
            result = dns_resolver.resolve_domain("www", "example.com")

        assert result.domain == "www.example.com"

    def test_resolve_domain_mixed_ips(self, dns_resolver):
        """Test resolve_domain with mixed CF and non-CF IPs."""

        def mock_resolve(domain, record_type):
            if record_type == "A":
                answers = []
                for ip in ["192.168.1.1", "104.16.1.1"]:
                    mock_answer = MagicMock()
                    mock_answer.address = ip
                    answers.append(mock_answer)
                return answers
            raise dns.resolver.NoAnswer

        with patch("dns.resolver.resolve", side_effect=mock_resolve):
            result = dns_resolver.resolve_domain("mixed.example.com")

        assert result.status == "found"
        assert len(result.ipv4) == 2
        assert len(result.ipv4_cloudflare) == 1
        assert result.has_non_cf_ip is True
