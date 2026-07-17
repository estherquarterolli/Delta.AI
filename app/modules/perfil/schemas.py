"""Schemas Pydantic de resposta do módulo de perfil (IMC)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from .calculos import Classificacao

MotivoBloqueio = Literal["menor_de_18", "gestante"]

CampoFaltante = Literal["altura_cm", "data_nascimento", "peso"]


class ImcOut(BaseModel):
    """Resposta de `GET /perfil/imc`, cobrindo os estados elegível e bloqueado.

    Quando `elegivel` é `False` (bloqueio por idade ou gestação), todos os
    campos numéricos/derivados (`imc`, `classificacao`,
    `classificacao_label`, `peso_kg`, `altura_cm`,
    `pesagem_registrada_em`) são `None` — bloqueio total, nunca parcial
    (ver `specs/2026-07-17-calculo-imc.md`, seção "Regras de negócio").
    """

    elegivel: bool
    motivo_bloqueio: MotivoBloqueio | None
    mensagem: str | None
    imc: float | None
    classificacao: Classificacao | None
    classificacao_label: str | None
    peso_kg: float | None
    altura_cm: int | None
    pesagem_registrada_em: datetime | None
    calculado_em: datetime


class CondicoesSaudeUpdate(BaseModel):
    """Payload de atualização parcial de `condicoes_saude`.

    Hoje só expõe `esta_gestante` — usado pelo cálculo de IMC pra checar
    elegibilidade por gestação (ver `specs/2026-07-17-calculo-imc.md`).
    A escrita é um UPSERT por `user_id`, sem afetar outros campos já
    preenchidos (ex.: `condicoes`, texto livre) — ver `repository.py`.
    """

    esta_gestante: bool


class CondicoesSaudeOut(BaseModel):
    """Confirmação do valor gravado em `condicoes_saude`."""

    esta_gestante: bool


class PerfilIncompletoOut(BaseModel):
    """Corpo de erro de `422 PERFIL_INCOMPLETO`.

    Usado só como `response_model` de documentação (OpenAPI) — a resposta
    real é montada manualmente no router pra bater exatamente com o
    contrato do spec (corpo top-level, sem o envelope `{"detail": ...}`
    padrão de `HTTPException`). Ver `router.py` pra justificativa.
    """

    erro: Literal["PERFIL_INCOMPLETO"] = "PERFIL_INCOMPLETO"
    mensagem: str
    campos_faltantes: list[CampoFaltante]
