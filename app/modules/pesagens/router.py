"""Rotas do módulo de pesagens: criar, listar, editar e excluir pesagens
do próprio usuário autenticado. Toda rota exige `Depends(get_current_user)`
— sem token válido, `401` e nenhuma query é executada.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.db.auth import User, get_current_user

from . import service
from .schemas import PesagemCreate, PesagemOut, PesagemUpdate

router = APIRouter(prefix="/pesagens", tags=["pesagens"])

_ERRO_PESO_FORA_DA_FAIXA = "peso_kg deve estar entre 20 e 400 kg."
_ERRO_DATA_FUTURA = "registrada_em não pode ser uma data no futuro."
_ERRO_ATUALIZACAO_VAZIA = "Informe ao menos peso_kg ou registrada_em para editar a pesagem."
_ERRO_PESAGEM_NAO_ENCONTRADA = "Pesagem não encontrada."


@router.post("", response_model=PesagemOut, status_code=status.HTTP_201_CREATED)
async def criar_pesagem(
    payload: PesagemCreate,
    user: User = Depends(get_current_user),
) -> PesagemOut:
    try:
        return await service.registrar_pesagem(
            user, peso_kg=payload.peso_kg, registrada_em=payload.registrada_em
        )
    except service.PesoForaDaFaixaError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_ERRO_PESO_FORA_DA_FAIXA,
        ) from exc
    except service.DataFuturaError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=_ERRO_DATA_FUTURA
        ) from exc


@router.get("", response_model=list[PesagemOut])
async def listar_pesagens(user: User = Depends(get_current_user)) -> list[PesagemOut]:
    return await service.listar_historico(user)


@router.put("/{pesagem_id}", response_model=PesagemOut)
async def editar_pesagem(
    pesagem_id: UUID,
    payload: PesagemUpdate,
    user: User = Depends(get_current_user),
) -> PesagemOut:
    try:
        return await service.editar_pesagem(
            user,
            pesagem_id,
            peso_kg=payload.peso_kg,
            registrada_em=payload.registrada_em,
        )
    except service.PesoForaDaFaixaError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_ERRO_PESO_FORA_DA_FAIXA,
        ) from exc
    except service.DataFuturaError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=_ERRO_DATA_FUTURA
        ) from exc
    except service.AtualizacaoVaziaError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_ERRO_ATUALIZACAO_VAZIA,
        ) from exc
    except service.PesagemNaoEncontradaError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=_ERRO_PESAGEM_NAO_ENCONTRADA
        ) from exc


@router.delete("/{pesagem_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def excluir_pesagem(
    pesagem_id: UUID,
    user: User = Depends(get_current_user),
) -> None:
    try:
        await service.excluir_pesagem(user, pesagem_id)
    except service.PesagemNaoEncontradaError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=_ERRO_PESAGEM_NAO_ENCONTRADA
        ) from exc
