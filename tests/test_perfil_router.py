"""Testes de integração de `app/modules/perfil/router.py`: `GET /perfil/imc`
e `PATCH /perfil/condicoes-saude`.

Usa `FakeSupabaseClient`/`fake_store` (ver `tests/conftest.py`) — não há
Postgres/Supabase real disponível neste ambiente. Ver docstring do
`conftest.py` pra uma explicação explícita do que essa abordagem prova
(orquestração/contrato do endpoint) e do que fica coberto pela RLS real do
banco (isolamento entre usuários na tabela física), fora do alcance destes
testes.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from httpx import AsyncClient

import app.db.auth as auth_module
import app.modules.perfil.service as perfil_service
from app.db.auth import get_current_user
from app.main import app
from app.modules.perfil.calculos import calcular_imc
from tests.conftest import inserir_condicoes_saude, inserir_perfil, inserir_pesagem

AuthedClientFactory = Callable[..., Coroutine[Any, Any, AsyncClient]]

_HOJE = datetime.now(timezone.utc).date()


def _nascido_ha(anos: int) -> str:
    return _HOJE.replace(year=_HOJE.year - anos).isoformat()


class TestElegivel:
    async def test_200_elegivel_com_corpo_completo(
        self, make_authed_client: AuthedClientFactory, fake_store: dict
    ) -> None:
        user_id = "user-elegivel"
        inserir_perfil(fake_store, user_id, altura_cm=173, data_nascimento=_nascido_ha(30))
        registrada_em = datetime.now(timezone.utc) - timedelta(days=2)
        inserir_pesagem(fake_store, user_id, peso_kg=70.0, registrada_em=registrada_em)

        client = await make_authed_client(user_id)
        resposta = await client.get("/perfil/imc")

        assert resposta.status_code == 200
        corpo = resposta.json()
        imc_esperado, classificacao_esperada = calcular_imc(70.0, 173)
        assert corpo["elegivel"] is True
        assert corpo["motivo_bloqueio"] is None
        assert corpo["mensagem"] is None
        assert corpo["imc"] == imc_esperado
        assert corpo["classificacao"] == classificacao_esperada
        assert corpo["peso_kg"] == 70.0
        assert corpo["altura_cm"] == 173
        assert corpo["pesagem_registrada_em"] is not None
        assert corpo["calculado_em"] is not None

    async def test_200_elegivel_sem_linha_condicoes_saude_nao_e_erro(
        self, make_authed_client: AuthedClientFactory, fake_store: dict
    ) -> None:
        """Ponto crítico do supabase-architect: usuário que nunca preencheu
        `condicoes_saude` não deve virar 500 nem 422 — é `esta_gestante =
        False` implícito."""
        user_id = "user-sem-condicoes-saude"
        inserir_perfil(fake_store, user_id, altura_cm=160, data_nascimento=_nascido_ha(25))
        inserir_pesagem(fake_store, user_id, peso_kg=60.0, registrada_em=datetime.now(timezone.utc))
        # Nenhuma linha em condicoes_saude inserida de propósito.

        client = await make_authed_client(user_id)
        resposta = await client.get("/perfil/imc")

        assert resposta.status_code == 200
        assert resposta.json()["elegivel"] is True


class TestBloqueadoPorElegibilidade:
    async def test_200_bloqueado_menor_de_18(
        self, make_authed_client: AuthedClientFactory, fake_store: dict
    ) -> None:
        user_id = "user-menor"
        inserir_perfil(fake_store, user_id, altura_cm=160, data_nascimento=_nascido_ha(15))
        inserir_pesagem(fake_store, user_id, peso_kg=55.0, registrada_em=datetime.now(timezone.utc))

        client = await make_authed_client(user_id)
        resposta = await client.get("/perfil/imc")

        assert resposta.status_code == 200
        corpo = resposta.json()
        assert corpo["elegivel"] is False
        assert corpo["motivo_bloqueio"] == "menor_de_18"
        for campo in (
            "imc",
            "classificacao",
            "classificacao_label",
            "peso_kg",
            "altura_cm",
            "pesagem_registrada_em",
        ):
            assert corpo[campo] is None
        assert corpo["mensagem"] is not None

    async def test_200_bloqueado_gestante(
        self, make_authed_client: AuthedClientFactory, fake_store: dict
    ) -> None:
        user_id = "user-gestante"
        inserir_perfil(fake_store, user_id, altura_cm=165, data_nascimento=_nascido_ha(28))
        inserir_condicoes_saude(fake_store, user_id, esta_gestante=True)
        inserir_pesagem(fake_store, user_id, peso_kg=68.0, registrada_em=datetime.now(timezone.utc))

        client = await make_authed_client(user_id)
        resposta = await client.get("/perfil/imc")

        assert resposta.status_code == 200
        corpo = resposta.json()
        assert corpo["elegivel"] is False
        assert corpo["motivo_bloqueio"] == "gestante"
        for campo in (
            "imc",
            "classificacao",
            "classificacao_label",
            "peso_kg",
            "altura_cm",
            "pesagem_registrada_em",
        ):
            assert corpo[campo] is None


class TestPerfilIncompleto:
    async def test_422_sem_altura(
        self, make_authed_client: AuthedClientFactory, fake_store: dict
    ) -> None:
        user_id = "user-sem-altura"
        inserir_perfil(fake_store, user_id, altura_cm=None, data_nascimento=_nascido_ha(30))
        inserir_pesagem(fake_store, user_id, peso_kg=70.0, registrada_em=datetime.now(timezone.utc))

        client = await make_authed_client(user_id)
        resposta = await client.get("/perfil/imc")

        assert resposta.status_code == 422
        corpo = resposta.json()
        assert corpo == {
            "erro": "PERFIL_INCOMPLETO",
            "mensagem": "Complete seu perfil para calcular o IMC.",
            "campos_faltantes": ["altura_cm"],
        }

    async def test_422_sem_data_nascimento(
        self, make_authed_client: AuthedClientFactory, fake_store: dict
    ) -> None:
        user_id = "user-sem-nascimento"
        inserir_perfil(fake_store, user_id, altura_cm=170, data_nascimento=None)
        inserir_pesagem(fake_store, user_id, peso_kg=70.0, registrada_em=datetime.now(timezone.utc))

        client = await make_authed_client(user_id)
        resposta = await client.get("/perfil/imc")

        assert resposta.status_code == 422
        assert resposta.json()["campos_faltantes"] == ["data_nascimento"]

    async def test_422_sem_nenhuma_pesagem(
        self, make_authed_client: AuthedClientFactory, fake_store: dict
    ) -> None:
        user_id = "user-sem-pesagem"
        inserir_perfil(fake_store, user_id, altura_cm=170, data_nascimento=_nascido_ha(30))
        # Nenhuma pesagem inserida.

        client = await make_authed_client(user_id)
        resposta = await client.get("/perfil/imc")

        assert resposta.status_code == 422
        assert resposta.json()["campos_faltantes"] == ["peso"]

    async def test_422_multiplos_campos_faltando_lista_todos(
        self, make_authed_client: AuthedClientFactory, fake_store: dict
    ) -> None:
        user_id = "user-perfil-vazio"
        inserir_perfil(fake_store, user_id, altura_cm=None, data_nascimento=None)
        # Nenhuma pesagem inserida.

        client = await make_authed_client(user_id)
        resposta = await client.get("/perfil/imc")

        assert resposta.status_code == 422
        corpo = resposta.json()
        assert corpo["erro"] == "PERFIL_INCOMPLETO"
        assert corpo["campos_faltantes"] == ["altura_cm", "data_nascimento", "peso"]

    async def test_422_usuario_sem_linha_em_profiles(
        self, make_authed_client: AuthedClientFactory, fake_store: dict
    ) -> None:
        # Nenhuma linha em `profiles` (não deveria acontecer por causa do
        # trigger `handle_new_user`, mas o endpoint se defende).
        client = await make_authed_client("user-sem-profile")
        resposta = await client.get("/perfil/imc")

        assert resposta.status_code == 422
        assert resposta.json()["campos_faltantes"] == ["altura_cm", "data_nascimento", "peso"]


class TestAtualizarCondicoesSaude:
    """`PATCH /perfil/condicoes-saude` — grava `esta_gestante` via UPSERT
    sem afetar outros campos já preenchidos (ex.: `condicoes`)."""

    async def test_cria_linha_quando_nao_existe(
        self, make_authed_client: AuthedClientFactory, fake_store: dict
    ) -> None:
        user_id = "user-sem-condicoes-saude"
        assert "condicoes_saude" not in fake_store or not fake_store["condicoes_saude"]

        client = await make_authed_client(user_id)
        resposta = await client.patch("/perfil/condicoes-saude", json={"esta_gestante": True})

        assert resposta.status_code == 200
        assert resposta.json() == {"esta_gestante": True}

        linhas = [
            linha for linha in fake_store["condicoes_saude"] if linha["user_id"] == user_id
        ]
        assert len(linhas) == 1
        assert linhas[0]["esta_gestante"] is True

    async def test_atualiza_linha_existente_sem_zerar_outros_campos(
        self, make_authed_client: AuthedClientFactory, fake_store: dict
    ) -> None:
        """Ponto crítico do UPSERT: `condicoes` (já preenchido) não pode
        ser sobrescrito/zerado por um PATCH que só manda `esta_gestante`.

        O `FakeSupabaseClient` simula isso reproduzindo fielmente o
        `Prefer: resolution=merge-duplicates` que `supabase-py` usa por
        padrão em `.upsert()` (ver `tests/conftest.py::_FakeTable.upsert`):
        em caso de conflito de PK, só as colunas PRESENTES no payload
        (`user_id`, `esta_gestante`) são sobrescritas — `condicoes`, que
        não está no payload enviado por `repository.upsert_esta_gestante`,
        permanece intocado. Se esse comportamento não fosse simulado (ex.:
        um fake que fizesse `REPLACE` da linha inteira em vez de `MERGE`),
        este teste pegaria a regressão.
        """
        user_id = "user-com-condicoes"
        inserir_condicoes_saude(
            fake_store, user_id, esta_gestante=False, condicoes=["hipertensao"]
        )

        client = await make_authed_client(user_id)
        resposta = await client.patch("/perfil/condicoes-saude", json={"esta_gestante": True})

        assert resposta.status_code == 200
        assert resposta.json() == {"esta_gestante": True}

        linha = next(row for row in fake_store["condicoes_saude"] if row["user_id"] == user_id)
        assert linha["esta_gestante"] is True
        assert linha["condicoes"] == ["hipertensao"]

    async def test_toggle_de_volta_para_false(
        self, make_authed_client: AuthedClientFactory, fake_store: dict
    ) -> None:
        user_id = "user-toggle"
        inserir_condicoes_saude(fake_store, user_id, esta_gestante=True)

        client = await make_authed_client(user_id)
        resposta = await client.patch("/perfil/condicoes-saude", json={"esta_gestante": False})

        assert resposta.status_code == 200
        assert resposta.json() == {"esta_gestante": False}
        linha = next(row for row in fake_store["condicoes_saude"] if row["user_id"] == user_id)
        assert linha["esta_gestante"] is False

    async def test_user_id_do_body_e_ignorado(
        self, make_authed_client: AuthedClientFactory, fake_store: dict
    ) -> None:
        """`CondicoesSaudeUpdate` nem declara `user_id` — mesmo que o
        cliente mande um no corpo, o schema o descarta (Pydantic ignora
        campo extra por padrão) e o escopo da escrita vem sempre de
        `get_current_user`, nunca do body."""
        client = await make_authed_client("user-real")

        resposta = await client.patch(
            "/perfil/condicoes-saude",
            json={"esta_gestante": True, "user_id": "user-forjado"},
        )

        assert resposta.status_code == 200
        linhas = fake_store["condicoes_saude"]
        assert len(linhas) == 1
        assert linhas[0]["user_id"] == "user-real"

    async def test_fecha_o_loop_com_imc_apos_marcar_gestante(
        self, make_authed_client: AuthedClientFactory, fake_store: dict
    ) -> None:
        """Caminho end-to-end: `PATCH esta_gestante=true` seguido de
        `GET /perfil/imc` do mesmo usuário (adulto, com altura+pesagem)
        passa a bloquear por `motivo_bloqueio: "gestante"`."""
        user_id = "user-fecha-loop"
        inserir_perfil(fake_store, user_id, altura_cm=165, data_nascimento=_nascido_ha(28))
        inserir_pesagem(fake_store, user_id, peso_kg=68.0, registrada_em=datetime.now(timezone.utc))

        client = await make_authed_client(user_id)

        resposta_imc_antes = await client.get("/perfil/imc")
        assert resposta_imc_antes.json()["elegivel"] is True

        resposta_patch = await client.patch(
            "/perfil/condicoes-saude", json={"esta_gestante": True}
        )
        assert resposta_patch.status_code == 200

        resposta_imc_depois = await client.get("/perfil/imc")
        corpo = resposta_imc_depois.json()
        assert corpo["elegivel"] is False
        assert corpo["motivo_bloqueio"] == "gestante"
        assert corpo["imc"] is None


class TestAutenticacaoCondicoesSaude:
    async def test_401_sem_token(self, client: AsyncClient) -> None:
        resposta = await client.patch("/perfil/condicoes-saude", json={"esta_gestante": True})

        assert resposta.status_code == 401

    async def test_401_token_invalido(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class _AuthFalho:
            @staticmethod
            async def get_user(_token: str) -> None:
                raise RuntimeError("token inválido/expirado")

        class _ClienteAuthFalho:
            auth = _AuthFalho

        async def _criar_cliente_falho(_token: str) -> _ClienteAuthFalho:
            return _ClienteAuthFalho()

        monkeypatch.setattr(auth_module, "criar_supabase_client", _criar_cliente_falho)

        resposta = await client.patch(
            "/perfil/condicoes-saude",
            json={"esta_gestante": True},
            headers={"Authorization": "Bearer token-invalido"},
        )

        assert resposta.status_code == 401


class TestAutenticacao:
    async def test_401_sem_token(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        chamou = {"valor": False}

        async def _falha_se_chamado(*_args: object, **_kwargs: object) -> None:
            chamou["valor"] = True
            raise AssertionError("obter_perfil não deveria ser chamado sem autenticação.")

        monkeypatch.setattr(perfil_service, "obter_perfil", _falha_se_chamado)

        resposta = await client.get("/perfil/imc")

        assert resposta.status_code == 401
        assert chamou["valor"] is False

    async def test_401_token_invalido(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        chamou = {"valor": False}

        async def _falha_se_chamado(*_args: object, **_kwargs: object) -> None:
            chamou["valor"] = True
            raise AssertionError("obter_perfil não deveria ser chamado com token inválido.")

        monkeypatch.setattr(perfil_service, "obter_perfil", _falha_se_chamado)

        class _AuthFalho:
            """Espelha `client.auth` do supabase-py só no que é usado aqui."""

            @staticmethod
            async def get_user(_token: str) -> None:
                raise RuntimeError("token inválido/expirado")

        class _ClienteAuthFalho:
            auth = _AuthFalho

        async def _criar_cliente_falho(_token: str) -> _ClienteAuthFalho:
            return _ClienteAuthFalho()

        monkeypatch.setattr(auth_module, "criar_supabase_client", _criar_cliente_falho)

        resposta = await client.get(
            "/perfil/imc", headers={"Authorization": "Bearer token-invalido"}
        )

        assert resposta.status_code == 401
        assert chamou["valor"] is False

    async def test_dependency_override_e_limpo_entre_testes(self, client: AsyncClient) -> None:
        """Garantia de que `_limpa_dependency_overrides` (autouse) funciona:
        se um teste anterior usou `make_authed_client`, este teste (que usa
        o `client` puro, sem token) ainda deve receber 401."""
        assert get_current_user not in app.dependency_overrides
        resposta = await client.get("/perfil/imc")
        assert resposta.status_code == 401
