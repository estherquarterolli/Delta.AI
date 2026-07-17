"""Testes unitários da orquestração de elegibilidade de IMC
(`app/modules/perfil/service.py`), isolando I/O via monkeypatch.

Não usa `FakeSupabaseClient`/`fake_store` aqui de propósito: o objetivo
desta suíte é testar a ORQUESTRAÇÃO (ordem de checagens, prioridade de
motivo de bloqueio, campos faltantes) isoladamente, sem depender de como
`repository.py`/`pesagens.service` resolvem os dados — isso é coberto em
`test_perfil_repository.py` e nos testes de integração de rota.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.db.auth import User
from app.modules.perfil import service as perfil_service
from app.modules.perfil.repository import PerfilRow
from app.modules.perfil.service import PerfilIncompletoError, calcular_imc_usuario
from app.modules.pesagens import service as pesagens_service
from app.modules.pesagens.schemas import PesagemOut

_HOJE = date.today()


def _usuario_fake(user_id: str = "user-1") -> User:
    # `supabase` nunca é usado nestes testes: todo I/O é mockado via
    # monkeypatch nas funções que o service chama, não no client.
    return User(id=user_id, email=None, supabase=None)  # type: ignore[arg-type]


def _pesagem_fake(peso_kg: float, registrada_em: datetime | None = None) -> PesagemOut:
    momento = registrada_em or datetime.now(timezone.utc)
    return PesagemOut(
        id=uuid4(),
        peso_kg=peso_kg,
        registrada_em=momento,
        created_at=momento,
        updated_at=momento,
    )


def _idade_para_data_nascimento(idade: int) -> date:
    """Data de nascimento cuja idade completa, calculada hoje, é `idade`."""
    return _HOJE.replace(year=_HOJE.year - idade)


class _MockAsync:
    """Substitui uma função async por um mock simples que registra chamadas
    e devolve um valor fixo (ou levanta, se `erro` for informado)."""

    def __init__(self, retorno: object = None, *, erro: Exception | None = None) -> None:
        self.retorno = retorno
        self.erro = erro
        self.chamadas: list[tuple[object, ...]] = []

    async def __call__(self, *args: object) -> object:
        self.chamadas.append(args)
        if self.erro is not None:
            raise self.erro
        return self.retorno


@pytest.fixture
def mocks(monkeypatch: pytest.MonkeyPatch):
    """Substitui os três pontos de I/O que `calcular_imc_usuario` orquestra:
    `obter_perfil`, `obter_esta_gestante` (ambos de `repository.py`, mas
    ligados ao namespace de `service.py`) e
    `pesagens_service.obter_pesagem_mais_recente`."""

    class _Mocks:
        obter_perfil = _MockAsync()
        obter_esta_gestante = _MockAsync(retorno=False)
        obter_pesagem_mais_recente = _MockAsync()

    m = _Mocks()
    monkeypatch.setattr(perfil_service, "obter_perfil", m.obter_perfil)
    monkeypatch.setattr(perfil_service, "obter_esta_gestante", m.obter_esta_gestante)
    monkeypatch.setattr(pesagens_service, "obter_pesagem_mais_recente", m.obter_pesagem_mais_recente)
    return m


class TestAdultoElegivel:
    async def test_adulto_nao_gestante_dados_completos_e_elegivel(self, mocks) -> None:
        mocks.obter_perfil.retorno = PerfilRow(
            altura_cm=173, data_nascimento=_idade_para_data_nascimento(30)
        )
        mocks.obter_esta_gestante.retorno = False
        mocks.obter_pesagem_mais_recente.retorno = _pesagem_fake(70.0)

        resultado = await calcular_imc_usuario(_usuario_fake())

        assert resultado.elegivel is True
        assert resultado.motivo_bloqueio is None
        assert resultado.mensagem is None
        assert resultado.imc == 23.4
        assert resultado.classificacao == "peso_normal"
        assert resultado.classificacao_label == "Peso normal"
        assert resultado.peso_kg == 70.0
        assert resultado.altura_cm == 173

    async def test_idade_exatamente_18_anos_e_elegivel(self, mocks) -> None:
        mocks.obter_perfil.retorno = PerfilRow(
            altura_cm=170, data_nascimento=_idade_para_data_nascimento(18)
        )
        mocks.obter_esta_gestante.retorno = False
        mocks.obter_pesagem_mais_recente.retorno = _pesagem_fake(70.0)

        resultado = await calcular_imc_usuario(_usuario_fake())

        assert resultado.elegivel is True
        assert resultado.motivo_bloqueio is None
        assert resultado.imc is not None


class TestBloqueioPorIdade:
    async def test_idade_17_anos_bloqueia_com_campos_nulos(self, mocks) -> None:
        mocks.obter_perfil.retorno = PerfilRow(
            altura_cm=170, data_nascimento=_idade_para_data_nascimento(17)
        )
        mocks.obter_esta_gestante.retorno = False
        mocks.obter_pesagem_mais_recente.retorno = _pesagem_fake(60.0)

        resultado = await calcular_imc_usuario(_usuario_fake())

        assert resultado.elegivel is False
        assert resultado.motivo_bloqueio == "menor_de_18"
        assert resultado.imc is None
        assert resultado.classificacao is None
        assert resultado.classificacao_label is None
        assert resultado.peso_kg is None
        assert resultado.altura_cm is None
        assert resultado.pesagem_registrada_em is None
        assert "profissional" in resultado.mensagem.lower() or "pediatra" in resultado.mensagem.lower()

    async def test_faz_18_anos_amanha_ainda_e_menor_de_18(self, mocks) -> None:
        # Aniversário de 18 anos é amanhã: hoje a pessoa ainda tem 17 anos
        # completos (o aniversário de hoje + 1 dia cai 18 anos atrás).
        data_nascimento = _HOJE.replace(year=_HOJE.year - 18) + timedelta(days=1)
        mocks.obter_perfil.retorno = PerfilRow(altura_cm=170, data_nascimento=data_nascimento)
        mocks.obter_esta_gestante.retorno = False
        mocks.obter_pesagem_mais_recente.retorno = _pesagem_fake(60.0)

        resultado = await calcular_imc_usuario(_usuario_fake())

        assert resultado.elegivel is False
        assert resultado.motivo_bloqueio == "menor_de_18"


class TestBloqueioPorGestacao:
    async def test_gestante_adulta_bloqueia_com_campos_nulos(self, mocks) -> None:
        mocks.obter_perfil.retorno = PerfilRow(
            altura_cm=165, data_nascimento=_idade_para_data_nascimento(28)
        )
        mocks.obter_esta_gestante.retorno = True
        mocks.obter_pesagem_mais_recente.retorno = _pesagem_fake(65.0)

        resultado = await calcular_imc_usuario(_usuario_fake())

        assert resultado.elegivel is False
        assert resultado.motivo_bloqueio == "gestante"
        assert resultado.imc is None
        assert resultado.peso_kg is None
        assert resultado.altura_cm is None
        assert resultado.pesagem_registrada_em is None
        assert "pré-natal" in resultado.mensagem.lower() or "profissional" in resultado.mensagem.lower()

    async def test_menor_de_18_e_gestante_prioriza_menor_de_18(self, mocks) -> None:
        mocks.obter_perfil.retorno = PerfilRow(
            altura_cm=160, data_nascimento=_idade_para_data_nascimento(15)
        )
        mocks.obter_esta_gestante.retorno = True
        mocks.obter_pesagem_mais_recente.retorno = _pesagem_fake(55.0)

        resultado = await calcular_imc_usuario(_usuario_fake())

        assert resultado.motivo_bloqueio == "menor_de_18"
        # Decisão explícita do spec: idade é checada primeiro. A checagem de
        # gestação nem deveria rodar quando já bloqueou por idade.
        assert mocks.obter_esta_gestante.chamadas == []


class TestPerfilIncompleto:
    async def test_sem_altura_levanta_perfil_incompleto(self, mocks) -> None:
        mocks.obter_perfil.retorno = PerfilRow(
            altura_cm=None, data_nascimento=_idade_para_data_nascimento(30)
        )
        mocks.obter_pesagem_mais_recente.retorno = _pesagem_fake(70.0)

        with pytest.raises(PerfilIncompletoError) as exc_info:
            await calcular_imc_usuario(_usuario_fake())

        assert exc_info.value.campos_faltantes == ["altura_cm"]

    async def test_sem_data_nascimento_levanta_perfil_incompleto(self, mocks) -> None:
        mocks.obter_perfil.retorno = PerfilRow(altura_cm=170, data_nascimento=None)
        mocks.obter_pesagem_mais_recente.retorno = _pesagem_fake(70.0)

        with pytest.raises(PerfilIncompletoError) as exc_info:
            await calcular_imc_usuario(_usuario_fake())

        assert exc_info.value.campos_faltantes == ["data_nascimento"]

    async def test_sem_nenhuma_pesagem_levanta_perfil_incompleto_com_campo_peso(
        self, mocks
    ) -> None:
        mocks.obter_perfil.retorno = PerfilRow(
            altura_cm=170, data_nascimento=_idade_para_data_nascimento(30)
        )
        mocks.obter_pesagem_mais_recente.retorno = None

        with pytest.raises(PerfilIncompletoError) as exc_info:
            await calcular_imc_usuario(_usuario_fake())

        assert exc_info.value.campos_faltantes == ["peso"]

    async def test_multiplos_campos_faltando_lista_todos(self, mocks) -> None:
        mocks.obter_perfil.retorno = PerfilRow(altura_cm=None, data_nascimento=None)
        mocks.obter_pesagem_mais_recente.retorno = None

        with pytest.raises(PerfilIncompletoError) as exc_info:
            await calcular_imc_usuario(_usuario_fake())

        assert exc_info.value.campos_faltantes == ["altura_cm", "data_nascimento", "peso"]

    async def test_perfil_ausente_e_tratado_como_incompleto_nao_como_erro(self, mocks) -> None:
        # `obter_perfil` retornando None (usuário sem linha em `profiles`,
        # não deveria acontecer por causa do trigger, mas o service defende).
        mocks.obter_perfil.retorno = None
        mocks.obter_pesagem_mais_recente.retorno = None

        with pytest.raises(PerfilIncompletoError) as exc_info:
            await calcular_imc_usuario(_usuario_fake())

        assert exc_info.value.campos_faltantes == ["altura_cm", "data_nascimento", "peso"]

    async def test_perfil_incompleto_nao_chama_obter_esta_gestante(self, mocks) -> None:
        """Checagem de completude vem antes de elegibilidade — não faz
        sentido checar gestação de um perfil que nem tem os dados básicos."""
        mocks.obter_perfil.retorno = PerfilRow(altura_cm=None, data_nascimento=None)
        mocks.obter_pesagem_mais_recente.retorno = None

        with pytest.raises(PerfilIncompletoError):
            await calcular_imc_usuario(_usuario_fake())

        assert mocks.obter_esta_gestante.chamadas == []
