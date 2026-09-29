"""Readers: parse an input file into a :class:`DocumentModel`."""

from __future__ import annotations

import csv
import io
import json
import logging
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

from app.converters.document_model import (
    ContentBlock,
    DocumentModel,
    Table,
    parse_delimited,
    text_to_table,
)
from app.utils.errors import ConversionFailedError, DependencyMissingError

logger = logging.getLogger(__name__)

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
LIST_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$")
FENCE_RE = re.compile(r"^\s*```")


# --- text-like -----------------------------------------------------------

def read_txt(path: Path, title: str) -> DocumentModel:
    text = _read_text(path)
    model = DocumentModel(title=title)
    for block in _blocks_from_text(text):
        model.blocks.append(block)
    return model


def read_markdown(path: Path, title: str) -> DocumentModel:
    text = _read_text(path)
    model = DocumentModel(title=title)
    in_fence = False
    fence_buffer: list[str] = []
    buffer: list[str] = []

    def flush_paragraph() -> None:
        if buffer:
            joined = "\n".join(buffer).strip()
            if joined:
                model.blocks.append(ContentBlock(kind="paragraph", text=joined))
            buffer.clear()

    for line in text.splitlines():
        if FENCE_RE.match(line):
            if in_fence:
                model.blocks.append(ContentBlock(kind="code", text="\n".join(fence_buffer)))
                fence_buffer.clear()
                in_fence = False
            else:
                flush_paragraph()
                in_fence = True
            continue
        if in_fence:
            fence_buffer.append(line)
            continue

        heading = HEADING_RE.match(line)
        if heading:
            flush_paragraph()
            level = len(heading.group(1))
            model.blocks.append(
                ContentBlock(kind="heading", text=heading.group(2).strip(), level=level)
            )
            continue

        list_match = LIST_RE.match(line)
        if list_match:
            flush_paragraph()
            if model.blocks and model.blocks[-1].kind == "list":
                model.blocks[-1].items.append(list_match.group(1).strip())
            else:
                model.blocks.append(
                    ContentBlock(kind="list", items=[list_match.group(1).strip()])
                )
            continue

        if not line.strip():
            flush_paragraph()
            continue

        buffer.append(line)

    flush_paragraph()
    if in_fence and fence_buffer:
        model.blocks.append(ContentBlock(kind="code", text="\n".join(fence_buffer)))
    return model


