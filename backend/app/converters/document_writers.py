"""Writers: render a :class:`DocumentModel` into an output file."""

from __future__ import annotations

import html as html_module
import json
import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable
from xml.sax.saxutils import escape as xml_escape

from app.converters.document_model import ContentBlock, DocumentModel, Table
from app.utils.errors import ConversionFailedError, DependencyMissingError

logger = logging.getLogger(__name__)

# Long lines are wrapped in PDF/TXT output instead of running off the page.
_WRAP_COLUMNS = 92


# --- plain text ----------------------------------------------------------

def write_txt(model: DocumentModel, path: Path) -> Path:
    path.write_text(model.plain_text() + "\n", encoding="utf-8")
    return path


def write_markdown(model: DocumentModel, path: Path) -> Path:
    path.write_text(model.markdown() + "\n", encoding="utf-8")
    return path


def write_html(model: DocumentModel, path: Path) -> Path:
    path.write_text(model.html(), encoding="utf-8")
    return path


# --- structured ----------------------------------------------------------

def write_csv(model: DocumentModel, path: Path, delimiter: str = ",") -> Path:
    from app.converters.document_readers import csv_text

    table = model.primary_table()
    if table is None:
        # No table found: fall back to one column of flattened text.
        rows = [[line] for line in model.plain_text().splitlines() if line.strip()]
        if not rows:
            rows = [["text"]]
        path.write_text(csv_text(rows, delimiter), encoding="utf-8")
        return path
    path.write_text(csv_text(table.normalize().to_rows(), delimiter), encoding="utf-8")
    return path


def write_tsv(model: DocumentModel, path: Path) -> Path:
    return write_csv(model, path, delimiter="\t")


def write_json(model: DocumentModel, path: Path) -> Path:
    table = model.primary_table()
    if table is not None:
        normalized = table.normalize()
        records = [dict(zip(normalized.headers, row)) for row in normalized.rows]
    else:
        records = [{"text": block.text} for block in model.blocks if block.text.strip()]

    payload: dict[str, Any] = {
        "title": model.title,
        "count": len(records),
        "data": records,
    }
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=_json_default) + "\n",
        encoding="utf-8",
    )
    return path


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def write_yaml(model: DocumentModel, path: Path) -> Path:
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        # Minimal, correct YAML for the restricted shapes we emit.
        table = model.primary_table()
        lines: list[str] = [f"title: {yaml_scalar(model.title)}", "data:"]
        if table is not None:
            normalized = table.normalize()
            for row in normalized.rows:
                lines.append("  - " + yaml_scalar(json.dumps(dict(zip(normalized.headers, row)))))
        else:
            for block in model.blocks:
                if block.text.strip():
                    lines.append("  - text: " + yaml_scalar(block.text.strip()))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    table = model.primary_table()
    if table is not None:
        normalized = table.normalize()
        payload = {"title": model.title, "data": [dict(zip(normalized.headers, row)) for row in normalized.rows]}
    else:
        payload = {"title": model.title, "data": [{"text": b.text} for b in model.blocks if b.text.strip()]}
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def yaml_scalar(value: str) -> str:
    return f"'{value.replace(chr(39), chr(39) * 2)}'"


def write_xml(model: DocumentModel, path: Path) -> Path:
    table = model.primary_table()
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<document>"]
    lines.append(f"  <title>{xml_escape(model.title)}</title>")
    if table is not None:
        normalized = table.normalize()
        lines.append("  <data>")
        for row in normalized.rows:
            cells = "".join(f"<cell>{xml_escape(cell)}</cell>" for cell in row)
            lines.append(f"    <row>{cells}</row>")
        lines.append("  </data>")
    else:
        lines.append("  <content>")
        for block in model.blocks:
            if block.text.strip():
                lines.append(f"    <paragraph>{xml_escape(block.text.strip())}</paragraph>")
        lines.append("  </content>")
    lines.append("</document>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_xlsx(model: DocumentModel, path: Path) -> Path:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font
    except ImportError as exc:
        raise DependencyMissingError("Spreadsheet conversion requires 'openpyxl'.") from exc

    workbook = Workbook()
    default_sheet = workbook.active
    workbook.remove(default_sheet)

    tables = model.tables
    if not tables:
        sheet = workbook.create_sheet("Document")
        sheet.append(["text"])
        for block in model.blocks:
            if block.text.strip():
                sheet.append([block.text.strip()])
        if sheet.max_row == 1:
            sheet.append([""])
        _autosize(sheet)
        path.parent.mkdir(parents=True, exist_ok=True)
        workbook.save(str(path))
        return path

    for index, raw_table in enumerate(tables, start=1):
        normalized = raw_table.normalize()
        sheet = workbook.create_sheet(_sheet_name(normalized, index))
        for row in normalized.to_rows():
            sheet.append(row)
        if normalized.headers:
            for cell in sheet[1]:
                cell.font = Font(bold=True)
                cell.alignment = Alignment(vertical="top", wrap_text=True)
        _autosize(sheet)

    workbook.save(str(path))
    return path


def _sheet_name(table: Table, index: int) -> str:
    candidate = (table.headers[0] if table.headers else "") or f"Sheet{index}"
    cleaned = re.sub(r"[\\/*?:\[\]]", "", candidate).strip()[:31]
    return cleaned or f"Sheet{index}"


def _autosize(sheet: Any) -> None:
    widths: dict[int, int] = {}
    for row in sheet.iter_rows():
        for cell in row:
            if cell.value is None:
                continue
            length = len(str(cell.value))
            if length > widths.get(cell.column, 0):
                widths[cell.column] = length
    from openpyxl.utils import get_column_letter

    for column, width in widths.items():
        sheet.column_dimensions[get_column_letter(column)].width = min(max(width + 2, 10), 70)


# --- docx ----------------------------------------------------------------

def write_docx(model: DocumentModel, path: Path) -> Path:
    try:
        import docx
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import Pt
    except ImportError as exc:
        raise DependencyMissingError("DOCX conversion requires the 'python-docx' package.") from exc

    document = docx.Document()
    if model.title.strip():
        document.add_heading(model.title.strip(), level=0)

    for block in model.blocks:
        if block.kind == "heading" and block.text.strip():
            document.add_heading(block.text.strip(), level=max(1, min(9, block.level or 1)))
        elif block.kind == "list" and block.items:
            for item in block.items:
                document.add_paragraph(item, style="List Bullet")
        elif block.kind == "code":
            paragraph = document.add_paragraph()
            run = paragraph.add_run(block.text)
            run.font.name = "Courier New"
            run.font.size = Pt(9)
        elif block.kind == "table" and block.table is not None:
            table = block.table.normalize()
            if not table.to_rows():
                continue
            width = table.width()
            docx_table = document.add_table(rows=0, cols=width)
            try:
                docx_table.style = "Table Grid"
            except KeyError:
                pass
            for row_index, row in enumerate(table.to_rows()):
                cells = docx_table.add_row().cells
                for cell_index in range(width):
                    value = row[cell_index] if cell_index < len(row) else ""
                    cells[cell_index].text = value
                if row_index == 0 and table.headers:
                    for cell in cells:
                        for paragraph in cell.paragraphs:
                            for run in paragraph.runs:
                                run.bold = True
        else:
            if block.text.strip():
                document.add_paragraph(block.text.strip(), style="Normal")

    path.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(path))
    return path


