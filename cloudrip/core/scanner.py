"""CloudRip scanner - core scanning logic."""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Optional

from .cloudflare import CloudflareIPRanges
from .models import ResolveResult, ScanReport
from .proxy import ProxyManager
from .resolver import DNSResolver


class CloudRipScanner:
    """Core CloudRip scanner - can be used programmatically."""

    def __init__(
        self,
        domain: str,
        threads: int = 10,
        rate_limit: float = 0.05,
        proxy_manager: Optional[ProxyManager] = None,
    ):
        self.domain = domain
        self.threads = threads
        self.rate_limit = rate_limit
        self.proxy_manager = proxy_manager

        self.cf_ranges = CloudflareIPRanges()
        self.resolver = DNSResolver(self.cf_ranges, proxy_manager=proxy_manager)
        self.report = ScanReport(target_domain=domain)
        self.stop_requested = False

        self._on_result: Optional[Callable[[ResolveResult], None]] = None
        self._on_progress: Optional[Callable[[int, int], None]] = None

    def set_callbacks(
        self,
        on_result: Optional[Callable[[ResolveResult], None]] = None,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        """Set callbacks for progress reporting.

        Args:
            on_result: Called with each ResolveResult as it completes
            on_progress: Called with (completed, total) counts
        """
        self._on_result = on_result
        self._on_progress = on_progress

    def load_cf_ranges(self) -> tuple[bool, bool]:
        """Load Cloudflare IP ranges. Returns (v4_from_api, v6_from_api)."""
        return self.cf_ranges.load()

    def load_wordlist(self, path: str | Path) -> set[str]:
        """Load subdomains from a wordlist file."""
        subdomains: set[str] = set()
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Wordlist not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    subdomains.add(stripped)

        return subdomains

    def load_wordlists(self, paths: list[str | Path]) -> list[str]:
        """Load and merge multiple wordlists."""
        subdomains: set[str] = set()

        for path in paths:
            try:
                subdomains.update(self.load_wordlist(path))
            except FileNotFoundError:
                continue

        return sorted(subdomains)

    def resolve_subdomain(self, subdomain: Optional[str] = None) -> ResolveResult:
        """Resolve a subdomain (or root domain if None)."""
        if subdomain:
            return self.resolver.resolve_domain(subdomain, self.domain)
        return self.resolver.resolve_domain(self.domain)

    def add_result(self, result: ResolveResult) -> None:
        """Categorize and store a result."""
        if result.status == "found":
            self.report.found.append(result)
        elif result.status == "cloudflare":
            self.report.cloudflare.append(result)
        elif result.status == "not_found":
            self.report.not_found.append(result)
        else:
            self.report.errors.append(result)

        self.report.total_checked += 1

        if self._on_result:
            self._on_result(result)

    def stop(self) -> None:
        """Request scan to stop."""
        self.stop_requested = True

    def scan(
        self,
        subdomains: list[str],
        include_root: bool = True,
    ) -> ScanReport:
        """Execute the scan.

        Args:
            subdomains: List of subdomains to scan
            include_root: Whether to check root domain first

        Returns:
            ScanReport with all results
        """
        self.stop_requested = False
        self.report = ScanReport(target_domain=self.domain)

        if not self.cf_ranges.is_loaded:
            self.cf_ranges.load()

        if include_root:
            root_result = self.resolve_subdomain()
            self.add_result(root_result)

        total = len(subdomains)

        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            futures = {
                executor.submit(self.resolve_subdomain, sub): sub for sub in subdomains
            }

            completed = 0
            for future in as_completed(futures):
                if self.stop_requested:
                    executor.shutdown(wait=False, cancel_futures=True)
                    break

                result = future.result()
                self.add_result(result)

                completed += 1
                if self._on_progress:
                    self._on_progress(completed, total)

                time.sleep(self.rate_limit)

        return self.report

    def scan_from_wordlists(
        self,
        wordlist_paths: list[str | Path],
        include_root: bool = True,
    ) -> ScanReport:
        """Load wordlists and execute scan.

        Args:
            wordlist_paths: Paths to wordlist files
            include_root: Whether to check root domain first

        Returns:
            ScanReport with all results
        """
        subdomains = self.load_wordlists(wordlist_paths)
        return self.scan(subdomains, include_root)
