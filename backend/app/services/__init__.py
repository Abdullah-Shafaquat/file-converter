"""Service layer and the composition root for API dependencies."""

from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings, get_settings
from app.services.cleanup_service import CleanupService
from app.services.conversion_service import ConversionService
from app.services.file_service import FileService
from app.services.store import InMemoryStore

__all__ = [
    "AppContainer",
    "CleanupService",
    "ConversionService",
    "FileService",
    "InMemoryStore",
    "get_container",
]


@dataclass
class AppContainer:
    """Single place where services are constructed and wired together."""

    settings: Settings
    store: InMemoryStore
    file_service: FileService
    conversion_service: ConversionService
    cleanup_service: CleanupService

    @classmethod
    def build(cls, settings: Settings | None = None) -> "AppContainer":
        settings = settings or get_settings()
        settings.ensure_directories()

        store = InMemoryStore()
        file_service = FileService(store, settings)
        conversion_service = ConversionService(store, file_service, settings)
        cleanup_service = CleanupService(store, settings)

        return cls(
            settings=settings,
            store=store,
            file_service=file_service,
            conversion_service=conversion_service,
            cleanup_service=cleanup_service,
        )

    def shutdown(self) -> None:
        self.cleanup_service.stop()
        self.conversion_service.shutdown()


_container: AppContainer | None = None


def get_container() -> AppContainer:
    global _container
    if _container is None:
        _container = AppContainer.build()
    return _container


def reset_container() -> None:
    """Used by tests to get a fresh, isolated container."""
    global _container
    if _container is not None:
        _container.shutdown()
    _container = None
