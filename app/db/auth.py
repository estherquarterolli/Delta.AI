"""Dependency de autenticação: valida o Bearer token do Supabase Auth.

Primeira rota autenticada do backend nasceu aqui (módulo de pesagens) —
`get_current_user` é a dependency reutilizável que qualquer rota
autenticada de qualquer módulo (`perfil`, `nutricao`, etc.) deve usar via
`Depends(get_current_user)`.
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase._async.client import AsyncClient

from app.db.supabase_client import SupabaseNaoConfiguradoError, criar_supabase_client

logger = structlog.get_logger("delta.auth")

_bearer_scheme = HTTPBearer(auto_error=False)

_ERRO_TOKEN_INVALIDO = "Token de autenticação ausente, inválido ou expirado."


@dataclass(frozen=True)
class User:
    """Usuário autenticado, extraído do JWT do Supabase Auth.

    Carrega também o client Supabase (`supabase`) já autenticado com o
    token do próprio usuário, pra os `repository.py` de cada módulo
    reusarem sem reconstruir a conexão a cada query — toda query feita
    com esse client passa pelas RLS policies (`auth.uid() = user_id`).
    """

    id: str
    email: str | None
    supabase: AsyncClient


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> User:
    """Valida o Bearer token do Supabase Auth e retorna o usuário autenticado.

    Levanta `401` se o token estiver ausente, for inválido ou tiver
    expirado. Nenhuma query ao banco é feita antes dessa validação —
    o client só é construído (e a chamada de verificação ao Supabase Auth
    só é feita) depois de confirmar que existe um Bearer token no request.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=_ERRO_TOKEN_INVALIDO
        )

    token = credentials.credentials

    try:
        client = await criar_supabase_client(token)
    except SupabaseNaoConfiguradoError as exc:
        logger.error("supabase_nao_configurado", erro=str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=_ERRO_TOKEN_INVALIDO
        ) from exc

    try:
        resposta = await client.auth.get_user(token)
    except Exception as exc:  # nunca vaza detalhe do provedor de auth pro cliente
        logger.warning("token_invalido", erro=str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=_ERRO_TOKEN_INVALIDO
        ) from exc

    if resposta is None or resposta.user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=_ERRO_TOKEN_INVALIDO
        )

    return User(id=resposta.user.id, email=resposta.user.email, supabase=client)
