"""DNS resolution utilities."""

from typing import Optional

import dns.resolver

from .cloudflare import CloudflareIPRanges
from .models import ResolveResult
from .proxy import ProxyManager


class DNSResolver:
    """DNS resolver with Cloudflare IP detection and SOCKS proxy support."""

    def __init__(
        self,
        cf_ranges: CloudflareIPRanges | None = None,
        proxy_manager: Optional[ProxyManager] = None,
    ):
        self.cf_ranges = cf_ranges or CloudflareIPRanges()
        self.proxy_manager = proxy_manager
        self._use_tcp = proxy_manager is not None and proxy_manager.has_proxies

    def resolve_record(self, domain: str, record_type: str) -> list[str]:
        """Resolve a DNS record type and return all IPs."""
        ips = []
        try:
            # Use TCP when proxying (SOCKS only supports TCP)
            if self._use_tcp and self.proxy_manager:
                ips = self._resolve_via_proxy(domain, record_type)
            else:
                answers = dns.resolver.resolve(domain, record_type)
                for rdata in answers:
                    ips.append(rdata.address)
        except (
            dns.resolver.NXDOMAIN,
            dns.resolver.NoAnswer,
            dns.resolver.NoNameservers,
            dns.resolver.Timeout,
            dns.resolver.LifetimeTimeout,
        ):
            pass
        except Exception:
            pass
        return ips

    def _resolve_via_proxy(self, domain: str, record_type: str) -> list[str]:
        """Resolve DNS via SOCKS proxy using TCP."""
        import struct

        ips = []
        sock = None

        try:
            # Create SOCKS-wrapped socket
            sock = self.proxy_manager.create_socket()
            sock.settimeout(5.0)

            # Google DNS over TCP
            sock.connect(("8.8.8.8", 53))

            query = self._build_dns_query(domain, record_type)

            # TCP DNS needs length prefix
            sock.sendall(struct.pack(">H", len(query)) + query)

            response_len_data = sock.recv(2)
            if len(response_len_data) < 2:
                return ips
            response_len = struct.unpack(">H", response_len_data)[0]

            response = b""
            while len(response) < response_len:
                chunk = sock.recv(response_len - len(response))
                if not chunk:
                    break
                response += chunk

            ips = self._parse_dns_response(response, record_type)

        except Exception:
            pass
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

        return ips

    def _build_dns_query(self, domain: str, record_type: str) -> bytes:
        """Build a DNS query packet."""
        import struct
        import random

        transaction_id = random.randint(0, 65535)
        flags = 0x0100  # standard query + recursion

        # header: txid, flags, qdcount=1, ancount=0, nscount=0, arcount=0
        header = struct.pack(">HHHHHH", transaction_id, flags, 1, 0, 0, 0)

        qname = b""
        for part in domain.split("."):
            qname += bytes([len(part)]) + part.encode("ascii")
        qname += b"\x00"

        qtype = 1 if record_type == "A" else 28  # A=1, AAAA=28
        qclass = 1  # IN

        question = qname + struct.pack(">HH", qtype, qclass)

        return header + question

    def _parse_dns_response(self, response: bytes, record_type: str) -> list[str]:
        """Parse DNS response and extract IPs."""
        import struct
        import socket

        ips = []
        if len(response) < 12:
            return ips

        _, flags, qdcount, ancount, _, _ = struct.unpack(">HHHHHH", response[:12])

        if flags & 0x8000 == 0:  # not a response
            return ips
        if flags & 0x000F != 0:  # rcode != 0
            return ips

        offset = 12

        # skip question section
        for _ in range(qdcount):
            while offset < len(response) and response[offset] != 0:
                if response[offset] & 0xC0 == 0xC0:
                    offset += 2
                    break
                offset += response[offset] + 1
            else:
                offset += 1
            offset += 4  # qtype + qclass

        for _ in range(ancount):
            if offset >= len(response):
                break

            # skip name (might be compressed)
            if response[offset] & 0xC0 == 0xC0:
                offset += 2
            else:
                while offset < len(response) and response[offset] != 0:
                    offset += response[offset] + 1
                offset += 1

            if offset + 10 > len(response):
                break

            rtype, rclass, ttl, rdlength = struct.unpack(
                ">HHIH", response[offset : offset + 10]
            )
            offset += 10

            if offset + rdlength > len(response):
                break

            if record_type == "A" and rtype == 1 and rdlength == 4:
                ip = socket.inet_ntoa(response[offset : offset + 4])
                ips.append(ip)
            elif record_type == "AAAA" and rtype == 28 and rdlength == 16:
                ip = socket.inet_ntop(socket.AF_INET6, response[offset : offset + 16])
                ips.append(ip)

            offset += rdlength

        return ips

    def resolve_domain(
        self, domain: str, base_domain: str | None = None
    ) -> ResolveResult:
        """Resolve a domain for both A and AAAA records.

        Args:
            domain: Subdomain to resolve (or full domain if base_domain is None)
            base_domain: Base domain to append (e.g., 'example.com')

        Returns:
            ResolveResult with all IPs and Cloudflare status
        """
        full_domain = f"{domain}.{base_domain}" if base_domain else domain
        result = ResolveResult(domain=full_domain)

        # Resolve IPv4 (A records)
        ipv4_list = self.resolve_record(full_domain, "A")
        result.ipv4 = ipv4_list
        result.ipv4_cloudflare = [
            ip for ip in ipv4_list if self.cf_ranges.is_cloudflare_ip(ip)
        ]

        # Resolve IPv6 (AAAA records)
        ipv6_list = self.resolve_record(full_domain, "AAAA")
        result.ipv6 = ipv6_list
        result.ipv6_cloudflare = [
            ip for ip in ipv6_list if self.cf_ranges.is_cloudflare_ip(ip)
        ]

        # Determine status
        if not result.ipv4 and not result.ipv6:
            result.status = "not_found"
        elif result.has_non_cf_ip:
            result.status = "found"
        else:
            result.status = "cloudflare"

        return result
