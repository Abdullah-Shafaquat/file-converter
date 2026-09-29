"""Archive repacking with path-traversal and zip-bomb protection."""

from __future__ import annotations

import bz2
import gzip
import logging
import lzma
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Literal, TypeAlias

from app.converters.base import BaseConverter, ConversionContext
from app.converters.formats import canonical_extension
from app.models.schemas import Category
from app.utils.errors import ConversionFailedError, DependencyMissingError

logger = logging.getLogger(__name__)

#: Refuse archives that would expand beyond this. Zip-bomb guard.
MAX_EXPANDED_BYTES = 2 * 1024 * 1024 * 1024
MAX_MEMBERS = 50_000
COMPRESSION_LEVEL = 6

#: The only tarfile open modes this module uses, spelled out so the type
#: checker and readers both see exactly what is permitted.
TarMode: TypeAlias = Literal["r:", "r:gz"]


def seven_zip_support() -> bool:
    """True when py7zr is fully importable.

    py7zr depends on a compiled BCJ helper that ships without a wheel on some
    platforms, so a bare ``import py7zr`` can raise ImportError from deep
    inside the package rather than at the top level.
    """
    try:
        import py7zr  # noqa: F401
    except Exception:  # noqa: BLE001 - any failure means "not usable"
        return False
    return True


