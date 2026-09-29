"""Registry, format metadata, security helpers, health and cleanup."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.converters import registry
from app.converters.base import ConverterRegistry
from app.converters.formats import BLOCKED_EXTENSIONS, canonical_extension, get_format
from app.models.schemas import Category
from app.utils.security import (
    build_output_name,
    resolve_within,
    sanitize_filename,
    split_extension,
)


# --- registry ------------------------------------------------------------

def test_registry_resolves_each_category():
    for source, target in [
        ("png", "jpg"),
        ("csv", "pdf"),
        ("zip", "tar"),
    ]:
        converter = registry.resolve(source, target)
        assert converter is not None
        assert converter.can_convert(source, target)


def test_registry_rejects_unknown_pair():
    from app.utils.errors import UnsupportedFormatError

    with pytest.raises(UnsupportedFormatError):
        registry.resolve("exe", "png")


def test_registry_rejects_identical_formats():
    from app.utils.errors import UnsupportedFormatError

    with pytest.raises(UnsupportedFormatError):
        registry.resolve("png", "png")


def test_targets_for_lists_only_valid_outputs():
    targets = registry.targets_for("png")
    assert "jpg" in targets and "webp" in targets
    assert "png" not in targets
    assert "csv" not in targets


def test_matrix_is_non_empty_and_sorted():
    matrix = registry.conversion_matrix()
    assert matrix
    assert "png" in matrix
    for key, targets in matrix.items():
        assert targets == sorted(targets), key
        assert key not in targets, f"{key} must not convert to itself"


def test_csv_and_pdf_are_mutually_convertible():
    matrix = registry.conversion_matrix()
    assert "pdf" in matrix["csv"], "CSV -> PDF must be supported"
    assert "csv" in matrix["pdf"], "PDF -> CSV must be supported"


def test_audio_and_video_are_not_advertised():
    matrix = registry.conversion_matrix()
    for removed in ("mp3", "mp4", "wav", "mkv", "flac"):
        assert removed not in matrix, f"{removed} should not be offered"


def test_custom_converter_can_be_registered():
    """Proves the plugin architecture: a new converter needs no other changes."""

    class FakeConverter(registry.all()[0].__class__):
        name = "fake"
        category = Category.DOCUMENT
        source_formats = frozenset({"aaa"})
        target_formats = frozenset({"bbb"})

        def convert(self, input_path, output_path, context=None):
            output_path.write_bytes(input_path.read_bytes())
            return output_path

    local = ConverterRegistry()
    local.register(FakeConverter())

    assert local.resolve("aaa", "bbb").name == "fake"
    assert local.targets_for("aaa") == ["bbb"]
    with pytest.raises(ValueError):
        local.register(FakeConverter())


# --- format metadata -----------------------------------------------------

def test_alias_normalisation():
    assert canonical_extension("JPEG") == "jpg"
    assert canonical_extension(".TIF") == "tiff"
    assert canonical_extension("htm") == "html"
    assert canonical_extension("yml") == "yaml"


def test_formats_carry_category_and_mime():
    png = get_format("png")
    pdf = get_format("pdf")
    archive = get_format("zip")
    assert png is not None and png.category is Category.IMAGE
    assert pdf is not None and pdf.category is Category.DOCUMENT
    assert archive is not None and archive.category is Category.ARCHIVE
    assert "image/png" in png.mime_types


def test_dangerous_extensions_are_blocked():
    for extension in ("exe", "bat", "ps1", "sh", "jar", "msi"):
        assert extension in BLOCKED_EXTENSIONS


# --- security helpers ----------------------------------------------------

@pytest.mark.parametrize(
    "raw",
    [
        "../../etc/passwd",
        r"C:\Windows\System32\cmd.exe",
        "....//....//etc/shadow",
        "name with spaces.txt",
        "..",
        "CON.txt",
    ],
)
def test_sanitize_filename_neutralises_traversal(raw):
    cleaned = sanitize_filename(raw)
    assert "/" not in cleaned
    assert "\\" not in cleaned
    assert ".." not in cleaned


def test_split_extension():
    assert split_extension("photo.PNG") == "png"
    assert split_extension("archive.tar.gz") == "gz"
    assert split_extension("noext") == ""


def test_build_output_name_keeps_stem():
    assert build_output_name("holiday-photo.jpg", "png") == "holiday-photo.png"
    assert build_output_name("report.pdf", "docx") == "report.docx"
    assert build_output_name("data.tar.gz", "zip") == "data.tar.zip"


def test_resolve_within_blocks_escape(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    assert resolve_within(base, "ok.txt").parent == base.resolve()

    with pytest.raises(ValueError):
        resolve_within(base, "..", "outside.txt")


def test_download_filename_is_sanitised(tmp_path):
    # A hostile upload name must not leak into the Content-Disposition header.
    assert "/" not in build_output_name("../../evil.png", "jpg")


# --- API surface ---------------------------------------------------------

def test_health_reports_dependencies(client):
    response = client.get("/api/health")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "ok"
    assert "converters" in body
    assert body["supported_conversions"] > 0
    assert "python_packages" in body["dependencies"]


def test_formats_endpoint_shape(client):
    response = client.get("/api/formats")
    assert response.status_code == 200

    data = response.json()["data"]
    assert data["max_file_size_mb"] > 0
    assert {category["id"] for category in data["categories"]} >= {
        "document",
        "image",
        "archive",
    }
    assert "png" in data["conversions"]
    assert "libreoffice" in data["external_tools"]


def test_unknown_endpoint_returns_json_error(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.json()["success"] is False
    assert "Traceback" not in response.text


# --- cleanup -------------------------------------------------------------

def test_cleanup_removes_expired_files(container, settings):
    uploads, outputs = settings.upload_dir, settings.output_dir

    stale_upload = uploads / "stale.bin"
    stale_upload.write_bytes(b"x")
    stale_output = outputs / "stale-out.bin"
    stale_output.write_bytes(b"y")

    old = time.time() - (settings.file_retention_minutes * 60 + 120)
    for path in (stale_upload, stale_output):
        import os

        os.utime(path, (old, old))

    removed = container.cleanup_service.run_once()

    assert removed["uploads"] >= 1
    assert removed["outputs"] >= 1
    assert not stale_upload.exists()
    assert not stale_output.exists()


def test_cleanup_keeps_fresh_files(container, settings):
    fresh = settings.upload_dir / "fresh.bin"
    fresh.write_bytes(b"keep me")

    container.cleanup_service.run_once()
    assert fresh.exists()


def test_cleanup_removes_expired_store_entries(container, settings):
    from app.models.schemas import UploadedFileInfo
    from datetime import datetime, timedelta, timezone

    old_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    info = UploadedFileInfo(
        id="expired-id",
        original_name="a.png",
        extension="png",
        category=Category.IMAGE,
        size_bytes=1,
        available_formats=["jpg"],
        uploaded_at=old_time,
    )
    path = settings.upload_dir / "expired-id.png"
    path.write_bytes(b"x")
    container.store.save_upload(info, str(path))

    container.cleanup_service.run_once()
    assert container.store.get_upload("expired-id") is None
    assert not path.exists()
