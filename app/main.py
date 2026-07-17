"""Ponto de entrada da API FastAPI do Delta.AI.

Este módulo só monta a aplicação e registra o essencial (health
check, CORS, logging estruturado, Sentry, routers dos módulos de
domínio). Lógica de negócio vive em app/modules/*; nada é
implementado diretamente aqui.
"""

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sentry_sdk.integrations.fastapi import FastApiIntegration

from app.config import get_settings
from app.db.health import DatabaseUnavailableError, check_db_connection
from app.logging_config import RequestLoggingMiddleware, configure_logging
from app.modules.perfil.router import router as perfil_router
from app.modules.pesagens.router import router as pesagens_router

# Versão única da API — lida por /health, nunca hardcoded em outro lugar.
API_VERSION = "0.0.1"

settings = get_settings()
configure_logging(settings)

if settings.sentry_dsn_backend:
    sentry_sdk.init(
        dsn=settings.sentry_dsn_backend,
        integrations=[FastApiIntegration()],
        traces_sample_rate=0.1,
        environment=settings.environment,
    )

app = FastAPI(
    title="Delta.AI API",
    description="Backend do app de acompanhamento de emagrecimento.",
    version=API_VERSION,
)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Health check usado pelo Fly.io pra restart automático da VM."""
    return {"status": "ok", "version": API_VERSION}


@app.get("/health/db")
async def health_check_db() -> JSONResponse:
    """Testa a conexão com o Postgres (Supabase) via `DATABASE_URL`.

    Nunca derruba a app se o banco estiver indisponível ou não
    configurado — só reporta o status via HTTP 503.
    """
    try:
        await check_db_connection()
    except DatabaseUnavailableError as exc:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "db": "unreachable", "detail": str(exc)},
        )
    return JSONResponse(content={"status": "ok", "db": "reachable"})


# Routers dos módulos de domínio (perfil, nutricao, treinos, fotos,
# chat, notificacoes) são registrados aqui pelo backend-engineer à
# medida que forem implementados. Cada router já define seu próprio
# `prefix`/`tags` (ver app/modules/<nome>/router.py) — não repetir aqui.
app.include_router(pesagens_router)
app.include_router(perfil_router)
