"""Tests for the CLI module."""

import argparse
import signal
import sys
from io import StringIO
from unittest.mock import MagicMock, patch, call

import pytest

from cloudrip.core.models import OutputFormat, ResolveResult, ScanReport
from cloudrip.cli.main import CloudRipCLI, parse_arguments, main


class TestCloudRipCLI:
    """Tests for CloudRipCLI class."""

    @pytest.fixture
    def mock_scanner(self):
        """Create a mock scanner."""
        with patch("cloudrip.cli.main.CloudRipScanner") as mock:
            scanner = MagicMock()
            scanner.report = ScanReport(target_domain="example.com")
            scanner.stop_requested = False
            mock.return_value = scanner
            yield scanner

    @pytest.fixture
    def cli(self, mock_scanner):
        """Create a CLI instance with mocked scanner."""
        return CloudRipCLI(
            domain="example.com",
            wordlists=["dom.txt"],
            threads=10,
            output_file=None,
            output_format=OutputFormat.NORMAL,
            verbose=False,
            quiet=False,
        )

    def test_init_defaults(self, mock_scanner):
        """Test CLI initialization with default values."""
        cli = CloudRipCLI(domain="example.com", wordlists=["dom.txt"])
        assert cli.domain == "example.com"
        assert cli.wordlists == ["dom.txt"]
        assert cli.output_file is None
        assert cli.output_format == OutputFormat.NORMAL
        assert cli.verbose is False
        assert cli.quiet is False

    def test_init_custom_values(self, mock_scanner):
        """Test CLI initialization with custom values."""
        cli = CloudRipCLI(
            domain="test.com",
            wordlists=["w1.txt", "w2.txt"],
            threads=20,
            output_file="report.json",
            output_format=OutputFormat.JSON,
            verbose=True,
            quiet=False,
        )
        assert cli.domain == "test.com"
        assert cli.wordlists == ["w1.txt", "w2.txt"]
        assert cli.output_file == "report.json"
        assert cli.output_format == OutputFormat.JSON
        assert cli.verbose is True

    def test_log_normal_mode(self, cli):
        """Test logging in normal mode."""
        with patch("cloudrip.cli.main.tqdm") as mock_tqdm:
            cli.log("Test message")
            mock_tqdm.write.assert_called_once_with("Test message")

    def test_log_quiet_mode(self, mock_scanner):
        """Test logging is suppressed in quiet mode."""
        cli = CloudRipCLI(
            domain="example.com",
            wordlists=["dom.txt"],
            quiet=True,
        )
        with patch("cloudrip.cli.main.tqdm") as mock_tqdm:
            cli.log("Test message")
            mock_tqdm.write.assert_not_called()

    def test_log_verbose_level_without_verbose_flag(self, cli):
        """Test verbose messages are suppressed without verbose flag."""
        with patch("cloudrip.cli.main.tqdm") as mock_tqdm:
            cli.log("Verbose message", level="verbose")
            mock_tqdm.write.assert_not_called()

    def test_log_verbose_level_with_verbose_flag(self, mock_scanner):
        """Test verbose messages are shown with verbose flag."""
        cli = CloudRipCLI(
            domain="example.com",
            wordlists=["dom.txt"],
            verbose=True,
        )
        with patch("cloudrip.cli.main.tqdm") as mock_tqdm:
            cli.log("Verbose message", level="verbose")
            mock_tqdm.write.assert_called_once_with("Verbose message")

    def test_display_banner_normal(self, cli):
        """Test banner is displayed in normal mode."""
        with patch("cloudrip.cli.main.tqdm") as mock_tqdm:
            with patch("cloudrip.cli.main.pyfiglet.Figlet") as mock_figlet:
                mock_figlet.return_value.renderText.return_value = "CloudRip"
                cli.display_banner()
                assert mock_tqdm.write.call_count >= 1

    def test_display_banner_quiet(self, mock_scanner):
        """Test banner is not displayed in quiet mode."""
        cli = CloudRipCLI(
            domain="example.com",
            wordlists=["dom.txt"],
            quiet=True,
        )
        with patch("cloudrip.cli.main.tqdm") as mock_tqdm:
            cli.display_banner()
            mock_tqdm.write.assert_not_called()

    def test_on_result_found(self, cli):
        """Test _on_result callback with found status."""
        result = ResolveResult(
            domain="mail.example.com",
            ipv4=["192.168.1.1"],
            ipv6=[],
            status="found",
        )
        with patch.object(cli, "_log_found") as mock_log:
            cli._on_result(result)
            mock_log.assert_called_once_with(result)

    def test_on_result_cloudflare(self, cli):
        """Test _on_result callback with cloudflare status."""
        result = ResolveResult(
            domain="www.example.com",
            ipv4=["104.16.1.1"],
            ipv6=[],
            status="cloudflare",
        )
        with patch.object(cli, "_log_cloudflare") as mock_log:
            cli._on_result(result)
            mock_log.assert_called_once_with(result)

    def test_on_result_not_found_verbose(self, mock_scanner):
        """Test _on_result callback with not_found status in verbose mode."""
        cli = CloudRipCLI(
            domain="example.com",
            wordlists=["dom.txt"],
            verbose=True,
        )
        result = ResolveResult(
            domain="nonexistent.example.com",
            ipv4=[],
            ipv6=[],
            status="not_found",
        )
        with patch.object(cli, "log") as mock_log:
            cli._on_result(result)
            mock_log.assert_called_once()
            assert "NOT FOUND" in mock_log.call_args[0][0]

    def test_on_result_not_found_normal(self, cli):
        """Test _on_result callback with not_found status in normal mode."""
        result = ResolveResult(
            domain="nonexistent.example.com",
            ipv4=[],
            ipv6=[],
            status="not_found",
        )
        with patch.object(cli, "log") as mock_log:
            cli._on_result(result)
            # Should be called with level="verbose" which is suppressed
            mock_log.assert_called_once()
            assert mock_log.call_args[1]["level"] == "verbose"

    def test_log_found_ipv4_only(self, cli):
        """Test _log_found with IPv4 only."""
        result = ResolveResult(
            domain="mail.example.com",
            ipv4=["192.168.1.1"],
            ipv6=[],
            status="found",
        )
        with patch.object(cli, "log") as mock_log:
            cli._log_found(result)
            mock_log.assert_called_once()
            assert "FOUND" in mock_log.call_args[0][0]
            assert "mail.example.com" in mock_log.call_args[0][0]

    def test_log_found_ipv6_only(self, cli):
        """Test _log_found with IPv6 only."""
        result = ResolveResult(
            domain="mail.example.com",
            ipv4=[],
            ipv6=["2001:db8::1"],
            status="found",
        )
        with patch.object(cli, "log") as mock_log:
            cli._log_found(result)
            mock_log.assert_called_once()
            assert "FOUND" in mock_log.call_args[0][0]

    def test_log_found_mixed_ips_with_cf(self, cli):
        """Test _log_found with mixed IPs including Cloudflare."""
        result = ResolveResult(
            domain="mail.example.com",
            ipv4=["192.168.1.1", "104.16.1.1"],
            ipv6=["2001:db8::1", "2606:4700::1"],
            status="found",
            ipv4_cloudflare=["104.16.1.1"],
            ipv6_cloudflare=["2606:4700::1"],
        )
        with patch.object(cli, "log") as mock_log:
            cli._log_found(result)
            mock_log.assert_called_once()
            log_msg = mock_log.call_args[0][0]
            assert "FOUND" in log_msg
            assert "[CF]" in log_msg

    def test_log_cloudflare_ipv4(self, cli):
        """Test _log_cloudflare with IPv4."""
        result = ResolveResult(
            domain="www.example.com",
            ipv4=["104.16.1.1"],
            ipv6=[],
            status="cloudflare",
        )
        with patch.object(cli, "log") as mock_log:
            cli._log_cloudflare(result)
            mock_log.assert_called_once()
            assert "CLOUDFLARE" in mock_log.call_args[0][0]

    def test_log_cloudflare_ipv6(self, cli):
        """Test _log_cloudflare with IPv6."""
        result = ResolveResult(
            domain="www.example.com",
            ipv4=[],
            ipv6=["2606:4700::1"],
            status="cloudflare",
        )
        with patch.object(cli, "log") as mock_log:
            cli._log_cloudflare(result)
            mock_log.assert_called_once()
            assert "CLOUDFLARE" in mock_log.call_args[0][0]

    def test_log_cloudflare_both(self, cli):
        """Test _log_cloudflare with both IPv4 and IPv6."""
        result = ResolveResult(
            domain="www.example.com",
            ipv4=["104.16.1.1"],
            ipv6=["2606:4700::1"],
            status="cloudflare",
        )
        with patch.object(cli, "log") as mock_log:
            cli._log_cloudflare(result)
            mock_log.assert_called_once()
            log_msg = mock_log.call_args[0][0]
            assert "v4:" in log_msg
            assert "v6:" in log_msg

    def test_on_progress_updates_pbar(self, cli):
        """Test _on_progress updates progress bar."""
        cli._pbar = MagicMock()
        cli.scanner.report = ScanReport(target_domain="example.com")
        cli.scanner.report.found = [MagicMock(), MagicMock()]
        cli.scanner.report.cloudflare = [MagicMock()]

        cli._on_progress(10, 100)

        cli._pbar.update.assert_called_once_with(1)
        cli._pbar.set_postfix_str.assert_called_once_with("found:2 cf:1")

    def test_on_progress_no_pbar(self, cli):
        """Test _on_progress with no progress bar."""
        cli._pbar = None
        # Should not raise
        cli._on_progress(10, 100)

    def test_handle_interrupt_force_quit(self, cli):
        """Test handle_interrupt with force quit."""
        cli.scanner.stop_requested = True
        with patch("cloudrip.cli.main.tqdm") as mock_tqdm:
            with pytest.raises(SystemExit) as exc_info:
                cli.handle_interrupt(signal.SIGINT, None)
            assert exc_info.value.code == 0

    def test_handle_interrupt_confirm_yes(self, cli):
        """Test handle_interrupt with user confirming quit."""
        cli.scanner.stop_requested = False
        with patch("cloudrip.cli.main.tqdm"):
            with patch("builtins.input", return_value="y"):
                cli.handle_interrupt(signal.SIGINT, None)
                cli.scanner.stop.assert_called_once()

    def test_handle_interrupt_confirm_no(self, cli):
        """Test handle_interrupt with user declining quit."""
        cli.scanner.stop_requested = False
        with patch("cloudrip.cli.main.tqdm"):
            with patch("builtins.input", return_value="n"):
                cli.handle_interrupt(signal.SIGINT, None)
                cli.scanner.stop.assert_not_called()

    def test_handle_interrupt_eof(self, cli):
        """Test handle_interrupt with EOF (pipe closed)."""
        cli.scanner.stop_requested = False
        with patch("cloudrip.cli.main.tqdm"):
            with patch("builtins.input", side_effect=EOFError):
                cli.handle_interrupt(signal.SIGINT, None)
                cli.scanner.stop.assert_called_once()


