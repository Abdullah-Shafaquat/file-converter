"""Safe subprocess execution for external converters."""

from __future__ import annotations

import logging
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

from app.config import Settings, get_settings
from app.utils.errors import ConversionFailedError, DependencyMissingError

logger = logging.getLogger(__name__)

# Cap captured output so a misbehaving encoder cannot exhaust memory.
MAX_CAPTURED_BYTES = 256 * 1024


@lru_cache
def find_executable(candidate: str) -> str | None:
    """Resolve an executable name or path, returning None when absent."""
    if not candidate:
        return None

    direct = Path(candidate)
    if direct.is_file():
        return str(direct)

    if direct.is_absolute():
        return None

    return shutil.which(candidate)


@lru_cache
def tool_available(candidate: str) -> bool:
    return find_executable(candidate) is not None


def require_tool(candidate: str, friendly_name: str) -> str:
    """Return the resolved executable path or raise a user-safe error."""
    resolved = find_executable(candidate)
    if resolved is None:
        logger.warning("Required tool unavailable: %s (%s)", friendly_name, candidate)
        raise DependencyMissingError(
            f"{friendly_name} is not installed on the server, "
            f"so this conversion cannot run here."
        )
    return resolved


def run_command(
    args: list[str],
    *,
    cwd: Path | None = None,
    timeout: int | None = None,
    settings: Settings | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Run an external tool with an argument list (never a shell string).

    ``shell=False`` is mandatory: uploaded filenames are untrusted and are
    never interpolated into a command line.
    """
    settings = settings or get_settings()
    timeout = timeout or settings.conversion_timeout_seconds

    logger.info("exec: %s", " ".join(args))
    try:
        process = subprocess.run(  # noqa: S603 - args list, shell=False
            args,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            timeout=timeout,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ConversionFailedError(
            f"{Path(args[0]).name} timed out after {timeout} seconds."
        ) from exc
    except OSError as exc:
        raise DependencyMissingError(
            f"Could not start {Path(args[0]).name}: {exc.strerror or exc}"
        ) from exc

    if process.returncode != 0:
        detail = _tail(process.stderr) or _tail(process.stdout)
        logger.warning(
            "command failed rc=%s cmd=%s detail=%s",
            process.returncode,
            " ".join(args),
            detail,
        )
        raise ConversionFailedError(
            f"{Path(args[0]).name} exited with status {process.returncode}."
        )

    return process


def _tail(stream: bytes | None, limit: int = 800) -> str:
    if not stream:
        return ""
    text = stream[-MAX_CAPTURED_BYTES:].decode("utf-8", errors="replace").strip()
    return text[-limit:]
