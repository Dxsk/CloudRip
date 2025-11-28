"""Tests for cloudrip.core.scanner."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cloudrip.core.models import ResolveResult, ScanReport
from cloudrip.core.scanner import CloudRipScanner


class TestCloudRipScanner:
    """Tests for CloudRipScanner class."""

    def test_init_defaults(self):
        """Test initialization with default values."""
        scanner = CloudRipScanner("example.com")
        assert scanner.domain == "example.com"
        assert scanner.threads == 10
        assert scanner.rate_limit == 0.05
        assert scanner.stop_requested is False

    def test_init_custom_values(self):
        """Test initialization with custom values."""
        scanner = CloudRipScanner("example.com", threads=20, rate_limit=0.1)
        assert scanner.threads == 20
        assert scanner.rate_limit == 0.1

    def test_set_callbacks(self, scanner):
        """Test setting callbacks."""
        on_result = MagicMock()
        on_progress = MagicMock()

        scanner.set_callbacks(on_result=on_result, on_progress=on_progress)

        assert scanner._on_result is on_result
        assert scanner._on_progress is on_progress

    def test_load_cf_ranges(self, scanner):
        """Test load_cf_ranges calls load on cf_ranges."""
        result = scanner.load_cf_ranges()
        scanner.cf_ranges.load.assert_called_once()

    def test_load_wordlist(self, scanner, temp_wordlist):
        """Test loading a single wordlist."""
        subdomains = scanner.load_wordlist(temp_wordlist)

        assert "www" in subdomains
        assert "mail" in subdomains
        assert "api" in subdomains
        assert "ftp" in subdomains
        # Comments and empty lines should be excluded
        assert len(subdomains) == 4

    def test_load_wordlist_not_found(self, scanner):
        """Test loading non-existent wordlist raises error."""
        with pytest.raises(FileNotFoundError):
            scanner.load_wordlist("/nonexistent/wordlist.txt")

    def test_load_wordlists_multiple(self, scanner, temp_wordlist):
        """Test loading multiple wordlists."""
        # Create second wordlist
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("admin\n")
            f.write("www\n")  # Duplicate
            f.write("test\n")
            path2 = Path(f.name)

        try:
            subdomains = scanner.load_wordlists([temp_wordlist, path2])

            # Should be deduplicated and sorted
            assert "www" in subdomains
            assert "admin" in subdomains
            assert "test" in subdomains
            assert subdomains == sorted(set(subdomains))
        finally:
            path2.unlink(missing_ok=True)

    def test_load_wordlists_skips_missing(self, scanner, temp_wordlist):
        """Test loading wordlists skips missing files."""
        subdomains = scanner.load_wordlists([temp_wordlist, "/nonexistent/file.txt"])
        assert len(subdomains) == 4

    def test_resolve_subdomain_root(self, scanner):
        """Test resolving root domain."""
        mock_result = ResolveResult(domain="example.com", status="found")

        with patch.object(scanner.resolver, "resolve_domain", return_value=mock_result):
            result = scanner.resolve_subdomain()

        assert result.domain == "example.com"

    def test_resolve_subdomain_with_sub(self, scanner):
        """Test resolving subdomain."""
        mock_result = ResolveResult(domain="www.example.com", status="found")

        with patch.object(
            scanner.resolver, "resolve_domain", return_value=mock_result
        ) as mock_resolve:
            result = scanner.resolve_subdomain("www")
            mock_resolve.assert_called_with("www", "example.com")

    def test_add_result_found(self, scanner, sample_resolve_result):
        """Test add_result categorizes found results."""
        sample_resolve_result.status = "found"
        scanner.add_result(sample_resolve_result)

        assert len(scanner.report.found) == 1
        assert scanner.report.total_checked == 1

    def test_add_result_cloudflare(self, scanner, sample_cf_result):
        """Test add_result categorizes cloudflare results."""
        scanner.add_result(sample_cf_result)

        assert len(scanner.report.cloudflare) == 1

    def test_add_result_not_found(self, scanner, sample_not_found_result):
        """Test add_result categorizes not_found results."""
        scanner.add_result(sample_not_found_result)

        assert len(scanner.report.not_found) == 1

    def test_add_result_error(self, scanner):
        """Test add_result categorizes error results."""
        error_result = ResolveResult(
            domain="error.example.com",
            status="error",
            error="Some error",
        )
        scanner.add_result(error_result)

        assert len(scanner.report.errors) == 1

    def test_add_result_triggers_callback(self, scanner, sample_resolve_result):
        """Test add_result triggers on_result callback."""
        callback = MagicMock()
        scanner.set_callbacks(on_result=callback)

        scanner.add_result(sample_resolve_result)

        callback.assert_called_once_with(sample_resolve_result)

    def test_stop(self, scanner):
        """Test stop sets stop_requested."""
        assert scanner.stop_requested is False
        scanner.stop()
        assert scanner.stop_requested is True

    def test_scan_basic(self, scanner):
        """Test basic scan execution."""
        mock_result = ResolveResult(
            domain="test.example.com",
            ipv4=["192.168.1.1"],
            status="found",
        )

        with patch.object(scanner, "resolve_subdomain", return_value=mock_result):
            report = scanner.scan(["www", "mail"], include_root=False)

        assert report.total_checked == 2
        assert len(report.found) == 2

    def test_scan_with_root(self, scanner):
        """Test scan includes root domain."""
        mock_result = ResolveResult(
            domain="example.com",
            ipv4=["192.168.1.1"],
            status="found",
        )

        with patch.object(scanner, "resolve_subdomain", return_value=mock_result):
            report = scanner.scan(["www"], include_root=True)

        # Root + www = 2
        assert report.total_checked == 2

    def test_scan_progress_callback(self, scanner):
        """Test scan triggers progress callback."""
        progress_calls = []

        def on_progress(completed, total):
            progress_calls.append((completed, total))

        scanner.set_callbacks(on_progress=on_progress)

        mock_result = ResolveResult(domain="test.example.com", status="not_found")
        with patch.object(scanner, "resolve_subdomain", return_value=mock_result):
            scanner.scan(["www", "mail", "api"], include_root=False)

        assert len(progress_calls) == 3
        assert progress_calls[-1] == (3, 3)

    def test_scan_from_wordlists(self, scanner, temp_wordlist):
        """Test scan_from_wordlists."""
        mock_result = ResolveResult(domain="test.example.com", status="not_found")

        with patch.object(scanner, "resolve_subdomain", return_value=mock_result):
            report = scanner.scan_from_wordlists([temp_wordlist], include_root=False)

        # 4 subdomains in wordlist
        assert report.total_checked == 4

    def test_scan_stop_requested(self, scanner):
        """Test scan stops when stop_requested is set."""
        call_count = 0

        def mock_resolve(sub=None):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                scanner.stop_requested = True
            return ResolveResult(domain="test.example.com", status="not_found")

        with patch.object(scanner, "resolve_subdomain", side_effect=mock_resolve):
            report = scanner.scan(["www", "mail", "api", "ftp"], include_root=False)

        # Should stop early
        assert report.total_checked < 4

    def test_report_reset_on_scan(self, scanner):
        """Test report is reset on new scan."""
        scanner.report.total_checked = 100
        scanner.report.found.append(
            ResolveResult(domain="old.example.com", status="found")
        )

        mock_result = ResolveResult(domain="test.example.com", status="not_found")
        with patch.object(scanner, "resolve_subdomain", return_value=mock_result):
            scanner.scan(["www"], include_root=False)

        # Report should be fresh
        assert scanner.report.total_checked == 1
        assert len(scanner.report.found) == 0
