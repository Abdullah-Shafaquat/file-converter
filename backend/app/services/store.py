"""In-memory store for uploads and conversion jobs.

Deliberately swappable: the service layer only uses this interface, so a
database-backed implementation can replace it later without touching routes.
"""

from __future__ import annotations

import threading
from typing import Protocol

from app.models.schemas import ConversionJob, JobStatus, UploadedFileInfo


class JobStore(Protocol):
    def save_upload(self, info: UploadedFileInfo, path: str) -> None: ...
    def get_upload(self, file_id: str) -> tuple[UploadedFileInfo, str] | None: ...
    def delete_upload(self, file_id: str) -> None: ...

    def save_job(self, job: ConversionJob, output_path: str | None) -> None: ...
    def get_job(self, job_id: str) -> tuple[ConversionJob, str | None] | None: ...
    def update_job(self, job_id: str, **changes: object) -> ConversionJob | None: ...
    def delete_job(self, job_id: str) -> None: ...


class InMemoryStore:
    """Thread-safe dictionaries guarded by a single lock.

    Fine for a single-process MVP. Swap for Redis/Postgres when scaling out.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._uploads: dict[str, tuple[UploadedFileInfo, str]] = {}
        self._jobs: dict[str, tuple[ConversionJob, str | None]] = {}

    # -- uploads --------------------------------------------------------

    def save_upload(self, info: UploadedFileInfo, path: str) -> None:
        with self._lock:
            self._uploads[info.id] = (info, path)

    def get_upload(self, file_id: str) -> tuple[UploadedFileInfo, str] | None:
        with self._lock:
            return self._uploads.get(file_id)

    def delete_upload(self, file_id: str) -> None:
        with self._lock:
            self._uploads.pop(file_id, None)

    # -- jobs -----------------------------------------------------------

    def save_job(self, job: ConversionJob, output_path: str | None) -> None:
        with self._lock:
            self._jobs[job.id] = (job, output_path)

    def get_job(self, job_id: str) -> tuple[ConversionJob, str | None] | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update_job(self, job_id: str, **changes: object) -> ConversionJob | None:
        with self._lock:
            entry = self._jobs.get(job_id)
            if entry is None:
                return None
            job = entry[0].model_copy(update=changes)
            self._jobs[job_id] = (job, entry[1])
            return job

    def set_output_path(self, job_id: str, output_path: str) -> None:
        with self._lock:
            entry = self._jobs.get(job_id)
            if entry is not None:
                self._jobs[job_id] = (entry[0], output_path)

    def delete_job(self, job_id: str) -> None:
        with self._lock:
            self._jobs.pop(job_id, None)

    # -- maintenance ----------------------------------------------------

    def all_uploads(self) -> list[tuple[UploadedFileInfo, str]]:
        with self._lock:
            return list(self._uploads.values())

    def all_jobs(self) -> list[tuple[ConversionJob, str | None]]:
        with self._lock:
            return list(self._jobs.values())

    def clear(self) -> None:
        with self._lock:
            self._uploads.clear()
            self._jobs.clear()
