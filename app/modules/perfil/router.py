"""Rotas do módulo de perfil: cálculo de IMC e condições de saúde
relevantes pra ele (`esta_gestante`), sempre do usuário autenticado."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.db.auth import User, get_current_user

from .schemas import CondicoesSaudeOut, CondicoesSaudeUpdate, ImcOut, PerfilIncompletoOut
from .service import PerfilIncompletoError, atualizar_esta_gestante, calcular_imc_usuario

router = APIRouter(prefix="/perfil", tags=["perfil"])


@router.get(
    "/imc",
    response_model=ImcOut,
    responses={
        422: {
            "model": PerfilIncompletoOut,
            "description": "Perfil incompleto para calcular o IMC.",
        }
    },
)
async def obter_imc(user: User = Depends(get_current_user)) -> ImcOut | JSONResponse:
    """Retorna o IMC do usuário autenticado (elegível ou bloqueado por
    idade/gestação) ou `422 PERFIL_INCOMPLETO` se faltar altura, data de
    nascimento e/ou pesagem.

    `401` (token ausente/inválido/expirado) é resolvido antes de qualquer
    leitura, pelo próprio `Depends(get_current_user)`. Um `ValueError`
    inesperado de `calcular_imc` (dado corrompido fora da faixa
    fisiológica esperada — não deveria acontecer, os `CHECK`s do banco já
    impedem) propaga sem tratamento especial e vira `500` genérico,
    capturado pelo Sentry, sem vazar detalhe/stack trace pro cliente.
    """
    try:
        return await calcular_imc_usuario(user)
    except PerfilIncompletoError as exc:
        # O contrato deste endpoint (specs/2026-07-17-calculo-imc.md) exige
        # um corpo top-level (`erro`/`mensagem`/`campos_faltantes`), sem o
        # envelope `{"detail": ...}` padrão de `HTTPException` — por isso a
        # resposta é montada manualmente aqui, mesmo padrão já usado em
        # `/health/db` (ver app/main.py) para respostas de erro com formato
        # próprio.
        return JSONResponse(
            status_code=422,
            content={
                "erro": "PERFIL_INCOMPLETO",
                "mensagem": "Complete seu perfil para calcular o IMC.",
                "campos_faltantes": exc.campos_faltantes,
            },
        )


@router.patch("/condicoes-saude", response_model=CondicoesSaudeOut)
async def atualizar_condicoes_saude(
    payload: CondicoesSaudeUpdate,
    user: User = Depends(get_current_user),
) -> CondicoesSaudeOut:
    """Grava `esta_gestante` do usuário autenticado.

    UPSERT por `user_id` em `condicoes_saude` (tabela sem trigger de
    auto-criação no signup — ver `repository.upsert_esta_gestante`), sem
    afetar outros campos já preenchidos (ex.: `condicoes`). `user_id`
    nunca vem do body/URL — sempre de `get_current_user`, e a escrita
    passa pelo client autenticado com o token do próprio usuário (RLS
    `auth.uid() = user_id`, nunca `service_role`).
    """
    esta_gestante = await atualizar_esta_gestante(user, esta_gestante=payload.esta_gestante)
    return CondicoesSaudeOut(esta_gestante=esta_gestante)
