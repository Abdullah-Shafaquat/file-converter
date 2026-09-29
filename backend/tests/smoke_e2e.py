"""End-to-end smoke test against a running server on :8000."""

from __future__ import annotations

import io
import json
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

BASE = "http://localhost:8010"
OUT = Path(__file__).resolve().parent / "e2e"
OUT.mkdir(parents=True, exist_ok=True)


def post_multipart(path: str, filename: str, content: bytes, content_type: str) -> dict:
    boundary = "----smoke" + "0" * 20
    parts: list[bytes] = []
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode()
    )
    parts.append(f"Content-Type: {content_type}\r\n\r\n".encode())
    parts.append(content)
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    body = b"".join(parts)

    request = urllib.request.Request(
        f"{BASE}{path}", data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def get_json(path: str) -> dict:
    with urllib.request.urlopen(f"{BASE}{path}") as response:
        return json.load(response)


def post_json(path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def download(path: str) -> bytes:
    with urllib.request.urlopen(f"{BASE}{path}") as response:
        return response.read()


def convert_one(filename: str, content: bytes, target: str, content_type: str) -> tuple[bool, str]:
    info = post_multipart("/api/upload", filename, content, content_type)["data"]
    started = post_json(
        "/api/convert", {"file_id": info["id"], "target_format": target}
    )["data"]

    deadline = time.time() + 120
    job = {}
    while time.time() < deadline:
        job = get_json(f"/api/conversions/{started['id']}")["data"]
        if job["status"] in ("completed", "failed"):
            break
        time.sleep(0.2)

    if job.get("status") != "completed":
        return False, job.get("error") or job.get("status", "timeout")

    blob = download(f"/api/download/{started['id']}")
    if not blob:
        return False, "empty download"
    (OUT / job["output_name"]).write_bytes(blob)
    return True, f"{job['output_name']} ({len(blob)} bytes)"


def png_bytes(colour: str = "teal") -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (64, 48), colour).save(buffer, format="PNG")
    return buffer.getvalue()


def pdf_with_table() -> bytes:
    import tempfile

    from app.converters.document_model import ContentBlock, DocumentModel, Table
    from app.converters.document_writers import write_pdf

    table = Table(headers=["Region", "Sales"], rows=[["North", "120"], ["South", "95"]])
    model = DocumentModel(title="Sales")
    model.blocks.append(ContentBlock(kind="table", table=table))
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "s.pdf"
        write_pdf(model, path)
        return path.read_bytes()


def docx_bytes() -> bytes:
    from io import BytesIO

    from docx import Document

    document = Document()
    document.add_heading("Report", level=1)
    document.add_paragraph("Quarterly numbers are up.")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Item"
    table.cell(1, 0).text = "Widget"
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def zip_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("notes.txt", "hello archive")
        archive.writestr("data/values.csv", "a,b\n1,2\n")
    return buffer.getvalue()


CSV = b"name,score\nAli,9\nSara,8\n"
CASES = [
    ("scores.csv", CSV, "text/csv", "pdf"),
    ("scores.csv", CSV, "text/csv", "xlsx"),
    ("scores.csv", CSV, "text/csv", "json"),
    ("data.json", b'{"data":[{"a":"1","b":"2"}]}', "application/json", "csv"),
    ("notes.md", b"# Title\n\nSome text.", "text/markdown", "html"),
    ("notes.md", b"# Title\n\nSome text.", "text/markdown", "pdf"),
    ("photo.png", png_bytes(), "image/png", "webp"),
    ("photo.png", png_bytes("orange"), "image/png", "jpg"),
    ("photo.png", png_bytes("red"), "image/png", "tiff"),
    (
        "report.docx",
        docx_bytes(),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pdf",
    ),
    (
        "report.docx",
        docx_bytes(),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "txt",
    ),
    ("sales.pdf", pdf_with_table(), "application/pdf", "csv"),
    ("sales.pdf", pdf_with_table(), "application/pdf", "json"),
    ("sales.pdf", pdf_with_table(), "application/pdf", "docx"),
    ("bundle.zip", zip_bytes(), "application/zip", "tar"),
]


def main() -> int:
    failures = 0
    for filename, content, content_type, target in CASES:
        ok, detail = convert_one(filename, content, target, content_type)
        print(f"{'OK  ' if ok else 'FAIL'} {filename:>14} -> {target:<5} {detail}")
        if not ok:
            failures += 1

    print(f"\n{len(CASES) - failures}/{len(CASES)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
