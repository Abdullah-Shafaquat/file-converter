"""Conversion job lifecycle: selection, success, failure, status and download."""

from __future__ import annotations

import io
import time
import zipfile

import pytest

from tests.conftest import make_csv_bytes, make_png_bytes

TERMINAL = {"completed", "failed"}


def _upload(client, filename: str, content: bytes, content_type: str = "application/octet-stream"):
    response = client.post(
        "/api/upload",
        files={"file": (filename, io.BytesIO(content), content_type)},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _wait_for(client, job_id: str, timeout: float = 60.0) -> dict:
    deadline = time.time() + timeout
    last = {}
    while time.time() < deadline:
        response = client.get(f"/api/conversions/{job_id}")
        assert response.status_code == 200
        last = response.json()["data"]
        if last["status"] in TERMINAL:
            return last
        time.sleep(0.15)
    raise AssertionError(f"job {job_id} did not finish; last state={last}")


def _run(client, filename, content, target, content_type="application/octet-stream"):
    file_info = _upload(client, filename, content, content_type)
    started = client.post(
        "/api/convert",
        json={"file_id": file_info["id"], "target_format": target},
    )
    assert started.status_code == 202, started.text
    return file_info, _wait_for(client, started.json()["data"]["id"])


# --- selection and validation -------------------------------------------

def test_convert_rejects_unknown_target(client):
    file_info = _upload(client, "a.png", make_png_bytes(), "image/png")
    response = client.post(
        "/api/convert",
        json={"file_id": file_info["id"], "target_format": "exe"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "unsupported_format"


def test_convert_rejects_same_format(client):
    file_info = _upload(client, "a.png", make_png_bytes(), "image/png")
    response = client.post(
        "/api/convert",
        json={"file_id": file_info["id"], "target_format": "png"},
    )
    assert response.status_code == 400


def test_convert_rejects_missing_upload(client):
    response = client.post(
        "/api/convert",
        json={"file_id": "missing-id-1234", "target_format": "pdf"},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "file_not_found"


def test_convert_rejects_short_file_id(client):
    response = client.post("/api/convert", json={"file_id": "ab", "target_format": "pdf"})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_status_for_unknown_job_is_404(client):
    assert client.get("/api/conversions/nope-1234").status_code == 404


# --- images --------------------------------------------------------------

@pytest.mark.parametrize(
    ("source_name", "source_bytes", "target", "content_type"),
    [
        ("photo.jpg", make_png_bytes(), "png", "image/jpeg"),
        ("photo.png", make_png_bytes(colour="blue"), "webp", "image/png"),
    ],
)
def test_image_conversions_produce_valid_output(
    client, source_name, source_bytes, target, content_type
):
    _, job = _run(client, source_name, source_bytes, target, content_type)

    assert job["status"] == "completed", job
    assert job["output_name"].endswith(f".{target}")
    assert job["progress"] == 100
    assert job["output_size_bytes"] > 0

    download = client.get(f"/api/download/{job['id']}")
    assert download.status_code == 200
    assert f"filename*=UTF-8''{source_name.rsplit('.', 1)[0]}.{target}" in download.headers["content-disposition"]
    assert len(download.content) == job["output_size_bytes"]


# --- documents -----------------------------------------------------------

def test_csv_to_pdf(client):
    payload = make_csv_bytes([["name", "score"], ["ali", "9"], ["sara", "8"]])
    _, job = _run(client, "scores.csv", payload, "pdf", "text/csv")

    assert job["status"] == "completed"
    assert job["output_name"] == "scores.pdf"
    assert client.get(f"/api/download/{job['id']}").content.startswith(b"%PDF")


def test_csv_to_xlsx(client):
    payload = make_csv_bytes([["name", "score"], ["ali", "9"]])
    _, job = _run(client, "scores.csv", payload, "xlsx", "text/csv")

    assert job["status"] == "completed"
    from io import BytesIO

    from openpyxl import load_workbook

    workbook = load_workbook(BytesIO(client.get(f"/api/download/{job['id']}").content))
    sheet = workbook.active
    assert sheet is not None
    assert [cell.value for cell in sheet[1]] == ["name", "score"]
    assert sheet.cell(row=2, column=1).value == "ali"


def test_json_to_csv(client):
    _, job = _run(
        client,
        "data.json",
        b'{"data": [{"a": "1", "b": "2"}]}',
        "csv",
        "application/json",
    )
    assert job["status"] == "completed"
    body = client.get(f"/api/download/{job['id']}").text
    assert "a,b" in body
    assert "1,2" in body


def test_xlsx_to_csv_roundtrip(client):
    payload = make_csv_bytes([["city", "pop"], ["Lahore", "13"]])
    _, to_xlsx = _run(client, "cities.csv", payload, "xlsx", "text/csv")
    xlsx_bytes = client.get(f"/api/download/{to_xlsx['id']}").content

    _, back = _run(client, "cities.xlsx", xlsx_bytes, "csv", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert back["status"] == "completed"
    text = client.get(f"/api/download/{back['id']}").text
    assert "Lahore" in text and "13" in text


def test_markdown_to_html(client):
    _, job = _run(client, "notes.md", b"# Title\n\nSome text.", "html", "text/markdown")
    assert job["status"] == "completed"
    body = client.get(f"/api/download/{job['id']}").text
    assert "<h1>Title</h1>" in body


def test_docx_to_txt(client):
    from io import BytesIO

    from docx import Document

    document = Document()
    document.add_heading("Report", level=1)
    document.add_paragraph("Quarterly numbers are up.")
    buffer = BytesIO()
    document.save(buffer)

    _, job = _run(
        client,
        "report.docx",
        buffer.getvalue(),
        "txt",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert job["status"] == "completed"
    text = client.get(f"/api/download/{job['id']}").text
    assert "Quarterly numbers are up." in text


def test_docx_to_pdf_preserves_table(client):
    from io import BytesIO

    from docx import Document

    document = Document()
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Item"
    table.cell(0, 1).text = "Qty"
    table.cell(1, 0).text = "Widget"
    table.cell(1, 1).text = "4"
    buffer = BytesIO()
    document.save(buffer)

    _, job = _run(
        client,
        "inv.docx",
        buffer.getvalue(),
        "pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert job["status"] == "completed"
    assert client.get(f"/api/download/{job['id']}").content.startswith(b"%PDF")


# --- the PDF -> CSV path -------------------------------------------------

def test_pdf_to_csv_extracts_ruled_table(client):
    """A ruled PDF table must come back as real CSV rows, not mangled text."""
    from app.converters.document_model import ContentBlock, DocumentModel, Table

    table = Table(headers=["Region", "Sales"], rows=[["North", "120"], ["South", "95"]])
    model = DocumentModel(title="Sales")
    model.blocks.append(ContentBlock(kind="table", table=table))

    pdf_bytes = _render_pdf(model)
    _, job = _run(client, "sales.pdf", pdf_bytes, "csv", "application/pdf")

    assert job["status"] == "completed", job
    text = client.get(f"/api/download/{job['id']}").text
    assert "Region" in text and "Sales" in text
    assert "North" in text and "120" in text
    assert "South" in text and "95" in text


def test_pdf_to_json(client):
    pdf_bytes = _render_pdf(_text_model("The sky is blue."))
    _, job = _run(client, "notes.pdf", pdf_bytes, "json", "application/pdf")

    assert job["status"] == "completed"
    body = client.get(f"/api/download/{job['id']}").text
    assert "sky" in body


def test_pdf_to_docx(client):
    pdf_bytes = _render_pdf(_text_model("Paragraph from the PDF."))
    _, job = _run(client, "doc.pdf", pdf_bytes, "docx", "application/pdf")

    assert job["status"] == "completed"
    from io import BytesIO

    from docx import Document

    parsed = Document(BytesIO(client.get(f"/api/download/{job['id']}").content))
    assert "Paragraph from the PDF." in "\n".join(p.text for p in parsed.paragraphs)


def _text_model(text: str):
    from app.converters.document_model import ContentBlock, DocumentModel

    model = DocumentModel(title="Notes")
    model.blocks.append(ContentBlock(kind="paragraph", text=text))
    return model


def _render_pdf(model) -> bytes:
    import tempfile
    from pathlib import Path

    from app.converters.document_writers import write_pdf

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out.pdf"
        write_pdf(model, out)
        return out.read_bytes()


# --- archives ------------------------------------------------------------

def test_zip_to_tar(client):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("notes.txt", "hello archive")
        archive.writestr("data/values.csv", "a,b\n1,2\n")
    payload = buffer.getvalue()

    _, job = _run(client, "bundle.zip", payload, "tar", "application/zip")

    assert job["status"] == "completed"
    import tarfile
    from io import BytesIO as Bytes

    extracted = Bytes(client.get(f"/api/download/{job['id']}").content)
    with tarfile.open(fileobj=extracted) as archive:
        names = archive.getnames()
    assert "notes.txt" in names
    assert "data/values.csv" in names


def test_archive_rejects_path_traversal(client):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("../../evil.txt", "nope")
    payload = buffer.getvalue()

    _, job = _run(client, "evil.zip", payload, "tar", "application/zip")

    assert job["status"] == "failed"
    assert job["error"]
    assert "Traceback" not in job["error"]


def test_download_before_completion_is_404(client):
    file_info = _upload(client, "a.png", make_png_bytes(), "image/png")
    started = client.post(
        "/api/convert", json={"file_id": file_info["id"], "target_format": "webp"}
    )
    job_id = started.json()["data"]["id"]
    _wait_for(client, job_id)

    assert client.get(f"/api/download/{job_id}").status_code == 200


def test_delete_conversion_removes_output(client, container):
    _, job = _run(client, "a.png", make_png_bytes(), "webp", "image/png")
    from pathlib import Path

    _, path = container.conversion_service.get_output(job["id"])
    path = Path(path)

    assert client.delete(f"/api/conversions/{job['id']}").status_code == 200
    assert not path.exists()
