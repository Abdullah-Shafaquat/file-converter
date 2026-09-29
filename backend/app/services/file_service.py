"""Upload handling: streaming, validation and safe storage."""

from __future__ import annotations

import logging
import mimetypes
from datetime import datetime, timezone
from pathlib import Path

from fastapi import UploadFile

from app.config import Settings, get_settings
from app.converters import registry
from app.converters.formats import BLOCKED_EXTENSIONS, canonical_extension, get_format
from app.models.schemas import Category, UploadedFileInfo
from app.services.store import InMemoryStore
from app.utils.errors import FileTooLargeError, UnsupportedFormatError
from app.utils.security import random_token, resolve_within, sanitize_filename

logger = logging.getLogger(__name__)

#: Read uploads to disk in chunks so a 500 MB file never lands on the heap.
CHUNK_SIZE = 1024 * 1024

#: Extensions we will consider even though the OS may not map them to a MIME type.
_EXTRA_MIME_TYPES: dict[str, str] = {
    "md": "text/markdown",
    "markdown": "text/markdown",
    "tsv": "text/tab-separated-values",
    "webp": "image/webp",
    "avif": "image/avif",
    "heic": "image/heic",
    "ico": "image/x-icon",
    "mdown": "text/markdown",
    "yaml": "application/yaml",
    "yml": "application/yaml",
    "7z": "application/x-7z-compressed",
    "tgz": "application/gzip",
}


class FileService:
    def __init__(self, store: InMemoryStore, settings: Settings | None = None) -> None:
        self.store = store
        self.settings = settings or get_settings()

    async def store_upload(self, upload: UploadFile) -> UploadedFileInfo:
        original_name = sanitize_filename(upload.filename or "file")
        extension = canonical_extension(Path(original_name).suffix)
        self._validate_extension(extension)

        file_id = random_token()
        target = resolve_within(self.settings.upload_dir, f"{file_id}.{extension}")

        size = await self._stream_to_disk(upload, target)
        self._validate_mime(upload.content_type, extension)

        spec = get_format(extension)
        info = UploadedFileInfo(
            id=file_id,
            original_name=original_name,
            extension=extension,
            category=spec.category if spec else None,
            size_bytes=size,
            mime_type=upload.content_type or self._expected_mime(extension),
            label=spec.label if spec else extension.upper(),
            available_formats=registry.targets_for(extension),
            uploaded_at=datetime.now(timezone.utc).isoformat(),
        )
        self.store.save_upload(info, str(target))

        logger.info(
            "upload id=%s name=%s ext=%s bytes=%s targets=%s",
            file_id,
            original_name,
            extension,
            size,
            len(info.available_formats),
        )
        return info

    async def _stream_to_disk(self, upload: UploadFile, target: Path) -> int:
        target.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        try:
            with target.open("wb") as handle:
                while True:
                    chunk = await upload.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > self.settings.max_file_size_bytes:
                        raise FileTooLargeError(
                            f"Maximum upload size is {self.settings.max_file_size_mb} MB."
                        )
                    handle.write(chunk)
        except FileTooLargeError:
            target.unlink(missing_ok=True)
            raise
        except Exception:
            target.unlink(missing_ok=True)
            raise

        if written == 0:
            target.unlink(missing_ok=True)
            raise UnsupportedFormatError("The uploaded file is empty.")

        return written

    def _validate_extension(self, extension: str) -> None:
        if not extension:
            raise UnsupportedFormatError(
                "This file has no extension, so its type cannot be detected."
            )
        if extension in BLOCKED_EXTENSIONS:
            raise UnsupportedFormatError("Sorry, this file format is not supported.")
        if not registry.is_supported_source(extension):
            raise UnsupportedFormatError("Sorry, this file format is not supported.")

    def _expected_mime(self, extension: str) -> str | None:
        spec = get_format(extension)
        if spec and spec.mime_types:
            return spec.mime_types[0]
        return None

    def _validate_mime(self, declared: str | None, extension: str) -> None:
        """Reject a declared type that flatly contradicts the extension.

        Browsers are loose with MIME types, so this only fails on an outright
        mismatch between the extension and a *text-bearing* declared type.
        """
        if not declared:
            return
        normalized = declared.split(";")[0].strip().lower()
        if normalized in ("application/octet-stream", "binary/octet-stream", ""):
            return

        expected = self._expected_mime(extension)
        if normalized == expected:
            return

        # Accept any type the registry lists for this extension.
        if normalized in _mimes_for(extension):
            return

        # Allow the generic text/* family for text-like documents.
        if normalized.startswith("text/") and extension in TEXT_LIKE_FORMATS:
            return
        if "charset" in declared.lower() and extension in TEXT_LIKE_FORMATS:
            return

        raise UnsupportedFormatError(
            "Sorry, this file format is not supported."
        )

    # -- retrieval ------------------------------------------------------

    def get_upload(self, file_id: str) -> tuple[UploadedFileInfo, Path]:
        entry = self.store.get_upload(file_id)
        if entry is None:
            from app.utils.errors import FileNotFoundError_

            raise FileNotFoundError_()

        info, stored_path = entry
        path = Path(stored_path)
        if not path.exists():
            self.store.delete_upload(file_id)
            from app.utils.errors import FileNotFoundError_

            raise FileNotFoundError_()
        return info, path

    def delete_upload(self, file_id: str) -> bool:
        entry = self.store.get_upload(file_id)
        if entry is None:
            return False
        _, stored_path = entry
        Path(stored_path).unlink(missing_ok=True)
        self.store.delete_upload(file_id)
        logger.info("deleted upload id=%s", file_id)
        return True

    def delete_path(self, path: str | Path | None) -> None:
        if not path:
            return
        Path(path).unlink(missing_ok=True)


TEXT_LIKE_FORMATS: frozenset[str] = frozenset(
    {"txt", "md", "markdown", "csv", "tsv", "html", "htm", "json", "xml", "yaml", "yml", "rtf"}
)


def _mimes_for(extension: str) -> set[str]:
    spec = get_format(extension)
    if not spec:
        return set()
    known = {mime.lower() for mime in spec.mime_types}
    guessed = mimetypes.guess_type(f"x.{extension}")[0]
    if guessed:
        known.add(guessed.lower())
    return known
