"""Upload and file-deletion routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, UploadFile

from app.api.dependencies import ContainerDep
from app.models.schemas import ApiResponse, UploadedFileInfo

logger = logging.getLogger(__name__)

router = APIRouter(tags=["files"])


@router.post(
    "/upload",
    response_model=ApiResponse,
    summary="Upload a file for conversion",
)
async def upload_file(container: ContainerDep, file: UploadFile = File(...)) -> ApiResponse:
    """Store an upload in an isolated temp directory and report its targets."""
    info = await container.file_service.store_upload(file)
    return ApiResponse(success=True, data=info)


@router.delete(
    "/files/{file_id}",
    response_model=ApiResponse,
    summary="Delete an uploaded file",
)
def delete_file(file_id: str, container: ContainerDep) -> ApiResponse:
    container.file_service.delete_upload(file_id)
    return ApiResponse(success=True, data={"id": file_id, "deleted": True})


@router.get(
    "/files/{file_id}",
    response_model=ApiResponse,
    summary="Get upload details",
)
def get_file(file_id: str, container: ContainerDep) -> ApiResponse:
    info, _ = container.file_service.get_upload(file_id)
    return ApiResponse(success=True, data=info)
