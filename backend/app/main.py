"""FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.dependencies import install_exception_handlers
from app.api.routes import conversions, files, health
from app.config import get_settings
from app.converters import registry
from app.services import get_container
from app.utils.logging_config import configure_logging

logger = logging.getLogger(__name__)

DESCRIPTION = """
Local-first universal file converter.

**Flow**

1. `POST /api/upload` - store a file, get back an id and the list of targets.
2. `POST /api/convert` - queue a job (`file_id` + `target_format`).
3. `GET /api/conversions/{id}` - poll until `completed` or `failed`.
4. `GET /api/download/{id}` - download the result.
5. `DELETE /api/files/{id}` - remove your upload early.

Uploads are stored under randomised names in an isolated temp directory and are
deleted automatically after `FILE_RETENTION_MINUTES`.

**Not supported?** If a format pair is absent from `GET /api/formats`, it is
genuinely not available on this server - the app never fakes a conversion.
Legacy `DOC`/`ODT`/`RTF`/`XLS` need LibreOffice; without it those pairs are
simply not advertised.
"""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    container = get_container()
    container.cleanup_service.start()
    logger.info(
        "%s ready | env=%s | max=%sMB | retention=%smin | converters=%s",
        settings.app_name,
        settings.app_env,
        settings.max_file_size_mb,
        settings.file_retention_minutes,
        [converter.name for converter in registry.all()],
    )
    try:
        yield
    finally:
        container.shutdown()
        logger.info("shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging("INFO" if settings.app_env != "test" else "WARNING")

    app = FastAPI(
        title=settings.app_name,
        description=DESCRIPTION,
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )

    install_exception_handlers(app)

    prefix = settings.api_prefix
    app.include_router(health.router, prefix=prefix, tags=["health"])
    app.include_router(files.router, prefix=prefix)
    app.include_router(conversions.router, prefix=prefix)

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, Any]:
        return {
            "name": settings.app_name,
            "docs": "/docs",
            "health": f"{prefix}/health",
            "formats": f"{prefix}/formats",
        }

    return app


app = create_app()
