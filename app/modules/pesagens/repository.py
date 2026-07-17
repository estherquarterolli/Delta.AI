"""Acesso à tabela `public.pesagens` via Supabase (client autenticado do
usuário — RLS decide o que cada um vê/altera). Nenhuma query aqui filtra
por `user_id` manualmente pra suprir RLS: a policy `auth.uid() = user_id`
já garante isolamento; o `user_id` só é enviado no `insert`.

Este é o único arquivo do backend que conhece o schema de `pesagens`.
Qualquer outro módulo (ex.: `app/modules/perfil`) deve consumir
`app.modules.pesagens.service.obter_pesagem_mais_recente`, nunca esta
tabela direto — ver `specs/2026-07-17-registro-de-peso.md`.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import structlog
from postgrest.exceptions import APIError

from app.db.auth import User

from .schemas import PesagemOut

logger = structlog.get_logger("delta.pesagens.repository")

_TABELA = "pesagens"
_COLUNAS = "id, peso_kg, registrada_em, created_at, updated_at"


class PesagemRepositorioError(Exception):
    """Erro inesperado de acesso a `pesagens` (ex.: falha do Supabase).

    Indica um problema de infraestrutura, não um erro de validação do
    usuário — o router converte isso em `500`, nunca em `422`.
    """


def _to_pesagem_out(linha: dict) -> PesagemOut:
    return PesagemOut.model_validate(linha)


async def criar_pesagem(user: User, *, peso_kg: float, registrada_em: datetime) -> PesagemOut:
    """Insere uma nova pesagem. Validações de aplicação já ocorreram antes
    (faixa de `peso_kg`, data não-futura) — esta função só grava."""
    try:
        resposta = (
            await user.supabase.table(_TABELA)
            .insert(
                {
                    "user_id": user.id,
                    "peso_kg": peso_kg,
                    "registrada_em": registrada_em.isoformat(),
                }
            )
            .execute()
        )
    except APIError as exc:
        logger.error("erro_ao_criar_pesagem", erro=str(exc), user_id=user.id)
        raise PesagemRepositorioError("Não foi possível registrar a pesagem.") from exc

    return _to_pesagem_out(resposta.data[0])


async def listar_pesagens(user: User) -> list[PesagemOut]:
    """Lista o histórico de pesagens do usuário, mais recente primeiro."""
    try:
        resposta = (
            await user.supabase.table(_TABELA)
            .select(_COLUNAS)
            .order("registrada_em", desc=True)
            .execute()
        )
    except APIError as exc:
        logger.error("erro_ao_listar_pesagens", erro=str(exc), user_id=user.id)
        raise PesagemRepositorioError("Não foi possível listar as pesagens.") from exc

    return [_to_pesagem_out(linha) for linha in resposta.data]


async def obter_pesagem_mais_recente(user: User) -> PesagemOut | None:
    """Retorna a pesagem mais recente do usuário por `registrada_em`, ou
    `None` se ele nunca registrou nenhuma pesagem.

    Ordena pelo índice `(user_id, registrada_em desc)` já criado na
    migration — sem scan/sort adicional.
    """
    try:
        resposta = (
            await user.supabase.table(_TABELA)
            .select(_COLUNAS)
            .order("registrada_em", desc=True)
            .limit(1)
            .maybe_single()
            .execute()
        )
    except APIError as exc:
        logger.error("erro_ao_obter_pesagem_mais_recente", erro=str(exc), user_id=user.id)
        raise PesagemRepositorioError(
            "Não foi possível buscar a pesagem mais recente."
        ) from exc

    if resposta is None or resposta.data is None:
        return None
    return _to_pesagem_out(resposta.data)


async def obter_pesagem_por_id(user: User, pesagem_id: UUID) -> PesagemOut | None:
    """Busca uma pesagem específica do próprio usuário (RLS filtra o resto)."""
    try:
        resposta = (
            await user.supabase.table(_TABELA)
            .select(_COLUNAS)
            .eq("id", str(pesagem_id))
            .maybe_single()
            .execute()
        )
    except APIError as exc:
        logger.error(
            "erro_ao_obter_pesagem", erro=str(exc), user_id=user.id, pesagem_id=str(pesagem_id)
        )
        raise PesagemRepositorioError("Não foi possível buscar a pesagem.") from exc

    if resposta is None or resposta.data is None:
        return None
    return _to_pesagem_out(resposta.data)


async def atualizar_pesagem(
    user: User,
    pesagem_id: UUID,
    *,
    peso_kg: float | None,
    registrada_em: datetime | None,
) -> PesagemOut | None:
    """Atualiza os campos informados de uma pesagem própria.

    Retorna `None` se a pesagem não existir ou não pertencer ao usuário
    (RLS já filtra a segunda hipótese antes mesmo de chegar aqui).
    """
    dados: dict[str, object] = {}
    if peso_kg is not None:
        dados["peso_kg"] = peso_kg
    if registrada_em is not None:
        dados["registrada_em"] = registrada_em.isoformat()

    try:
        resposta = (
            await user.supabase.table(_TABELA)
            .update(dados)
            .eq("id", str(pesagem_id))
            .execute()
        )
    except APIError as exc:
        logger.error(
            "erro_ao_atualizar_pesagem",
            erro=str(exc),
            user_id=user.id,
            pesagem_id=str(pesagem_id),
        )
        raise PesagemRepositorioError("Não foi possível editar a pesagem.") from exc

    if not resposta.data:
        return None
    return _to_pesagem_out(resposta.data[0])


async def excluir_pesagem(user: User, pesagem_id: UUID) -> bool:
    """Exclui uma pesagem própria. Retorna `True` se algo foi excluído."""
    try:
        resposta = (
            await user.supabase.table(_TABELA)
            .delete()
            .eq("id", str(pesagem_id))
            .execute()
        )
    except APIError as exc:
        logger.error(
            "erro_ao_excluir_pesagem",
            erro=str(exc),
            user_id=user.id,
            pesagem_id=str(pesagem_id),
        )
        raise PesagemRepositorioError("Não foi possível excluir a pesagem.") from exc

    return bool(resposta.data)
