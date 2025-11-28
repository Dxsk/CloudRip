"""Tests for cloudrip.core.models."""

import pytest

from cloudrip.core.models import OutputFormat, ResolveResult, ScanReport


class TestOutputFormat:
    """Tests for OutputFormat enum."""

    def test_enum_values(self):
        """Test all enum values exist."""
        assert OutputFormat.NORMAL.value == "normal"
        assert OutputFormat.JSON.value == "json"
        assert OutputFormat.YAML.value == "yaml"
        assert OutputFormat.CSV.value == "csv"

    def test_enum_from_string(self):
        """Test creating enum from string."""
        assert OutputFormat("normal") == OutputFormat.NORMAL
        assert OutputFormat("json") == OutputFormat.JSON


class TestResolveResult:
    """Tests for ResolveResult dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        result = ResolveResult(domain="test.com")
        assert result.domain == "test.com"
        assert result.ipv4 == []
        assert result.ipv6 == []
        assert result.status == "unknown"
        assert result.ipv4_cloudflare == []
        assert result.ipv6_cloudflare == []
        assert result.error is None

    def test_ipv4_non_cf(self, sample_resolve_result):
        """Test ipv4_non_cf property filters correctly."""
        non_cf = sample_resolve_result.ipv4_non_cf
        assert "192.168.1.1" in non_cf
        assert "104.16.1.1" not in non_cf

    def test_ipv6_non_cf(self, sample_resolve_result):
        """Test ipv6_non_cf property filters correctly."""
        non_cf = sample_resolve_result.ipv6_non_cf
        assert "2001:db8::1" in non_cf
        assert "2606:4700::1" not in non_cf

    def test_has_non_cf_ip_true(self, sample_resolve_result):
        """Test has_non_cf_ip returns True when non-CF IPs exist."""
        assert sample_resolve_result.has_non_cf_ip is True

    def test_has_non_cf_ip_false(self, sample_cf_result):
        """Test has_non_cf_ip returns False when all IPs are CF."""
        assert sample_cf_result.has_non_cf_ip is False

    def test_all_cloudflare_true(self, sample_cf_result):
        """Test all_cloudflare returns True when all IPs are CF."""
        assert sample_cf_result.all_cloudflare is True

    def test_all_cloudflare_false(self, sample_resolve_result):
        """Test all_cloudflare returns False when some IPs are not CF."""
        assert sample_resolve_result.all_cloudflare is False

    def test_all_cloudflare_empty(self):
        """Test all_cloudflare returns False when no IPs."""
        result = ResolveResult(domain="test.com")
        assert result.all_cloudflare is False

    def test_to_dict(self, sample_resolve_result):
        """Test to_dict conversion."""
        d = sample_resolve_result.to_dict()
        assert d["domain"] == "test.example.com"
        assert d["ipv4"] == ["192.168.1.1", "104.16.1.1"]
        assert d["status"] == "found"


class TestScanReport:
    """Tests for ScanReport dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        report = ScanReport(target_domain="example.com")
        assert report.target_domain == "example.com"
        assert report.total_checked == 0
        assert report.found == []
        assert report.cloudflare == []
        assert report.not_found == []
        assert report.errors == []
        assert report.scan_date is not None

    def test_to_dict(self, sample_scan_report):
        """Test to_dict conversion."""
        d = sample_scan_report.to_dict()
        assert d["target_domain"] == "example.com"
        assert d["total_checked"] == 3
        assert d["summary"]["found"] == 1
        assert d["summary"]["cloudflare"] == 1
        assert d["summary"]["not_found"] == 1
        assert d["summary"]["errors"] == 0
        assert "results" in d
        assert len(d["results"]["found"]) == 1
        assert len(d["results"]["cloudflare"]) == 1

    def test_to_dict_results_structure(self, sample_scan_report):
        """Test to_dict results have correct structure."""
        d = sample_scan_report.to_dict()
        found_result = d["results"]["found"][0]
        assert "domain" in found_result
        assert "ipv4" in found_result
        assert "ipv6" in found_result
        assert "status" in found_result
