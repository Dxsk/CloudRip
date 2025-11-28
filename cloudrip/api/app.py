"""FastAPI application for CloudRip API."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router
from .settings import settings

app = FastAPI(
    title="CloudRip API",
    description="""
CloudRip API - Find real IP addresses behind Cloudflare.

## Features

- **Async Scanning**: Start scans and retrieve results asynchronously
- **Quick Check**: Instantly check if a domain is behind Cloudflare
- **Batch Check**: Check multiple domains at once
- **Progress Tracking**: Monitor scan progress in real-time

## Usage

### Start a scan
```bash
curl -X POST "http://localhost:8000/api/v1/scan" \\
  -H "Content-Type: application/json" \\
  -d '{"domain": "example.com", "threads": 20}'
```

### Check scan status
```bash
curl "http://localhost:8000/api/v1/scan/{job_id}"
```

### Quick domain check
```bash
curl -X POST "http://localhost:8000/api/v1/check" \\
  -H "Content-Type: application/json" \\
  -d '{"domain": "www.example.com"}'
```
    """,
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware for browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(router, prefix="/api/v1")


@app.get("/", tags=["Root"])
async def root() -> dict[str, str]:
    """Root endpoint with API information."""
    return {
        "name": "CloudRip API",
        "version": "3.0.0",
        "docs": "/docs",
        "health": "/api/v1/health",
    }


def run_server(
    host: str | None = None,
    port: int | None = None,
    reload: bool | None = None,
    workers: int | None = None,
) -> None:
    """Run the API server.

    Args:
        host: Host to bind to (default: from settings/env)
        port: Port to bind to (default: from settings/env)
        reload: Enable auto-reload (default: from settings/env)
        workers: Number of workers (default: from settings/env)
    """
    import uvicorn

    uvicorn.run(
        "cloudrip.api.app:app",
        host=host or settings.host,
        port=port or settings.port,
        reload=reload if reload is not None else settings.reload,
        workers=workers or settings.workers,
    )


if __name__ == "__main__":
    run_server()
