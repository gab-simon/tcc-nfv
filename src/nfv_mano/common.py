"""Shared helpers: ids, logging and error handling."""

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


def generate_id(prefix: str = "") -> str:
    """Return a unique identifier, optionally prefixed."""
    return f"{prefix}{uuid.uuid4().hex}"


def configure_logging(component: str, level: int | str = logging.INFO) -> logging.Logger:
    """Return a logger for a component with a single handler."""
    logger = logging.getLogger(component)
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                "%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)
    return logger


class NFVManoError(Exception):
    """Base class for all NFV-MANO errors."""


class NotFoundError(NFVManoError):
    """A requested entity or resource does not exist."""


class ConflictError(NFVManoError):
    """An entity already exists or conflicts with the current state."""


class InvalidStateError(NFVManoError):
    """An operation is not allowed for the current lifecycle state."""


class RepositoryError(NFVManoError):
    """A data repository backend failed to read or write state."""


class DriverError(NFVManoError):
    """A VIM driver failed to manage NFVI resources."""


class VimClientError(NFVManoError):
    """A call to the VIM on ``Vi-Vnfm`` failed."""


class VnfmClientError(NFVManoError):
    """A call to the VNFM on ``Or-Vnfm`` failed."""


_ERROR_STATUS = {
    NotFoundError: 404,
    ConflictError: 409,
    InvalidStateError: 409,
    DriverError: 502,
    VimClientError: 502,
    VnfmClientError: 502,
    RepositoryError: 500,
}


def register_exception_handlers(app: FastAPI) -> None:
    """Map NFV-MANO exceptions to HTTP status codes."""

    @app.exception_handler(NFVManoError)
    async def _handle(request: Request, exc: NFVManoError) -> JSONResponse:
        return JSONResponse(
            status_code=_ERROR_STATUS.get(type(exc), 500),
            content={"detail": str(exc), "type": type(exc).__name__},
        )
