"""API routes for CloudRip."""

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException

from ..core.cloudflare import CloudflareIPRanges
from ..core.models import ResolveResult
from ..core.proxy import ProxyManager, parse_proxy_list
from ..core.resolver import DNSResolver
from ..core.scanner import CloudRipScanner
from .schemas import (
    HealthResponse,
    QuickScanRequest,
    QuickScanResponse,
    ResolveResultResponse,
    ScanJobListResponse,
    ScanJobResponse,
    ScanReportResponse,
    ScanRequest,
    ScanStatus,
    ScanSummary,
)
from .settings import settings
from .wordlist import WordlistDownloadError, cleanup_temp_dir, download_wordlists

router = APIRouter()

# Global state for scan jobs and shared CF ranges
_scan_jobs: Dict[str, dict] = {}
_cf_ranges: CloudflareIPRanges | None = None
_proxy_manager: ProxyManager | None = None


def get_cf_ranges() -> CloudflareIPRanges:
    """Get or create shared Cloudflare IP ranges instance."""
    global _cf_ranges
    if _cf_ranges is None:
        _cf_ranges = CloudflareIPRanges()
        _cf_ranges.load()
    return _cf_ranges


def get_proxy_manager() -> ProxyManager:
    """Get or create shared proxy manager instance."""
    global _proxy_manager
    if _proxy_manager is None:
        proxies = parse_proxy_list(settings.proxies)
        _proxy_manager = ProxyManager(proxies, rotate=settings.proxy_rotate)
    return _proxy_manager


def should_use_proxy(use_proxy: Optional[bool]) -> bool:
    """Determine if proxy should be used based on request and config.

    Args:
        use_proxy: Request parameter (None=auto, True=force, False=disable)

    Returns:
        True if proxy should be used
    """
    if use_proxy is not None:
        return use_proxy and settings.has_proxies
    # Auto: use proxy if configured
    return settings.has_proxies


def _result_to_response(result: ResolveResult) -> ResolveResultResponse:
    """Convert ResolveResult to API response."""
    return ResolveResultResponse(
        domain=result.domain,
        ipv4=result.ipv4,
        ipv6=result.ipv6,
        status=result.status,
        ipv4_cloudflare=result.ipv4_cloudflare,
        ipv6_cloudflare=result.ipv6_cloudflare,
        error=result.error,
    )


def _run_scan_job(job_id: str, request: ScanRequest) -> None:
    """Run a scan job in background."""
    job = _scan_jobs[job_id]
    job["status"] = ScanStatus.RUNNING
    job["started_at"] = datetime.now(timezone.utc)

    temp_dir: Optional[Path] = None

    try:
        all_wordlists = list(request.wordlists)
        if request.wordlist_urls:
            temp_dir, downloaded_files = download_wordlists(request.wordlist_urls)
            all_wordlists.extend(str(f) for f in downloaded_files)

        proxy_mgr = get_proxy_manager() if should_use_proxy(request.use_proxy) else None

        scanner = CloudRipScanner(
            domain=request.domain,
            threads=request.threads,
            proxy_manager=proxy_mgr,
        )
        scanner.cf_ranges = get_cf_ranges()

        subdomains = scanner.load_wordlists(all_wordlists)
        job["total"] = len(subdomains) + (1 if request.include_root else 0)

        def on_progress(completed: int, total: int) -> None:
            job["progress"] = completed + (1 if request.include_root else 0)

        scanner.set_callbacks(on_progress=on_progress)

        report = scanner.scan(subdomains, include_root=request.include_root)

        job["report"] = ScanReportResponse(
            target_domain=report.target_domain,
            scan_date=report.scan_date,
            total_checked=report.total_checked,
            summary=ScanSummary(
                found=len(report.found),
                cloudflare=len(report.cloudflare),
                not_found=len(report.not_found),
                errors=len(report.errors),
            ),
            results={
                "found": [_result_to_response(r) for r in report.found],
                "cloudflare": [_result_to_response(r) for r in report.cloudflare],
                "not_found": [_result_to_response(r) for r in report.not_found],
                "errors": [_result_to_response(r) for r in report.errors],
            },
        )

        job["status"] = ScanStatus.COMPLETED
        job["progress"] = job["total"]

    except WordlistDownloadError as e:
        job["status"] = ScanStatus.FAILED
        job["error"] = f"Wordlist download error: {e}"

    except Exception as e:
        job["status"] = ScanStatus.FAILED
        job["error"] = str(e)

    finally:
        job["completed_at"] = datetime.now(timezone.utc)
        if temp_dir:
            cleanup_temp_dir(temp_dir)


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """Check API health and Cloudflare ranges status."""
    cf = get_cf_ranges()
    v4_count, v6_count = cf.range_count
    proxy_mgr = get_proxy_manager()

    return HealthResponse(
        status="ok",
        version="3.0.0",
        cf_ranges_loaded=cf.is_loaded,
        cf_v4_count=v4_count,
        cf_v6_count=v6_count,
        proxy_configured=proxy_mgr.has_proxies,
        proxy_count=proxy_mgr.proxy_count,
    )


