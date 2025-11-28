"""Remote wordlist download utility."""

import tempfile
from pathlib import Path
from typing import List, Tuple
from urllib.parse import urlparse

import requests

from .settings import settings


class WordlistDownloadError(Exception):
    """Error downloading a wordlist."""

    pass


def validate_url(url: str) -> bool:
    """Validate that a URL is safe to download from.

    Args:
        url: URL to validate

    Returns:
        True if URL is valid and safe
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        if not parsed.netloc:
            return False
        # no internal IPs
        hostname = parsed.hostname or ""
        blocked = (
            "localhost",
            "127.",
            "10.",
            "192.168.",
            "172.16.",
            "172.17.",
            "172.18.",
            "172.19.",
            "172.20.",
            "172.21.",
            "172.22.",
            "172.23.",
            "172.24.",
            "172.25.",
            "172.26.",
            "172.27.",
            "172.28.",
            "172.29.",
            "172.30.",
            "172.31.",
            "169.254.",
            "0.0.0.0",
            "::1",
            "[::1]",
        )
        if any(hostname.startswith(b) or hostname == b for b in blocked):
            return False
        return True
    except Exception:
        return False


def download_wordlist(url: str, temp_dir: Path) -> Path:
    """Download a wordlist from a URL to a temporary file.

    Args:
        url: URL to download from
        temp_dir: Directory to store temporary file

    Returns:
        Path to downloaded file

    Raises:
        WordlistDownloadError: If download fails
    """
    if not validate_url(url):
        raise WordlistDownloadError(f"Invalid or blocked URL: {url}")

    try:
        response = requests.get(
            url,
            timeout=settings.wordlist_timeout,
            stream=True,
            headers={"User-Agent": "CloudRip/3.0.0"},
        )
        response.raise_for_status()

        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > settings.max_wordlist_size:
            raise WordlistDownloadError(
                f"Wordlist too large: {int(content_length)} bytes "
                f"(max: {settings.max_wordlist_size})"
            )

        downloaded = 0
        temp_file = temp_dir / f"wordlist_{hash(url) & 0xFFFFFFFF}.txt"

        with open(temp_file, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                downloaded += len(chunk)
                if downloaded > settings.max_wordlist_size:
                    temp_file.unlink(missing_ok=True)
                    raise WordlistDownloadError(
                        f"Wordlist too large: exceeded {settings.max_wordlist_size} bytes"
                    )
                f.write(chunk)

        return temp_file

    except requests.RequestException as e:
        raise WordlistDownloadError(f"Failed to download {url}: {e}")


def download_wordlists(urls: List[str]) -> Tuple[Path, List[Path]]:
    """Download multiple wordlists to a temporary directory.

    Args:
        urls: List of URLs to download

    Returns:
        Tuple of (temp_dir, list of downloaded file paths)

    Raises:
        WordlistDownloadError: If any download fails
    """
    if len(urls) > settings.max_wordlist_urls:
        raise WordlistDownloadError(
            f"Too many wordlist URLs: {len(urls)} (max: {settings.max_wordlist_urls})"
        )

    temp_dir = Path(tempfile.mkdtemp(prefix="cloudrip_"))
    downloaded = []

    try:
        for url in urls:
            path = download_wordlist(url, temp_dir)
            downloaded.append(path)
        return temp_dir, downloaded
    except Exception:
        cleanup_temp_dir(temp_dir)
        raise


def cleanup_temp_dir(temp_dir: Path) -> None:
    """Remove temporary directory and all its contents.

    Args:
        temp_dir: Directory to remove
    """
    if temp_dir and temp_dir.exists():
        for file in temp_dir.iterdir():
            file.unlink(missing_ok=True)
        temp_dir.rmdir()
