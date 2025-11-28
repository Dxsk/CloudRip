#!/usr/bin/env python3
"""
CloudRip v2 - CloudFlare Bypasser.

Find real IP addresses behind Cloudflare by resolving subdomains
and filtering out Cloudflare's IP ranges (fetched dynamically).
Supports both IPv4 and IPv6.

CLI entry point - delegates to cloudrip.cli module.
"""

from cloudrip.cli import main

if __name__ == "__main__":
    main()