@router.post("/scan", response_model=ScanJobResponse, tags=["Scanning"])
async def start_scan(
    request: ScanRequest, background_tasks: BackgroundTasks
) -> ScanJobResponse:
    """Start a new subdomain scan.

    Returns a job ID that can be used to check progress and retrieve results.
    """
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    job = {
        "job_id": job_id,
        "status": ScanStatus.PENDING,
        "domain": request.domain,
        "created_at": now,
        "started_at": None,
        "completed_at": None,
        "progress": 0,
        "total": 0,
        "report": None,
        "error": None,
    }

    _scan_jobs[job_id] = job

    # Start scan in background
    background_tasks.add_task(_run_scan_job, job_id, request)

    return ScanJobResponse(**job)


@router.get("/scan/{job_id}", response_model=ScanJobResponse, tags=["Scanning"])
async def get_scan_status(job_id: str) -> ScanJobResponse:
    """Get the status and results of a scan job."""
    if job_id not in _scan_jobs:
        raise HTTPException(status_code=404, detail="Scan job not found")

    return ScanJobResponse(**_scan_jobs[job_id])


@router.delete("/scan/{job_id}", tags=["Scanning"])
async def cancel_scan(job_id: str) -> dict:
    """Cancel a running scan job."""
    if job_id not in _scan_jobs:
        raise HTTPException(status_code=404, detail="Scan job not found")

    job = _scan_jobs[job_id]
    if job["status"] == ScanStatus.RUNNING:
        job["status"] = ScanStatus.CANCELLED
        job["completed_at"] = datetime.now(timezone.utc)

    return {"status": "cancelled", "job_id": job_id}


@router.get("/scans", response_model=ScanJobListResponse, tags=["Scanning"])
async def list_scans(
    limit: int = 50,
    offset: int = 0,
    status: ScanStatus | None = None,
) -> ScanJobListResponse:
    """List all scan jobs with optional filtering."""
    jobs = list(_scan_jobs.values())

    # Filter by status if provided
    if status:
        jobs = [j for j in jobs if j["status"] == status]

    # Sort by created_at descending
    jobs.sort(key=lambda x: x["created_at"], reverse=True)

    total = len(jobs)
    jobs = jobs[offset : offset + limit]

    return ScanJobListResponse(
        jobs=[ScanJobResponse(**j) for j in jobs],
        total=total,
    )


@router.post("/check", response_model=QuickScanResponse, tags=["Quick Check"])
async def quick_check(request: QuickScanRequest) -> QuickScanResponse:
    """Quick check a single domain for Cloudflare status.

    This is a synchronous endpoint for quickly checking if a domain
    is behind Cloudflare without starting a full scan job.
    """
    cf_ranges = get_cf_ranges()
    proxy_mgr = get_proxy_manager() if should_use_proxy(request.use_proxy) else None
    resolver = DNSResolver(cf_ranges, proxy_manager=proxy_mgr)

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None, resolver.resolve_domain, request.domain, None
    )

    return QuickScanResponse(
        domain=result.domain,
        ipv4=result.ipv4,
        ipv6=result.ipv6,
        ipv4_cloudflare=result.ipv4_cloudflare,
        ipv6_cloudflare=result.ipv6_cloudflare,
        is_cloudflare=result.all_cloudflare,
        has_non_cf_ip=result.has_non_cf_ip,
    )


@router.post(
    "/check/batch", response_model=list[QuickScanResponse], tags=["Quick Check"]
)
async def batch_check(domains: list[str]) -> list[QuickScanResponse]:
    """Check multiple domains for Cloudflare status.

    Maximum domains per request is configurable via CLOUDRIP_MAX_BATCH_DOMAINS.
    """
    if len(domains) > settings.max_batch_domains:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {settings.max_batch_domains} domains per batch request",
        )

    cf_ranges = get_cf_ranges()
    resolver = DNSResolver(cf_ranges)

    loop = asyncio.get_event_loop()

    async def check_domain(domain: str) -> QuickScanResponse:
        result = await loop.run_in_executor(None, resolver.resolve_domain, domain, None)
        return QuickScanResponse(
            domain=result.domain,
            ipv4=result.ipv4,
            ipv6=result.ipv6,
            ipv4_cloudflare=result.ipv4_cloudflare,
            ipv6_cloudflare=result.ipv6_cloudflare,
            is_cloudflare=result.all_cloudflare,
            has_non_cf_ip=result.has_non_cf_ip,
        )

    results = await asyncio.gather(*[check_domain(d) for d in domains])
    return list(results)


@router.delete("/scans/completed", tags=["Scanning"])
async def clear_completed_scans() -> dict:
    """Clear all completed/failed/cancelled scan jobs from memory."""
    to_remove = [
        job_id
        for job_id, job in _scan_jobs.items()
        if job["status"]
        in (ScanStatus.COMPLETED, ScanStatus.FAILED, ScanStatus.CANCELLED)
    ]

    for job_id in to_remove:
        del _scan_jobs[job_id]

    return {"cleared": len(to_remove)}