class TestCLIRun:
    """Tests for CloudRipCLI.run method."""

    @pytest.fixture
    def mock_scanner(self):
        """Create a mock scanner."""
        with patch("cloudrip.cli.main.CloudRipScanner") as mock:
            scanner = MagicMock()
            scanner.report = ScanReport(target_domain="example.com")
            scanner.stop_requested = False
            scanner.load_cf_ranges.return_value = (True, True)
            scanner.cf_ranges.range_count = (15, 7)
            scanner.load_wordlists.return_value = ["www", "mail", "api"]
            scanner.resolve_subdomain.return_value = ResolveResult(
                domain="example.com",
                ipv4=["93.184.216.34"],
                status="found",
            )
            mock.return_value = scanner
            yield scanner

    def test_run_success(self, mock_scanner):
        """Test successful run."""
        cli = CloudRipCLI(
            domain="example.com",
            wordlists=["dom.txt"],
            quiet=True,  # Suppress output for cleaner tests
        )

        with patch("cloudrip.cli.main.signal.signal"):
            with patch("cloudrip.cli.main.tqdm"):
                cli.run()

        mock_scanner.load_cf_ranges.assert_called_once()
        mock_scanner.load_wordlists.assert_called_once()
        mock_scanner.scan.assert_called_once()

    def test_run_with_fallback_ranges(self, mock_scanner):
        """Test run with fallback CF ranges."""
        mock_scanner.load_cf_ranges.return_value = (False, False)

        cli = CloudRipCLI(
            domain="example.com",
            wordlists=["dom.txt"],
            quiet=True,
        )

        with patch("cloudrip.cli.main.signal.signal"):
            with patch("cloudrip.cli.main.tqdm"):
                cli.run()

        mock_scanner.load_cf_ranges.assert_called_once()

    def test_run_no_subdomains(self, mock_scanner):
        """Test run with no subdomains loaded."""
        mock_scanner.load_wordlists.return_value = []

        cli = CloudRipCLI(
            domain="example.com",
            wordlists=["nonexistent.txt"],
            quiet=True,
        )

        with patch("cloudrip.cli.main.signal.signal"):
            with patch("cloudrip.cli.main.tqdm"):
                with pytest.raises(SystemExit) as exc_info:
                    cli.run()
                assert exc_info.value.code == 1

    def test_run_with_output_file(self, mock_scanner):
        """Test run with output file."""
        cli = CloudRipCLI(
            domain="example.com",
            wordlists=["dom.txt"],
            output_file="report.json",
            output_format=OutputFormat.JSON,
            quiet=True,
        )

        with patch("cloudrip.cli.main.signal.signal"):
            with patch("cloudrip.cli.main.tqdm"):
                with patch(
                    "cloudrip.cli.main.ReportWriter.write_to_file"
                ) as mock_write:
                    cli.run()
                    mock_write.assert_called_once()

    def test_run_output_file_error(self, mock_scanner):
        """Test run with output file write error."""
        cli = CloudRipCLI(
            domain="example.com",
            wordlists=["dom.txt"],
            output_file="/nonexistent/path/report.json",
            quiet=True,
        )

        with patch("cloudrip.cli.main.signal.signal"):
            with patch("cloudrip.cli.main.tqdm"):
                with patch(
                    "cloudrip.cli.main.ReportWriter.write_to_file",
                    side_effect=OSError("Permission denied"),
                ):
                    # Should not raise, just log error
                    cli.run()

    def test_run_with_errors_in_report(self, mock_scanner):
        """Test run with errors in report."""
        mock_scanner.report.errors = [MagicMock()]

        cli = CloudRipCLI(
            domain="example.com",
            wordlists=["dom.txt"],
            quiet=True,
        )

        with patch("cloudrip.cli.main.signal.signal"):
            with patch("cloudrip.cli.main.tqdm"):
                cli.run()


