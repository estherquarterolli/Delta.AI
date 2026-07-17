"""Orquestra o cálculo de IMC: perfil + pesagem mais recente + elegibilidade.

Ordem fixa (ver `specs/2026-07-17-calculo-imc.md`): buscar perfil (altura,
data de nascimento) -> buscar pesagem mais recente (via
`app.modules.pesagens.service.obter_pesagem_mais_recente`, nunca acessando
`pesagens` direto) -> checar completude -> checar elegibilidade (idade,
gestação) -> só então chamar `calculos.calcular_imc`.

Também orquestra a escrita de `esta_gestante` (`atualizar_esta_gestante`),
o único campo de `condicoes_saude` gravável por este módulo hoje.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.db.auth import User
from app.modules.pesagens import service as pesagens_service

from .calculos import CLASSIFICACAO_LABELS, calcular_imc
from .repository import obter_esta_gestante, obter_perfil, upsert_esta_gestante
from .schemas import CampoFaltante, ImcOut, MotivoBloqueio

_MENSAGEM_MENOR_DE_18 = (
    "Para calcular o IMC de forma segura em menores de 18 anos, é "
    "necessário acompanhamento especializado. Recomendamos conversar com "
    "um pediatra ou nutricionista."
)
_MENSAGEM_GESTANTE = (
    "Durante a gestação, o IMC padrão não é um indicador adequado — o "
    "ganho de peso esperado varia bastante de pessoa para pessoa. "
    "Recomendamos acompanhar seu peso com o pré-natal."
)

_IDADE_MINIMA_ELEGIVEL = 18


class PerfilIncompletoError(Exception):
    """Levantado quando falta `altura_cm`, `data_nascimento` e/ou pesagem.

    `campos_faltantes` usa os nomes lógicos do contrato do endpoint —
    `peso` é o nome lógico pra "nenhuma pesagem registrada" (o dado mora
    em `pesagens`, não em `profiles`, mas a API não expõe esse detalhe de
    schema pro frontend).
    """

    def __init__(self, campos_faltantes: list[CampoFaltante]) -> None:
        self.campos_faltantes = campos_faltantes
        super().__init__("Perfil incompleto para calcular o IMC.")


def _calcular_idade(data_nascimento: date, hoje: date) -> int:
    """Anos completos entre `data_nascimento` e `hoje`. 18 anos completos
    já é elegível (adulto) — ver decisão explícita do spec de IMC."""
    idade = hoje.year - data_nascimento.year
    if (hoje.month, hoje.day) < (data_nascimento.month, data_nascimento.day):
        idade -= 1
    return idade


def _resposta_bloqueada(motivo: MotivoBloqueio, mensagem: str, *, calculado_em: datetime) -> ImcOut:
    """Bloqueio total (ver spec, seção "Regras de negócio"): nenhum campo
    numérico/derivado é retornado, mesmo que os dados existam."""
    return ImcOut(
        elegivel=False,
        motivo_bloqueio=motivo,
        mensagem=mensagem,
        imc=None,
        classificacao=None,
        classificacao_label=None,
        peso_kg=None,
        altura_cm=None,
        pesagem_registrada_em=None,
        calculado_em=calculado_em,
    )


async def calcular_imc_usuario(user: User) -> ImcOut:
    """Calcula o IMC do usuário autenticado ou retorna o bloqueio/estado
    de perfil incompleto aplicável.

    Levanta `PerfilIncompletoError` se faltar altura, data de nascimento
    e/ou pesagem — o router converte isso em `422 PERFIL_INCOMPLETO`.
    Deixa propagar `ValueError` de `calcular_imc` (dado corrompido fora da
    faixa fisiológica esperada, não deveria acontecer) pro router
    responder `500` defensivamente, sem tratamento especial aqui.
    """
    calculado_em = datetime.now(timezone.utc)

    perfil = await obter_perfil(user)
    pesagem = await pesagens_service.obter_pesagem_mais_recente(user)

    campos_faltantes: list[CampoFaltante] = []
    if perfil is None or perfil.altura_cm is None:
        campos_faltantes.append("altura_cm")
    if perfil is None or perfil.data_nascimento is None:
        campos_faltantes.append("data_nascimento")
    if pesagem is None:
        campos_faltantes.append("peso")

    if campos_faltantes:
        raise PerfilIncompletoError(campos_faltantes)

    # Garantido pelas checagens acima: perfil e pesagem existem e têm os
    # campos necessários a partir deste ponto.
    assert perfil is not None
    assert perfil.altura_cm is not None
    assert perfil.data_nascimento is not None
    assert pesagem is not None

    idade = _calcular_idade(perfil.data_nascimento, calculado_em.date())

    # Idade é checada primeiro: se as duas condições baterem (menor de 18
    # E gestante), motivo_bloqueio prioriza "menor_de_18" — decisão
    # explícita do spec.
    if idade < _IDADE_MINIMA_ELEGIVEL:
        return _resposta_bloqueada(
            "menor_de_18", _MENSAGEM_MENOR_DE_18, calculado_em=calculado_em
        )

    esta_gestante = await obter_esta_gestante(user)
    if esta_gestante:
        return _resposta_bloqueada("gestante", _MENSAGEM_GESTANTE, calculado_em=calculado_em)

    imc, classificacao = calcular_imc(float(pesagem.peso_kg), float(perfil.altura_cm))

    return ImcOut(
        elegivel=True,
        motivo_bloqueio=None,
        mensagem=None,
        imc=imc,
        classificacao=classificacao,
        classificacao_label=CLASSIFICACAO_LABELS[classificacao],
        peso_kg=float(pesagem.peso_kg),
        altura_cm=perfil.altura_cm,
        pesagem_registrada_em=pesagem.registrada_em,
        calculado_em=calculado_em,
    )


async def atualizar_esta_gestante(user: User, *, esta_gestante: bool) -> bool:
    """Grava `esta_gestante` do usuário autenticado em `condicoes_saude`.

    Repassa pro `repository.upsert_esta_gestante`, que faz UPSERT por
    `user_id` (a tabela não tem trigger de auto-criação no signup) sem
    afetar outros campos já preenchidos. Sem validação de negócio extra
    aqui — `esta_gestante` é um booleano simples, sem faixa/formato a
    checar antes de gravar.
    """
    return await upsert_esta_gestante(user, esta_gestante=esta_gestante)
