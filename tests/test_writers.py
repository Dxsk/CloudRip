"""Tests for cloudrip.output.writers."""

import io
import json

from cloudrip.core.models import OutputFormat, ResolveResult, ScanReport
from cloudrip.output.writers import ReportWriter


class TestReportWriter:
    """Tests for ReportWriter class."""

    def test_format_ips_with_cf_tags(self, sample_resolve_result):
        """Test _format_ips adds CF tags correctly."""
        formatted = ReportWriter._format_ips(sample_resolve_result)

        assert "192.168.1.1" in formatted
        assert "104.16.1.1 [CF]" in formatted
        assert "2001:db8::1" in formatted
        assert "2606:4700::1 [CF]" in formatted

    def test_format_ips_empty(self):
        """Test _format_ips with no IPs."""
        result = ResolveResult(domain="test.com")
        formatted = ReportWriter._format_ips(result)
        assert formatted == "N/A"

    def test_format_ips_ipv4_only(self):
        """Test _format_ips with IPv4 only."""
        result = ResolveResult(domain="test.com", ipv4=["1.2.3.4"])
        formatted = ReportWriter._format_ips(result)
        assert "v4:" in formatted
        assert "v6:" not in formatted

    def test_format_ips_ipv6_only(self):
        """Test _format_ips with IPv6 only."""
        result = ResolveResult(domain="test.com", ipv6=["2001:db8::1"])
        formatted = ReportWriter._format_ips(result)
        assert "v6:" in formatted
        assert "v4:" not in formatted

    def test_write_normal(self, sample_scan_report):
        """Test writing normal format."""
        output = io.StringIO()
        ReportWriter.write(sample_scan_report, output, OutputFormat.NORMAL)

        content = output.getvalue()
        assert "CloudRip Scan Report" in content
        assert "Target: example.com" in content
        assert "[FOUND]" in content
        assert "[CLOUDFLARE]" in content
        assert "[NOT FOUND]" in content
        assert "test.example.com" in content

    def test_write_json(self, sample_scan_report):
        """Test writing JSON format."""
        output = io.StringIO()
        ReportWriter.write(sample_scan_report, output, OutputFormat.JSON)

        content = output.getvalue()
        data = json.loads(content)

        assert data["target_domain"] == "example.com"
        assert data["total_checked"] == 3
        assert data["summary"]["found"] == 1
        assert data["summary"]["cloudflare"] == 1
        assert "results" in data

    def test_write_yaml(self, sample_scan_report):
        """Test writing YAML format."""
        output = io.StringIO()
        ReportWriter.write(sample_scan_report, output, OutputFormat.YAML)

        content = output.getvalue()
        assert "target_domain: example.com" in content
        assert "total_checked: 3" in content
        assert "summary:" in content
        assert "results:" in content

    def test_write_csv(self, sample_scan_report):
        """Test writing CSV format."""
        output = io.StringIO()
        ReportWriter.write(sample_scan_report, output, OutputFormat.CSV)

        content = output.getvalue()
        lines = content.strip().split("\n")

        # Header
        assert (
            "domain,ipv4,ipv4_cloudflare,ipv6,ipv6_cloudflare,status,error" in lines[0]
        )

        # Should have header + 3 results
        assert len(lines) == 4

        # Check found result
        assert "test.example.com" in content
        assert "found" in content

    def test_write_csv_multiple_ips(self):
        """Test CSV with multiple IPs uses semicolon separator."""
        result = ResolveResult(
            domain="multi.example.com",
            ipv4=["1.2.3.4", "5.6.7.8"],
            status="found",
        )
        report = ScanReport(target_domain="example.com")
        report.found.append(result)

        output = io.StringIO()
        ReportWriter.write(report, output, OutputFormat.CSV)

        content = output.getvalue()
        assert "1.2.3.4;5.6.7.8" in content

    def test_write_to_file(self, sample_scan_report, temp_output_file):
        """Test write_to_file saves to disk."""
        ReportWriter.write_to_file(
            sample_scan_report, temp_output_file, OutputFormat.JSON
        )

        assert temp_output_file.exists()
        content = temp_output_file.read_text()
        data = json.loads(content)
        assert data["target_domain"] == "example.com"

    def test_write_to_file_path_string(self, sample_scan_report, temp_output_file):
        """Test write_to_file accepts string path."""
        ReportWriter.write_to_file(
            sample_scan_report, str(temp_output_file), OutputFormat.JSON
        )

        assert temp_output_file.exists()

    def test_write_normal_with_errors(self):
        """Test normal format includes errors section."""
        report = ScanReport(target_domain="example.com")
        report.errors.append(
            ResolveResult(
                domain="error.example.com",
                status="error",
                error="Connection timeout",
            )
        )

        output = io.StringIO()
        ReportWriter.write(report, output, OutputFormat.NORMAL)

        content = output.getvalue()
        assert "[ERRORS]" in content
        assert "error.example.com" in content
        assert "Connection timeout" in content

    def test_write_normal_no_errors_section(self, sample_scan_report):
        """Test normal format hides errors section when empty."""
        # sample_scan_report has no errors
        output = io.StringIO()
        ReportWriter.write(sample_scan_report, output, OutputFormat.NORMAL)

        content = output.getvalue()
        # Should not have errors section since no errors
        assert "[ERRORS]" not in content

    def test_dict_to_yaml_nested(self):
        """Test YAML serializer handles nested dicts."""
        data = {"level1": {"level2": {"value": 42}}}
        output = io.StringIO()
        ReportWriter._dict_to_yaml(data, output)

        content = output.getvalue()
        assert "level1:" in content
        assert "level2:" in content
        assert "value: 42" in content

    def test_dict_to_yaml_list(self):
        """Test YAML serializer handles lists."""
        data = {"items": ["a", "b", "c"]}
        output = io.StringIO()
        ReportWriter._dict_to_yaml(data, output)

        content = output.getvalue()
        assert "items:" in content
        assert "  - a" in content
        assert "  - b" in content
        assert "  - c" in content

    def test_dict_to_yaml_list_of_dicts(self):
        """Test YAML serializer handles list of dicts."""
        data = {
            "results": [
                {"name": "test1", "value": 1},
                {"name": "test2", "value": 2},
            ]
        }
        output = io.StringIO()
        ReportWriter._dict_to_yaml(data, output)

        content = output.getvalue()
        assert "results:" in content
        assert "- name: test1" in content
        assert "value: 1" in content