class TestParseArguments:
    """Tests for parse_arguments function."""

    def test_parse_domain_only(self):
        """Test parsing with domain only."""
        with patch("sys.argv", ["cloudrip", "example.com"]):
            args = parse_arguments()
            assert args.domain == "example.com"
            assert args.wordlists == []
            assert args.threads == 10
            assert args.output is None
            assert args.format == "normal"
            assert args.verbose is False
            assert args.quiet is False

    def test_parse_single_wordlist(self):
        """Test parsing with single wordlist."""
        with patch("sys.argv", ["cloudrip", "example.com", "-w", "custom.txt"]):
            args = parse_arguments()
            assert args.wordlists == ["custom.txt"]

    def test_parse_multiple_wordlists(self):
        """Test parsing with multiple wordlists."""
        with patch(
            "sys.argv",
            ["cloudrip", "example.com", "-w", "w1.txt", "-w", "w2.txt", "-w", "w3.txt"],
        ):
            args = parse_arguments()
            assert args.wordlists == ["w1.txt", "w2.txt", "w3.txt"]

    def test_parse_threads(self):
        """Test parsing with custom threads."""
        with patch("sys.argv", ["cloudrip", "example.com", "-t", "50"]):
            args = parse_arguments()
            assert args.threads == 50

    def test_parse_threads_long(self):
        """Test parsing with --threads."""
        with patch("sys.argv", ["cloudrip", "example.com", "--threads", "25"]):
            args = parse_arguments()
            assert args.threads == 25

    def test_parse_output_file(self):
        """Test parsing with output file."""
        with patch("sys.argv", ["cloudrip", "example.com", "-o", "report.json"]):
            args = parse_arguments()
            assert args.output == "report.json"

    def test_parse_output_format_json(self):
        """Test parsing with JSON format."""
        with patch("sys.argv", ["cloudrip", "example.com", "-f", "json"]):
            args = parse_arguments()
            assert args.format == "json"

    def test_parse_output_format_yaml(self):
        """Test parsing with YAML format."""
        with patch("sys.argv", ["cloudrip", "example.com", "-f", "yaml"]):
            args = parse_arguments()
            assert args.format == "yaml"

    def test_parse_output_format_csv(self):
        """Test parsing with CSV format."""
        with patch("sys.argv", ["cloudrip", "example.com", "-f", "csv"]):
            args = parse_arguments()
            assert args.format == "csv"

    def test_parse_verbose(self):
        """Test parsing with verbose flag."""
        with patch("sys.argv", ["cloudrip", "example.com", "-v"]):
            args = parse_arguments()
            assert args.verbose is True

    def test_parse_quiet(self):
        """Test parsing with quiet flag."""
        with patch("sys.argv", ["cloudrip", "example.com", "-q"]):
            args = parse_arguments()
            assert args.quiet is True

    def test_parse_full_options(self):
        """Test parsing with all options."""
        with patch(
            "sys.argv",
            [
                "cloudrip",
                "example.com",
                "-w",
                "w1.txt",
                "-w",
                "w2.txt",
                "-t",
                "30",
                "-o",
                "report.yaml",
                "-f",
                "yaml",
                "-v",
            ],
        ):
            args = parse_arguments()
            assert args.domain == "example.com"
            assert args.wordlists == ["w1.txt", "w2.txt"]
            assert args.threads == 30
            assert args.output == "report.yaml"
            assert args.format == "yaml"
            assert args.verbose is True

    def test_parse_invalid_format(self):
        """Test parsing with invalid format."""
        with patch("sys.argv", ["cloudrip", "example.com", "-f", "invalid"]):
            with pytest.raises(SystemExit):
                parse_arguments()

    def test_parse_missing_domain(self):
        """Test parsing without domain."""
        with patch("sys.argv", ["cloudrip"]):
            with pytest.raises(SystemExit):
                parse_arguments()


