"""Converter plugin interface and the central registry.

Adding support for a new format pair means writing a :class:`BaseConverter`
subclass and registering it - no changes to routes, services or the frontend.
"""

from __future__ import annotations

import abc
import logging
from pathlib import Path

from app.models.schemas import Category
from app.utils.errors import UnsupportedFormatError

logger = logging.getLogger(__name__)


class ConversionContext:
    """Progress reporting handed to a running converter."""

    def __init__(self, report: "callable[[int, str], None] | None" = None) -> None:
        self._report = report

    def update(self, percent: int, stage: str) -> None:
        if self._report is not None:
            self._report(max(0, min(100, percent)), stage)


class BaseConverter(abc.ABC):
    """One converter handles a whole category of format pairs."""

    name: str = "base"
    category: Category = Category.DOCUMENT
    #: Extensions this converter accepts as input.
    source_formats: frozenset[str] = frozenset()
    #: Extensions this converter can produce.
    target_formats: frozenset[str] = frozenset()
    #: True when pairs inside target_formats are also valid inputs (e.g. images).
    transcode: bool = True

    @property
    def id(self) -> str:
        return self.name

    def can_convert(self, source_format: str, target_format: str) -> bool:
        source = source_format.lower().lstrip(".")
        target = target_format.lower().lstrip(".")
        if source not in self.source_formats or target not in self.target_formats:
            return False
        if source == target:
            return False
        if not self.transcode and source not in self.target_formats:
            return False
        return True

    def supported_pairs(self) -> list[tuple[str, str]]:
        return [
            (source, target)
            for source in sorted(self.source_formats)
            for target in sorted(self.target_formats)
            if self.can_convert(source, target)
        ]

    @abc.abstractmethod
    def convert(
        self,
        input_path: Path,
        output_path: Path,
        context: ConversionContext | None = None,
    ) -> Path:
        """Write the converted result to ``output_path`` and return it."""

    def _context(self, context: ConversionContext | None) -> ConversionContext:
        return context or ConversionContext()

    def _require(self, source_format: str, target_format: str) -> None:
        if not self.can_convert(source_format, target_format):
            raise UnsupportedFormatError(
                f"{self.name} cannot convert {source_format} to {target_format}."
            )


class ConverterRegistry:
    """Holds every registered converter and resolves format pairs."""

    def __init__(self) -> None:
        self._converters: dict[str, BaseConverter] = {}

    def register(self, converter: BaseConverter) -> BaseConverter:
        if converter.id in self._converters:
            raise ValueError(f"Converter id already registered: {converter.id}")
        self._converters[converter.id] = converter
        logger.debug("Registered converter %s", converter.id)
        return converter

    def unregister(self, converter_id: str) -> None:
        self._converters.pop(converter_id, None)

    def get(self, converter_id: str) -> BaseConverter | None:
        return self._converters.get(converter_id)

    def all(self) -> list[BaseConverter]:
        return list(self._converters.values())

    def resolve(self, source_format: str, target_format: str) -> BaseConverter:
        for converter in self._converters.values():
            if converter.can_convert(source_format, target_format):
                return converter
        raise UnsupportedFormatError(
            f"Conversion from {source_format} to {target_format} is not supported."
        )

    def targets_for(self, source_format: str) -> list[str]:
        """Every target format reachable from ``source_format``, deduplicated."""
        source = source_format.lower().lstrip(".")
        found: list[str] = []
        for converter in self._converters.values():
            for target in sorted(converter.target_formats):
                if target not in found and converter.can_convert(source, target):
                    found.append(target)
        return found

    def conversion_matrix(self) -> dict[str, list[str]]:
        matrix: dict[str, list[str]] = {}
        for converter in self._converters.values():
            for source, target in converter.supported_pairs():
                matrix.setdefault(source, [])
                if target not in matrix[source]:
                    matrix[source].append(target)
        return {key: sorted(value) for key, value in sorted(matrix.items())}

    def is_supported_source(self, extension: str) -> bool:
        extension = extension.lower().lstrip(".")
        return any(extension in c.source_formats for c in self._converters.values())


registry = ConverterRegistry()
