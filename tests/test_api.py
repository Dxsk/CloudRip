"""Tests for cloudrip.api module."""

from unittest.mock import MagicMock, patch

import pytest

from cloudrip.core.models import ResolveResult


# Skip all tests if FastAPI not installed
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from cloudrip.api.app import app
from cloudrip.api import routes
from cloudrip.api.schemas import ScanStatus


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_state():
    """Reset global state between tests."""
    routes._scan_jobs.clear()
    routes._cf_ranges = None
    yield
    routes._scan_jobs.clear()
    routes._cf_ranges = None


class TestHealthEndpoint:
    """Tests for /api/v1/health endpoint."""

    def test_health_check(self, client):
        """Test health check returns OK."""
        with patch.object(routes, "get_cf_ranges") as mock_cf:
            mock_ranges = MagicMock()
            mock_ranges.is_loaded = True
            mock_ranges.range_count = (15, 7)
            mock_cf.return_value = mock_ranges

            response = client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == "3.0.0"
        assert data["cf_ranges_loaded"] is True


class TestRootEndpoint:
    """Tests for / endpoint."""

    def test_root(self, client):
        """Test root endpoint."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "CloudRip API"
        assert "docs" in data


class TestQuickCheckEndpoint:
    """Tests for /api/v1/check endpoint."""

    def test_quick_check(self, client):
        """Test quick domain check."""
        mock_result = ResolveResult(
            domain="test.example.com",
            ipv4=["192.168.1.1"],
            ipv6=[],
            status="found",
        )

        with patch.object(routes, "get_cf_ranges") as mock_cf:
            mock_ranges = MagicMock()
            mock_cf.return_value = mock_ranges

            with patch(
                "cloudrip.api.routes.DNSResolver.resolve_domain",
                return_value=mock_result,
            ):
                response = client.post(
                    "/api/v1/check",
                    json={"domain": "test.example.com"},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["domain"] == "test.example.com"
        assert "192.168.1.1" in data["ipv4"]

    def test_quick_check_cloudflare(self, client):
        """Test quick check for Cloudflare domain."""
        mock_result = ResolveResult(
            domain="cf.example.com",
            ipv4=["104.16.1.1"],
            ipv6=[],
            status="cloudflare",
            ipv4_cloudflare=["104.16.1.1"],
        )

        with patch.object(routes, "get_cf_ranges") as mock_cf:
            mock_ranges = MagicMock()
            mock_cf.return_value = mock_ranges

            with patch(
                "cloudrip.api.routes.DNSResolver.resolve_domain",
                return_value=mock_result,
            ):
                response = client.post(
                    "/api/v1/check",
                    json={"domain": "cf.example.com"},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["is_cloudflare"] is True


class TestBatchCheckEndpoint:
    """Tests for /api/v1/check/batch endpoint."""

    def test_batch_check(self, client):
        """Test batch domain check."""
        mock_result = ResolveResult(
            domain="test.example.com",
            ipv4=["192.168.1.1"],
            status="found",
        )

        with patch.object(routes, "get_cf_ranges") as mock_cf:
            mock_ranges = MagicMock()
            mock_cf.return_value = mock_ranges

            with patch(
                "cloudrip.api.routes.DNSResolver.resolve_domain",
                return_value=mock_result,
            ):
                response = client.post(
                    "/api/v1/check/batch",
                    json=["test1.example.com", "test2.example.com"],
                )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_batch_check_limit(self, client):
        """Test batch check rejects too many domains."""
        domains = [f"test{i}.example.com" for i in range(101)]

        response = client.post("/api/v1/check/batch", json=domains)

        assert response.status_code == 400
        assert "100" in response.json()["detail"]


class TestScanEndpoints:
    """Tests for /api/v1/scan endpoints."""

    def test_start_scan(self, client):
        """Test starting a scan."""
        with patch.object(routes, "get_cf_ranges") as mock_cf:
            mock_ranges = MagicMock()
            mock_ranges.is_loaded = True
            mock_cf.return_value = mock_ranges

            # Mock background task to not actually run scan
            with patch.object(routes, "_run_scan_job"):
                response = client.post(
                    "/api/v1/scan",
                    json={"domain": "example.com", "threads": 5},
                )

        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["domain"] == "example.com"
        assert data["status"] == "pending"

    def test_get_scan_status(self, client):
        """Test getting scan status."""
        # First create a scan
        with patch.object(routes, "get_cf_ranges") as mock_cf:
            mock_ranges = MagicMock()
            mock_cf.return_value = mock_ranges

            with patch.object(routes, "_run_scan_job"):
                create_response = client.post(
                    "/api/v1/scan",
                    json={"domain": "example.com"},
                )
                job_id = create_response.json()["job_id"]

                # Then get status
                response = client.get(f"/api/v1/scan/{job_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id

    def test_get_scan_not_found(self, client):
        """Test getting non-existent scan."""
        response = client.get("/api/v1/scan/nonexistent-id")

        assert response.status_code == 404

    def test_cancel_scan(self, client):
        """Test canceling a scan."""
        # Create a scan
        with patch.object(routes, "get_cf_ranges") as mock_cf:
            mock_ranges = MagicMock()
            mock_cf.return_value = mock_ranges

            with patch.object(routes, "_run_scan_job"):
                create_response = client.post(
                    "/api/v1/scan",
                    json={"domain": "example.com"},
                )
                job_id = create_response.json()["job_id"]

                # Mark as running to test cancel
                routes._scan_jobs[job_id]["status"] = ScanStatus.RUNNING

                # Cancel
                response = client.delete(f"/api/v1/scan/{job_id}")

        assert response.status_code == 200
        assert routes._scan_jobs[job_id]["status"] == ScanStatus.CANCELLED

    def test_cancel_scan_not_found(self, client):
        """Test canceling non-existent scan."""
        response = client.delete("/api/v1/scan/nonexistent-id")

        assert response.status_code == 404


class TestListScansEndpoint:
    """Tests for /api/v1/scans endpoint."""

    def test_list_scans_empty(self, client):
        """Test listing scans when empty."""
        response = client.get("/api/v1/scans")

        assert response.status_code == 200
        data = response.json()
        assert data["jobs"] == []
        assert data["total"] == 0

    def test_list_scans(self, client):
        """Test listing scans."""
        with patch.object(routes, "get_cf_ranges") as mock_cf:
            mock_ranges = MagicMock()
            mock_cf.return_value = mock_ranges

            with patch.object(routes, "_run_scan_job"):
                # Create some scans
                client.post("/api/v1/scan", json={"domain": "example1.com"})
                client.post("/api/v1/scan", json={"domain": "example2.com"})

                response = client.get("/api/v1/scans")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["jobs"]) == 2

    def test_list_scans_with_limit(self, client):
        """Test listing scans with limit."""
        with patch.object(routes, "get_cf_ranges") as mock_cf:
            mock_ranges = MagicMock()
            mock_cf.return_value = mock_ranges

            with patch.object(routes, "_run_scan_job"):
                for i in range(5):
                    client.post("/api/v1/scan", json={"domain": f"example{i}.com"})

                response = client.get("/api/v1/scans?limit=2")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["jobs"]) == 2


class TestClearCompletedEndpoint:
    """Tests for /api/v1/scans/completed endpoint."""

    def test_clear_completed(self, client):
        """Test clearing completed scans."""
        with patch.object(routes, "get_cf_ranges") as mock_cf:
            mock_ranges = MagicMock()
            mock_cf.return_value = mock_ranges

            with patch.object(routes, "_run_scan_job"):
                # Create a scan and mark as completed
                create_response = client.post(
                    "/api/v1/scan",
                    json={"domain": "example.com"},
                )
                job_id = create_response.json()["job_id"]
                routes._scan_jobs[job_id]["status"] = ScanStatus.COMPLETED

                # Clear
                response = client.delete("/api/v1/scans/completed")

        assert response.status_code == 200
        data = response.json()
        assert data["cleared"] == 1
        assert job_id not in routes._scan_jobs
