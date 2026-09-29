"""Conversion lifecycle, status and download routes."""

from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.api.dependencies import ContainerDep
from app.converters import registry
from app.converters.document_converter import libreoffice_path
from app.converters.formats import canonical_extension
from app.models.schemas import ApiResponse, ConversionJob, FormatsResponse
from app.services.cleanup_service import delete_conversion_output
from app.utils.executor import find_executable

logger = logging.getLogger(__name__)

router = APIRouter(tags=["conversions"])


class ConvertRequest(BaseModel):
    file_id: str = Field(..., min_length=8, description="Id returned by POST /api/upload")
    target_format: str = Field(..., min_length=1, description="Target extension, e.g. 'pdf'")

    def normalized_target(self) -> str:
        return canonical_extension(self.target_format)


@router.post(
    "/convert",
    response_model=ApiResponse,
    status_code=202,
    summary="Start a conversion",
)
def start_conversion(payload: ConvertRequest, container: ContainerDep) -> ApiResponse:
    """Queue a job. Poll GET /api/conversions/{id} for progress."""
    job = container.conversion_service.start(
        payload.file_id, payload.normalized_target()
    )
    return ApiResponse(success=True, data=job)


@router.get(
    "/conversions/{job_id}",
    response_model=ApiResponse,
    summary="Get conversion status",
)
def get_conversion(job_id: str, container: ContainerDep) -> ApiResponse:
    job = container.conversion_service.get_job(job_id)
    return ApiResponse(success=True, data=job)


@router.get(
    "/download/{job_id}",
    summary="Download the converted file",
    response_class=FileResponse,
)
def download_conversion(job_id: str, container: ContainerDep) -> FileResponse:
    job, output_path = container.conversion_service.get_output(job_id)
    path = Path(output_path)
    download_name = job.output_name or f"{job.id}.{job.target_extension}"
    return FileResponse(
        path=str(path),
        media_type="application/octet-stream",
        filename=download_name,
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{download_name}\"; "
                f"filename*=UTF-8''{quote(download_name)}"
            )
        },
    )


@router.delete(
    "/conversions/{job_id}",
    response_model=ApiResponse,
    summary="Delete a conversion result",
)
def delete_conversion(job_id: str, container: ContainerDep) -> ApiResponse:
    delete_conversion_output(job_id, container.store)
    return ApiResponse(success=True, data={"id": job_id, "deleted": True})


@router.get(
    "/formats",
    response_model=ApiResponse,
    summary="Supported formats and conversions",
)
def list_formats(container: ContainerDep) -> ApiResponse:
    """The backend is the single source of truth for the conversion matrix."""
    settings = container.settings
    response = FormatsResponse(
        categories=_categories(container),
        conversions=registry.conversion_matrix(),
        max_file_size_mb=settings.max_file_size_mb,
        external_tools={
            "libreoffice": libreoffice_path() is not None,
            "ffmpeg": find_executable(settings.ffmpeg_path) is not None,
        },
    )
    return ApiResponse(success=True, data=response)


def _categories(container) -> list:
    """Build the category cards, advertising only formats converters support.

    The metadata table also carries formats no converter reads (EPUB) or that
    need a missing optional package, so it is intersected with what the
    registry can actually turn into something.
    """
    from app.converters.formats import CATEGORY_DESCRIPTIONS, FORMATS
    from app.models.schemas import Category, CategoryInfo, FormatInfo

    matrix = registry.conversion_matrix()
    convertible: set[str] = set(matrix)
    for targets in matrix.values():
        convertible.update(targets)

    result: list[CategoryInfo] = []
    for category in Category:
        formats = [
            FormatInfo(
                extension=extension,
                label=spec.label,
                category=category,
                mime_types=list(spec.mime_types),
            )
            for extension, spec in sorted(FORMATS.items())
            if spec.category is category and extension in convertible
        ]
        result.append(
            CategoryInfo(
                id=category,
                label=category.value.title(),
                description=CATEGORY_DESCRIPTIONS.get(category, ""),
                formats=formats,
            )
        )
    return result
