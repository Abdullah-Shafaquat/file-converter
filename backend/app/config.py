"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_ROOT / ".env", BACKEND_ROOT.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_name: str = "Universal File Converter"
    api_prefix: str = "/api"

    max_file_size_mb: int = 100
    file_retention_minutes: int = 30
    cleanup_interval_seconds: int = 300

    upload_dir: Path = BACKEND_ROOT / "temp" / "uploads"
    output_dir: Path = BACKEND_ROOT / "temp" / "outputs"

    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    libreoffice_path: str = "soffice"

    # NoDecode keeps pydantic-settings from JSON-parsing this before our
    # validator runs; a comma-separated CORS list is not valid JSON.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    conversion_timeout_seconds: int = 900
    max_concurrent_jobs: int = 4

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        # Accept a JSON array, a comma-separated list, or a real list.
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("["):
                import json

                try:
                    return json.loads(text)
                except ValueError:
                    pass
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("upload_dir", "output_dir", mode="before")
    @classmethod
    def _resolve_dir(cls, value: object) -> object:
        if isinstance(value, str) and not Path(value).is_absolute():
            return (BACKEND_ROOT / value).resolve()
        return value

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    def ensure_directories(self) -> None:
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
