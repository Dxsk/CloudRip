# CloudRip Container

Guide for deploying CloudRip API with Podman or Docker.

**Table of Contents**
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Custom Wordlists](#custom-wordlists)
- [Docker Compose](#docker-compose)
- [Best Practices](#best-practices)

---

## Quick Start

### Build

```bash
# Podman
podman build -t cloudrip .

# Docker
docker build -t cloudrip .
```

### Run

<details>
<summary><strong>Podman</strong></summary>

```bash
# Start the container
podman run -d -p 8000:8000 --name cloudrip-api cloudrip

# View logs
podman logs -f cloudrip-api

# Stop and remove
podman stop cloudrip-api && podman rm cloudrip-api
```

</details>

<details>
<summary><strong>Docker</strong></summary>

```bash
# Start the container
docker run -d -p 8000:8000 --name cloudrip-api cloudrip

# View logs
docker logs -f cloudrip-api

# Stop and remove
docker stop cloudrip-api && docker rm cloudrip-api
```

</details>

The API will be available at `http://localhost:8000`.

---

## Configuration

Configure via environment variables:

```bash
podman run -d -p 8080:8080 \
  -e CLOUDRIP_PORT=8080 \
  -e CLOUDRIP_WORKERS=4 \
  -e CLOUDRIP_PROXIES="socks5://proxy:1080" \
  --name cloudrip-api \
  cloudrip
```

| Variable | Default | Description |
|----------|---------|-------------|
| `CLOUDRIP_HOST` | `0.0.0.0` | Listen host |
| `CLOUDRIP_PORT` | `8000` | Listen port |
| `CLOUDRIP_WORKERS` | `1` | Number of uvicorn workers |
| `CLOUDRIP_PROXIES` | `` | SOCKS proxies (comma-separated) |
| `CLOUDRIP_PROXY_ROTATE` | `true` | Enable proxy rotation |

---

## Custom Wordlists

Four options to use custom wordlists with the container:

### Option 1: Fetch via URL (Recommended)

The API can download wordlists from URLs. No container modification needed:

```bash
curl -X POST http://localhost:8000/api/v1/scan \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "example.com",
    "wordlist_urls": [
      "https://raw.githubusercontent.com/danielmiessler/SecLists/master/Discovery/DNS/subdomains-top1million-5000.txt"
    ]
  }'
```

Files are downloaded temporarily and deleted after the scan.

---

### Option 2: Volume Mount

Mount a local directory containing your wordlists:

<details>
<summary><strong>Podman</strong></summary>

```bash
podman run -d -p 8000:8000 \
  -v /path/to/wordlists:/app/wordlists:ro \
  --name cloudrip-api \
  cloudrip
```

</details>

<details>
<summary><strong>Docker</strong></summary>

```bash
docker run -d -p 8000:8000 \
  -v /path/to/wordlists:/app/wordlists:ro \
  --name cloudrip-api \
  cloudrip
```

</details>

Then reference the path in API requests:

```bash
curl -X POST http://localhost:8000/api/v1/scan \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "example.com",
    "wordlists": ["wordlists/custom.txt"]
  }'
```

---

### Option 3: Modify the Containerfile

To bake wordlists directly into the image:

```dockerfile
# Add after the COPY dom.txt line
COPY --chown=cloudrip:cloudrip my-wordlists/ ./wordlists/
```

<details>
<summary><strong>Full Containerfile example</strong></summary>

```dockerfile
# CloudRip API Container - Custom
FROM docker.io/library/python:3.12-alpine AS builder

WORKDIR /build

RUN apk add --no-cache --virtual .build-deps \
    gcc \
    musl-dev \
    libffi-dev

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements/ ./requirements/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements/api.txt

FROM docker.io/library/python:3.12-alpine AS runtime

RUN addgroup -g 1000 -S cloudrip && \
    adduser -u 1000 -S -G cloudrip -h /app cloudrip

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --chown=cloudrip:cloudrip cloudrip/ ./cloudrip/
COPY --chown=cloudrip:cloudrip dom.txt ./

# Add your custom wordlists
COPY --chown=cloudrip:cloudrip wordlists/ ./wordlists/

USER cloudrip

ENV CLOUDRIP_HOST=0.0.0.0 \
    CLOUDRIP_PORT=8000 \
    CLOUDRIP_WORKERS=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1

ENTRYPOINT ["python", "-m", "uvicorn"]
CMD ["cloudrip.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

</details>

---

### Option 4: Docker Compose / Podman Compose

See the [Docker Compose](#docker-compose) section below.

---

## Docker Compose

### Basic Setup

Create a `compose.yml` file:

```yaml
services:
  cloudrip:
    build: .
    container_name: cloudrip-api
    ports:
      - "8000:8000"
    environment:
      - CLOUDRIP_WORKERS=2
    volumes:
      - ./wordlists:/app/wordlists:ro
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')"]
      interval: 30s
      timeout: 5s
      retries: 3
```

Start:
```bash
# Podman Compose
podman-compose up -d

# Docker Compose
docker compose up -d
```

---

### With Tor Proxy

<details>
<summary><strong>compose.yml with Tor integration</strong></summary>

```yaml
services:
  cloudrip:
    build: .
    container_name: cloudrip-api
    ports:
      - "8000:8000"
    environment:
      - CLOUDRIP_WORKERS=2
      - CLOUDRIP_PROXIES=socks5://tor:9050
    volumes:
      - ./wordlists:/app/wordlists:ro
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')"]
      interval: 30s
      timeout: 5s
      retries: 3

  # Tor proxy for anonymous DNS queries
  tor:
    image: docker.io/osminogin/tor-simple:latest
    container_name: cloudrip-tor
    restart: unless-stopped
```

With this configuration, CloudRip automatically routes DNS queries through Tor.

</details>

---

### Advanced Setup

<details>
<summary><strong>compose.yml with multiple wordlist sources</strong></summary>

```yaml
services:
  cloudrip:
    build:
      context: .
      dockerfile: Containerfile
    container_name: cloudrip-api
    ports:
      - "8000:8000"
    environment:
      - CLOUDRIP_WORKERS=4
      - CLOUDRIP_MAX_THREADS=50
    volumes:
      # SecLists wordlists
      - ./seclists/Discovery/DNS:/app/wordlists/seclists:ro
      # Custom wordlists
      - ./my-wordlists:/app/wordlists/custom:ro
    restart: unless-stopped

volumes:
  seclists:
```

Usage:
```bash
curl -X POST http://localhost:8000/api/v1/scan \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "example.com",
    "wordlists": [
      "wordlists/seclists/subdomains-top1million-5000.txt",
      "wordlists/custom/internal.txt"
    ],
    "threads": 30
  }'
```

</details>

---

## Best Practices

| Practice | Description |
|----------|-------------|
| **Use URLs for public wordlists** | No need to modify the image |
| **Mount as read-only** | Use `:ro` for wordlist volumes |
| **Limit workers** | 1-2 workers are usually sufficient |
| **Use a proxy** | Tor or SOCKS to avoid rate limits |

---

## Health Check

Verify the API is running:

```bash
curl http://localhost:8000/api/v1/health
```

<details>
<summary><strong>Expected response</strong></summary>

```json
{
  "status": "ok",
  "version": "3.0.0",
  "cf_ranges_loaded": true,
  "cf_v4_count": 15,
  "cf_v6_count": 7,
  "proxy_configured": false,
  "proxy_count": 0
}
```

</details>

---

## See Also

- [API Documentation](api.md) - Full API documentation
- [CLI Usage](cli.md) - Command-line usage
