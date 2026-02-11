from __future__ import annotations

from dataclasses import dataclass
import os
from urllib.parse import urlparse


def _normalize_registry_url(raw: str | None) -> str:
    value = (raw or "").strip()
    if not value:
        value = "http://192.168.5.54:5000"
    if not value.startswith(("http://", "https://")):
        value = f"http://{value}"
    return value.rstrip("/")


def _resolve_push_host(registry_url: str, explicit_push_host: str | None) -> str:
    if explicit_push_host:
        return (
            explicit_push_host.strip()
            .removeprefix("http://")
            .removeprefix("https://")
            .rstrip("/")
        )
    parsed = urlparse(registry_url)
    return parsed.netloc or parsed.path


@dataclass(frozen=True)
class Settings:
    registry_api_url: str
    registry_push_host: str
    request_timeout_sec: float
    max_catalog_results: int
    sync_job_retention: int


def load_settings() -> Settings:
    registry_api_url = _normalize_registry_url(os.getenv("REGISTRY_API_URL"))
    registry_push_host = _resolve_push_host(
        registry_api_url,
        os.getenv("REGISTRY_PUSH_HOST"),
    )
    request_timeout_sec = float(os.getenv("REQUEST_TIMEOUT_SEC", "20"))
    max_catalog_results = int(os.getenv("MAX_CATALOG_RESULTS", "200"))
    sync_job_retention = int(os.getenv("SYNC_JOB_RETENTION", "120"))
    return Settings(
        registry_api_url=registry_api_url,
        registry_push_host=registry_push_host,
        request_timeout_sec=request_timeout_sec,
        max_catalog_results=max_catalog_results,
        sync_job_retention=sync_job_retention,
    )
