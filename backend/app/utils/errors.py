"""Domain-specific exceptions mapped to HTTP responses by the API layer."""

from __future__ import annotations


class ConverterError(Exception):
    """Base class for all recoverable converter errors."""

    code = "conversion_error"
    http_status = 500
    user_message = "We couldn't convert this file. Please try again."


class UnsupportedFormatError(ConverterError):
    code = "unsupported_format"
    http_status = 400
    user_message = "Sorry, this file format is not supported."


class FileTooLargeError(ConverterError):
    code = "file_too_large"
    http_status = 413
    user_message = "Your file exceeds the maximum allowed size."


class FileNotFoundError_(ConverterError):
    code = "file_not_found"
    http_status = 404
    user_message = "The requested file could not be found. It may have expired."


class ConversionFailedError(ConverterError):
    code = "conversion_failed"
    http_status = 422
    user_message = "We couldn't convert this file. Please try again."


class DependencyMissingError(ConverterError):
    code = "dependency_missing"
    http_status = 503
    user_message = "A required conversion tool is not available on this server."


class ServerError(ConverterError):
    code = "server_error"
    http_status = 500
    user_message = "Something went wrong. Please try again later."
