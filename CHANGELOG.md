# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.0] - 2025-11-28

### Added

#### Modular Architecture
- Reorganized into `cloudrip/` package with submodules: `core/`, `output/`, `cli/`, `api/`, `utils/`
- Added Library mode - Use CloudRip as a Python package (`from cloudrip import CloudRipScanner`)
- Clean separation of concerns: core scanning logic, output formatting, CLI, and API

#### REST API (FastAPI)
- Added FastAPI-based REST API server with async scanning support
- `/api/v1/health` - Health check with Cloudflare ranges and proxy status
- `/api/v1/check` - Quick synchronous single domain check
- `/api/v1/check/batch` - Batch check multiple domains (up to 100)
- `/api/v1/scan` - Start async subdomain scan job
- `/api/v1/scan/{job_id}` - Get scan status and results
- `/api/v1/scans` - List all scan jobs with filtering
- Added Swagger UI (`/docs`) and ReDoc (`/redoc`) documentation
- Configuration via environment variables or `.env` file

#### Remote Wordlist Support (API)
- API can download wordlists from remote URLs (`wordlist_urls` parameter)
- Temporary files cleaned up automatically after scan
- Configurable size limits (default 10MB per file)
- Configurable URL count limits (default 5 URLs per scan)
- SSRF protection: blocks private/local IPs (localhost, 127.x, 10.x, 192.168.x, etc.)

#### SOCKS Proxy Support
- Added SOCKS4/5 proxy support for DNS queries
- DNS-over-TCP tunneled through SOCKS proxies for anonymity
- CLI: `-p/--proxy` flag for proxy URLs (can be specified multiple times)
- CLI: `--no-rotate` flag to disable proxy rotation
- API: `CLOUDRIP_PROXIES` environment variable (comma-separated)
- API: `CLOUDRIP_PROXY_ROTATE` environment variable
- API: `use_proxy` request parameter (null=auto, true=force, false=disable)
- Proxy rotation support for load balancing across multiple proxies
- Authentication support (`socks5://user:pass@host:port`)

#### Container Support
- Added OCI-compliant `Containerfile` for Podman/Docker
- Multi-stage build with Python 3.12 Alpine base
- Security-hardened: rootless, non-root user, minimal image
- Health check endpoint integration
- Configurable via environment variables
- Added `docs/container.md` with deployment guide
- Compose examples with Tor proxy integration

#### Testing & CI
- Added comprehensive test suite with 208 unit tests (84% coverage)
- Added pytest configuration with pytest-cov for coverage reporting
- Added proxy module tests (100% coverage on proxy module)
- Added GitHub Actions CI workflow (`.github/workflows/ci.yml`)
  - Lint job: ruff check, ruff format, mypy type checking
  - Test job: pytest on Python 3.11, 3.12, 3.13
  - Codecov integration for coverage reporting
  - Container build on develop (validation only, no push)
  - Container build & push to GitHub Container Registry (`ghcr.io`) on main/tags
  - Multi-arch builds: `linux/amd64`, `linux/arm64`
  - Automatic tagging: `latest` on main, semver on tags (v3.0.0 → 3.0.0, 3.0, 3)
- Added `pyproject.toml` with centralized tool configuration
- Replaced black + flake8 with ruff for linting and formatting
- Added mypy with strict type hint enforcement (`disallow_untyped_defs`)

#### Documentation
- Added `docs/cli.md` - CLI usage and examples
- Added `docs/library.md` - Python library integration
- Added `docs/api.md` - REST API documentation
- Added `docs/container.md` - Container deployment guide
- Added `.env.example` with all configuration options

### Fixed

#### CI Workflow
- Fixed ruff linting errors in test files (unused imports, unsorted imports, unused variables)
- Added SIM117 to ignored rules (nested `with` statements for test readability)
- Fixed mypy in CI by installing API dependencies (`requirements/api.txt`) for pydantic/fastapi type stubs

---

## [2.1.0] - 2025-11-28

### Added

#### IPv6 Support
- Added full IPv6 (AAAA record) resolution support alongside IPv4
- Added Cloudflare IPv6 IP ranges detection (7 ranges)
- Results now display both IPv4 and IPv6 addresses with individual Cloudflare status indicators

#### Multiple IPs Detection
- DNS resolution now returns ALL IPs for a domain, not just the first one
- Each IP is individually checked against Cloudflare ranges
- Output displays all IPs in list format: `v4:[ip1, ip2, ip3]`
- CSV export uses semicolon separator for multiple IPs

#### Progress Bar
- Added real-time progress bar during subdomain scanning using `tqdm`
- Shows elapsed time and estimated time remaining
- Displays live stats: found count and cloudflare count
- Automatically disabled in quiet mode (`-q`)

#### Wordlist Improvements
- Added support for comments in wordlists (lines starting with `#` are ignored)
- Empty lines are automatically skipped

#### Dynamic Cloudflare IP Ranges
- Added dynamic fetching of Cloudflare IP ranges from official API endpoints (`https://www.cloudflare.com/ips-v4` and `https://www.cloudflare.com/ips-v6`)
- Added fallback mechanism to hardcoded ranges if API is unreachable
- Added status logging indicating whether ranges were fetched from API or fallback

