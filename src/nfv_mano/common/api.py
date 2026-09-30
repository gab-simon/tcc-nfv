"""Shared FastAPI helpers for the NFV-MANO reference points."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from nfv_mano.common.exceptions import (
    ConflictError,
    DriverError,
    InvalidStateError,
    NFVManoError,
    NotFoundError,
    RepositoryError,
    VimClientError,
    VnfmClientError,
)

_ERROR_STATUS: dict[type[NFVManoError], int] = {
    NotFoundError: 404,
    ConflictError: 409,
    InvalidStateError: 409,
    DriverError: 502,
    VimClientError: 502,
    VnfmClientError: 502,
    RepositoryError: 500,
}


def register_exception_handlers(app: FastAPI) -> None:
    """Map NFV-MANO exceptions to HTTP status codes.

    Keeps the API layer thin: components raise domain exceptions and the
    reference point answers with the proper ETSI-style error status.
    """

    @app.exception_handler(NFVManoError)
    async def _handle(request: Request, exc: NFVManoError) -> JSONResponse:
        status_code = _ERROR_STATUS.get(type(exc), 500)
        return JSONResponse(
            status_code=status_code,
            content={"detail": str(exc), "type": type(exc).__name__},
        )
