"""Regras de negócio do módulo de pesagens.

Valida faixa de peso e "não pode ser data futura" (422 de aplicação, além
dos `CHECK`s do banco) e orquestra as operações de CRUD via
`repository.py`. Encapsula todo acesso a `public.pesagens`: nenhum outro
módulo deve importar `repository.py` diretamente — o único ponto de
consumo externo permitido é `obter_pesagem_mais_recente`, o contrato
definido em `specs/2026-07-17-registro-de-peso.md` e consumido por
`app/modules/perfil` (cálculo de IMC).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from app.db.auth import User

from . import repository
from .schemas import PesagemOut

PESO_MIN_KG = 20.0
PESO_MAX_KG = 400.0


class PesoForaDaFaixaError(Exception):
    """`peso_kg` fora da faixa 20-400kg."""


class DataFuturaError(Exception):
    """`registrada_em` é uma data/hora futura."""


class AtualizacaoVaziaError(Exception):
    """Edição sem nenhum campo informado (`peso_kg`/`registrada_em`)."""


class PesagemNaoEncontradaError(Exception):
    """Pesagem inexistente ou não pertencente ao usuário autenticado."""


def _para_utc(momento: datetime) -> datetime:
    """Normaliza pra UTC, assumindo UTC se o valor vier sem timezone."""
    if momento.tzinfo is None:
        return momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(timezone.utc)


def _validar_peso(peso_kg: float) -> None:
    if not (PESO_MIN_KG <= peso_kg <= PESO_MAX_KG):
        raise PesoForaDaFaixaError(
            f"peso_kg deve estar entre {PESO_MIN_KG:.0f} e {PESO_MAX_KG:.0f} kg."
        )


def _validar_data_nao_futura(registrada_em: datetime, *, agora: datetime) -> None:
    if registrada_em > agora:
        raise DataFuturaError("registrada_em não pode ser uma data no futuro.")


async def registrar_pesagem(
    user: User, *, peso_kg: float, registrada_em: datetime | None
) -> PesagemOut:
    """Cria uma pesagem nova. `registrada_em` default = agora (UTC), se omitido."""
    agora = datetime.now(timezone.utc)
    momento = _para_utc(registrada_em) if registrada_em is not None else agora

    _validar_peso(peso_kg)
    _validar_data_nao_futura(momento, agora=agora)

    return await repository.criar_pesagem(user, peso_kg=peso_kg, registrada_em=momento)


async def listar_historico(user: User) -> list[PesagemOut]:
    """Lista o histórico de pesagens do usuário, mais recente primeiro."""
    return await repository.listar_pesagens(user)


async def obter_pesagem_mais_recente(user: User) -> PesagemOut | None:
    """Contrato reutilizável por outros módulos (ex.: `app/modules/perfil`).

    Retorna a pesagem mais recente do usuário por `registrada_em`, ou
    `None` se ele nunca registrou nenhuma pesagem — nunca levanta erro só
    por ausência de dado, quem chama decide o que "sem pesagem" significa
    (ex.: perfil incompleto).
    """
    return await repository.obter_pesagem_mais_recente(user)


async def editar_pesagem(
    user: User,
    pesagem_id: UUID,
    *,
    peso_kg: float | None,
    registrada_em: datetime | None,
) -> PesagemOut:
    """Edita peso e/ou data de uma pesagem própria (correção de erro de
    digitação — LGPD art. 18, direito de correção do próprio dado)."""
    if peso_kg is None and registrada_em is None:
        raise AtualizacaoVaziaError("Informe ao menos peso_kg ou registrada_em.")

    agora = datetime.now(timezone.utc)
    momento = _para_utc(registrada_em) if registrada_em is not None else None

    if peso_kg is not None:
        _validar_peso(peso_kg)
    if momento is not None:
        _validar_data_nao_futura(momento, agora=agora)

    pesagem = await repository.atualizar_pesagem(
        user, pesagem_id, peso_kg=peso_kg, registrada_em=momento
    )
    if pesagem is None:
        raise PesagemNaoEncontradaError("Pesagem não encontrada.")
    return pesagem


async def excluir_pesagem(user: User, pesagem_id: UUID) -> None:
    """Exclui uma pesagem própria."""
    excluiu = await repository.excluir_pesagem(user, pesagem_id)
    if not excluiu:
        raise PesagemNaoEncontradaError("Pesagem não encontrada.")
