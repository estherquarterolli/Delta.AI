"""Acesso a `profiles` (altura, data de nascimento) e `condicoes_saude`
(`esta_gestante`) — os dois insumos de perfil consumidos pelo cálculo de
IMC, além da pesagem mais recente (que NÃO é lida aqui — vem de
`app.modules.pesagens.service.obter_pesagem_mais_recente`, o único ponto
de acesso permitido a `pesagens`; ver `specs/2026-07-17-registro-de-peso.md`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import structlog
from postgrest.exceptions import APIError

from app.db.auth import User

logger = structlog.get_logger("delta.perfil.repository")


class PerfilRepositorioError(Exception):
    """Erro inesperado de acesso a `profiles`/`condicoes_saude`.

    Indica um problema de infraestrutura, não ausência de dado — quem
    chama deve deixar propagar pra virar `500`, nunca confundir com
    perfil incompleto (`422`).
    """


@dataclass(frozen=True)
class PerfilRow:
    """Campos de `profiles` relevantes pro cálculo de IMC."""

    altura_cm: int | None
    data_nascimento: date | None


async def obter_perfil(user: User) -> PerfilRow | None:
    """Busca `profiles.altura_cm`/`data_nascimento` do usuário autenticado.

    `profiles` tem trigger de auto-criação no signup (`handle_new_user`) —
    não deveria existir usuário sem linha, mas se acontecer, `None` é
    tratado pelo service como perfil incompleto (nunca `500`), conforme o
    edge case explícito do spec de IMC.
    """
    try:
        resposta = (
            await user.supabase.table("profiles")
            .select("altura_cm, data_nascimento")
            .eq("id", user.id)
            .maybe_single()
            .execute()
        )
    except APIError as exc:
        logger.error("erro_ao_obter_perfil", erro=str(exc), user_id=user.id)
        raise PerfilRepositorioError("Não foi possível buscar o perfil.") from exc

    if resposta is None or resposta.data is None:
        return None

    dados = resposta.data
    data_nascimento_raw = dados.get("data_nascimento")
    data_nascimento = date.fromisoformat(data_nascimento_raw) if data_nascimento_raw else None
    return PerfilRow(altura_cm=dados.get("altura_cm"), data_nascimento=data_nascimento)


async def obter_esta_gestante(user: User) -> bool:
    """Busca `condicoes_saude.esta_gestante` do usuário autenticado.

    `condicoes_saude` NÃO tem trigger de auto-criação no signup (diferente
    de `profiles`) — o usuário pode não ter nenhuma linha ainda. Ausência
    de linha é tratada como `esta_gestante = False` (o mesmo default da
    coluna), nunca como erro (`404`/`500`) — regra explícita do spec de
    cálculo de IMC.
    """
    try:
        resposta = (
            await user.supabase.table("condicoes_saude")
            .select("esta_gestante")
            .eq("user_id", user.id)
            .maybe_single()
            .execute()
        )
    except APIError as exc:
        logger.error("erro_ao_obter_esta_gestante", erro=str(exc), user_id=user.id)
        raise PerfilRepositorioError(
            "Não foi possível buscar dados de condições de saúde."
        ) from exc

    if resposta is None or resposta.data is None:
        return False
    return bool(resposta.data.get("esta_gestante", False))


async def upsert_esta_gestante(user: User, *, esta_gestante: bool) -> bool:
    """Grava `condicoes_saude.esta_gestante` do usuário autenticado.

    `condicoes_saude` NÃO tem trigger de auto-criação no signup (diferente
    de `profiles`) — por isso esta escrita é sempre um UPSERT por
    `user_id` (a própria PK da tabela), nunca um `UPDATE` puro: cria a
    linha se ainda não existir, atualiza se já existir.

    O payload enviado ao PostgREST contém só `user_id` e `esta_gestante`
    — o `Prefer: resolution=merge-duplicates` do upsert só atualiza, em
    caso de conflito, as colunas presentes no payload, então `condicoes`
    (e qualquer outro campo já preenchido) nunca é sobrescrito/zerado por
    esta chamada. `on_conflict="user_id"` é explícito por clareza, mesmo
    já sendo a PK (comportamento padrão do PostgREST se omitido).
    """
    try:
        resposta = (
            await user.supabase.table("condicoes_saude")
            .upsert(
                {"user_id": user.id, "esta_gestante": esta_gestante},
                on_conflict="user_id",
            )
            .execute()
        )
    except APIError as exc:
        logger.error("erro_ao_gravar_esta_gestante", erro=str(exc), user_id=user.id)
        raise PerfilRepositorioError(
            "Não foi possível salvar a informação de gestação."
        ) from exc

    if not resposta.data:
        raise PerfilRepositorioError("Não foi possível salvar a informação de gestação.")
    return bool(resposta.data[0].get("esta_gestante", esta_gestante))
