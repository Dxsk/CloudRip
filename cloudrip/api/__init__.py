"""FastAPI-based REST API for CloudRip.

To run the API server:
    python -m cloudrip.api.app

Or:
    from cloudrip.api import app, run_server
    run_server(host="0.0.0.0", port=8000)

Requires: pip install cloudrip[api]
"""

__all__: list[str] = []

try:
    from .app import app as app
    from .app import run_server as run_server
    from .routes import router as router

    __all__ = ["app", "router", "run_server"]
except ImportError:
    # FastAPI not installed - API features unavailable
    pass
