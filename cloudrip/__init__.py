"""
CloudRip - Find real IP addresses behind Cloudflare.

Usage as a library:
    from cloudrip import CloudRipScanner, ResolveResult, ScanReport

    scanner = CloudRipScanner("example.com")
    scanner.load_cf_ranges()
    report = scanner.scan_from_wordlists(["dom.txt"])

    for result in report.found:
        print(f"{result.domain}: {result.ipv4_non_cf}")
"""

from .core.cloudflare import CloudflareIPRanges
from .core.models import OutputFormat, ResolveResult, ScanReport
from .core.resolver import DNSResolver
from .core.scanner import CloudRipScanner
from .output.writers import ReportWriter

__version__ = "3.0.0"
__all__ = [
    "CloudRipScanner",
    "CloudflareIPRanges",
    "DNSResolver",
    "ResolveResult",
    "ScanReport",
    "OutputFormat",
    "ReportWriter",
]
