"""Runtime settings. Every API key is optional; pipelines that need a missing key report `skipped`."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    # Threat-intel / recon keys
    shodan_api_key: str = ""
    censys_api_token: str = ""  # Censys Platform personal access token (preferred)
    censys_api_id: str = ""  # legacy Search API
    censys_api_secret: str = ""
    virustotal_api_key: str = ""
    abuseipdb_api_key: str = ""
    greynoise_api_key: str = ""  # community endpoint works without a key, but is rate-limited
    otx_api_key: str = ""
    urlscan_api_key: str = ""
    securitytrails_api_key: str = ""
    ipinfo_token: str = ""

    # Map-layer keys
    firms_map_key: str = ""
    aisstream_api_key: str = ""

    # Behaviour
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    pipeline_timeout_s: float = 20.0
    recon_cache_ttl_s: int = 3600
    max_upload_mb: int = 50
    user_agent: str = "osint-dashboard/0.1 (+infrastructure recon)"


@lru_cache
def get_settings() -> Settings:
    return Settings()
