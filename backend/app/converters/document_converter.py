"""Document conversions: any supported source format to any writable target.

Reads and writes go through the shared :class:`DocumentModel`, so a new
document format only needs a reader and/or a writer - never a new pair.

Legacy Microsoft/OpenOffice formats (DOC, ODT, RTF, XLS) are routed through
LibreOffice headless when it is installed. When it is not, those pairs are
simply not advertised, which is the documented behaviour rather than a fake
conversion.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from app.converters.base import BaseConverter, ConversionContext
from app.converters.document_model import ContentBlock, DocumentModel, Table, text_to_table
from app.converters.document_readers import READERS
from app.converters.document_writers import WRITERS
from app.converters.formats import canonical_extension
from app.config import get_settings
from app.models.schemas import Category
from app.utils.errors import ConversionFailedError, DependencyMissingError
from app.utils.executor import find_executable, run_command

logger = logging.getLogger(__name__)

#: Formats LibreOffice can read, and the intermediate format we normalise
#: them through. The intermediate must have a native reader, so ODT and RTF
#: are routed via DOCX rather than being declared their own output.
LIBREOFFICE_SOURCE_MAP: dict[str, str] = {
    "doc": "docx",
    "odt": "docx",
    "rtf": "docx",
    "xls": "xlsx",
}

#: Formats LibreOffice can write, and the native format we hand it. The
#: intermediate must have a native writer, so the same DOCX/XLSX bridges
#: serve every legacy target.
LIBREOFFICE_TARGET_MAP: dict[str, str] = {
    "doc": "docx",
    "odt": "docx",
    "rtf": "docx",
    "xls": "xlsx",
}

#: Formats we can write natively; LibreOffice is only needed for the targets above.
NATIVE_READERS: frozenset[str] = frozenset(READERS.keys())
NATIVE_WRITERS: frozenset[str] = frozenset(WRITERS.keys())


def libreoffice_path() -> str | None:
    settings = get_settings()
    candidates = [settings.libreoffice_path, "soffice", "libreoffice"]
    if settings.libreoffice_path:
        candidates.insert(0, settings.libreoffice_path)
    for candidate in candidates:
        if candidate and find_executable(candidate):
            return candidate
    return None


class DocumentConverter(BaseConverter):
    name = "document"
    category = Category.DOCUMENT
    source_formats = frozenset(
        NATIVE_READERS
        | set(LIBREOFFICE_SOURCE_MAP)
        | {"pdf", "html", "md", "txt", "csv", "tsv", "xlsx", "json", "xml", "yaml"}
    )
    target_formats = frozenset(
        NATIVE_WRITERS
        | set(LIBREOFFICE_TARGET_MAP)
        | {"pdf", "docx", "html", "md", "txt", "csv", "tsv", "xlsx", "json", "xml", "yaml"}
    )

    def can_convert(self, source_format: str, target_format: str) -> bool:
        source = canonical_extension(source_format)
        target = canonical_extension(target_format)
        if source not in self.source_formats or target not in self.target_formats:
            return False
        if source == target:
            return False
        # A legacy source or a legacy target both need LibreOffice, so only
        # advertise the pair when the binary is actually present.
        if source in LIBREOFFICE_SOURCE_MAP or target in LIBREOFFICE_TARGET_MAP:
            if libreoffice_path() is None:
                return False
        return True

    def convert(
        self,
        input_path: Path,
        output_path: Path,
        context: ConversionContext | None = None,
    ) -> Path:
        ctx = self._context(context)
        source_ext = canonical_extension(input_path.suffix)
        target_ext = canonical_extension(output_path.suffix)
        self._require(source_ext, target_ext)

        ctx.update(5, f"Reading {source_ext.upper()}")
        with tempfile.TemporaryDirectory(prefix="doc-convert-") as workspace:
            read_path, read_ext, cleanup = self._prepare_source(
                input_path, source_ext, Path(workspace)
            )
            try:
                reader = READERS.get(read_ext)
                if reader is None:
                    raise ConversionFailedError(
                        f"Cannot read {read_ext.upper()} files."
                    )
                model = reader(read_path, input_path.stem or "Document")
            finally:
                if cleanup is not None:
                    cleanup.unlink(missing_ok=True)

            ctx.update(50, f"Writing {target_ext.upper()}")

            # PDF/CSV has a dedicated path so ruled tables survive round-trips.
            if target_ext in ("csv", "tsv", "xlsx", "json") and source_ext == "pdf":
                model = self._refine_for_tabular(model, ctx)

            if target_ext in LIBREOFFICE_TARGET_MAP:
                return self._write_via_libreoffice(model, output_path, target_ext, ctx)

            writer = WRITERS.get(target_ext)
            if writer is None:
                raise ConversionFailedError(f"Cannot write {target_ext.upper()} files.")
            try:
                writer(model, output_path)
            except (DependencyMissingError, ConversionFailedError):
                raise
            except Exception as exc:  # noqa: BLE001
                logger.exception("Document write failed: %s -> %s", source_ext, target_ext)
                raise ConversionFailedError(f"Could not write the output file: {exc}") from exc

        ctx.update(100, "Complete")
        return output_path

    # -- helpers --------------------------------------------------------

    def _prepare_source(
        self, input_path: Path, source_ext: str, workspace: Path
    ) -> tuple[Path, str, Path | None]:
        """Return (readable_path, extension_to_read_with, temp_to_delete)."""
        if source_ext in NATIVE_READERS:
            return input_path, source_ext, None

        intermediate_ext = LIBREOFFICE_SOURCE_MAP.get(source_ext)
        if intermediate_ext is None:
            raise ConversionFailedError(f"Cannot read {source_ext.upper()} files.")

        executable = libreoffice_path()
        if executable is None:
            raise DependencyMissingError(
                f"Converting {source_ext.upper()} files requires LibreOffice, "
                "which is not installed on this server."
            )

        staged = workspace / f"source.{source_ext}"
        shutil.copy2(input_path, staged)
        run_command(
            [
                executable,
                "--headless",
                "--norestore",
                "--invisible",
                f"-env:UserInstallation=file:///{(workspace / 'loprofile').as_posix()}",
                "--convert-to",
                intermediate_ext,
                "--outdir",
                str(workspace),
                str(staged),
            ],
            timeout=180,
        )
        produced = workspace / f"source.{intermediate_ext}"
        if not produced.exists():
            raise ConversionFailedError(
                f"LibreOffice could not read this {source_ext.upper()} file."
            )
        return produced, intermediate_ext, produced

    def _write_via_libreoffice(
        self, model: DocumentModel, output_path: Path, target_ext: str, ctx: ConversionContext
    ) -> Path:
        executable = libreoffice_path()
        if executable is None:
            raise DependencyMissingError(
                f"Writing {target_ext.upper()} files requires LibreOffice, "
                "which is not installed on this server."
            )

        intermediate_ext = LIBREOFFICE_TARGET_MAP[target_ext]
        intermediate_writer = WRITERS[intermediate_ext]
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="doc-write-") as workspace:
            work = Path(workspace)
            intermediate = work / f"output.{intermediate_ext}"
            intermediate_writer(model, intermediate)

            outdir = work / "out"
            outdir.mkdir(parents=True, exist_ok=True)
            run_command(
                [
                    executable,
                    "--headless",
                    "--norestore",
                    "--invisible",
                    f"-env:UserInstallation=file:///{(work / 'loprofile').as_posix()}",
                    "--convert-to",
                    target_ext,
                    "--outdir",
                    str(outdir),
                    str(intermediate),
                ],
                timeout=180,
            )
            produced = outdir / f"output.{target_ext}"
            if not produced.exists():
                candidates = list(outdir.glob(f"*.{target_ext}"))
                if not candidates:
                    raise ConversionFailedError(
                        f"LibreOffice could not produce a {target_ext.upper()} file."
                    )
                produced = candidates[0]
            shutil.copy2(produced, output_path)

        ctx.update(100, "Complete")
        return output_path

    def _refine_for_tabular(self, model: DocumentModel, ctx: ConversionContext) -> DocumentModel:
        """For PDF sources, try harder to recover a real table.

        pdfplumber finds ruled tables. When a PDF has no ruling lines we fall
        back to whitespace-aligned text, and finally to a single text column.
        """
        if model.tables:
            return model

        ctx.update(35, "Detecting table layout")
        for block in model.blocks:
            if block.kind == "paragraph" and block.text:
                candidate = text_to_table(block.text)
                if candidate is not None and len(candidate.rows) >= 1:
                    model.tables.insert(0, candidate)
                    block.kind = "table"
                    block.table = candidate
                    break
        return model
