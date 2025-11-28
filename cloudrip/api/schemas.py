"""Pydantic schemas for the CloudRip API."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class OutputFormatEnum(str, Enum):
    """Output format options."""

    NORMAL = "normal"
    JSON = "json"
    YAML = "yaml"
    CSV = "csv"


class ScanRequest(BaseModel):
    """Request to start a new scan."""

    domain: str = Field(..., description="Target domain to scan")
    wordlists: list[str] = Field(
        default=["dom.txt"],
        description="List of wordlist file paths",
    )
    wordlist_urls: list[str] = Field(
        default=[],
        description="List of URLs to download wordlists from (temporary)",
    )
    threads: int = Field(default=10, ge=1, le=100, description="Number of threads")
    include_root: bool = Field(default=True, description="Check root domain first")
    use_proxy: Optional[bool] = Field(
        default=None,
        description="Use SOCKS proxy (None=auto based on config)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "domain": "example.com",
                "threads": 20,
                "wordlist_urls": ["https://example.com/subdomains.txt"],
            }
        }
    }


class ScanStatus(str, Enum):
    """Scan job status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ResolveResultResponse(BaseModel):
    """Single domain resolution result."""

    domain: str
    ipv4: list[str] = []
    ipv6: list[str] = []
    status: str
    ipv4_cloudflare: list[str] = []
    ipv6_cloudflare: list[str] = []
    error: Optional[str] = None

    @property
    def ipv4_non_cf(self) -> list[str]:
        return [ip for ip in self.ipv4 if ip not in self.ipv4_cloudflare]

    @property
    def ipv6_non_cf(self) -> list[str]:
        return [ip for ip in self.ipv6 if ip not in self.ipv6_cloudflare]


class ScanSummary(BaseModel):
    """Summary statistics for a scan."""

    found: int = 0
    cloudflare: int = 0
    not_found: int = 0
    errors: int = 0


class ScanReportResponse(BaseModel):
    """Complete scan report response."""

    target_domain: str
    scan_date: str
    total_checked: int = 0
    summary: ScanSummary
    results: dict[str, list[ResolveResultResponse]]


class ScanJobResponse(BaseModel):
    """Response for a scan job."""

    job_id: str
    status: ScanStatus
    domain: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: int = 0
    total: int = 0
    report: Optional[ScanReportResponse] = None
    error: Optional[str] = None


class ScanJobListResponse(BaseModel):
    """List of scan jobs."""

    jobs: list[ScanJobResponse]
    total: int


class QuickScanRequest(BaseModel):
    """Request for a quick single-domain check."""

    domain: str = Field(
        ..., description="Full domain to check (e.g., mail.example.com)"
    )
    use_proxy: Optional[bool] = Field(
        default=None,
        description="Use SOCKS proxy (None=auto based on config)",
    )


class QuickScanResponse(BaseModel):
    """Response for a quick single-domain check."""

    domain: str
    ipv4: list[str] = []
    ipv6: list[str] = []
    ipv4_cloudflare: list[str] = []
    ipv6_cloudflare: list[str] = []
    is_cloudflare: bool
    has_non_cf_ip: bool


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    version: str = "3.0.0"
    cf_ranges_loaded: bool = False
    cf_v4_count: int = 0
    cf_v6_count: int = 0
    proxy_configured: bool = False
    proxy_count: int = 0
