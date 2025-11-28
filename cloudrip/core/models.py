"""Data models for CloudRip."""

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum


class OutputFormat(Enum):
    """Supported output formats."""

    NORMAL = "normal"
    JSON = "json"
    YAML = "yaml"
    CSV = "csv"


@dataclass
class ResolveResult:
    """Result of a DNS resolution attempt."""

    domain: str
    ipv4: list[str] = field(default_factory=list)
    ipv6: list[str] = field(default_factory=list)
    status: str = "unknown"
    ipv4_cloudflare: list[str] = field(default_factory=list)
    ipv6_cloudflare: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def ipv4_non_cf(self) -> list[str]:
        """Get IPv4 addresses not behind Cloudflare."""
        return [ip for ip in self.ipv4 if ip not in self.ipv4_cloudflare]

    @property
    def ipv6_non_cf(self) -> list[str]:
        """Get IPv6 addresses not behind Cloudflare."""
        return [ip for ip in self.ipv6 if ip not in self.ipv6_cloudflare]

    @property
    def has_non_cf_ip(self) -> bool:
        """Check if at least one IP is not behind Cloudflare."""
        return bool(self.ipv4_non_cf or self.ipv6_non_cf)

    @property
    def all_cloudflare(self) -> bool:
        """Check if all resolved IPs are Cloudflare."""
        if not self.ipv4 and not self.ipv6:
            return False
        all_v4_cf = (
            all(ip in self.ipv4_cloudflare for ip in self.ipv4) if self.ipv4 else True
        )
        all_v6_cf = (
            all(ip in self.ipv6_cloudflare for ip in self.ipv6) if self.ipv6 else True
        )
        return all_v4_cf and all_v6_cf

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class ScanReport:
    """Complete scan report."""

    target_domain: str
    scan_date: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    total_checked: int = 0
    found: list[ResolveResult] = field(default_factory=list)
    cloudflare: list[ResolveResult] = field(default_factory=list)
    not_found: list[ResolveResult] = field(default_factory=list)
    errors: list[ResolveResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert report to dictionary."""
        return {
            "target_domain": self.target_domain,
            "scan_date": self.scan_date,
            "total_checked": self.total_checked,
            "summary": {
                "found": len(self.found),
                "cloudflare": len(self.cloudflare),
                "not_found": len(self.not_found),
                "errors": len(self.errors),
            },
            "results": {
                "found": [asdict(r) for r in self.found],
                "cloudflare": [asdict(r) for r in self.cloudflare],
                "not_found": [asdict(r) for r in self.not_found],
                "errors": [asdict(r) for r in self.errors],
            },
        }
