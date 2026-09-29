"""Conversion orchestration: job lifecycle, progress and error mapping."""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings, get_settings
from app.converters import registry
from app.converters.base import ConversionContext
from app.converters.formats import canonical_extension
from app.models.schemas import ConversionJob, JobStatus
from app.services.file_service import FileService
from app.services.store import InMemoryStore
from app.utils.errors import (
    ConversionFailedError,
    ConverterError,
    FileNotFoundError_,
    UnsupportedFormatError,
)
from app.utils.security import build_output_name, random_token, resolve_within

logger = logging.getLogger(__name__)

#: Error codes the client is allowed to see verbatim.
_PUBLIC_CODES = {"unsupported_format", "file_too_large", "file_not_found"}


class ConversionService:
    def __init__(
        self,
        store: InMemoryStore,
        file_service: FileService,
        settings: Settings | None = None,
    ) -> None:
        self.store = store
        self.file_service = file_service
        self.settings = settings or get_settings()
        self._executor = ThreadPoolExecutor(
            max_workers=self.settings.max_concurrent_jobs,
            thread_name_prefix="conversion",
        )
        self._active = threading.Semaphore(self.settings.max_concurrent_jobs)

    # -- public API -----------------------------------------------------

    def start(self, file_id: str, target_format: str) -> ConversionJob:
        info, input_path = self.file_service.get_upload(file_id)
        target = canonical_extension(target_format)

        if not target:
            raise UnsupportedFormatError("Please choose an output format.")
        if target == info.extension:
            raise UnsupportedFormatError(
                "The output format is the same as the input file."
            )
        if target not in info.available_formats:
            available = ", ".join(info.available_formats[:8])
            raise UnsupportedFormatError(
                f"Converting {info.extension.upper()} to {target.upper()} is not "
                f"supported. Available targets: {available}."
            )

        # Resolving now turns a bad pair into a 400 instead of a background failure.
        registry.resolve(info.extension, target)

        now = datetime.now(timezone.utc).isoformat()
        job = ConversionJob(
            id=random_token(),
            status=JobStatus.QUEUED,
            progress=0,
            stage="Queued",
            source_name=info.original_name,
            source_extension=info.extension,
            target_extension=target,
            created_at=now,
            updated_at=now,
        )
        self.store.save_job(job, None)

        self._executor.submit(
            self._run, job.id, info.extension, target, input_path, info.original_name
        )
        logger.info(
            "conversion queued job=%s src=%s dst=%s", job.id, info.extension, target
        )
        return job

    def get_job(self, job_id: str) -> ConversionJob:
        entry = self.store.get_job(job_id)
        if entry is None:
            raise FileNotFoundError_("This conversion job could not be found.")
        return entry[0]

    def get_output(self, job_id: str) -> tuple[ConversionJob, str]:
        entry = self.store.get_job(job_id)
        if entry is None:
            raise FileNotFoundError_("This conversion job could not be found.")
        job, output_path = entry
        if job.status is not JobStatus.COMPLETED or not output_path:
            raise FileNotFoundError_("This conversion has no downloadable output yet.")
        return job, output_path

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    # -- worker ---------------------------------------------------------

    def _run(
        self,
        job_id: str,
        source_ext: str,
        target_ext: str,
        input_path: Path,
        original_name: str,
    ) -> None:
        started = time.perf_counter()
        with self._active:
            self._progress(job_id, JobStatus.PROCESSING, 1, "Starting")

            try:
                converter = registry.resolve(source_ext, target_ext)
            except ConverterError as exc:
                self._fail(job_id, exc)
                return

            # Name the download after the user's file, not the randomised
            # on-disk storage name.
            output_name = build_output_name(original_name, target_ext)
            try:
                output_path = resolve_within(
                    self.settings.output_dir, f"{random_token()}-{output_name}"
                )
            except ValueError as exc:
                self._fail(job_id, ConversionFailedError("Invalid output name."))
                logger.error("output path rejected for job=%s: %s", job_id, exc)
                return

            def report(percent: int, stage: str) -> None:
                self._progress(job_id, JobStatus.PROCESSING, percent, stage)

            try:
                converter.convert(
                    input_path,
                    output_path,
                    ConversionContext(report=report),
                )
            except ConverterError as exc:
                output_path.unlink(missing_ok=True)
                self._fail(job_id, exc)
                return
            except Exception as exc:  # noqa: BLE001
                output_path.unlink(missing_ok=True)
                logger.exception("Unhandled conversion error job=%s", job_id)
                self._fail(
                    job_id,
                    ConversionFailedError("We couldn't convert this file. Please try again."),
                )
                return

            if not output_path.exists() or output_path.stat().st_size == 0:
                output_path.unlink(missing_ok=True)
                self._fail(
                    job_id,
                    ConversionFailedError("The conversion produced an empty file."),
                )
                return

            self.store.set_output_path(job_id, str(output_path))
            duration = time.perf_counter() - started
            now = datetime.now(timezone.utc).isoformat()
            self.store.update_job(
                job_id,
                status=JobStatus.COMPLETED,
                progress=100,
                stage="Complete",
                output_name=output_name,
                output_size_bytes=output_path.stat().st_size,
                updated_at=now,
            )
            logger.info(
                "conversion completed job=%s converter=%s out=%s bytes=%s in %.2fs",
                job_id,
                converter.name,
                output_name,
                output_path.stat().st_size,
                duration,
            )

    # -- helpers --------------------------------------------------------

    def _progress(self, job_id: str, status: JobStatus, percent: int, stage: str) -> None:
        self.store.update_job(
            job_id,
            status=status,
            progress=max(0, min(100, percent)),
            stage=stage,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

    def _fail(self, job_id: str, error: ConverterError) -> None:
        # The client sees a friendly message plus a stable code, never a stack trace.
        message = error.user_message
        if error.code in _PUBLIC_CODES and str(error):
            message = str(error)
        self.store.update_job(
            job_id,
            status=JobStatus.FAILED,
            stage="Failed",
            error=message,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        logger.warning(
            "conversion failed job=%s code=%s detail=%s", job_id, error.code, error
        )
