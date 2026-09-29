"""Central format metadata registry - the single source of truth.

The frontend never hard-codes a conversion matrix; it fetches it from
``GET /api/formats``, which is generated from the converters plus this table.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.schemas import Category


@dataclass(frozen=True)
class FormatSpec:
    label: str
    category: Category
    mime_types: tuple[str, ...] = field(default_factory=tuple)


FORMATS: dict[str, FormatSpec] = {
    # --- documents -----------------------------------------------------
    "pdf": FormatSpec("PDF", Category.DOCUMENT, ("application/pdf",)),
    "docx": FormatSpec(
        "DOCX",
        Category.DOCUMENT,
        ("application/vnd.openxmlformats-officedocument.wordprocessingml.document",),
    ),
    "doc": FormatSpec("DOC", Category.DOCUMENT, ("application/msword",)),
    "odt": FormatSpec(
        "ODT",
        Category.DOCUMENT,
        ("application/vnd.oasis.opendocument.text",),
    ),
    "rtf": FormatSpec("RTF", Category.DOCUMENT, ("application/rtf", "text/rtf")),
    "txt": FormatSpec("TXT", Category.DOCUMENT, ("text/plain",)),
    "md": FormatSpec("Markdown", Category.DOCUMENT, ("text/markdown",)),
    "html": FormatSpec("HTML", Category.DOCUMENT, ("text/html", "application/xhtml+xml")),
    "epub": FormatSpec("EPUB", Category.DOCUMENT, ("application/epub+zip",)),
    "csv": FormatSpec("CSV", Category.DOCUMENT, ("text/csv",)),
    "tsv": FormatSpec("TSV", Category.DOCUMENT, ("text/tab-separated-values",)),
    "xlsx": FormatSpec(
        "XLSX",
        Category.DOCUMENT,
        ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",),
    ),
    "xls": FormatSpec("XLS", Category.DOCUMENT, ("application/vnd.ms-excel",)),
    "json": FormatSpec("JSON", Category.DOCUMENT, ("application/json", "text/json")),
    "xml": FormatSpec("XML", Category.DOCUMENT, ("application/xml", "text/xml")),
    "yaml": FormatSpec("YAML", Category.DOCUMENT, ("application/yaml", "text/yaml")),
    # --- images --------------------------------------------------------
    "jpg": FormatSpec("JPG", Category.IMAGE, ("image/jpeg",)),
    "jpeg": FormatSpec("JPEG", Category.IMAGE, ("image/jpeg",)),
    "png": FormatSpec("PNG", Category.IMAGE, ("image/png",)),
    "webp": FormatSpec("WEBP", Category.IMAGE, ("image/webp",)),
    "gif": FormatSpec("GIF", Category.IMAGE, ("image/gif",)),
    "bmp": FormatSpec("BMP", Category.IMAGE, ("image/bmp", "image/x-ms-bmp")),
    "tiff": FormatSpec("TIFF", Category.IMAGE, ("image/tiff",)),
    "svg": FormatSpec("SVG", Category.IMAGE, ("image/svg+xml",)),
    "ico": FormatSpec("ICO", Category.IMAGE, ("image/x-icon", "image/vnd.microsoft.icon")),
    "avif": FormatSpec("AVIF", Category.IMAGE, ("image/avif",)),
    "heic": FormatSpec("HEIC", Category.IMAGE, ("image/heic", "image/heif")),
    # --- archives ------------------------------------------------------
    "zip": FormatSpec("ZIP", Category.ARCHIVE, ("application/zip", "application/x-zip-compressed")),
    "tar": FormatSpec("TAR", Category.ARCHIVE, ("application/x-tar",)),
    "gz": FormatSpec("GZ", Category.ARCHIVE, ("application/gzip", "application/x-gzip")),
    "tgz": FormatSpec("TAR.GZ", Category.ARCHIVE, ("application/gzip",)),
    "bz2": FormatSpec("BZIP2", Category.ARCHIVE, ("application/x-bzip2",)),
    "xz": FormatSpec("XZ", Category.ARCHIVE, ("application/x-xz",)),
    "7z": FormatSpec("7Z", Category.ARCHIVE, ("application/x-7z-compressed",)),
}

# Alternative spellings that resolve to a canonical extension.
EXTENSION_ALIASES: dict[str, str] = {
    "jpeg": "jpg",
    "tif": "tiff",
    "markdown": "md",
    "htm": "html",
    "text": "txt",
    "yml": "yaml",
    "gzip": "gz",
    "taz": "tar",
    "log": "txt",
}

CATEGORY_DESCRIPTIONS: dict[Category, str] = {
    Category.DOCUMENT: "PDF, Word, spreadsheets, structured data and plain text.",
    Category.IMAGE: "Raster and vector images between every common web format.",
    Category.ARCHIVE: "Repack archives between ZIP, TAR and compressed TAR.",
}

#: Extensions that are rejected outright, regardless of converter support.
BLOCKED_EXTENSIONS: frozenset[str] = frozenset(
    {
        "exe", "msi", "bat", "cmd", "com", "scr", "dll", "sys", "cpl",
        "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9",
        "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9",
        "ps1", "psm1", "vbs", "vbe", "wsf", "wsh", "hta", "jar", "jse",
        "sh", "bash", "zsh", "run", "bin", "apk", "app", "dmg", "iso", "img",
        "reg", "lnk", "pif", "sct", "vb", "ws", "htaccess",
    }
)


def canonical_extension(extension: str) -> str:
    """Normalise an extension to its canonical registry key."""
    ext = extension.lower().lstrip(".")
    return EXTENSION_ALIASES.get(ext, ext)


def get_format(extension: str) -> FormatSpec | None:
    return FORMATS.get(canonical_extension(extension))


def is_blocked(extension: str) -> bool:
    ext = extension.lower().lstrip(".")
    return ext in BLOCKED_EXTENSIONS


def mime_types_for(extension: str) -> list[str]:
    spec = get_format(extension)
    return list(spec.mime_types) if spec else []