class TestMain:
    """Tests for main function."""

    def test_main_default_wordlist(self):
        """Test main with default wordlist."""
        with patch("sys.argv", ["cloudrip", "example.com"]):
            with patch("cloudrip.cli.main.CloudRipCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli

                main()

                mock_cli_class.assert_called_once()
                call_kwargs = mock_cli_class.call_args[1]
                assert call_kwargs["wordlists"] == ["dom.txt"]
                mock_cli.run.assert_called_once()

    def test_main_custom_wordlists(self):
        """Test main with custom wordlists."""
        with patch("sys.argv", ["cloudrip", "example.com", "-w", "custom.txt"]):
            with patch("cloudrip.cli.main.CloudRipCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli

                main()

                call_kwargs = mock_cli_class.call_args[1]
                assert call_kwargs["wordlists"] == ["custom.txt"]

    def test_main_all_options(self):
        """Test main with all options."""
        with patch(
            "sys.argv",
            [
                "cloudrip",
                "test.com",
                "-w",
                "words.txt",
                "-t",
                "20",
                "-o",
                "out.json",
                "-f",
                "json",
                "-v",
            ],
        ):
            with patch("cloudrip.cli.main.CloudRipCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli

                main()

                call_kwargs = mock_cli_class.call_args[1]
                assert call_kwargs["domain"] == "test.com"
                assert call_kwargs["wordlists"] == ["words.txt"]
                assert call_kwargs["threads"] == 20
                assert call_kwargs["output_file"] == "out.json"
                assert call_kwargs["output_format"] == OutputFormat.JSON
                assert call_kwargs["verbose"] is True
