"""Report writers for various output formats."""

import csv
import json
from pathlib import Path
from typing import TextIO

from ..core.models import OutputFormat, ResolveResult, ScanReport


class ReportWriter:
    """Handles writing scan reports in various formats."""

    @staticmethod
    def write(report: ScanReport, output: TextIO, fmt: OutputFormat) -> None:
        """Write report to output stream in specified format."""
        writers = {
            OutputFormat.NORMAL: ReportWriter._write_normal,
            OutputFormat.JSON: ReportWriter._write_json,
            OutputFormat.YAML: ReportWriter._write_yaml,
            OutputFormat.CSV: ReportWriter._write_csv,
        }
        writers[fmt](report, output)

    @staticmethod
    def write_to_file(report: ScanReport, path: str | Path, fmt: OutputFormat) -> None:
        """Write report to file."""
        with open(path, "w", encoding="utf-8") as f:
            ReportWriter.write(report, f, fmt)

    @staticmethod
    def _format_ips(result: ResolveResult) -> str:
        """Format IPs with Cloudflare status indicators."""
        parts = []
        if result.ipv4:
            v4_formatted = []
            for ip in result.ipv4:
                cf_tag = " [CF]" if ip in result.ipv4_cloudflare else ""
                v4_formatted.append(f"{ip}{cf_tag}")
            parts.append(f"v4:[{', '.join(v4_formatted)}]")
        if result.ipv6:
            v6_formatted = []
            for ip in result.ipv6:
                cf_tag = " [CF]" if ip in result.ipv6_cloudflare else ""
                v6_formatted.append(f"{ip}{cf_tag}")
            parts.append(f"v6:[{', '.join(v6_formatted)}]")
        return " | ".join(parts) if parts else "N/A"

    @staticmethod
    def _write_normal(report: ScanReport, output: TextIO) -> None:
        output.write("CloudRip Scan Report\n")
        output.write(f"{'=' * 60}\n")
        output.write(f"Target: {report.target_domain}\n")
        output.write(f"Date: {report.scan_date}\n")
        output.write(f"Total checked: {report.total_checked}\n\n")

        output.write(f"[FOUND] Non-Cloudflare IPs ({len(report.found)}):\n")
        for r in report.found:
            output.write(f"  {r.domain}\n")
            output.write(f"    {ReportWriter._format_ips(r)}\n")

        output.write(f"\n[CLOUDFLARE] Behind Cloudflare ({len(report.cloudflare)}):\n")
        for r in report.cloudflare:
            output.write(f"  {r.domain}\n")
            output.write(f"    {ReportWriter._format_ips(r)}\n")

        output.write(f"\n[NOT FOUND] No DNS record ({len(report.not_found)}):\n")
        for r in report.not_found:
            output.write(f"  {r.domain}\n")

        if report.errors:
            output.write(f"\n[ERRORS] ({len(report.errors)}):\n")
            for r in report.errors:
                output.write(f"  {r.domain}: {r.error}\n")

    @staticmethod
    def _write_json(report: ScanReport, output: TextIO) -> None:
        json.dump(report.to_dict(), output, indent=2)
        output.write("\n")

    @staticmethod
    def _write_yaml(report: ScanReport, output: TextIO) -> None:
        data = report.to_dict()
        ReportWriter._dict_to_yaml(data, output)

    @staticmethod
    def _dict_to_yaml(data: dict, output: TextIO, indent: int = 0) -> None:
        """Simple YAML serializer without external dependencies."""
        prefix = "  " * indent
        for key, value in data.items():
            if isinstance(value, dict):
                output.write(f"{prefix}{key}:\n")
                ReportWriter._dict_to_yaml(value, output, indent + 1)
            elif isinstance(value, list):
                output.write(f"{prefix}{key}:\n")
                for item in value:
                    if isinstance(item, dict):
                        first = True
                        for k, v in item.items():
                            if first:
                                output.write(f"{prefix}  - {k}: {v}\n")
                                first = False
                            else:
                                output.write(f"{prefix}    {k}: {v}\n")
                    else:
                        output.write(f"{prefix}  - {item}\n")
            else:
                output.write(f"{prefix}{key}: {value}\n")

    @staticmethod
    def _write_csv(report: ScanReport, output: TextIO) -> None:
        writer = csv.writer(output)
        writer.writerow(
            [
                "domain",
                "ipv4",
                "ipv4_cloudflare",
                "ipv6",
                "ipv6_cloudflare",
                "status",
                "error",
            ]
        )

        for r in report.found + report.cloudflare + report.not_found + report.errors:
            writer.writerow(
                [
                    r.domain,
                    ";".join(r.ipv4) if r.ipv4 else "",
                    ";".join(r.ipv4_cloudflare) if r.ipv4_cloudflare else "",
                    ";".join(r.ipv6) if r.ipv6 else "",
                    ";".join(r.ipv6_cloudflare) if r.ipv6_cloudflare else "",
                    r.status,
                    r.error or "",
                ]
            )
