"""Pytest fixtures for CloudRip tests."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cloudrip.core.cloudflare import CloudflareIPRanges
from cloudrip.core.models import OutputFormat, ResolveResult, ScanReport
from cloudrip.core.resolver import DNSResolver
from cloudrip.core.scanner import CloudRipScanner


@pytest.fixture
def sample_resolve_result() -> ResolveResult:
    """Create a sample ResolveResult for testing."""
    return ResolveResult(
        domain="test.example.com",
        ipv4=["192.168.1.1", "104.16.1.1"],
        ipv6=["2001:db8::1", "2606:4700::1"],
        status="found",
        ipv4_cloudflare=["104.16.1.1"],
        ipv6_cloudflare=["2606:4700::1"],
    )


@pytest.fixture
def sample_cf_result() -> ResolveResult:
    """Create a Cloudflare-only ResolveResult."""
    return ResolveResult(
        domain="www.example.com",
        ipv4=["104.16.1.1", "104.16.2.2"],
        ipv6=["2606:4700::1"],
        status="cloudflare",
        ipv4_cloudflare=["104.16.1.1", "104.16.2.2"],
        ipv6_cloudflare=["2606:4700::1"],
    )


@pytest.fixture
def sample_not_found_result() -> ResolveResult:
    """Create a not found ResolveResult."""
    return ResolveResult(
        domain="notfound.example.com",
        status="not_found",
    )


@pytest.fixture
def sample_scan_report(
    sample_resolve_result, sample_cf_result, sample_not_found_result
) -> ScanReport:
    """Create a sample ScanReport for testing."""
    report = ScanReport(target_domain="example.com")
    report.found.append(sample_resolve_result)
    report.cloudflare.append(sample_cf_result)
    report.not_found.append(sample_not_found_result)
    report.total_checked = 3
    return report


@pytest.fixture
def cf_ranges() -> CloudflareIPRanges:
    """Create CloudflareIPRanges with fallback data (no API call)."""
    ranges = CloudflareIPRanges()
    # Force load with fallback to avoid network calls
    with patch.object(ranges, "_fetch_from_api", return_value=[]):
        ranges.load()
    return ranges


@pytest.fixture
def mock_cf_ranges() -> CloudflareIPRanges:
    """Create a mocked CloudflareIPRanges."""
    ranges = MagicMock(spec=CloudflareIPRanges)
    ranges.is_loaded = True
    ranges.is_cloudflare_ip = MagicMock(
        side_effect=lambda ip: ip.startswith("104.") or ip.startswith("2606:4700")
    )
    ranges.range_count = (15, 7)
    ranges.load = MagicMock(return_value=(True, True))
    return ranges


@pytest.fixture
def dns_resolver(mock_cf_ranges) -> DNSResolver:
    """Create a DNSResolver with mocked CF ranges."""
    return DNSResolver(mock_cf_ranges)


@pytest.fixture
def scanner(mock_cf_ranges) -> CloudRipScanner:
    """Create a CloudRipScanner with mocked CF ranges."""
    s = CloudRipScanner("example.com", threads=2)
    s.cf_ranges = mock_cf_ranges
    return s


@pytest.fixture
def temp_wordlist() -> Path:
    """Create a temporary wordlist file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("# Comment line\n")
        f.write("www\n")
        f.write("mail\n")
        f.write("\n")  # Empty line
        f.write("api\n")
        f.write("# Another comment\n")
        f.write("ftp\n")
        path = Path(f.name)
    yield path
    path.unlink(missing_ok=True)


@pytest.fixture
def temp_output_file() -> Path:
    """Create a temporary output file path."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = Path(f.name)
    yield path
    path.unlink(missing_ok=True)