#### Multiple Output Formats
- Added JSON output format (`-f json`)
- Added YAML output format (`-f yaml`) with custom serializer (no external dependency)
- Added CSV output format (`-f csv`)
- Enhanced normal text output with structured report sections

#### Multiple Wordlists Support
- Added ability to specify multiple wordlist files using repeated `-w` flags
- Wordlists are automatically merged and deduplicated
- Each loaded wordlist is logged individually

#### Verbosity Controls
- Added verbose mode (`-v, --verbose`) to show all results including "not found" entries
- Added quiet mode (`-q, --quiet`) for minimal output showing only found IPs
- Implemented structured logging system with verbosity levels

#### Root Domain Check
- Added automatic checking of the root domain before subdomain enumeration

#### Scan Summary
- Added comprehensive end-of-scan summary showing:
  - Total domains checked
  - Count of found (non-Cloudflare) IPs
  - Count of Cloudflare-protected domains
  - Count of not found domains
  - Count of errors (if any)

#### Data Classes and Type Hints
- Added `ResolveResult` dataclass for structured result storage with list-based IP fields
- `ResolveResult.ipv4` and `ResolveResult.ipv6` are now `list[str]` to store multiple IPs
- `ResolveResult.ipv4_cloudflare` and `ResolveResult.ipv6_cloudflare` store which IPs are behind CF
- Added `ipv4_non_cf` and `ipv6_non_cf` properties to filter non-Cloudflare IPs
- Added `ScanReport` dataclass for complete scan reports with serialization support
- Added `CloudflareIPRanges` class for IP range management
- Added `ReportWriter` class for multi-format output handling
- Added `CloudRip` main scanner class with encapsulated state
- Added `Colors` class for terminal color constants
- Added `OutputFormat` enum for output format types
- Added comprehensive type hints throughout the codebase

### Changed

#### Architecture
- Refactored from procedural to object-oriented architecture
- Encapsulated scanner state and configuration in `CloudRip` class
- Separated concerns into dedicated classes (IP ranges, reporting, scanning)

#### Cloudflare IP Detection
- Changed from inline import of `ipaddress` module to module-level import
- Separated IPv4 and IPv6 address parsing with proper error handling using `AddressValueError`
- IP ranges are now lazily loaded on first check

#### Error Handling
- Added handling for `dns.resolver.LifetimeTimeout` exception
- Added `EOFError` handling for interrupt signal during input prompt
- Improved file encoding handling with explicit UTF-8 specification

#### Signal Handling
- Moved signal handler from global function to instance method
- Added `cancel_futures=True` to executor shutdown for cleaner interruption

#### Rate Limiting
- Reduced inter-request delay from 0.1s to 0.05s for faster scanning

#### Output Formatting
- Changed result logging to show both IPv4 and IPv6 with `[CF]` tags for Cloudflare IPs
- Added colored `[CLOUDFLARE]` status for domains behind Cloudflare
- Improved report structure with categorized sections (found, cloudflare, not_found, errors)

#### Documentation
- Added module-level docstring describing the tool's purpose
- Added docstrings to all classes and methods

### Removed

- Removed `os` module import (replaced with `pathlib.Path`)
- Removed global `stop_requested` variable (now instance attribute)
- Removed standalone color constant variables (now in `Colors` class)

### Technical Improvements

#### Code Quality
- Added shebang line (`#!/usr/bin/env python3`) for direct execution
- Added proper module structure with `__all__` implicit through class definitions
- Used `pathlib.Path` for file operations instead of `os.path`
- Used `set` for wordlist deduplication with sorted output
- Added proper encoding parameter to all file operations

#### Dependencies
- Added `requests` library for HTTP API calls
- Added `tqdm` library for progress bar
- Added `csv` module usage for CSV export
- Added `json` module for JSON serialization
- Added `datetime` with timezone support for scan timestamps
- Added `dataclasses` for structured data
- Added `enum` for type-safe enumerations

#### CLI Improvements
- Added `RawDescriptionHelpFormatter` for better help text formatting
- Added usage examples in argument parser epilog
- Improved argument descriptions and help text

## [2.0.0]

### Added

- Massive wordlist upgrade - Took dom.txt from 100 to 600+ subdomains
- Added API variants, cloud infrastructure, IoT endpoints
- Covers auth/security, payment gateways, analytics, CI/CD pipelines
- Way better geo coverage - cities and more countries
- Handles modern cloud-native and microservices setups
- Better database and service discovery hits

## [1.5.0]

### Added

- Rate limiting so you don't get blocked

### Changed

- Thread handling works better now

### Fixed

- Doesn't crash on DNS failures anymore
- Prettier output with colors

## [1.0.0]

### Added

- First drop with the core stuff
- Multi-threaded subdomain scanning
- Filters out Cloudflare IPs
- Bring your own wordlist
- Save results to file
- Basic dom.txt with ~100 entries

