"""Schemas Pydantic de request/response do módulo de pesagens."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PesagemCreate(BaseModel):
    """Payload de criação de uma pesagem.

    `registrada_em` é opcional — quando omitido, o service usa o instante
    atual (UTC) como default. Faixa de `peso_kg` e "não pode ser data
    futura" são validadas na camada de service (422 antes de tocar o
    banco), além dos `CHECK`s já existentes na migration.
    """

    peso_kg: float = Field(..., description="Peso em quilogramas.")
    registrada_em: datetime | None = Field(
        default=None,
        description="Quando a pesagem foi feita. Default: agora, se omitido.",
    )


class PesagemUpdate(BaseModel):
    """Payload de edição de uma pesagem própria.

    Ambos os campos são opcionais, mas ao menos um deve ser informado
    (validado na camada de service) — uma edição vazia não faz sentido.
    """

    peso_kg: float | None = None
    registrada_em: datetime | None = None


class PesagemOut(BaseModel):
    """Representação de uma pesagem retornada pela API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    peso_kg: float
    registrada_em: datetime
    created_at: datetime
    updated_at: datetime
