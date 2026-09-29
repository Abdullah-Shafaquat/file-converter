"""Shared pytest fixtures: isolated temp dirs and a fresh app container."""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Set before any app module reads settings.
os.environ["APP_ENV"] = "test"


@pytest.fixture()
def temp_dirs(tmp_path: Path) -> Iterator[tuple[Path, Path]]:
    uploads = tmp_path / "uploads"
    outputs = tmp_path / "outputs"
    uploads.mkdir()
    outputs.mkdir()
    yield uploads, outputs


@pytest.fixture()
def settings(temp_dirs):
    from app.config import Settings

    uploads, outputs = temp_dirs
    return Settings(
        app_env="test",
        max_file_size_mb=2,
        file_retention_minutes=30,
        cleanup_interval_seconds=3600,
        upload_dir=uploads,
        output_dir=outputs,
        max_concurrent_jobs=2,
    )


@pytest.fixture()
def container(settings):
    from app.services import AppContainer

    instance = AppContainer.build(settings)
    yield instance
    instance.shutdown()


@pytest.fixture()
def client(container):
    """A TestClient wired to the isolated container."""
    from fastapi.testclient import TestClient

    import app.services as services_module
    from app.main import create_app

    app = create_app()
    # Routes depend on `app.services.get_container`, so override that exact
    # callable to keep test state out of the module-level singleton.
    app.dependency_overrides[services_module.get_container] = lambda: container

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def make_png_bytes(width: int = 8, height: int = 8, colour: str = "red") -> bytes:
    """Build a real in-memory PNG so image tests use genuine image data."""
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (width, height), colour).save(buffer, format="PNG")
    return buffer.getvalue()


def make_csv_bytes(rows: list[list[str]]) -> bytes:
    from io import StringIO

    import csv

    buffer = StringIO()
    csv.writer(buffer, lineterminator="\n").writerows(rows)
    return buffer.getvalue().encode("utf-8")
