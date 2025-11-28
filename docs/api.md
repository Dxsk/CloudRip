# CloudRip REST API

FastAPI-based REST API for CloudRip subdomain scanning.

**Table of Contents**
- [Installation](#installation)
- [Configuration](#configuration)
- [Starting the Server](#starting-the-server)
- [Endpoints](#endpoints)
- [Examples](#examples)
- [Error Handling](#error-handling)

---

## Installation

<details>
<summary><strong>Python (pip)</strong></summary>

```bash
pip install -r requirements/api.txt
```

</details>

<details>
<summary><strong>Container (Podman/Docker)</strong></summary>

```bash
# Build image
podman build -t cloudrip .

# Run container
podman run -d -p 8000:8000 --name cloudrip-api cloudrip

# With custom config
podman run -d -p 8080:8080 \
  -e CLOUDRIP_PORT=8080 \
  -e CLOUDRIP_WORKERS=4 \
  --name cloudrip-api \
  cloudrip

# View logs
podman logs -f cloudrip-api

# Stop
podman stop cloudrip-api && podman rm cloudrip-api
```

See [Container Deployment](container.md) for more options.

</details>

---

## Configuration

The API can be configured via environment variables or a `.env` file:

```bash
cp .env.example .env
```

<details>
<summary><strong>Server Settings</strong></summary>

| Variable | Default | Description |
|----------|---------|-------------|
| `CLOUDRIP_HOST` | `127.0.0.1` | Host to bind to |
| `CLOUDRIP_PORT` | `8000` | Port to bind to |
| `CLOUDRIP_RELOAD` | `false` | Enable auto-reload |
| `CLOUDRIP_WORKERS` | `1` | Number of workers |
| `CLOUDRIP_CORS_ORIGINS` | `*` | Allowed CORS origins (comma-separated) |

</details>

<details>
<summary><strong>Scanning Limits</strong></summary>

| Variable | Default | Description |
|----------|---------|-------------|
| `CLOUDRIP_MAX_BATCH_DOMAINS` | `100` | Max domains per batch request |
| `CLOUDRIP_MAX_WORDLIST_URLS` | `5` | Max remote wordlist URLs per scan |
| `CLOUDRIP_MAX_WORDLIST_SIZE` | `10485760` | Max wordlist file size in bytes (10MB) |
| `CLOUDRIP_WORDLIST_TIMEOUT` | `30` | Wordlist download timeout in seconds |

</details>

<details>
<summary><strong>Proxy Settings</strong></summary>

| Variable | Default | Description |
|----------|---------|-------------|
| `CLOUDRIP_PROXIES` | `` | Comma-separated SOCKS proxy URLs |
| `CLOUDRIP_PROXY_ROTATE` | `true` | Enable proxy rotation |

**Proxy URL formats:**
- `socks5://host:port`
- `socks5://user:pass@host:port`
- `socks4://host:port`

</details>

---

## Starting the Server

```bash
# Default (127.0.0.1:8000)
uvicorn cloudrip.api:app

# Custom host/port
CLOUDRIP_HOST=0.0.0.0 CLOUDRIP_PORT=8080 uvicorn cloudrip.api:app

# Development mode (auto-reload)
uvicorn cloudrip.api:app --reload

# Production (multiple workers)
uvicorn cloudrip.api:app --workers 4
```

Once running, access the interactive documentation:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## Endpoints

### Health Check

Check API status and configuration.

```http
GET /api/v1/health
```

<details>
<summary><strong>Response</strong></summary>

```json
{
  "status": "ok",
  "version": "3.0.0",
  "cf_ranges_loaded": true,
  "cf_v4_count": 15,
  "cf_v6_count": 7,
  "proxy_configured": true,
  "proxy_count": 2
}
```

</details>

---

### Quick Check

Check a single domain for Cloudflare status (synchronous).

```http
POST /api/v1/check
Content-Type: application/json

{"domain": "mail.example.com"}
```

<details>
<summary><strong>Request Parameters</strong></summary>

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `domain` | string | required | Domain to check |
| `use_proxy` | bool/null | `null` | Use SOCKS proxy (`null`=auto, `true`=force, `false`=disable) |

</details>

<details>
<summary><strong>Response</strong></summary>

```json
{
  "domain": "mail.example.com",
  "ipv4": ["192.168.1.1", "104.16.1.1"],
  "ipv6": [],
  "ipv4_cloudflare": ["104.16.1.1"],
  "ipv6_cloudflare": [],
  "is_cloudflare": false,
  "has_non_cf_ip": true
}
```

</details>

---

### Batch Check

Check multiple domains at once (max 100).

```http
POST /api/v1/check/batch
Content-Type: application/json

["mail.example.com", "www.example.com", "api.example.com"]
```

<details>
<summary><strong>Response</strong></summary>

```json
[
  {
    "domain": "mail.example.com",
    "ipv4": ["192.168.1.1"],
    "ipv6": [],
    "ipv4_cloudflare": [],
    "ipv6_cloudflare": [],
    "is_cloudflare": false,
    "has_non_cf_ip": true
  },
  {
    "domain": "www.example.com",
    "ipv4": ["104.16.1.1"],
    "ipv6": [],
    "ipv4_cloudflare": ["104.16.1.1"],
    "ipv6_cloudflare": [],
    "is_cloudflare": true,
    "has_non_cf_ip": false
  }
]
```

</details>

---

### Start Scan

Start an asynchronous subdomain scan.

```http
POST /api/v1/scan
Content-Type: application/json

{
  "domain": "example.com",
  "threads": 20
}
```

<details>
<summary><strong>Request Parameters</strong></summary>

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `domain` | string | required | Target domain to scan |
| `wordlists` | array | `["dom.txt"]` | Local wordlist file paths |
| `wordlist_urls` | array | `[]` | URLs to download wordlists from |
| `threads` | int | `10` | Number of threads (1-100) |
| `include_root` | bool | `true` | Check root domain first |
| `use_proxy` | bool/null | `null` | Use SOCKS proxy |

</details>

<details>
<summary><strong>Remote Wordlists</strong></summary>

The API can download wordlists from remote URLs:

```json
{
  "domain": "example.com",
  "wordlist_urls": [
    "https://raw.githubusercontent.com/danielmiessler/SecLists/master/Discovery/DNS/subdomains-top1million-5000.txt"
  ]
}
```

**Behavior:**
- Downloaded temporarily before scan starts
- Cleaned up automatically after scan completes
- Size limit: 10MB per file (configurable)
- URL limit: 5 per scan (configurable)

**Security:** Private/local IPs are blocked (localhost, 127.x, 10.x, 192.168.x, etc.)

</details>

<details>
<summary><strong>SOCKS Proxy</strong></summary>

When proxies are configured via `CLOUDRIP_PROXIES`, DNS queries are tunneled through SOCKS4/5 proxies.

**Use cases:**
- Avoid rate limits from your IP
- Anonymize scan source
- Bypass network restrictions

**Proxy behavior:**
| Value | Behavior |
|-------|----------|
| `null` (default) | Auto: uses proxy if configured |
| `true` | Force proxy (fails if not configured) |
| `false` | Disable proxy for this request |

</details>

<details>
<summary><strong>Response</strong></summary>

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "domain": "example.com",
  "created_at": "2025-11-28T12:00:00Z",
  "started_at": null,
  "completed_at": null,
  "progress": 0,
  "total": 0,
  "report": null,
  "error": null
}
```

</details>

---

### Get Scan Status

Get the status and results of a scan job.

```http
GET /api/v1/scan/{job_id}
```

<details>
<summary><strong>Response (running)</strong></summary>

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "domain": "example.com",
  "created_at": "2025-11-28T12:00:00Z",
  "started_at": "2025-11-28T12:00:01Z",
  "completed_at": null,
  "progress": 150,
  "total": 600,
  "report": null,
  "error": null
}
```

</details>

<details>
<summary><strong>Response (completed)</strong></summary>

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "domain": "example.com",
  "created_at": "2025-11-28T12:00:00Z",
  "started_at": "2025-11-28T12:00:01Z",
  "completed_at": "2025-11-28T12:05:30Z",
  "progress": 601,
  "total": 601,
  "report": {
    "target_domain": "example.com",
    "scan_date": "2025-11-28T12:00:01Z",
    "total_checked": 601,
    "summary": {
      "found": 5,
      "cloudflare": 42,
      "not_found": 554,
      "errors": 0
    },
    "results": {
      "found": [
        {
          "domain": "mail.example.com",
          "ipv4": ["192.168.1.1"],
          "ipv6": [],
          "status": "found",
          "ipv4_cloudflare": [],
          "ipv6_cloudflare": [],
          "error": null
        }
      ],
      "cloudflare": [...],
      "not_found": [...],
      "errors": []
    }
  },
  "error": null
}
```

</details>

---

### Cancel Scan

Cancel a running scan job.

```http
DELETE /api/v1/scan/{job_id}
```

<details>
<summary><strong>Response</strong></summary>

```json
{
  "status": "cancelled",
  "job_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

</details>

---

### List Scans

List all scan jobs with optional filtering.

```http
GET /api/v1/scans?limit=50&offset=0&status=running
```

<details>
<summary><strong>Query Parameters</strong></summary>

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | `50` | Max jobs to return |
| `offset` | int | `0` | Jobs to skip |
| `status` | string | - | Filter: `pending`, `running`, `completed`, `failed`, `cancelled` |

</details>

<details>
<summary><strong>Response</strong></summary>

```json
{
  "jobs": [
    {
      "job_id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "running",
      "domain": "example.com",
      "progress": 150,
      "total": 600
    }
  ],
  "total": 1
}
```

</details>

---

### Clear Completed Scans

Clear all completed/failed/cancelled jobs from memory.

```http
DELETE /api/v1/scans/completed
```

<details>
<summary><strong>Response</strong></summary>

```json
{
  "cleared": 5
}
```

</details>

---

## Status Values

| Status | Description |
|--------|-------------|
| `pending` | Job created, waiting to start |
| `running` | Scan in progress |
| `completed` | Scan finished successfully |
| `failed` | Scan encountered an error |
| `cancelled` | Scan was cancelled by user |

---

## Examples

### cURL

<details>
<summary><strong>Quick Check</strong></summary>

```bash
curl -X POST http://localhost:8000/api/v1/check \
  -H "Content-Type: application/json" \
  -d '{"domain": "mail.example.com"}'
```

</details>

<details>
<summary><strong>Start Scan</strong></summary>

```bash
curl -X POST http://localhost:8000/api/v1/scan \
  -H "Content-Type: application/json" \
  -d '{"domain": "example.com", "threads": 20}'
```

</details>

<details>
<summary><strong>Start Scan with Remote Wordlist</strong></summary>

```bash
curl -X POST http://localhost:8000/api/v1/scan \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "example.com",
    "wordlist_urls": ["https://raw.githubusercontent.com/user/repo/main/subdomains.txt"],
    "threads": 20
  }'
```

</details>

<details>
<summary><strong>Quick Check with Proxy</strong></summary>

```bash
curl -X POST http://localhost:8000/api/v1/check \
  -H "Content-Type: application/json" \
  -d '{"domain": "mail.example.com", "use_proxy": true}'
```

</details>

<details>
<summary><strong>Check Scan Status</strong></summary>

```bash
curl http://localhost:8000/api/v1/scan/550e8400-e29b-41d4-a716-446655440000
```

</details>

<details>
<summary><strong>Poll Until Complete (bash script)</strong></summary>

```bash
#!/bin/bash
JOB_ID="$1"

while true; do
  STATUS=$(curl -s "http://localhost:8000/api/v1/scan/$JOB_ID" | jq -r '.status')
  echo "Status: $STATUS"

  if [[ "$STATUS" == "completed" ]] || [[ "$STATUS" == "failed" ]]; then
    curl -s "http://localhost:8000/api/v1/scan/$JOB_ID" | jq '.report'
    break
  fi

  sleep 2
done
```

</details>

### Python

<details>
<summary><strong>Using requests (sync)</strong></summary>

```python
import requests
import time

BASE_URL = "http://localhost:8000/api/v1"

# Quick check
response = requests.post(f"{BASE_URL}/check", json={"domain": "mail.example.com"})
result = response.json()
print(f"Is Cloudflare: {result['is_cloudflare']}")

# Start scan
response = requests.post(f"{BASE_URL}/scan", json={
    "domain": "example.com",
    "threads": 20
})
job = response.json()
job_id = job["job_id"]
print(f"Started job: {job_id}")

# Poll for completion
while True:
    response = requests.get(f"{BASE_URL}/scan/{job_id}")
    job = response.json()
    print(f"Progress: {job['progress']}/{job['total']}")

    if job["status"] in ("completed", "failed"):
        break

    time.sleep(2)

# Get results
if job["status"] == "completed":
    report = job["report"]
    print(f"\nFound {report['summary']['found']} domains with exposed IPs")

    for result in report["results"]["found"]:
        print(f"  {result['domain']}: {result['ipv4']}")
```

</details>

<details>
<summary><strong>Using httpx (async)</strong></summary>

```python
import asyncio
import httpx

BASE_URL = "http://localhost:8000/api/v1"

async def scan_domain(domain: str):
    async with httpx.AsyncClient() as client:
        # Start scan
        response = await client.post(f"{BASE_URL}/scan", json={
            "domain": domain,
            "threads": 20
        })
        job = response.json()
        job_id = job["job_id"]

        # Wait for completion
        while True:
            response = await client.get(f"{BASE_URL}/scan/{job_id}")
            job = response.json()

            if job["status"] == "completed":
                return job["report"]
            elif job["status"] == "failed":
                raise Exception(job["error"])

            await asyncio.sleep(2)

# Run
report = asyncio.run(scan_domain("example.com"))
print(report)
```

</details>

---

## Error Handling

All error responses follow this format:

```json
{
  "detail": "Error message here"
}
```

| Status Code | Description |
|-------------|-------------|
| 400 | Bad request (e.g., too many domains in batch) |
| 404 | Resource not found (e.g., invalid job ID) |
| 500 | Internal server error |

---

## See Also

- [CLI Usage](cli.md) - Command-line interface
- [Library Usage](library.md) - Use CloudRip as a Python library
- [Container Deployment](container.md) - Deploy with Podman/Docker
