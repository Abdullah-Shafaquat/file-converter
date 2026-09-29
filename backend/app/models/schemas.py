"""Pydantic schemas exposed by the API."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Category(str, Enum):
    """Categories exposed by this build.

    Audio and video are intentionally absent: no converter implements them,
    so they must never reach the client.
    """

    DOCUMENT = "document"
    IMAGE = "image"
    ARCHIVE = "archive"


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ApiResponse(BaseModel):
    success: bool = True
    data: Any | None = None
    error: str | None = None
    code: str | None = None


class FormatInfo(BaseModel):
    extension: str
    label: str
    category: Category
    mime_types: list[str] = Field(default_factory=list)


class CategoryInfo(BaseModel):
    id: Category
    label: str
    description: str
    formats: list[FormatInfo]


class FormatsResponse(BaseModel):
    categories: list[CategoryInfo]
    conversions: dict[str, list[str]]
    max_file_size_mb: int
    external_tools: dict[str, bool]


class UploadedFileInfo(BaseModel):
    id: str
    original_name: str
    extension: str
    category: Category | None = None
    size_bytes: int
    mime_type: str | None = None
    label: str | None = None
    available_formats: list[str] = Field(default_factory=list)
    uploaded_at: str


class ConversionJob(BaseModel):
    id: str
    status: JobStatus
    progress: int = 0
    stage: str | None = None
    source_name: str | None = None
    source_extension: str | None = None
    target_extension: str | None = None
    output_name: str | None = None
    output_size_bytes: int | None = None
    error: str | None = None
    created_at: str
    updated_at: str
