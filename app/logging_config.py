"""Configuração de logging estruturado (structlog) do backend.

Centraliza a config do structlog e o middleware de logging de
requests, mantendo `app/main.py` enxuto. Em produção (qualquer
`environment` diferente de `"development"`) os logs saem em JSON,
prontos pra um coletor (ex. Fly.io logs, Sentry breadcrumbs); em
desenvolvimento saem formatados pra leitura no console.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import Settings

logger = structlog.get_logger("delta.request")


def configure_logging(settings: Settings) -> None:
    """Configura o structlog uma única vez, na inicialização da app."""
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    renderer: structlog.types.Processor
    if settings.environment == "development":
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Loga cada request com method, path, status_code, duração e request_id.

    O `request_id` (uuid4) também é devolvido no header `X-Request-ID`
    da resposta, útil pro frontend correlacionar erros com logs do
    backend/Sentry.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = str(uuid.uuid4())
        start = time.perf_counter()

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_finished",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response
