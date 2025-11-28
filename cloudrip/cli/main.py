"""CloudRip CLI - Command line interface."""

import argparse
import signal
import sys

import pyfiglet
from tqdm import tqdm

from ..core.models import OutputFormat, ResolveResult
from ..core.proxy import ProxyManager
from ..core.scanner import CloudRipScanner
from ..output.writers import ReportWriter
from ..utils.colors import Colors


class CloudRipCLI:
    """CLI interface for CloudRip scanner."""

    def __init__(
        self,
        domain: str,
        wordlists: list[str],
        threads: int = 10,
        output_file: str | None = None,
        output_format: OutputFormat = OutputFormat.NORMAL,
        verbose: bool = False,
        quiet: bool = False,
        proxy_urls: list[str] | None = None,
        proxy_rotate: bool = True,
    ):
        self.domain = domain
        self.wordlists = wordlists
        self.output_file = output_file
        self.output_format = output_format
        self.verbose = verbose
        self.quiet = quiet

        self.proxy_manager: ProxyManager | None = None
        if proxy_urls:
            self.proxy_manager = ProxyManager(proxy_urls, rotate=proxy_rotate)

        self.scanner = CloudRipScanner(
            domain=domain, threads=threads, proxy_manager=self.proxy_manager
        )
        self._pbar: tqdm | None = None

    def log(self, message: str, level: str = "info") -> None:
        """Print message to console based on verbosity settings."""
        if self.quiet:
            return
        if level == "verbose" and not self.verbose:
            return
        tqdm.write(message)

    def display_banner(self) -> None:
        """Display the CloudRip banner."""
        if self.quiet:
            return

        figlet_text = pyfiglet.Figlet(font="slant").renderText("CloudRip")
        tqdm.write(f"{Colors.BLUE}{figlet_text}")
        tqdm.write(
            f"{Colors.RED}CloudFlare Bypasser - Find Real IP Addresses Behind Cloudflare"
        )
        tqdm.write(f'{Colors.YELLOW}"Ripping through the clouds to expose the truth"')
        tqdm.write(
            f"{Colors.WHITE}GitHub: {Colors.BLUE}https://github.com/lucky89144/CloudRip\n"
        )

    def _on_result(self, result: ResolveResult) -> None:
        """Callback for each result."""
        if result.status == "found":
            self._log_found(result)
        elif result.status == "cloudflare":
            self._log_cloudflare(result)
        elif result.status == "not_found":
            self.log(f"{Colors.RED}[NOT FOUND] {result.domain}", level="verbose")

    def _log_found(self, result: ResolveResult) -> None:
        """Log a found (non-CF) result."""
        parts = []
        if result.ipv4:
            v4_parts = []
            for ip in result.ipv4:
                if ip in result.ipv4_cloudflare:
                    v4_parts.append(f"{ip}{Colors.YELLOW}[CF]{Colors.WHITE}")
                else:
                    v4_parts.append(ip)
            parts.append(f"v4:[{', '.join(v4_parts)}]")
        if result.ipv6:
            v6_parts = []
            for ip in result.ipv6:
                if ip in result.ipv6_cloudflare:
                    v6_parts.append(f"{ip}{Colors.YELLOW}[CF]{Colors.WHITE}")
                else:
                    v6_parts.append(ip)
            parts.append(f"v6:[{', '.join(v6_parts)}]")

        ips_str = f"{Colors.WHITE} | ".join(parts)
        self.log(f"{Colors.GREEN}[FOUND] {result.domain} -> {ips_str}")

    def _log_cloudflare(self, result: ResolveResult) -> None:
        """Log a Cloudflare result."""
        parts = []
        if result.ipv4:
            parts.append(f"v4:[{', '.join(result.ipv4)}]")
        if result.ipv6:
            parts.append(f"v6:[{', '.join(result.ipv6)}]")

        ips_str = " | ".join(parts)
        self.log(f"{Colors.YELLOW}[CLOUDFLARE] {result.domain} -> {ips_str}")

    def _on_progress(self, completed: int, total: int) -> None:
        """Callback for progress updates."""
        if self._pbar:
            self._pbar.update(1)
            found = len(self.scanner.report.found)
            cf = len(self.scanner.report.cloudflare)
            self._pbar.set_postfix_str(f"found:{found} cf:{cf}")

    def handle_interrupt(self, signum: int, frame: object) -> None:
        """Handle Ctrl+C gracefully."""
        if self.scanner.stop_requested:
            tqdm.write(f"{Colors.RED}\n[INFO] Force quitting...")
            sys.exit(0)

        tqdm.write(f"{Colors.RED}\n[INFO] Ctrl+C detected. Quit? (y/n): ")

        try:
            if input().strip().lower() == "y":
                self.scanner.stop()
            else:
                tqdm.write(f"{Colors.YELLOW}[INFO] Resuming...")
        except EOFError:
            self.scanner.stop()

    def run(self) -> None:
        """Execute the CLI scan."""
        signal.signal(signal.SIGINT, self.handle_interrupt)

        self.display_banner()

        self.log(f"{Colors.YELLOW}[INFO] Fetching Cloudflare IP ranges...")
        v4_api, v6_api = self.scanner.load_cf_ranges()
        v4_count, v6_count = self.scanner.cf_ranges.range_count

        if v4_api:
            self.log(f"{Colors.GREEN}[INFO] IPv4: {v4_count} ranges from API")
        else:
            self.log(f"{Colors.YELLOW}[WARNING] IPv4: using {v4_count} fallback ranges")

        if v6_api:
            self.log(f"{Colors.GREEN}[INFO] IPv6: {v6_count} ranges from API")
        else:
            self.log(f"{Colors.YELLOW}[WARNING] IPv6: using {v6_count} fallback ranges")

        if self.proxy_manager and self.proxy_manager.has_proxies:
            self.log(
                f"{Colors.GREEN}[INFO] Using {self.proxy_manager.proxy_count} SOCKS "
                f"proxy(ies) for DNS queries"
            )

        self.log(f"{Colors.YELLOW}[INFO] Checking root domain: {self.domain}")
        root_result = self.scanner.resolve_subdomain()
        self.scanner.add_result(root_result)
        self._on_result(root_result)

        subdomains = self.scanner.load_wordlists(self.wordlists)
        if not subdomains:
            self.log(f"{Colors.RED}[ERROR] No subdomains loaded from any wordlist")
            sys.exit(1)

        for wl in self.wordlists:
            self.log(f"{Colors.YELLOW}[INFO] Loaded wordlist: {wl}")

        self.log(f"{Colors.YELLOW}[INFO] {len(subdomains)} unique subdomains to check")
        self.log(f"{Colors.YELLOW}[INFO] Starting scan...\n")

        self.scanner.set_callbacks(
            on_result=self._on_result,
            on_progress=self._on_progress,
        )

        with tqdm(
            total=len(subdomains),
            desc=f"{Colors.CYAN}Scanning",
            unit="sub",
            disable=self.quiet,
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}] {postfix}",
            ncols=80,
            leave=False,
        ) as pbar:
            self._pbar = pbar
            self.scanner.scan(subdomains, include_root=False)
            self._pbar = None

        report = self.scanner.report

        self.log(f"\n{Colors.WHITE}{'=' * 60}")
        self.log(f"{Colors.WHITE}Scan complete: {report.total_checked} checked")
        self.log(f"{Colors.GREEN}  Found (non-CF): {len(report.found)}")
        self.log(f"{Colors.YELLOW}  Cloudflare: {len(report.cloudflare)}")
        self.log(f"{Colors.RED}  Not found: {len(report.not_found)}")

        if report.errors:
            self.log(f"{Colors.YELLOW}  Errors: {len(report.errors)}")

        if self.output_file:
            try:
                ReportWriter.write_to_file(report, self.output_file, self.output_format)
                self.log(f"{Colors.GREEN}[INFO] Report saved to {self.output_file}")
            except OSError as e:
                self.log(f"{Colors.RED}[ERROR] Failed to save report: {e}")


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="CloudRip v2 - CloudFlare Bypasser (IPv4 + IPv6)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cloudrip.py example.com
  python cloudrip.py example.com -w wordlist1.txt -w wordlist2.txt
  python cloudrip.py example.com -o report.json -f json
  python cloudrip.py example.com -v  # verbose mode
  python cloudrip.py example.com -q  # quiet mode
  python cloudrip.py example.com -p socks5://127.0.0.1:9050  # via Tor
  python cloudrip.py example.com -p socks5://proxy1:1080 -p socks5://proxy2:1080
        """,
    )

    parser.add_argument("domain", help="Target domain (e.g., example.com)")

    parser.add_argument(
        "-w",
        "--wordlist",
        action="append",
        dest="wordlists",
        default=[],
        help="Wordlist file(s). Can be specified multiple times.",
    )

    parser.add_argument(
        "-t",
        "--threads",
        type=int,
        default=10,
        help="Concurrent threads (default: 10)",
    )

    parser.add_argument(
        "-o",
        "--output",
        help="Output file for report",
    )

    parser.add_argument(
        "-f",
        "--format",
        choices=["normal", "json", "yaml", "csv"],
        default="normal",
        help="Output format (default: normal)",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show all results including not found",
    )

    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Minimal output (only found IPs)",
    )

    parser.add_argument(
        "-p",
        "--proxy",
        action="append",
        dest="proxies",
        default=[],
        metavar="URL",
        help="SOCKS proxy URL (socks5://host:port). Can be specified multiple times.",
    )

    parser.add_argument(
        "--no-rotate",
        action="store_true",
        help="Disable proxy rotation (use first proxy only)",
    )

    return parser.parse_args()


def main() -> None:
    """CLI entry point."""
    args = parse_arguments()

    wordlists = args.wordlists if args.wordlists else ["dom.txt"]
    proxy_urls = args.proxies if args.proxies else None

    cli = CloudRipCLI(
        domain=args.domain,
        wordlists=wordlists,
        threads=args.threads,
        output_file=args.output,
        output_format=OutputFormat(args.format),
        verbose=args.verbose,
        quiet=args.quiet,
        proxy_urls=proxy_urls,
        proxy_rotate=not args.no_rotate,
    )

    cli.run()


if __name__ == "__main__":
    main()
