"""Upload validation, format detection and file-size limits."""

from __future__ import annotations

import io

from tests.conftest import make_csv_bytes, make_png_bytes


def _upload(client, filename: str, content: bytes, content_type: str = "application/octet-stream"):
    return client.post(
        "/api/upload",
        files={"file": (filename, io.BytesIO(content), content_type)},
    )


def test_upload_png_returns_detected_formats(client):
    response = _upload(client, "holiday-photo.png", make_png_bytes(), "image/png")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["original_name"] == "holiday-photo.png"
    assert data["extension"] == "png"
    assert data["category"] == "image"
    assert data["size_bytes"] > 0
    assert "jpg" in data["available_formats"]
    assert "webp" in data["available_formats"]


def test_upload_csv_is_detected_as_document(client):
    payload = make_csv_bytes([["name", "score"], ["ali", "9"], ["sara", "8"]])
    response = _upload(client, "scores.csv", payload, "text/csv")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["category"] == "document"
    assert "pdf" in data["available_formats"]
    assert "xlsx" in data["available_formats"]


def test_upload_pdf_is_detected(client):
    from app.converters.document_writers import DocumentModel, write_pdf

    from tests.conftest import BACKEND_ROOT

    pdf_bytes = _pdf_bytes(DocumentModel, write_pdf, BACKEND_ROOT)
    response = _upload(client, "report.pdf", pdf_bytes, "application/pdf")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["extension"] == "pdf"
    assert "docx" in data["available_formats"]
    assert "csv" in data["available_formats"]


def _pdf_bytes(document_model_cls, write_pdf, backend_root):
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "sample.pdf"
        model = document_model_cls(title="Sample")
        model.blocks.append(_block("Paragraph one."))
        model.blocks.append(_block("Paragraph two."))
        write_pdf(model, out)
        return out.read_bytes()


def _block(text: str):
    from app.converters.document_model import ContentBlock

    return ContentBlock(kind="paragraph", text=text)


def test_rejects_unsupported_extension(client):
    response = _upload(client, "virus.exe", b"MZ\x90\x00binary", "application/octet-stream")

    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["code"] == "unsupported_format"
    assert "not supported" in body["error"]


def test_rejects_executable_even_with_known_type(client):
    response = _upload(client, "payload.png.exe", b"MZ", "image/png")
    assert response.status_code == 400
    assert response.json()["code"] == "unsupported_format"


def test_rejects_mime_extension_mismatch(client):
    response = _upload(client, "notes.png", b"%PDF-1.4 not really a png", "application/pdf")

    assert response.status_code == 400
    assert response.json()["code"] == "unsupported_format"


def test_rejects_file_over_size_limit(client):
    # container fixture caps uploads at 2 MB.
    oversized = b"\x00" * (3 * 1024 * 1024)
    response = _upload(client, "big.png", oversized, "image/png")

    assert response.status_code == 413
    body = response.json()
    assert body["code"] == "file_too_large"
    assert "maximum" in body["error"].lower()


def test_rejects_empty_file(client):
    response = _upload(client, "empty.png", b"", "image/png")
    assert response.status_code == 400
    assert response.json()["code"] == "unsupported_format"


def test_rejects_file_without_extension(client):
    response = _upload(client, "noextension", b"data", "application/octet-stream")
    assert response.status_code == 400
    assert response.json()["code"] == "unsupported_format"


def test_stored_name_is_randomised(client, container):
    response = _upload(client, "../../../etc/passwd.png", make_png_bytes(), "image/png")

    assert response.status_code == 200
    file_id = response.json()["data"]["id"]
    # The echoed name is sanitised for display, but the path on disk is opaque.
    assert "/" not in response.json()["data"]["original_name"]
    assert ".." not in response.json()["data"]["original_name"]

    stored = next(p for _, p in container.store.all_uploads())
    assert stored.startswith(str(container.settings.upload_dir))
    assert file_id in stored


def test_missing_file_returns_404(client):
    response = client.get("/api/files/does-not-exist-1234")
    assert response.status_code == 404
    assert response.json()["code"] == "file_not_found"


def test_delete_upload_removes_file(client, container):
    response = _upload(client, "shot.png", make_png_bytes(), "image/png")
    file_id = response.json()["data"]["id"]
    _, path = container.file_service.get_upload(file_id)

    deleted = client.delete(f"/api/files/{file_id}")
    assert deleted.status_code == 200
    assert not path.exists()
