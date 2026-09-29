"""Health and readiness routes."""

from __future__ import annotations

import shutil
import time
from typing import Any

from fastapi import APIRouter

from app.api.dependencies import ContainerDep
from app.converters import registry
from app.converters.document_converter import libreoffice_path
from app.utils.executor import find_executable

router = APIRouter(tags=["health"])

STARTED_AT = time.time()


@router.get("/health", summary="Liveness and dependency report")
def health(container: ContainerDep) -> dict[str, Any]:
    settings = container.settings

    packages: dict[str, bool] = {}
    for module_name, label in (
        ("PIL", "pillow"),
        ("pdfplumber", "pdfplumber"),
        ("reportlab", "reportlab"),
        ("docx", "python-docx"),
        ("openpyxl", "openpyxl"),
        ("bs4", "beautifulsoup4"),
        ("markdown", "markdown"),
        ("yaml", "pyyaml"),
        ("svglib", "svglib"),
    ):
        try:
            __import__(module_name)
            packages[label] = True
        except ImportError:
            packages[label] = False

    # py7zr can fail inside a compiled dependency, so check it directly.
    from app.converters.archive_converter import seven_zip_support
    from app.converters.image_converter import svg_raster_support

    packages["py7zr"] = seven_zip_support()
    packages["svg_raster"] = svg_raster_support()

    converters = [converter.name for converter in registry.all()]
    conversion_pairs = sum(len(targets) for targets in registry.conversion_matrix().values())

    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.app_env,
        "uptime_seconds": round(time.time() - STARTED_AT, 1),
        "limits": {
            "max_file_size_mb": settings.max_file_size_mb,
            "retention_minutes": settings.file_retention_minutes,
            "max_concurrent_jobs": settings.max_concurrent_jobs,
        },
        "converters": converters,
        "supported_conversions": conversion_pairs,
        "dependencies": {
            "python_packages": packages,
            "external_tools": {
                "libreoffice": {
                    "available": libreoffice_path() is not None,
                    "required_for": ["doc", "odt", "rtf", "xls"],
                },
                "ffmpeg": {
                    "available": find_executable(settings.ffmpeg_path) is not None,
                    "required_for": [],
                    "note": "This build is document/image/archive only, so ffmpeg is unused.",
                },
            },
        },
        "disk_free_bytes": shutil.disk_usage(str(settings.upload_dir)).free,
    }
