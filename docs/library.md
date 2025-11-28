# CloudRip Library

Use CloudRip as a Python library for programmatic subdomain scanning and Cloudflare IP detection.

**Table of Contents**
- [Installation](#installation)
- [Quick Start](#quick-start)
- [API Reference](#api-reference)
- [Examples](#examples)

---

## Installation

```bash
pip install -r requirements.txt
```

---

## Quick Start

```python
from cloudrip import CloudRipScanner

# Create scanner
scanner = CloudRipScanner("example.com")

# Load Cloudflare IP ranges
scanner.load_cf_ranges()

# Scan from wordlist
report = scanner.scan_from_wordlists(["dom.txt"])

# Print found IPs (not behind Cloudflare)
for result in report.found:
    print(f"{result.domain}: {result.ipv4_non_cf}")
```

---

## API Reference

### CloudRipScanner

Main scanner class for subdomain enumeration.

```python
from cloudrip import CloudRipScanner

scanner = CloudRipScanner(
    domain="example.com",   # Target domain
    threads=10,             # Concurrent threads (default: 10)
    rate_limit=0.05         # Delay between requests (default: 0.05s)
)
```

<details>
<summary><strong>Methods</strong></summary>

**`load_cf_ranges()`** - Load Cloudflare IP ranges
```python
v4_from_api, v6_from_api = scanner.load_cf_ranges()
# Returns tuple of booleans indicating if ranges were fetched from API
```

**`load_wordlist(path)`** - Load a single wordlist
```python
subdomains = scanner.load_wordlist("wordlist.txt")
# Returns set of subdomain strings
```

**`load_wordlists(paths)`** - Load and merge multiple wordlists
```python
subdomains = scanner.load_wordlists(["common.txt", "dns.txt"])
# Returns sorted, deduplicated list
```

**`scan(subdomains, include_root=True)`** - Execute scan
```python
report = scanner.scan(["www", "mail", "api"], include_root=True)
```

**`scan_from_wordlists(paths, include_root=True)`** - Load wordlists and scan
```python
report = scanner.scan_from_wordlists(["dom.txt"])
```

**`set_callbacks(on_result, on_progress)`** - Set progress callbacks
```python
def on_result(result):
    print(f"Checked: {result.domain}")

def on_progress(completed, total):
    print(f"Progress: {completed}/{total}")

scanner.set_callbacks(on_result=on_result, on_progress=on_progress)
```

**`stop()`** - Request scan to stop gracefully
```python
scanner.stop()
```

</details>

---

### ResolveResult

Result of a DNS resolution attempt.

```python
from cloudrip import ResolveResult

result = ResolveResult(
    domain="mail.example.com",
    ipv4=["192.168.1.1", "104.16.1.1"],
    ipv6=["2001:db8::1"],
    status="found",  # "found", "cloudflare", "not_found", "error"
    ipv4_cloudflare=["104.16.1.1"],
    ipv6_cloudflare=[],
    error=None
)
```

<details>
<summary><strong>Properties</strong></summary>

```python
# Get IPs NOT behind Cloudflare
result.ipv4_non_cf  # ["192.168.1.1"]
result.ipv6_non_cf  # ["2001:db8::1"]

# Check if any IP is exposed
result.has_non_cf_ip  # True

# Check if all IPs are Cloudflare
result.all_cloudflare  # False

# Convert to dictionary
result.to_dict()
```

</details>

---

### ScanReport

Complete scan results.

```python
from cloudrip import ScanReport

report = ScanReport(target_domain="example.com")
```

<details>
<summary><strong>Attributes</strong></summary>

```python
# Access results by category
report.found       # List of ResolveResult with non-CF IPs
report.cloudflare  # List of ResolveResult fully behind CF
report.not_found   # List of domains with no DNS record
report.errors      # List of domains with resolution errors

# Metadata
report.target_domain  # "example.com"
report.scan_date      # ISO format timestamp
report.total_checked  # Total domains scanned

# Convert to dictionary
report.to_dict()
```

</details>

---

### ReportWriter

Export scan results to various formats.

```python
from cloudrip import ReportWriter, OutputFormat

# Write to file
ReportWriter.write_to_file(report, "results.json", OutputFormat.JSON)
ReportWriter.write_to_file(report, "results.csv", OutputFormat.CSV)
ReportWriter.write_to_file(report, "results.yaml", OutputFormat.YAML)
ReportWriter.write_to_file(report, "results.txt", OutputFormat.NORMAL)

# Write to stream
import sys
ReportWriter.write(report, sys.stdout, OutputFormat.NORMAL)
```

---

### CloudflareIPRanges

Direct access to Cloudflare IP range checking.

```python
from cloudrip import CloudflareIPRanges

cf = CloudflareIPRanges(timeout=10)
cf.load()

# Check if IP is Cloudflare
cf.is_cloudflare_ip("104.16.1.1")  # True
cf.is_cloudflare_ip("192.168.1.1")  # False

# Get range info
v4_count, v6_count = cf.range_count
v4_fallback, v6_fallback = cf.used_fallback
```

---

### DNSResolver

Low-level DNS resolution with Cloudflare classification.

```python
from cloudrip import DNSResolver, CloudflareIPRanges

cf_ranges = CloudflareIPRanges()
cf_ranges.load()

resolver = DNSResolver(cf_ranges)

# Resolve full domain
result = resolver.resolve_domain("mail.example.com")

# Resolve subdomain of base domain
result = resolver.resolve_domain("mail", "example.com")
```

---

## Examples

### Basic Scan with Progress

<details>
<summary><strong>Show code</strong></summary>

```python
from cloudrip import CloudRipScanner

def on_result(result):
    if result.status == "found":
        print(f"[FOUND] {result.domain} -> {result.ipv4_non_cf}")
    elif result.status == "cloudflare":
        print(f"[CF] {result.domain}")

def on_progress(done, total):
    print(f"\rProgress: {done}/{total} ({100*done//total}%)", end="")

scanner = CloudRipScanner("example.com", threads=20)
scanner.load_cf_ranges()
scanner.set_callbacks(on_result=on_result, on_progress=on_progress)

report = scanner.scan_from_wordlists(["dom.txt"])

print(f"\n\nScan complete!")
print(f"Found {len(report.found)} domains with exposed IPs")
```

</details>

---

### Export to Multiple Formats

<details>
<summary><strong>Show code</strong></summary>

```python
from cloudrip import CloudRipScanner, ReportWriter, OutputFormat

scanner = CloudRipScanner("example.com")
scanner.load_cf_ranges()
report = scanner.scan_from_wordlists(["dom.txt"])

# Export to all formats
ReportWriter.write_to_file(report, "results.json", OutputFormat.JSON)
ReportWriter.write_to_file(report, "results.csv", OutputFormat.CSV)
ReportWriter.write_to_file(report, "results.yaml", OutputFormat.YAML)
ReportWriter.write_to_file(report, "results.txt", OutputFormat.NORMAL)
```

</details>

---

### Check Single Domain

<details>
<summary><strong>Show code</strong></summary>

```python
from cloudrip import CloudflareIPRanges, DNSResolver

cf = CloudflareIPRanges()
cf.load()

resolver = DNSResolver(cf)
result = resolver.resolve_domain("example.com")

print(f"Domain: {result.domain}")
print(f"IPv4: {result.ipv4}")
print(f"IPv4 (CF): {result.ipv4_cloudflare}")
print(f"Status: {result.status}")
```

</details>

---

### Graceful Shutdown

<details>
<summary><strong>Show code</strong></summary>

```python
import signal
from cloudrip import CloudRipScanner

scanner = CloudRipScanner("example.com")

def signal_handler(sig, frame):
    print("\nStopping scan...")
    scanner.stop()

signal.signal(signal.SIGINT, signal_handler)

scanner.load_cf_ranges()
report = scanner.scan_from_wordlists(["dom.txt"])

# Report will contain partial results if stopped early
print(f"Scanned {report.total_checked} domains before stopping")
```

</details>

---

### Custom Subdomain List

<details>
<summary><strong>Show code</strong></summary>

```python
from cloudrip import CloudRipScanner

scanner = CloudRipScanner("example.com")
scanner.load_cf_ranges()

# Use custom list instead of wordlist file
subdomains = ["www", "mail", "ftp", "api", "dev", "staging", "admin"]
report = scanner.scan(subdomains, include_root=True)

for result in report.found:
    print(f"{result.domain}: {result.ipv4_non_cf}")
```

</details>

---

## See Also

- [CLI Usage](cli.md) - Command-line interface
- [REST API](api.md) - Run CloudRip as an API server
- [Container Deployment](container.md) - Deploy with Podman/Docker