class ArchiveConverter(BaseConverter):
    name = "archive"
    category = Category.ARCHIVE
    source_formats = frozenset({"zip", "tar", "gz", "tgz", "bz2", "xz", "7z"})
    target_formats = frozenset({"zip", "tar", "gz", "tgz", "bz2", "xz"})

    def can_convert(self, source_format: str, target_format: str) -> bool:
        source = canonical_extension(source_format)
        target = canonical_extension(target_format)
        if source not in self.source_formats or target not in self.target_formats:
            return False
        if source == target:
            return False
        # 7Z can be read, never written here.
        if target == "7z":
            return False
        # py7zr needs a compiled helper that has no wheel on every platform,
        # so 7Z input is advertised only when the import actually works.
        if source == "7z" and not seven_zip_support():
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

        ctx.update(5, f"Reading {source_ext.upper()} archive")
        with tempfile.TemporaryDirectory(prefix="archive-convert-") as workspace:
            work = Path(workspace)
            entries: list[tuple[Path, str]] = []
            try:
                entries = self._extract(input_path, source_ext, work, ctx)
            except ConversionFailedError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.exception("Archive extraction failed for %s", source_ext)
                raise ConversionFailedError(f"Could not read this archive: {exc}") from exc

            if not entries:
                raise ConversionFailedError("This archive is empty.")

            ctx.update(60, f"Writing {target_ext.upper()} archive")
            self._pack(entries, output_path, target_ext, ctx)

        ctx.update(100, "Complete")
        return output_path

    # -- extraction -----------------------------------------------------

    def _extract(
        self, archive: Path, source_ext: str, work: Path, ctx: ConversionContext
    ) -> list[tuple[Path, str]]:
        extract_dir = work / "extracted"

        if source_ext in ("gz", "bz2", "xz"):
            # A bare .gz/.bz2/.xz is one compressed *file*, not a TAR
            # container, so it must be stream-decompressed rather than opened
            # with tarfile (which would fail on a non-TAR payload).
            self._decompress_single(archive, extract_dir, source_ext)
        elif source_ext in ("tar", "tgz"):
            self._extract_tar(archive, extract_dir, "r:gz" if source_ext == "tgz" else "r:")
        elif source_ext == "zip":
            self._extract_zip(archive, extract_dir)
        elif source_ext == "7z":
            self._extract_7z(archive, extract_dir, work)
        else:
            raise ConversionFailedError(f"Cannot read {source_ext.upper()} archives.")

        files: list[tuple[Path, str]] = []
        total = 0
        for path in sorted(extract_dir.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(extract_dir).as_posix()
            total += path.stat().st_size
            if total > MAX_EXPANDED_BYTES:
                raise ConversionFailedError(
                    "This archive expands to more than 2 GB, which is not allowed."
                )
            files.append((path, relative))
            if len(files) > MAX_MEMBERS:
                raise ConversionFailedError(
                    "This archive contains too many files to convert safely."
                )

        ctx.update(45, f"Found {len(files)} file(s)")
        return files

    def _decompress_single(self, archive: Path, destination: Path, source_ext: str) -> None:
        """Stream-decompress a bare .gz/.bz2/.xz, enforcing the size guard."""
        destination.mkdir(parents=True, exist_ok=True)
        # The original stem carries the real inner filename: "notes.txt.gz"
        # decompresses to "notes.txt".
        inner = archive.name[: -len(source_ext) - 1] or "decompressed"
        if inner.startswith(".") or "/" in inner or "\\" in inner or ".." in inner:
            inner = "decompressed"
        output = destination / inner

        written = 0
        try:
            with _open_decompressor(archive, source_ext) as reader, output.open("wb") as writer:
                while True:
                    chunk = reader.read(1024 * 1024)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > MAX_EXPANDED_BYTES:
                        raise ConversionFailedError(
                            "This file expands to more than 2 GB, which is not allowed."
                        )
                    writer.write(chunk)
        except ConversionFailedError:
            output.unlink(missing_ok=True)
            raise
        except (OSError, gzip.BadGzipFile, lzma.LZMAError, EOFError) as exc:
            output.unlink(missing_ok=True)
            raise ConversionFailedError(
                f"This {source_ext.upper()} file is damaged: {exc}"
            ) from exc

    def _extract_tar(self, archive: Path, destination: Path, mode: TarMode) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        try:
            with tarfile.open(archive, mode) as tar:
                members = []
                for member in tar:
                    if len(members) > MAX_MEMBERS:
                        raise ConversionFailedError("This archive contains too many members.")
                    _reject_unsafe_member(member.name, member.isdir())
                    if member.issym() or member.islnk():
                        _reject_unsafe_member(member.linkname, False)
                    members.append(member)
                tar.extractall(destination, members=members, filter="data")
        except tarfile.TarError as exc:
            raise ConversionFailedError(f"This TAR archive is damaged: {exc}") from exc

    def _extract_zip(self, archive: Path, destination: Path) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(archive) as zip_file:
                infos = zip_file.infolist()
                if len(infos) > MAX_MEMBERS:
                    raise ConversionFailedError("This archive contains too many entries.")
                total = sum(info.file_size for info in infos)
                if total > MAX_EXPANDED_BYTES:
                    raise ConversionFailedError(
                        "This archive expands to more than 2 GB, which is not allowed."
                    )
                for info in infos:
                    if info.is_dir():
                        continue
                    _reject_unsafe_member(info.filename, False)
                zip_file.extractall(destination)
        except zipfile.BadZipFile as exc:
            raise ConversionFailedError(f"This ZIP archive is damaged: {exc}") from exc

    def _extract_7z(self, archive: Path, destination: Path, work: Path) -> None:
        try:
            import py7zr
        except Exception as exc:  # py7zr raises ImportError from a C dependency
            raise DependencyMissingError(
                "7Z archives need the 'py7zr' package, which is not available on "
                "this server. Convert the archive with 7-Zip instead."
            ) from exc

        destination.mkdir(parents=True, exist_ok=True)
        try:
            with py7zr.SevenZipFile(archive, mode="r") as seven_zip:
                names = seven_zip.getnames()
                if len(names) > MAX_MEMBERS:
                    raise ConversionFailedError("This archive contains too many entries.")
                for name in names:
                    _reject_unsafe_member(name, False)
                seven_zip.extractall(path=destination)
        except ConversionFailedError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ConversionFailedError(f"This 7Z archive is damaged: {exc}") from exc

    # -- packing --------------------------------------------------------

    def _pack(
        self, entries: list[tuple[Path, str]], output: Path, target_ext: str, ctx: ConversionContext
    ) -> Path:
        output.parent.mkdir(parents=True, exist_ok=True)

        if target_ext == "zip":
            with zipfile.ZipFile(
                output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=COMPRESSION_LEVEL
            ) as zip_file:
                for path, arcname in entries:
                    zip_file.write(path, arcname)
            return output

        if target_ext in ("tar", "tgz"):
            mode = "w:gz" if target_ext == "tgz" else "w"
            with tarfile.open(output, mode) as tar:
                for path, arcname in entries:
                    tar.add(path, arcname=arcname, recursive=False)
            return output

        if target_ext in ("gz", "bz2", "xz"):
            if len(entries) != 1:
                raise ConversionFailedError(
                    f"{target_ext.upper()} can only hold a single file, but this "
                    "archive contains several. Convert to ZIP or TAR instead."
                )
            source, arcname = entries[0]
            _compress_single(source, output, target_ext)
            return output

        raise ConversionFailedError(f"Cannot write {target_ext.upper()} archives.")

    def supported_pairs(self) -> list[tuple[str, str]]:
        return [
            (source, target)
            for source in sorted(self.source_formats)
            for target in sorted(self.target_formats)
            if self.can_convert(source, target)
        ]


def _open_decompressor(archive: Path, source_ext: str):
    """Open a bare single-file compressed stream for reading."""
    if source_ext == "gz":
        return gzip.open(archive, "rb")
    if source_ext == "bz2":
        return bz2.open(archive, "rb")
    if source_ext == "xz":
        return lzma.open(archive, "rb")
    raise ConversionFailedError(f"Cannot decompress {source_ext.upper()} files.")


def _compress_single(source: Path, output: Path, target_ext: str) -> None:
    data = source.read_bytes()
    if target_ext == "gz":
        with gzip.open(output, "wb", compresslevel=COMPRESSION_LEVEL) as handle:
            handle.write(data)
    elif target_ext == "bz2":
        with bz2.open(output, "wb", compresslevel=COMPRESSION_LEVEL) as handle:
            handle.write(data)
    elif target_ext == "xz":
        with lzma.open(output, "wb") as handle:
            handle.write(data)
    else:
        raise ConversionFailedError(f"Cannot write {target_ext.upper()}.")


def _reject_unsafe_member(name: str, is_dir: bool) -> None:
    """Fail closed on absolute paths, drive letters, backslashes and '..'."""
    if not name:
        return
    normalized = name.replace("\\", "/")
    if normalized.startswith("/") or (len(normalized) > 1 and normalized[1] == ":"):
        raise ConversionFailedError("This archive contains an unsafe file path.")
    if ".." in Path(normalized).parts:
        raise ConversionFailedError("This archive contains an unsafe file path.")
