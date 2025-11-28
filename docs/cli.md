# CloudRip CLI

Command-line interface for scanning subdomains and finding real IP addresses behind Cloudflare.

**Table of Contents**
- [Installation](#installation)
- [Basic Usage](#basic-usage)
- [Options](#options)
- [Examples](#examples)
- [Wordlist Format](#wordlist-format)

---

## Installation

```bash
git clone https://github.com/Dxsk/CloudRip.git
cd CloudRip

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Basic Usage

```bash
python cloudrip.py <domain> [options]
```

**Quick Start:**

```bash
# Basic scan with default wordlist
python cloudrip.py example.com

# Custom wordlist
python cloudrip.py example.com -w my_wordlist.txt

# Multiple wordlists (merged automatically)
python cloudrip.py example.com -w wordlist1.txt -w wordlist2.txt
```

---

## Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--wordlist` | `-w` | Wordlist file(s). Can be repeated | `dom.txt` |
| `--threads` | `-t` | Concurrent threads | `10` |
| `--output` | `-o` | Output file path | None |
| `--format` | `-f` | Output format: `normal`, `json`, `yaml`, `csv` | `normal` |
| `--verbose` | `-v` | Show all results including "not found" | False |
| `--quiet` | `-q` | Minimal output (only found IPs) | False |
| `--proxy` | `-p` | SOCKS proxy URL. Can be repeated | None |
| `--no-rotate` | | Disable proxy rotation | False |

---

## Examples

### Basic Scan

```bash
python cloudrip.py example.com
```

<details>
<summary><strong>Sample Output</strong></summary>

```
   ________                ______  _
  / ____/ /___  __  ______/ / __ \(_)___
 / /   / / __ \/ / / / __  / /_/ / / __ \
/ /___/ / /_/ / /_/ / /_/ / _, _/ / /_/ /
\____/_/\____/\__,_/\__,_/_/ |_/_/ .___/
                                /_/

CloudFlare Bypasser - Find Real IP Addresses Behind Cloudflare
"Ripping through the clouds to expose the truth"

[INFO] Fetching Cloudflare IP ranges...
[INFO] IPv4: 15 ranges from API
[INFO] IPv6: 7 ranges from API
[INFO] Checking root domain: example.com
[CLOUDFLARE] example.com -> v4:[104.21.20.41, 172.67.191.82]
[INFO] Loaded wordlist: dom.txt
[INFO] 600 unique subdomains to check
[INFO] Starting scan...

[FOUND] mail.example.com -> v4:[192.168.1.1, 192.168.1.2]
[CLOUDFLARE] www.example.com -> v4:[104.21.20.41]

============================================================
Scan complete: 601 checked
  Found (non-CF): 5
  Cloudflare: 42
  Not found: 554
```

</details>

---

### Output Formats

<details>
<summary><strong>JSON Export</strong></summary>

```bash
python cloudrip.py example.com -o report.json -f json
```

Output (`report.json`):
```json
{
  "target_domain": "example.com",
  "scan_date": "2025-11-28T12:00:00+00:00",
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
        "ipv4": ["192.168.1.1", "192.168.1.2"],
        "ipv6": [],
        "status": "found",
        "ipv4_cloudflare": [],
        "ipv6_cloudflare": []
      }
    ],
    "cloudflare": [...],
    "not_found": [...],
    "errors": []
  }
}
```

</details>

<details>
<summary><strong>CSV Export</strong></summary>

```bash
python cloudrip.py example.com -o report.csv -f csv
```

Output (`report.csv`):
```csv
domain,ipv4,ipv4_cloudflare,ipv6,ipv6_cloudflare,status,error
mail.example.com,192.168.1.1;192.168.1.2,,,,found,
www.example.com,104.21.20.41,104.21.20.41,,,cloudflare,
```

</details>

<details>
<summary><strong>YAML Export</strong></summary>

```bash
python cloudrip.py example.com -o report.yaml -f yaml
```

</details>

---

### Performance Tuning

<details>
<summary><strong>Fast Scan (more threads)</strong></summary>

```bash
python cloudrip.py example.com -t 50
```

Increase threads for faster scanning. Default is 10, max recommended is ~100.

</details>

---

### Verbosity Controls

<details>
<summary><strong>Verbose Mode (see all attempts)</strong></summary>

```bash
python cloudrip.py example.com -v
```

Shows all results including domains that don't resolve:
```
[FOUND] mail.example.com -> v4:[192.168.1.1]
[NOT FOUND] admin.example.com
[NOT FOUND] api.example.com
[CLOUDFLARE] www.example.com -> v4:[104.21.20.41]
```

</details>

<details>
<summary><strong>Quiet Mode (minimal output)</strong></summary>

```bash
python cloudrip.py example.com -q -o found.txt
```

Only shows found IPs. Perfect for piping to other tools.

</details>

---

### Multiple Wordlists

```bash
python cloudrip.py example.com -w common.txt -w dns.txt -w custom.txt
```

Wordlists are automatically merged and deduplicated.

---

### SOCKS Proxy

Route DNS queries through a SOCKS proxy for anonymity or bypassing restrictions.

<details>
<summary><strong>Single Proxy (e.g., Tor)</strong></summary>

```bash
python cloudrip.py example.com -p socks5://127.0.0.1:9050
```

</details>

<details>
<summary><strong>Proxy with Authentication</strong></summary>

```bash
python cloudrip.py example.com -p socks5://user:pass@proxy.example.com:1080
```

</details>

<details>
<summary><strong>Multiple Proxies (rotating)</strong></summary>

```bash
python cloudrip.py example.com -p socks5://proxy1:1080 -p socks5://proxy2:1080
```

Queries are distributed across proxies in round-robin fashion.

</details>

<details>
<summary><strong>Multiple Proxies (no rotation)</strong></summary>

```bash
python cloudrip.py example.com -p socks5://proxy1:1080 -p socks5://proxy2:1080 --no-rotate
```

Uses first proxy only. Others are fallbacks.

</details>

**Supported formats:**
- `socks5://host:port`
- `socks5://user:pass@host:port`
- `socks4://host:port`

---

## Wordlist Format

Simple text file with one subdomain per line:

```txt
# Comments start with #
www
mail
ftp
api

# Empty lines are ignored
admin
dev
staging
```

The default wordlist (`dom.txt`) contains 600+ common subdomains.

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+C` | Prompts to quit (press again to force) |

---

## Exit Codes

| Code | Description |
|------|-------------|
| `0` | Success |
| `1` | Error (no wordlists found, etc.) |

---

## See Also

- [Library Usage](library.md) - Use CloudRip as a Python library
- [REST API](api.md) - Run CloudRip as an API server
- [Container Deployment](container.md) - Deploy with Podman/Docker