# --- pdf -----------------------------------------------------------------

def write_pdf(model: DocumentModel, path: Path) -> Path:
    """Render the model to PDF with reportlab platypus (auto-paginates)."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table as PlatypusTable,
            TableStyle,
        )
    except ImportError as exc:
        raise DependencyMissingError("PDF conversion requires the 'reportlab' package.") from exc

    styles = getSampleStyleSheet()
    body_style = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10.5,
        leading=15,
        alignment=TA_LEFT,
        spaceAfter=7,
        wordWrap="CJK",
    )
    code_style = ParagraphStyle(
        "Code", parent=body_style, fontName="Courier", fontSize=8.5, leading=12
    )
    cell_style = ParagraphStyle("Cell", parent=body_style, fontSize=8.5, leading=11, spaceAfter=0)
    cell_head_style = ParagraphStyle(
        "CellHead", parent=cell_style, textColor=colors.white
    )

    document = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        title=model.title or "Document",
        author="Universal File Converter",
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )

    story: list[Any] = []
    if model.title.strip():
        story.append(Paragraph(_escape(model.title.strip()), styles["Title"]))
        story.append(Spacer(1, 6 * mm))

    for block in model.blocks:
        if block.kind == "heading" and block.text.strip():
            level = max(1, min(5, block.level or 1))
            story.append(Paragraph(_escape(block.text.strip()), styles[f"Heading{level}"]))
        elif block.kind == "list" and block.items:
            for item in block.items:
                story.append(Paragraph(f"&bull; {_escape(item)}", body_style))
        elif block.kind == "code":
            story.append(Paragraph(_escape(block.text).replace("\n", "<br/>"), code_style))
        elif block.kind == "table" and block.table is not None:
            story.append(_pdf_table(block.table, PlatypusTable, TableStyle, Paragraph,
                                     cell_style, cell_head_style, mm, colors))
            story.append(Spacer(1, 5 * mm))
        else:
            if not block.text.strip():
                continue
            escaped = _escape(block.text.strip()).replace("\n", "<br/>")
            story.append(Paragraph(escaped, body_style))

    if not story:
        story.append(Paragraph("This document is empty.", body_style))

    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        document.build(story)
    except Exception as exc:  # noqa: BLE001
        raise ConversionFailedError(f"Could not build the PDF output: {exc}") from exc
    return path


def _pdf_table(
    table: Table,
    platypus_table: Any,
    table_style: Any,
    paragraph: Any,
    cell_style: Any,
    cell_head_style: Any,
    mm: Any,
    colors: Any,
) -> Any:
    normalized = table.normalize()
    rows = normalized.to_rows()
    width = normalized.width()
    if width == 0:
        from reportlab.platypus import Spacer

        return Spacer(1, 1)

    available = 174 * mm
    if width > 1:
        column_width = available / width
    else:
        column_width = available
    # Very wide tables get a landscape-ish squeeze to stay on the page.
    column_width = min(column_width, 60 * mm)

    data = []
    for row_index, row in enumerate(rows):
        style = cell_head_style if row_index == 0 and normalized.headers else cell_style
        data.append([
            paragraph(_escape(str(row[i]) if i < len(row) else ""), style) for i in range(width)
        ])

    rendered = platypus_table(
        data,
        colWidths=[column_width] * width,
        repeatRows=1 if normalized.headers else 0,
        hAlign="LEFT",
    )
    rendered.setStyle(table_style([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d4d4d8")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3f3f46")) if normalized.headers else ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return rendered


def _escape(text: str) -> str:
    cleaned = html_module.escape(text, quote=False)
    return cleaned.replace("  ", "&nbsp;&nbsp;")


#: extension -> writer signature (model, path) -> path
WRITERS: dict[str, Callable[[DocumentModel, Path], Path]] = {
    "txt": write_txt,
    "md": write_markdown,
    "html": write_html,
    "pdf": write_pdf,
    "docx": write_docx,
    "xlsx": write_xlsx,
    "csv": write_csv,
    "tsv": write_tsv,
    "json": write_json,
    "xml": write_xml,
    "yaml": write_yaml,
}
