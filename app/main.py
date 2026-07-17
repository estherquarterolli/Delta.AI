"""Ponto de entrada da API FastAPI do Delta.AI.

Este módulo só monta a aplicação e registra o essencial (health
check, CORS, routers dos módulos de domínio). Lógica de negócio vive
em app/modules/*; nada é implementado diretamente aqui.
"""

from fastapi import FastAPI

app = FastAPI(
    title="Delta.AI API",
    description="Backend do app de acompanhamento de emagrecimento.",
    version="0.1.0",
)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Health check usado pelo Fly.io pra restart automático da VM."""
    return {"status": "ok"}


# Routers dos módulos de domínio (perfil, nutricao, treinos, fotos,
# chat, notificacoes) são registrados aqui pelo backend-engineer à
# medida que forem implementados. Ex.:
#
# from app.modules.perfil.router import router as perfil_router
# app.include_router(perfil_router, prefix="/perfil", tags=["perfil"])
