"""Shared FastAPI dependencies and the standard error envelope."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.services import AppContainer, get_container
from app.utils.errors import ConverterError

logger = logging.getLogger(__name__)


ContainerDep = Annotated[AppContainer, Depends(get_container)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def error_response(error: ConverterError) -> JSONResponse:
    """Consistent JSON error body. Never leaks stack traces to the client."""
    return JSONResponse(
        status_code=error.http_status,
        content={
            "success": False,
            "data": None,
            "error": error.user_message,
            "code": error.code,
        },
    )


def install_exception_handlers(app: Any) -> None:
    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException as StarletteHTTPException

    @app.exception_handler(ConverterError)
    async def _converter_error(_: Request, exc: ConverterError) -> JSONResponse:
        logger.warning("request failed code=%s detail=%s", exc.code, exc)
        return error_response(exc)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        logger.info("request validation failed: %s", exc.errors())
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "data": None,
                "error": "The request was not valid. Please check your input.",
                "code": "validation_error",
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        messages = {
            404: "That endpoint could not be found.",
            405: "That method is not allowed for this endpoint.",
            413: "Your file exceeds the maximum allowed size.",
        }
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "data": None,
                "error": messages.get(exc.status_code, "Something went wrong. Please try again later."),
                "code": f"http_{exc.status_code}",
            },
        )

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "data": None,
                "error": "Something went wrong. Please try again later.",
                "code": "server_error",
            },
        )
