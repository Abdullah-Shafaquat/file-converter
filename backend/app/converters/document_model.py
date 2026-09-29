"""Intermediate representation shared by every document reader and writer.

Readers parse an input format into a :class:`DocumentModel`; writers render that
model into an output format. This keeps N x M conversions linear instead of
quadratic - a new format is one reader or one writer, not a new pair.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Any, Literal

BlockKind = Literal["heading", "paragraph", "list", "table", "code"]


@dataclass
class Table:
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)

    def to_rows(self) -> list[list[str]]:
        return ([self.headers, *self.rows] if self.headers else self.rows)

    def width(self) -> int:
        return max((len(row) for row in self.to_rows()), default=0)

    def normalize(self) -> "Table":
        width = self.width()
        if width == 0:
            return Table()
        fixed_rows = [(row + [""] * width)[:width] for row in self.to_rows()]
        headers = fixed_rows[0]
        body = fixed_rows[1:]
        return Table(headers=headers, rows=body)

    @classmethod
    def from_records(cls, records: list[dict[str, Any]]) -> "Table":
        if not records:
            return Table()
        headers: list[str] = []
        for record in records:
            for key in record:
                if key not in headers:
                    headers.append(str(key))
        rows = [
            [_stringify(record.get(header, "")) for header in headers]
            for record in records
        ]
        return cls(headers=headers, rows=rows)


@dataclass
class ContentBlock:
    kind: BlockKind = "paragraph"
    text: str = ""
    level: int = 0
    items: list[str] = field(default_factory=list)
    table: Table | None = None


@dataclass
class DocumentModel:
    title: str = "Document"
    blocks: list[ContentBlock] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    # -- text views -----------------------------------------------------
    def plain_text(self) -> str:
        parts: list[str] = []
        for block in self.blocks:
            if block.kind == "table" and block.table is not None:
                parts.append(table_to_text(block.table))
            elif block.kind == "list":
                parts.append("\n".join(f"- {item}" for item in block.items))
            else:
                parts.append(block.text)
        return "\n\n".join(part for part in parts if part.strip()).strip()

    def markdown(self) -> str:
        parts: list[str] = []
        for block in self.blocks:
            if block.kind == "heading" and block.text.strip():
                level = max(1, min(6, block.level or 1))
                parts.append(f"{'#' * level} {block.text.strip()}")
            elif block.kind == "list" and block.items:
                parts.append("\n".join(f"- {item}" for item in block.items))
            elif block.kind == "code":
                parts.append(f"```\n{block.text}\n```")
            elif block.kind == "table" and block.table is not None:
                parts.append(table_to_markdown(block.table))
            else:
                if block.text.strip():
                    parts.append(block.text.strip())
        return "\n\n".join(parts).strip()

    def html(self) -> str:
        parts: list[str] = []
        for block in self.blocks:
            if block.kind == "heading" and block.text.strip():
                level = max(1, min(6, block.level or 1))
                parts.append(f"<h{level}>{html.escape(block.text.strip())}</h{level}>")
            elif block.kind == "list" and block.items:
                items = "".join(f"<li>{html.escape(item)}</li>" for item in block.items)
                parts.append(f"<ul>{items}</ul>")
            elif block.kind == "code":
                parts.append(f"<pre><code>{html.escape(block.text)}</code></pre>")
            elif block.kind == "table" and block.table is not None:
                parts.append(table_to_html(block.table))
            else:
                if block.text.strip():
                    parts.append(f"<p>{_paragraph_html(block.text)}</p>")
        body = "\n".join(parts)
        return wrap_html(self.title, body)

    def primary_table(self) -> Table | None:
        if self.tables:
            return max(self.tables, key=lambda t: len(t.rows))
        for block in self.blocks:
            if block.kind == "table" and block.table is not None:
                return block.table
        return None


# --- helpers -------------------------------------------------------------

_WHITESPACE_RUN = re.compile(r"[ \t]+")


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        text = f"{value:.10f}".rstrip("0").rstrip(".")
        return text or "0"
    return str(value)


def _paragraph_html(text: str) -> str:
    escaped = html.escape(text)
    escaped = escaped.replace("\n\n", "</p><p>").replace("\n", "<br />")
    return escaped


def wrap_html(title: str, body: str) -> str:
    safe_title = html.escape(title)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n'
        '<meta charset="utf-8" />\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1" />\n'
        f"<title>{safe_title}</title>\n"
        "<style>\n"
        "body{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;"
        "line-height:1.6;max-width:52rem;margin:2.5rem auto;padding:0 1.25rem;color:#111}\n"
        "h1,h2,h3,h4,h5,h6{line-height:1.25;margin:1.5em 0 .5em}\n"
        "table{border-collapse:collapse;width:100%;margin:1em 0}\n"
        "th,td{border:1px solid #d4d4d8;padding:.5rem .625rem;text-align:left}\n"
        "th{background:#f4f4f5}\n"
        "pre{background:#f4f4f5;padding:1rem;overflow-x:auto;border-radius:.5rem}\n"
        "ul{padding-left:1.25rem}\n"
        "</style>\n</head>\n<body>\n"
        f"{body}\n</body>\n</html>\n"
    )


def table_to_markdown(table: Table) -> str:
    normalized = table.normalize()
    rows = normalized.to_rows()
    if not rows:
        return ""
    headers = [cell.strip() or " " for cell in rows[0]]
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows[1:]:
        cells = [_WHITESPACE_RUN.sub(" ", cell.replace("\n", " ")).strip() for cell in row]
        lines.append("| " + " | ".join(cells or [" "]) + " |")
    return "\n".join(lines)


def table_to_html(table: Table) -> str:
    normalized = table.normalize()
    rows = normalized.to_rows()
    if not rows:
        return ""
    head = ""
    if normalized.headers:
        cells = "".join(f"<th>{html.escape(cell)}</th>" for cell in normalized.headers)
        head = f"<thead><tr>{cells}</tr></thead>"
    body_rows = "".join(
        "<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in row) + "</tr>"
        for row in normalized.rows
    )
    return f"<table>{head}<tbody>{body_rows}</tbody></table>"


def table_to_text(table: Table) -> str:
    normalized = table.normalize()
    rows = normalized.to_rows()
    if not rows:
        return ""
    width = normalized.width()
    widths = [
        max((len(row[index]) if index < len(row) else 0) for row in rows)
        for index in range(width)
    ]
    lines = []
    for row in rows:
        cells = [
            (row[index] if index < len(row) else "").replace("\n", " ")
            for index in range(width)
        ]
        lines.append("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells)).rstrip())
    return "\n".join(lines)


def parse_delimited(text: str, delimiter: str) -> list[list[str]]:
    """Parse delimited text with the stdlib csv module (RFC 4180 aware)."""
    import csv
    import io

    if not text.strip():
        return []

    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=delimiter)
    except csv.Error:
        class _Plain(csv.excel):
            pass
        dialect = _Plain()
        dialect.delimiter = delimiter

    reader = csv.reader(io.StringIO(text), dialect)
    return [list(row) for row in reader]


def text_to_table(text: str) -> Table | None:
    """Heuristic: treat aligned whitespace-separated text as a table."""
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return None

    rows = [re.split(r"\s{2,}|\t", line.strip()) for line in lines]
    column_counts = {len(row) for row in rows if len(row) > 1}
    if not column_counts or len(column_counts) > 2:
        return None
    if max(column_counts) < 2:
        return None

    width = max(column_counts)
    if len(rows) < 2:
        return None

    normalized = [row[:width] for row in rows]
    return Table(headers=normalized[0], rows=normalized[1:]).normalize()
