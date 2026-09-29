"""Background cleanup of expired uploads, outputs and store entries."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings, get_settings
from app.services.store import InMemoryStore
from app.utils.errors import FileNotFoundError_

logger = logging.getLogger(__name__)


class CleanupService:
    """Deletes temp files older than the retention window on a fixed interval.

    Files are also removed eagerly on DELETE /api/files/{id}, so a user never
    has to wait for the sweeper.
    """

    def __init__(self, store: InMemoryStore, settings: Settings | None = None) -> None:
        self.store = store
        self.settings = settings or get_settings()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="cleanup", daemon=True
        )
        self._thread.start()
        logger.info(
            "cleanup service started interval=%ss retention=%smin",
            self.settings.cleanup_interval_seconds,
            self.settings.file_retention_minutes,
        )

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def run_once(self) -> dict[str, int]:
        """Sweep expired files. Exposed so tests can call it directly."""
        cutoff = time.time() - (self.settings.file_retention_minutes * 60)
        removed = {"uploads": 0, "outputs": 0, "entries": 0}

        for info, stored_path in self.store.all_uploads():
            # Honour the recorded upload time as well as the file mtime, so an
            # entry cannot outlive its retention window just because the file
            # was touched after it was stored.
            if self._expired(stored_path, cutoff) or self._expired(
                created=info.uploaded_at, cutoff=cutoff
            ):
                Path(stored_path).unlink(missing_ok=True)
                self.store.delete_upload(info.id)
                removed["uploads"] += 1
                removed["entries"] += 1

        for job, output_path in self.store.all_jobs():
            if output_path and self._expired(output_path, cutoff):
                Path(output_path).unlink(missing_ok=True)
                removed["outputs"] += 1
            if self._expired(created=job.created_at, cutoff=cutoff):
                if output_path:
                    Path(output_path).unlink(missing_ok=True)
                self.store.delete_job(job.id)
                removed["entries"] += 1

        # Orphan sweep: anything on disk with no store entry past the cutoff.
        for directory in (self.settings.upload_dir, self.settings.output_dir):
            for path in directory.glob("*"):
                if not path.is_file():
                    continue
                if self._expired(str(path), cutoff) and not self._tracked(path):
                    path.unlink(missing_ok=True)
                    removed["uploads" if directory == self.settings.upload_dir else "outputs"] += 1

        if any(removed.values()):
            logger.info("cleanup removed %s", removed)
        return removed

    def _loop(self) -> None:
        interval = max(5, self.settings.cleanup_interval_seconds)
        while not self._stop.wait(interval):
            try:
                self.run_once()
            except Exception:  # noqa: BLE001 - a sweeper must never crash the app
                logger.exception("cleanup sweep failed")

    def _tracked(self, path: Path) -> bool:
        target = str(path)
        return any(stored == target for _, stored in self.store.all_uploads()) or any(
            output == target for _, output in self.store.all_jobs() if output
        )

    @staticmethod
    def _expired(
        path: str | Path | None = None,
        cutoff: float = 0.0,
        *,
        created: str | None = None,
    ) -> bool:
        """True when a path or timestamp predates the retention cutoff.

        A missing file counts as expired so the caller can drop its store entry.
        """
        if created is not None:
            try:
                timestamp = datetime.fromisoformat(created).timestamp()
            except ValueError:
                return True
            return timestamp < cutoff

        if not path:
            return True
        candidate = Path(path)
        if not candidate.exists():
            return True
        return candidate.stat().st_mtime < cutoff


def delete_conversion_output(job_id: str, store: InMemoryStore) -> bool:
    entry = store.get_job(job_id)
    if entry is None:
        raise FileNotFoundError_("This conversion job could not be found.")
    job, output_path = entry
    if output_path:
        Path(output_path).unlink(missing_ok=True)
    store.delete_job(job_id)
    logger.info("deleted conversion output job=%s", job_id)
    return True
