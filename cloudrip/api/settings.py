"""API settings with environment variable support."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """API configuration settings.

    Values can be set via environment variables or .env file.
    Environment variables are prefixed with CLOUDRIP_.
    """

    model_config = SettingsConfigDict(
        env_prefix="CLOUDRIP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server settings
    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = False
    workers: int = 1

    # CORS settings
    cors_origins: str = "*"

    # Scanning defaults
    default_threads: int = 10
    max_threads: int = 100
    max_batch_domains: int = 100

    # Remote wordlist settings
    max_wordlist_urls: int = 5
    max_wordlist_size: int = 10 * 1024 * 1024  # 10MB
    wordlist_timeout: int = 30  # seconds

    # Proxy settings (comma-separated SOCKS URLs)
    # Example: socks5://127.0.0.1:9050,socks5://127.0.0.1:9051
    proxies: str = ""
    proxy_rotate: bool = True

    @property
    def has_proxies(self) -> bool:
        """Check if proxies are configured."""
        return bool(self.proxies.strip())


settings = Settings()
