"""Tests for the wordlist download module."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from cloudrip.api.wordlist import (
    WordlistDownloadError,
    cleanup_temp_dir,
    download_wordlist,
    download_wordlists,
    validate_url,
)


class TestValidateUrl:
    """Tests for validate_url function."""

    def test_valid_https_url(self):
        """Test valid HTTPS URL."""
        assert validate_url("https://example.com/wordlist.txt") is True

    def test_valid_http_url(self):
        """Test valid HTTP URL."""
        assert validate_url("http://example.com/wordlist.txt") is True

    def test_invalid_scheme_ftp(self):
        """Test invalid FTP scheme."""
        assert validate_url("ftp://example.com/wordlist.txt") is False

    def test_invalid_scheme_file(self):
        """Test invalid file scheme."""
        assert validate_url("file:///etc/passwd") is False

    def test_invalid_no_scheme(self):
        """Test URL without scheme."""
        assert validate_url("example.com/wordlist.txt") is False

    def test_invalid_no_host(self):
        """Test URL without host."""
        assert validate_url("https:///wordlist.txt") is False

    def test_blocked_localhost(self):
        """Test localhost is blocked."""
        assert validate_url("https://localhost/wordlist.txt") is False
        assert validate_url("https://localhost:8080/wordlist.txt") is False

    def test_blocked_127_prefix(self):
        """Test 127.x.x.x is blocked."""
        assert validate_url("https://127.0.0.1/wordlist.txt") is False
        assert validate_url("https://127.1.2.3/wordlist.txt") is False

    def test_blocked_10_prefix(self):
        """Test 10.x.x.x is blocked."""
        assert validate_url("https://10.0.0.1/wordlist.txt") is False
        assert validate_url("https://10.255.255.255/wordlist.txt") is False

    def test_blocked_192_168_prefix(self):
        """Test 192.168.x.x is blocked."""
        assert validate_url("https://192.168.1.1/wordlist.txt") is False
        assert validate_url("https://192.168.0.100/wordlist.txt") is False

    def test_blocked_172_16_to_31(self):
        """Test 172.16-31.x.x is blocked."""
        assert validate_url("https://172.16.0.1/wordlist.txt") is False
        assert validate_url("https://172.31.255.255/wordlist.txt") is False

    def test_blocked_169_254_prefix(self):
        """Test 169.254.x.x (link-local) is blocked."""
        assert validate_url("https://169.254.1.1/wordlist.txt") is False

    def test_blocked_0_0_0_0(self):
        """Test 0.0.0.0 is blocked."""
        assert validate_url("https://0.0.0.0/wordlist.txt") is False

    def test_blocked_ipv6_loopback(self):
        """Test IPv6 loopback is blocked."""
        assert validate_url("https://[::1]/wordlist.txt") is False

    def test_valid_public_ip(self):
        """Test public IP is allowed."""
        assert validate_url("https://8.8.8.8/wordlist.txt") is True
        assert validate_url("https://1.1.1.1/wordlist.txt") is True

    def test_valid_domain(self):
        """Test valid domain is allowed."""
        assert (
            validate_url(
                "https://raw.githubusercontent.com/user/repo/main/wordlist.txt"
            )
            is True
        )

    def test_invalid_empty_string(self):
        """Test empty string."""
        assert validate_url("") is False

    def test_invalid_malformed_url(self):
        """Test malformed URL."""
        assert validate_url("not a url") is False
        assert validate_url("://missing.scheme") is False


class TestDownloadWordlist:
    """Tests for download_wordlist function."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_download_success(self, temp_dir):
        """Test successful download."""
        mock_response = MagicMock()
        mock_response.headers = {"Content-Length": "100"}
        mock_response.iter_content.return_value = [b"www\nmail\napi\n"]

        with patch("cloudrip.api.wordlist.requests.get", return_value=mock_response):
            path = download_wordlist("https://example.com/wordlist.txt", temp_dir)
            assert path.exists()
            assert path.read_text() == "www\nmail\napi\n"

    def test_download_invalid_url(self, temp_dir):
        """Test download with invalid URL."""
        with pytest.raises(WordlistDownloadError) as exc_info:
            download_wordlist("https://localhost/wordlist.txt", temp_dir)
        assert "Invalid or blocked URL" in str(exc_info.value)

    def test_download_content_too_large_header(self, temp_dir):
        """Test download rejected due to Content-Length header."""
        mock_response = MagicMock()
        mock_response.headers = {"Content-Length": str(100 * 1024 * 1024)}  # 100MB

        with patch("cloudrip.api.wordlist.requests.get", return_value=mock_response):
            with pytest.raises(WordlistDownloadError) as exc_info:
                download_wordlist("https://example.com/wordlist.txt", temp_dir)
            assert "too large" in str(exc_info.value)

    def test_download_content_too_large_streaming(self, temp_dir):
        """Test download rejected during streaming due to size."""
        mock_response = MagicMock()
        mock_response.headers = {}  # No Content-Length
        # Simulate large chunks
        large_chunk = b"x" * (1024 * 1024)  # 1MB chunks
        mock_response.iter_content.return_value = [large_chunk] * 15  # 15MB total

        with patch("cloudrip.api.wordlist.requests.get", return_value=mock_response):
            with patch("cloudrip.api.wordlist.settings") as mock_settings:
                mock_settings.max_wordlist_size = 10 * 1024 * 1024  # 10MB limit
                mock_settings.wordlist_timeout = 30
                with pytest.raises(WordlistDownloadError) as exc_info:
                    download_wordlist("https://example.com/wordlist.txt", temp_dir)
                assert "too large" in str(exc_info.value)

    def test_download_request_error(self, temp_dir):
        """Test download with request error."""
        with patch(
            "cloudrip.api.wordlist.requests.get",
            side_effect=requests.RequestException("Connection failed"),
        ):
            with pytest.raises(WordlistDownloadError) as exc_info:
                download_wordlist("https://example.com/wordlist.txt", temp_dir)
            assert "Failed to download" in str(exc_info.value)

    def test_download_http_error(self, temp_dir):
        """Test download with HTTP error."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")

        with patch("cloudrip.api.wordlist.requests.get", return_value=mock_response):
            with pytest.raises(WordlistDownloadError) as exc_info:
                download_wordlist("https://example.com/wordlist.txt", temp_dir)
            assert "Failed to download" in str(exc_info.value)

    def test_download_timeout(self, temp_dir):
        """Test download timeout."""
        with patch(
            "cloudrip.api.wordlist.requests.get",
            side_effect=requests.Timeout("Connection timed out"),
        ):
            with pytest.raises(WordlistDownloadError) as exc_info:
                download_wordlist("https://example.com/wordlist.txt", temp_dir)
            assert "Failed to download" in str(exc_info.value)


class TestDownloadWordlists:
    """Tests for download_wordlists function."""

    def test_download_single_url(self):
        """Test downloading a single URL."""
        mock_response = MagicMock()
        mock_response.headers = {"Content-Length": "50"}
        mock_response.iter_content.return_value = [b"www\nmail\n"]

        with patch("cloudrip.api.wordlist.requests.get", return_value=mock_response):
            temp_dir, files = download_wordlists(["https://example.com/wordlist.txt"])
            try:
                assert len(files) == 1
                assert files[0].exists()
            finally:
                cleanup_temp_dir(temp_dir)

    def test_download_multiple_urls(self):
        """Test downloading multiple URLs."""
        mock_response = MagicMock()
        mock_response.headers = {"Content-Length": "50"}
        mock_response.iter_content.return_value = [b"www\nmail\n"]

        with patch("cloudrip.api.wordlist.requests.get", return_value=mock_response):
            urls = [
                "https://example.com/wordlist1.txt",
                "https://example.com/wordlist2.txt",
            ]
            temp_dir, files = download_wordlists(urls)
            try:
                assert len(files) == 2
                for f in files:
                    assert f.exists()
            finally:
                cleanup_temp_dir(temp_dir)

    def test_download_too_many_urls(self):
        """Test error when too many URLs provided."""
        with patch("cloudrip.api.wordlist.settings") as mock_settings:
            mock_settings.max_wordlist_urls = 3
            urls = [f"https://example.com/w{i}.txt" for i in range(5)]
            with pytest.raises(WordlistDownloadError) as exc_info:
                download_wordlists(urls)
            assert "Too many wordlist URLs" in str(exc_info.value)

    def test_download_error_cleanup(self):
        """Test that temp directory is cleaned up on error."""
        mock_response = MagicMock()
        mock_response.headers = {"Content-Length": "50"}
        mock_response.iter_content.return_value = [b"www\n"]

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                raise requests.RequestException("Failed")
            return mock_response

        with patch("cloudrip.api.wordlist.requests.get", side_effect=side_effect):
            urls = [
                "https://example.com/wordlist1.txt",
                "https://example.com/wordlist2.txt",
            ]
            with pytest.raises(WordlistDownloadError):
                download_wordlists(urls)

    def test_download_empty_list(self):
        """Test downloading empty list."""
        temp_dir, files = download_wordlists([])
        try:
            assert len(files) == 0
            assert temp_dir.exists()
        finally:
            cleanup_temp_dir(temp_dir)


class TestCleanupTempDir:
    """Tests for cleanup_temp_dir function."""

    def test_cleanup_with_files(self):
        """Test cleanup removes files and directory."""
        with tempfile.TemporaryDirectory() as parent:
            temp_dir = Path(parent) / "test_cleanup"
            temp_dir.mkdir()
            (temp_dir / "file1.txt").write_text("test")
            (temp_dir / "file2.txt").write_text("test")

            assert temp_dir.exists()
            cleanup_temp_dir(temp_dir)
            assert not temp_dir.exists()

    def test_cleanup_empty_dir(self):
        """Test cleanup on empty directory."""
        with tempfile.TemporaryDirectory() as parent:
            temp_dir = Path(parent) / "empty_dir"
            temp_dir.mkdir()

            cleanup_temp_dir(temp_dir)
            assert not temp_dir.exists()

    def test_cleanup_nonexistent_dir(self):
        """Test cleanup on nonexistent directory."""
        temp_dir = Path("/nonexistent/path/12345")
        # Should not raise
        cleanup_temp_dir(temp_dir)

    def test_cleanup_none(self):
        """Test cleanup with None."""
        # Should not raise
        cleanup_temp_dir(None)
