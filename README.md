# CloudRip

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![Version](https://img.shields.io/badge/version-3.0.0-green.svg)
![Coverage](https://img.shields.io/badge/coverage-86%25-brightgreen.svg)
![Container](https://img.shields.io/badge/container-OCI-blueviolet.svg)
![License](https://img.shields.io/badge/license-MIT-lightgrey.svg)

Find real IP addresses behind Cloudflare by scanning subdomains. Built for penetration testing, security research, and understanding Cloudflare protection.

---

## Features

| Feature | Description |
|---------|-------------|
| **IPv4 & IPv6** | Resolves both A and AAAA records |
| **Multiple IPs** | Finds ALL IPs behind a domain |
| **Dynamic CF Detection** | Fetches latest IP ranges from Cloudflare's API |
| **Multiple Formats** | JSON, YAML, CSV, plain text output |
| **Multi-threaded** | Fast concurrent subdomain resolution |
| **SOCKS Proxy** | Route DNS through SOCKS4/5 (Tor compatible) |
| **REST API** | FastAPI server with async scanning |
| **Container Ready** | OCI-compliant image for Podman/Docker |

---

## Quick Start

### Installation

<details>
<summary><strong>Python</strong></summary>

```bash
git clone https://github.com/Dxsk/CloudRip.git
cd CloudRip

python3 -m venv venv
source venv/bin/activate
pip install -r requirements/base.txt

# For API mode
pip install -r requirements/api.txt

# For development
pip install -r requirements/dev.txt
```

</details>

<details>
<summary><strong>Container (Podman/Docker)</strong></summary>

```bash
# Build
podman build -t cloudrip .

# Run API
podman run -d -p 8000:8000 --name cloudrip cloudrip

# With custom config
podman run -d -p 8080:8080 \
  -e CLOUDRIP_PORT=8080 \
  -e CLOUDRIP_WORKERS=4 \
  cloudrip
```

</details>

### Usage Examples

<details>
<summary><strong>CLI</strong></summary>

```bash
# Basic scan
python3 cloudrip.py example.com

# With options
python3 cloudrip.py example.com -t 20 -o report.json -f json

# With proxy (Tor)
python3 cloudrip.py example.com -p socks5://127.0.0.1:9050
```

</details>

<details>
<summary><strong>Python Library</strong></summary>

```python
from cloudrip import CloudRipScanner

scanner = CloudRipScanner("example.com")
scanner.load_cf_ranges()
report = scanner.scan_from_wordlists(["dom.txt"])

for result in report.found:
    print(f"{result.domain}: {result.ipv4_non_cf}")
```

</details>

<details>
<summary><strong>REST API</strong></summary>

```bash
# Start server
uvicorn cloudrip.api:app --port 8000

# Quick check
curl -X POST localhost:8000/api/v1/check \
  -H "Content-Type: application/json" \
  -d '{"domain": "mail.example.com"}'

# Start scan
curl -X POST localhost:8000/api/v1/scan \
  -H "Content-Type: application/json" \
  -d '{"domain": "example.com", "threads": 20}'
```

</details>

---

## Documentation

| Mode | Description | Link |
|------|-------------|------|
| **CLI** | Command-line scanner | [docs/cli.md](docs/cli.md) |
| **Library** | Python integration | [docs/library.md](docs/library.md) |
| **API** | REST API server | [docs/api.md](docs/api.md) |
| **Container** | Podman/Docker deployment | [docs/container.md](docs/container.md) |

---

## Project Structure

<details>
<summary><strong>Show structure</strong></summary>

```
cloudrip/
├── core/           # Core scanning logic
│   ├── scanner.py      # CloudRipScanner class
│   ├── resolver.py     # DNS resolution
│   ├── cloudflare.py   # Cloudflare IP detection
│   ├── proxy.py        # SOCKS proxy support
│   └── models.py       # Data models
├── output/         # Report generation
│   └── writers.py      # JSON, YAML, CSV, text output
├── cli/            # Command-line interface
│   └── main.py         # CLI entry point
├── api/            # REST API (FastAPI)
│   ├── app.py          # FastAPI application
│   ├── routes.py       # API endpoints
│   ├── schemas.py      # Pydantic models
│   └── settings.py     # Configuration
└── utils/          # Utilities
    └── colors.py       # Terminal colors
```

</details>

---

## Contributing

Pull requests welcome. See [CHANGELOG.md](CHANGELOG.md) for version history.

---

## Legal

**Only use on systems you have permission to test.** For ethical security research and authorized penetration testing only.

---

## License

MIT

---

## Authors

- **moscovium-mc** - Original creator - [GitHub](https://github.com/moscovium-mc)
- **Dxsk** - [GitHub](https://github.com/Dxsk)