def read_html(path: Path, title: str) -> DocumentModel:
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise DependencyMissingError("HTML conversion requires 'beautifulsoup4'.") from exc

    soup = BeautifulSoup(_read_text(path, errors="replace"), "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    document_title = title
    if soup.title and soup.title.string and soup.title.string.strip():
        document_title = soup.title.string.strip()

    model = DocumentModel(title=document_title)
    for element in soup.body.descendants if soup.body else soup.descendants:
        if not getattr(element, "name", None):
            continue
        name = element.name.lower()

        if re.fullmatch(r"h[1-6]", name):
            text = element.get_text(" ", strip=True)
            if text:
                model.blocks.append(
                    ContentBlock(kind="heading", text=text, level=int(name[1]))
                )
        elif name in ("ul", "ol") and not element.find_parent(["ul", "ol"]):
            items = [
                li.get_text(" ", strip=True) for li in element.find_all("li", recursive=False)
            ]
            items = [item for item in items if item]
            if items:
                model.blocks.append(ContentBlock(kind="list", items=items))
        elif name == "table" and not element.find_parent("table"):
            table = _table_from_html(element)
            if table is not None:
                model.blocks.append(ContentBlock(kind="table", table=table))
                model.tables.append(table)
        elif name in ("p", "div", "section", "article", "blockquote") and not element.find(
            ["p", "div", "section", "article", "blockquote", "table", "ul", "ol"]
        ):
            text = element.get_text(" ", strip=True)
            if text:
                model.blocks.append(ContentBlock(kind="paragraph", text=text))

    if not model.blocks:
        text = soup.get_text("\n", strip=True)
        for block in _blocks_from_text(text):
            model.blocks.append(block)
    return model


def _table_from_html(element: Any) -> Table | None:
    headers: list[str] = []
    rows: list[list[str]] = []
    head_cells = element.find_all("th")
    if head_cells:
        headers = [cell.get_text(" ", strip=True) for cell in head_cells]
    for row_element in element.find_all("tr"):
        cells = row_element.find_all(["td", "th"])
        if not cells:
            continue
        values = [cell.get_text(" ", strip=True) for cell in cells]
        if headers and not rows and all(cell.name == "th" for cell in cells):
            continue
        rows.append(values)
    if not headers and not rows:
        return None
    return Table(headers=headers, rows=rows).normalize()


# --- structured data -----------------------------------------------------

def read_csv(path: Path, title: str, delimiter: str = ",") -> DocumentModel:
    rows = parse_delimited(_read_text(path, errors="replace"), delimiter)
    if not rows:
        return DocumentModel(title=title)
    table = Table(headers=rows[0], rows=rows[1:]).normalize()
    return DocumentModel(title=title, tables=[table], blocks=[ContentBlock(kind="table", table=table)])


def read_tsv(path: Path, title: str) -> DocumentModel:
    return read_csv(path, title, delimiter="\t")


def read_json(path: Path, title: str) -> DocumentModel:
    raw = _read_text(path, errors="replace")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConversionFailedError(f"This file is not valid JSON: {exc.msg} (line {exc.lineno}).") from exc

    table = _table_from_json(data)
    model = DocumentModel(title=title)
    if table is not None:
        model.tables.append(table)
        model.blocks.append(ContentBlock(kind="table", table=table))
        return model

    for record in _records_from_json(data):
        if isinstance(record, dict):
            lines = [f"{key}: {_display(value)}" for key, value in record.items()]
        else:
            lines = [_display(record)]
        model.blocks.append(ContentBlock(kind="paragraph", text="\n".join(lines)))
    return model


def _records_from_json(data: Any) -> list[Any]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("data", "items", "records", "results", "rows"):
            value = data.get(key)
            if isinstance(value, list):
                return value
        return [data]
    return [data]


def _table_from_json(data: Any) -> Table | None:
    records = _records_from_json(data)
    if not records or not all(isinstance(item, dict) for item in records):
        return None
    return Table.from_records(records)


def _display(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, float):
        text = f"{value:.10f}".rstrip("0").rstrip(".")
        return text or "0"
    return str(value)


def read_yaml(path: Path, title: str) -> DocumentModel:
    raw = _read_text(path, errors="replace")
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        return read_txt(path, title)
    try:
        data = yaml.safe_load(raw)
    except Exception as exc:  # noqa: BLE001
        raise ConversionFailedError(f"This file is not valid YAML: {exc}") from exc
    return _document_from_generic(data, title)


def read_xml(path: Path, title: str) -> DocumentModel:
    raw = _read_text(path, errors="replace")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ConversionFailedError(f"This file is not valid XML: {exc}") from exc

    model = DocumentModel(title=title)
    rows: list[list[str]] = []
    for element in root.iter():
        children = list(element)
        if children and all(len(list(child)) == 0 for child in children):
            rows.append([element.tag, *(child.text or "" for child in children)])
    if rows:
        table = Table(headers=rows[0], rows=rows[1:]).normalize()
        model.tables.append(table)
        model.blocks.append(ContentBlock(kind="table", table=table))
        return model

    text = "\n".join(
        f"{element.tag}: {(element.text or '').strip()}" for element in root.iter()
    )
    return read_xml_text_fallback(text, title)


def read_xml_text_fallback(text: str, title: str) -> DocumentModel:
    model = DocumentModel(title=title)
    for block in _blocks_from_text(text):
        model.blocks.append(block)
    return model


def _document_from_generic(data: Any, title: str) -> DocumentModel:
    table = _table_from_json(data)
    model = DocumentModel(title=title)
    if table is not None:
        model.tables.append(table)
        model.blocks.append(ContentBlock(kind="table", table=table))
        return model
    if isinstance(data, (dict, list)):
        text = json.dumps(data, indent=2, ensure_ascii=False)
    else:
        text = _display(data)
    for block in _blocks_from_text(text):
        model.blocks.append(block)
    return model


# --- office --------------------------------------------------------------

def read_docx(path: Path, title: str) -> DocumentModel:
    try:
        import docx  # type: ignore[import-untyped]
        from docx.table import Table as DocxTable
        from docx.text.paragraph import Paragraph
    except ImportError as exc:
        raise DependencyMissingError("DOCX conversion requires the 'python-docx' package.") from exc

    try:
        document = docx.Document(str(path))
    except Exception as exc:  # noqa: BLE001
        raise ConversionFailedError(f"Could not read this DOCX file: {exc}") from exc

    model = DocumentModel(title=title)
    for child in document.element.body.iterchildren():
        if child.tag.endswith("}p"):
            paragraph = Paragraph(child, document)
            style = (paragraph.style.name or "").lower() if paragraph.style else ""
            text = paragraph.text.strip()
            if not text:
                continue
            heading_match = re.fullmatch(r"heading (\d)", style)
            if heading_match:
                model.blocks.append(
                    ContentBlock(kind="heading", text=text, level=int(heading_match.group(1)))
                )
            elif style == "title":
                model.title = text
                model.blocks.append(ContentBlock(kind="heading", text=text, level=1))
            elif "list" in style:
                model.blocks.append(ContentBlock(kind="list", items=[text]))
            else:
                model.blocks.append(ContentBlock(kind="paragraph", text=text))
        elif child.tag.endswith("}tbl"):
            table = _table_from_docx(DocxTable(child, document))
            if table is not None:
                model.blocks.append(ContentBlock(kind="table", table=table))
                model.tables.append(table)
    return model


def _table_from_docx(table: Any) -> Table | None:
    rows: list[list[str]] = []
    for row in table.rows:
        rows.append([cell.text.strip() for cell in row.cells])
    if not rows:
        return None
    return Table(headers=rows[0], rows=rows[1:]).normalize()


def read_xlsx(path: Path, title: str) -> DocumentModel:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise DependencyMissingError("Spreadsheet conversion requires 'openpyxl'.") from exc

    try:
        workbook = load_workbook(str(path), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001
        raise ConversionFailedError(f"Could not read this spreadsheet: {exc}") from exc

    model = DocumentModel(title=title)
    try:
        for sheet in workbook.worksheets:
            rows: list[list[str]] = []
            for row in sheet.iter_rows(values_only=True):
                if row is None:
                    continue
                cells = ["" if cell is None else _display(cell) for cell in row]
                while cells and not cells[-1].strip():
                    cells.pop()
                if cells:
                    rows.append(cells)
            if not rows:
                continue
            if len(workbook.worksheets) > 1:
                model.blocks.append(
                    ContentBlock(kind="heading", text=sheet.title, level=2)
                )
            table = Table(headers=rows[0], rows=rows[1:]).normalize()
            model.blocks.append(ContentBlock(kind="table", table=table))
            model.tables.append(table)
    finally:
        workbook.close()
    return model


# --- pdf -----------------------------------------------------------------

def read_pdf(path: Path, title: str) -> DocumentModel:
    """Extract text and ruled tables from a PDF, page by page.

    Uses pdfplumber so that 100+ page files stream instead of being fully
    materialised in memory.
    """
    try:
        import pdfplumber
    except ImportError as exc:
        raise DependencyMissingError("PDF conversion requires the 'pdfplumber' package.") from exc

    model = DocumentModel(title=title)
    try:
        with pdfplumber.open(str(path)) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                if page_number % 10 == 0:
                    logger.debug("pdf extraction reached page %s", page_number)
                try:
                    tables = page.extract_tables()
                except Exception:  # noqa: BLE001 - malformed tables are not fatal
                    tables = []
                for raw_table in tables:
                    table = _clean_extracted_table(raw_table)
                    if table is not None:
                        model.tables.append(table)
                        model.blocks.append(ContentBlock(kind="table", table=table))
                        continue
                try:
                    text = page.extract_text() or ""
                except Exception:  # noqa: BLE001
                    text = ""
                if text.strip():
                    model.blocks.extend(_blocks_from_text(text))
    except ConversionFailedError:
        raise
    except Exception as exc:  # noqa: BLE001
        if "password" in str(exc).lower() or "encrypt" in str(exc).lower():
            raise ConversionFailedError(
                "This PDF is password protected. Remove the password and try again."
            ) from exc
        raise ConversionFailedError(f"Could not read this PDF file: {exc}") from exc

    if not model.blocks:
        raise ConversionFailedError(
            "No text or tables could be extracted from this PDF. "
            "It is most likely a scanned image PDF, which needs OCR."
        )
    return model


def _clean_extracted_table(raw: list[list[Any]]) -> Table | None:
    rows: list[list[str]] = []
    for raw_row in raw:
        if not raw_row:
            continue
        cells = ["" if cell is None else str(cell).replace("\n", " ").strip() for cell in raw_row]
        while cells and not cells[-1]:
            cells.pop()
        if any(cell for cell in cells):
            rows.append(cells)
    if len(rows) < 2:
        return None
    table = Table(headers=rows[0], rows=rows[1:]).normalize()
    if table.width() < 2 or not table.rows:
        return None
    return table


# --- helpers -------------------------------------------------------------

def _read_text(path: Path, errors: str = "strict") -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return path.read_text(encoding=encoding, errors=errors)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def _blocks_from_text(text: str) -> list[ContentBlock]:
    blocks: list[ContentBlock] = []
    buffer: list[str] = []
    current_list: list[str] | None = None

    def flush() -> None:
        nonlocal current_list
        if current_list:
            blocks.append(ContentBlock(kind="list", items=current_list))
            current_list = None
        if buffer:
            joined = "\n".join(buffer).strip()
            if joined:
                blocks.append(ContentBlock(kind="paragraph", text=joined))
            buffer.clear()

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        list_match = LIST_RE.match(line)
        if list_match:
            if buffer:
                flush()
            if current_list is None:
                current_list = []
            current_list.append(list_match.group(1).strip())
            continue
        if len(stripped) < 120 and stripped.endswith(":") and buffer == []:
            flush()
            current_list = []
            current_list.append(stripped)
            blocks.append(ContentBlock(kind="list", items=current_list))
            current_list = None
            continue
        buffer.append(line.rstrip())

    flush()
    return blocks


#: extension -> reader. Extended by LibreOffice-backed formats at import time.
READERS: dict[str, Callable[[Path, str], DocumentModel]] = {
    "txt": read_txt,
    "md": read_markdown,
    "html": read_html,
    "pdf": read_pdf,
    "docx": read_docx,
    "xlsx": read_xlsx,
    "csv": read_csv,
    "tsv": read_tsv,
    "json": read_json,
    "xml": read_xml,
    "yaml": read_yaml,
}


def csv_text(records: list[list[str]], delimiter: str = ",") -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=delimiter, lineterminator="\r\n")
    for record in records:
        writer.writerow(record)
    return buffer.getvalue()
