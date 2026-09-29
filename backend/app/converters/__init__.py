"""Converter registry bootstrap.

Importing this module registers every converter exactly once. To add a new
one: write the class, import it here, call ``registry.register``.
"""

from __future__ import annotations

from app.converters.archive_converter import ArchiveConverter
from app.converters.base import BaseConverter, ConversionContext, ConverterRegistry, registry
from app.converters.document_converter import DocumentConverter
from app.converters.image_converter import ImageConverter

__all__ = [
    "ArchiveConverter",
    "BaseConverter",
    "ConversionContext",
    "ConverterRegistry",
    "DocumentConverter",
    "ImageConverter",
    "build_registry",
    "registry",
]


def build_registry() -> ConverterRegistry:
    """Return the fully populated registry."""
    instance = ConverterRegistry()
    instance.register(ImageConverter())
    instance.register(DocumentConverter())
    instance.register(ArchiveConverter())
    return instance


registry = build_registry()
