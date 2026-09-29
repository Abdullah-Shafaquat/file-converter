"""Security helpers for handling untrusted uploads."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import unicodedata
from pathlib import Path

_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")
_REPEATED_DOTS = re.compile(r"\.{2,}")
_RESERVED_WINDOWS_NAMES = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}
MAX_STEM_LENGTH = 80


def random_token(length: int = 32) -> str:
    """Return an unguessable, URL-safe identifier for temp files and jobs."""
    return secrets.token_urlsafe(length)


def sanitize_filename(filename: str, fallback: str = "file") -> str:
    """Reduce an arbitrary user filename to a safe, display-only name.

    Never used to build filesystem paths for storage; storage always uses
    :func:`random_token`. This only sanitizes what we echo back to the user.
    """
    name = unicodedata.normalize("NFKD", filename or "")
    name = name.split("\\")[-1].split("/")[-1]
    name = _UNSAFE_CHARS.sub("_", name).strip("._")
    name = _REPEATED_DOTS.sub(".", name)

    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, ""

    stem = stem.strip("._") or fallback
    if stem.lower() in _RESERVED_WINDOWS_NAMES:
        stem = f"_{stem}"

    if len(stem) > MAX_STEM_LENGTH:
        stem = stem[:MAX_STEM_LENGTH]

    return f"{stem}.{ext}" if ext else stem


def split_extension(filename: str) -> str:
    """Return the lowercase extension without a leading dot ('' when absent)."""
    suffix = Path(sanitize_filename(filename)).suffix
    return suffix[1:].lower()


def build_output_name(source_name: str, target_extension: str) -> str:
    """Derive the download filename, keeping the original stem."""
    sanitized = sanitize_filename(source_name)
    stem = sanitized.rsplit(".", 1)[0] if "." in sanitized else sanitized
    target_extension = target_extension.lower().lstrip(".")
    return sanitize_filename(f"{stem}.{target_extension}")


def resolve_within(directory: Path, *parts: str) -> Path:
    """Join parts onto directory and guarantee the result stays inside it.

    Raises ValueError on traversal attempts so callers fail closed.
    """
    directory = directory.resolve()
    candidate = directory.joinpath(*parts).resolve()
    if candidate != directory and directory not in candidate.parents:
        raise ValueError("Path escapes the allowed directory")
    return candidate


def file_digest(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """SHA-256 of a file on disk, streamed so large files stay off the heap."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def constant_time_equals(left: str, right: str) -> bool:
    return hmac.compare_digest(left, right)
