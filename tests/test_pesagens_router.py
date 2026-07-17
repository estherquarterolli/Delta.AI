"""Testes de integração de `app/modules/pesagens/router.py` (CRUD de
pesagens + isolamento entre usuários).

Usa `FakeSupabaseClient`/`fake_store` (ver `tests/conftest.py`). Nota sobre
isolamento entre usuários (RLS): `app/modules/pesagens/repository.py` NÃO
filtra manualmente por `user_id` em nenhuma leitura/edição/exclusão
(`listar_pesagens`, `atualizar_pesagem`, `excluir_pesagem` só filtram por
`id`, quando filtram) — o isolamento observado abaixo depende inteiramente
da simulação de RLS do `FakeSupabaseClient` (cada usuário só vê linhas
onde `user_id` é o seu próprio `owner_id`), o mesmo contrato que a policy
real do Postgres (`auth.uid() = user_id`, ver
`supabase/migrations/20260717120000_create_pesagens.sql`) promete. Estes
testes provam que o CÓDIGO DO APP nunca precisa (nem faz) esse filtro
manual — ou seja, que a app confia corretamente na RLS e não tenta
reimplementá-la nem contorná-la via parâmetro de URL/body. A garantia de
que a policy SQL em si está corretamente habilitada num Postgres real é
responsabilidade da migration/`security-reviewer`, fora do alcance deste
teste.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from httpx import AsyncClient

from app.db.auth import get_current_user
from app.main import app
from tests.conftest import inserir_pesagem

AuthedClientFactory = Callable[..., Coroutine[Any, Any, AsyncClient]]


class TestCriarPesagem:
    async def test_criar_pesagem_valida_retorna_201(
        self, make_authed_client: AuthedClientFactory
    ) -> None:
        client = await make_authed_client("user-1")

        resposta = await client.post("/pesagens", json={"peso_kg": 82.5})

        assert resposta.status_code == 201
        corpo = resposta.json()
        assert corpo["peso_kg"] == 82.5
        assert "id" in corpo
        assert corpo["registrada_em"] is not None

    async def test_criar_pesagem_com_registrada_em_explicita(
        self, make_authed_client: AuthedClientFactory
    ) -> None:
        client = await make_authed_client("user-1")
        registrada_em = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()

        resposta = await client.post(
            "/pesagens", json={"peso_kg": 70.0, "registrada_em": registrada_em}
        )

        assert resposta.status_code == 201

    @pytest.mark.parametrize("peso_kg", [19.9, 400.1, 0, -5, 1000])
    async def test_peso_fora_da_faixa_retorna_422(
        self, make_authed_client: AuthedClientFactory, peso_kg: float
    ) -> None:
        client = await make_authed_client("user-1")

        resposta = await client.post("/pesagens", json={"peso_kg": peso_kg})

        assert resposta.status_code == 422

    async def test_registrada_em_no_futuro_retorna_422(
        self, make_authed_client: AuthedClientFactory
    ) -> None:
        client = await make_authed_client("user-1")
        amanha = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

        resposta = await client.post("/pesagens", json={"peso_kg": 70.0, "registrada_em": amanha})

        assert resposta.status_code == 422

    async def test_registrada_em_sem_timezone_e_tratada_como_utc(
        self, make_authed_client: AuthedClientFactory
    ) -> None:
        """`registrada_em` sem offset de timezone (ex.: usuário mandou
        `"2026-07-15T08:00:00"`) é normalizada como UTC, não rejeitada."""
        client = await make_authed_client("user-1")

        resposta = await client.post(
            "/pesagens", json={"peso_kg": 70.0, "registrada_em": "2020-01-01T08:00:00"}
        )

        assert resposta.status_code == 201
        assert resposta.json()["registrada_em"].startswith("2020-01-01T08:00:00")


class TestListarPesagens:
    async def test_lista_vazia_quando_sem_pesagens(
        self, make_authed_client: AuthedClientFactory
    ) -> None:
        client = await make_authed_client("user-1")

        resposta = await client.get("/pesagens")

        assert resposta.status_code == 200
        assert resposta.json() == []

    async def test_lista_ordenada_da_mais_recente_para_a_mais_antiga(
        self, make_authed_client: AuthedClientFactory, fake_store: dict
    ) -> None:
        agora = datetime.now(timezone.utc)
        inserir_pesagem(fake_store, "user-1", peso_kg=80.0, registrada_em=agora - timedelta(days=10))
        inserir_pesagem(fake_store, "user-1", peso_kg=78.0, registrada_em=agora - timedelta(days=1))
        inserir_pesagem(fake_store, "user-1", peso_kg=79.0, registrada_em=agora - timedelta(days=5))

        client = await make_authed_client("user-1")
        resposta = await client.get("/pesagens")

        assert resposta.status_code == 200
        pesos_na_ordem = [linha["peso_kg"] for linha in resposta.json()]
        assert pesos_na_ordem == [78.0, 79.0, 80.0]


class TestEditarPesagem:
    async def test_editar_peso_com_sucesso(
        self, make_authed_client: AuthedClientFactory, fake_store: dict
    ) -> None:
        pesagem = inserir_pesagem(
            fake_store, "user-1", peso_kg=80.0, registrada_em=datetime.now(timezone.utc)
        )
        client = await make_authed_client("user-1")

        resposta = await client.put(f"/pesagens/{pesagem['id']}", json={"peso_kg": 79.5})

        assert resposta.status_code == 200
        assert resposta.json()["peso_kg"] == 79.5

    async def test_editar_sem_nenhum_campo_retorna_422(
        self, make_authed_client: AuthedClientFactory, fake_store: dict
    ) -> None:
        pesagem = inserir_pesagem(
            fake_store, "user-1", peso_kg=80.0, registrada_em=datetime.now(timezone.utc)
        )
        client = await make_authed_client("user-1")

        resposta = await client.put(f"/pesagens/{pesagem['id']}", json={})

        assert resposta.status_code == 422

    async def test_editar_peso_fora_da_faixa_retorna_422(
        self, make_authed_client: AuthedClientFactory, fake_store: dict
    ) -> None:
        pesagem = inserir_pesagem(
            fake_store, "user-1", peso_kg=80.0, registrada_em=datetime.now(timezone.utc)
        )
        client = await make_authed_client("user-1")

        resposta = await client.put(f"/pesagens/{pesagem['id']}", json={"peso_kg": 1000.0})

        assert resposta.status_code == 422

    async def test_editar_data_futura_retorna_422(
        self, make_authed_client: AuthedClientFactory, fake_store: dict
    ) -> None:
        pesagem = inserir_pesagem(
            fake_store, "user-1", peso_kg=80.0, registrada_em=datetime.now(timezone.utc)
        )
        client = await make_authed_client("user-1")
        amanha = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

        resposta = await client.put(f"/pesagens/{pesagem['id']}", json={"registrada_em": amanha})

        assert resposta.status_code == 422

    async def test_editar_pesagem_inexistente_retorna_404(
        self, make_authed_client: AuthedClientFactory
    ) -> None:
        client = await make_authed_client("user-1")

        resposta = await client.put(
            "/pesagens/00000000-0000-0000-0000-000000000000", json={"peso_kg": 70.0}
        )

        assert resposta.status_code == 404


class TestExcluirPesagem:
    async def test_excluir_pesagem_propria_com_sucesso(
        self, make_authed_client: AuthedClientFactory, fake_store: dict
    ) -> None:
        pesagem = inserir_pesagem(
            fake_store, "user-1", peso_kg=80.0, registrada_em=datetime.now(timezone.utc)
        )
        client = await make_authed_client("user-1")

        resposta = await client.delete(f"/pesagens/{pesagem['id']}")

        assert resposta.status_code == 204
        assert fake_store["pesagens"] == []

    async def test_excluir_pesagem_inexistente_retorna_404(
        self, make_authed_client: AuthedClientFactory
    ) -> None:
        client = await make_authed_client("user-1")

        resposta = await client.delete("/pesagens/00000000-0000-0000-0000-000000000000")

        assert resposta.status_code == 404


class TestIsolamentoEntreUsuarios:
    """Ver docstring do módulo: cobre que o app nunca vê/edita/exclui
    pesagem de outro usuário, dado que a RLS (simulada aqui) isola por
    `user_id`. A garantia da policy SQL real fica a cargo da migration."""

    async def test_usuario_nao_ve_pesagem_de_outro_na_listagem(
        self, make_authed_client: AuthedClientFactory, fake_store: dict
    ) -> None:
        agora = datetime.now(timezone.utc)
        inserir_pesagem(fake_store, "user-a", peso_kg=70.0, registrada_em=agora)
        inserir_pesagem(fake_store, "user-b", peso_kg=90.0, registrada_em=agora)

        client_b = await make_authed_client("user-b")
        resposta = await client_b.get("/pesagens")

        assert resposta.status_code == 200
        pesos = [linha["peso_kg"] for linha in resposta.json()]
        assert pesos == [90.0]

    async def test_usuario_nao_edita_pesagem_de_outro(
        self, make_authed_client: AuthedClientFactory, fake_store: dict
    ) -> None:
        pesagem_de_a = inserir_pesagem(
            fake_store, "user-a", peso_kg=70.0, registrada_em=datetime.now(timezone.utc)
        )

        client_b = await make_authed_client("user-b")
        # `peso_kg` dentro da faixa válida (20-400) de propósito: o objetivo
        # deste teste é isolamento por RLS, não validação de faixa — um
        # peso inválido geraria 422 antes mesmo de chegar na checagem de
        # dono da pesagem.
        resposta = await client_b.put(f"/pesagens/{pesagem_de_a['id']}", json={"peso_kg": 71.0})

        assert resposta.status_code == 404
        # A pesagem original de A não foi alterada.
        assert fake_store["pesagens"][0]["peso_kg"] == 70.0

    async def test_usuario_nao_exclui_pesagem_de_outro(
        self, make_authed_client: AuthedClientFactory, fake_store: dict
    ) -> None:
        pesagem_de_a = inserir_pesagem(
            fake_store, "user-a", peso_kg=70.0, registrada_em=datetime.now(timezone.utc)
        )

        client_b = await make_authed_client("user-b")
        resposta = await client_b.delete(f"/pesagens/{pesagem_de_a['id']}")

        assert resposta.status_code == 404
        # A pesagem de A continua existindo.
        assert len(fake_store["pesagens"]) == 1

    async def test_criar_pesagem_sempre_usa_user_id_do_token_nunca_do_body(
        self, make_authed_client: AuthedClientFactory, fake_store: dict
    ) -> None:
        """`PesagemCreate` (schema de request) nem aceita `user_id` como
        campo — não há como o cliente forjar de quem é a pesagem. Envia um
        campo extra `user_id` no corpo (ignorado pelo Pydantic, que não o
        declara) e confirma que a pesagem criada pertence ao usuário do
        token (`user-a`), nunca ao valor forjado no body."""
        client_a = await make_authed_client("user-a")

        resposta = await client_a.post(
            "/pesagens", json={"peso_kg": 70.0, "user_id": "user-b-forjado"}
        )

        assert resposta.status_code == 201
        assert fake_store["pesagens"][0]["user_id"] == "user-a"


class TestAutenticacao:
    @pytest.mark.parametrize(
        ("metodo", "caminho", "corpo"),
        [
            ("POST", "/pesagens", {"peso_kg": 70.0}),
            ("GET", "/pesagens", None),
            ("PUT", "/pesagens/00000000-0000-0000-0000-000000000000", {"peso_kg": 70.0}),
            ("DELETE", "/pesagens/00000000-0000-0000-0000-000000000000", None),
        ],
    )
    async def test_401_sem_token_em_todas_as_rotas(
        self, client: AsyncClient, metodo: str, caminho: str, corpo: dict | None
    ) -> None:
        resposta = await client.request(metodo, caminho, json=corpo)

        assert resposta.status_code == 401

    async def test_dependency_override_nao_vaza_entre_testes(self, client: AsyncClient) -> None:
        assert get_current_user not in app.dependency_overrides
        resposta = await client.get("/pesagens")
        assert resposta.status_code == 401
