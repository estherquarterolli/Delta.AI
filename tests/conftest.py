"""Fixtures compartilhadas dos testes do backend.

Não há Postgres/Supabase real disponível neste ambiente de teste (sem
`supabase start` rodando) — ver nota em `FakeSupabaseClient` abaixo sobre
como isso é coberto sem mockar comportamento de negócio, só a camada de
transporte HTTP do Supabase.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Coroutine
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from postgrest.exceptions import APIError

from app.config import get_settings
from app.db.auth import User, get_current_user
from app.main import app


@pytest.fixture(autouse=True)
def _limpa_cache_de_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Garante DATABASE_URL ausente e cache de settings limpo em cada teste.

    Sem isso, um `.env` local com `DATABASE_URL` preenchida vazaria pro
    teste de `/health/db` e o CI (sem `.env`) se comportaria diferente
    do ambiente local — os testes ficariam não-determinísticos.

    IMPORTANTE: `monkeypatch.delenv` sozinho NÃO basta. `Settings`
    (`app/config.py`) usa `pydantic-settings` com `env_file=".env"`, cuja
    ordem de precedência é env var do processo > arquivo `.env` > default
    do campo — ou seja, *remover* a env var do processo só faz
    `pydantic-settings` cair pro valor do arquivo `.env` físico, se ele
    existir com `DATABASE_URL` preenchida (achado real neste projeto: um
    `.env` local, fora do controle de versão, com uma connection string de
    Supabase de verdade). `monkeypatch.setenv("DATABASE_URL", "")` resolve
    isso: define a env var do processo como string vazia, que tem
    precedência sobre o arquivo `.env` e ainda é "falsy" pra
    `if not settings.database_url` (`app/db/health.py`), preservando o
    comportamento esperado pelo teste independentemente do que exista (ou
    não) num `.env` local.
    """
    monkeypatch.setenv("DATABASE_URL", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _limpa_dependency_overrides() -> AsyncIterator[None]:
    """Garante que overrides de `Depends` não vazem de um teste pro outro.

    `make_authed_client` usa `app.dependency_overrides` (mecanismo padrão
    do FastAPI pra testes) pra injetar um `User` fake sem passar pela
    validação real de Bearer token — sem esta limpeza, um teste que usa
    `make_authed_client` deixaria a app "autenticada" por padrão pros
    testes seguintes, inclusive os de 401.
    """
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Cliente HTTP assíncrono contra a app FastAPI, sem subir servidor real."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# =============================================================================
# Fake do client Supabase (Postgrest) — usado nos testes de integração de
# rota (`test_perfil_router.py`, `test_pesagens_router.py`).
#
# NÃO mocka regra de negócio nem respostas "prontas" por endpoint: simula a
# própria camada de transporte do Postgrest (`.table().select().eq()...
# .execute()`) sobre um armazenamento em memória (`fake_store`), inclusive
# reproduzindo o comportamento de RLS own-row (`auth.uid() = user_id`) que,
# em produção, é aplicado pelo Postgres a partir do JWT do usuário — nunca
# pelo código Python dos `repository.py` (ver `app/modules/pesagens/
# repository.py`: `listar_pesagens`/`obter_pesagem_mais_recente`/
# `obter_pesagem_por_id`/`atualizar_pesagem`/`excluir_pesagem` não filtram
# por `user_id` manualmente — a isolação depende inteiramente da RLS).
#
# Cobertura explícita:
# - O QUE este fake prova: o código do app nunca precisa (e não faz) filtro
#   manual por `user_id` vindo de URL/body — todo isolamento observado nos
#   testes vem da simulação de RLS deste fake, reproduzindo exatamente o
#   contrato que a policy real do Postgres promete (`auth.uid() = user_id`).
# - O QUE este fake NÃO prova: que a policy SQL real, aplicada num Postgres
#   de verdade, está de fato correta/ativa (`ENABLE ROW LEVEL SECURITY` +
#   as 4 policies por tabela). Isso é responsabilidade da migration
#   (`supabase/migrations/20260717120000_create_pesagens.sql`) e deve ser
#   validado com Postgres real (`supabase start` + teste de integração
#   contra o banco, ou revisão do `security-reviewer`) — fora do alcance
#   deste conftest, que não tem acesso a um Postgres local neste ambiente.
# =============================================================================


class _FakeResponse:
    """Espelha o shape de `postgrest.APIResponse`: só o atributo `.data`."""

    def __init__(self, data: Any) -> None:
        self.data = data


class _FakeTable:
    """Uma tabela fake, já "escopada" pro usuário autenticado (RLS)."""

    def __init__(self, linhas: list[dict[str, Any]], coluna_owner: str, owner_id: str) -> None:
        self._linhas = linhas  # referência mutável à lista guardada em `fake_store`.
        self._coluna_owner = coluna_owner
        self._owner_id = owner_id

    def linhas_visiveis(self) -> list[dict[str, Any]]:
        """Simula a policy `using (auth.uid() = <coluna_owner>)`."""
        return [
            linha
            for linha in self._linhas
            if str(linha.get(self._coluna_owner)) == self._owner_id
        ]

    def inserir(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Simula a policy `with check (auth.uid() = <coluna_owner>)`."""
        dono = str(dados.get(self._coluna_owner))
        if dono != self._owner_id:
            raise APIError(
                {"message": "new row violates row-level security policy", "code": "42501"}
            )
        agora = datetime.now(timezone.utc).isoformat()
        linha: dict[str, Any] = {"id": str(uuid4()), "created_at": agora, "updated_at": agora}
        linha.update(dados)
        self._linhas.append(linha)
        return linha

    def upsert(self, dados: dict[str, Any], coluna_conflito: str) -> dict[str, Any]:
        """`INSERT ... ON CONFLICT (<coluna_conflito>) DO UPDATE`, simulando
        o `Prefer: resolution=merge-duplicates` que `supabase-py` usa por
        padrão em `.upsert()`: em caso de conflito, `linha.update(dados)`
        só sobrescreve as colunas PRESENTES no payload — colunas já
        preenchidas e ausentes do payload (ex.: `condicoes`) permanecem
        intocadas. Sem conflito, insere uma linha nova só com o que veio no
        payload (+ timestamps)."""
        dono = str(dados.get(self._coluna_owner))
        if dono != self._owner_id:
            raise APIError(
                {"message": "new row violates row-level security policy", "code": "42501"}
            )
        valor_conflito = str(dados.get(coluna_conflito))
        for linha in self._linhas:
            if str(linha.get(coluna_conflito)) == valor_conflito:
                linha.update(dados)
                linha["updated_at"] = datetime.now(timezone.utc).isoformat()
                return linha

        agora = datetime.now(timezone.utc).isoformat()
        linha = {"created_at": agora, "updated_at": agora}
        linha.update(dados)
        self._linhas.append(linha)
        return linha

    def atualizar(
        self, linhas_candidatas: list[dict[str, Any]], dados: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """`UPDATE ... WHERE <filtros> AND using(RLS)`: só afeta o que já é
        visível ao dono (`linhas_candidatas` já vem filtrada por RLS +
        `.eq()` antes de chegar aqui)."""
        atualizadas = []
        for linha in linhas_candidatas:
            linha.update(dados)
            linha["updated_at"] = datetime.now(timezone.utc).isoformat()
            atualizadas.append(linha)
        return atualizadas

    def excluir(self, linhas_candidatas: list[dict[str, Any]]) -> list[dict[str, Any]]:
        excluidas = []
        for linha in linhas_candidatas:
            self._linhas.remove(linha)
            excluidas.append(linha)
        return excluidas


class _FakeQueryBuilder:
    """Réplica mínima e chainable da API do `postgrest-py` usada pelos
    `repository.py` deste projeto (`select`/`insert`/`update`/`delete`/
    `eq`/`order`/`limit`/`maybe_single`/`execute`)."""

    def __init__(self, tabela: _FakeTable) -> None:
        self._tabela = tabela
        self._op = "select"
        self._payload: Any = None
        self._on_conflict: str | None = None
        self._filtros: list[tuple[str, str]] = []
        self._order_col: str | None = None
        self._order_desc = False
        self._limit: int | None = None
        self._single = False

    def select(self, *_args: Any, **_kwargs: Any) -> "_FakeQueryBuilder":
        self._op = "select"
        return self

    def insert(self, payload: Any) -> "_FakeQueryBuilder":
        self._op = "insert"
        self._payload = payload
        return self

    def upsert(
        self, payload: Any, *, on_conflict: str = "", **_kwargs: Any
    ) -> "_FakeQueryBuilder":
        self._op = "upsert"
        self._payload = payload
        self._on_conflict = on_conflict or self._tabela._coluna_owner
        return self

    def update(self, payload: dict[str, Any]) -> "_FakeQueryBuilder":
        self._op = "update"
        self._payload = payload
        return self

    def delete(self) -> "_FakeQueryBuilder":
        self._op = "delete"
        return self

    def eq(self, coluna: str, valor: Any) -> "_FakeQueryBuilder":
        self._filtros.append((coluna, str(valor)))
        return self

    def order(self, coluna: str, desc: bool = False) -> "_FakeQueryBuilder":
        self._order_col = coluna
        self._order_desc = desc
        return self

    def limit(self, n: int) -> "_FakeQueryBuilder":
        self._limit = n
        return self

    def maybe_single(self) -> "_FakeQueryBuilder":
        self._single = True
        return self

    async def execute(self) -> _FakeResponse:
        if self._op == "insert":
            payloads = self._payload if isinstance(self._payload, list) else [self._payload]
            criadas = [self._tabela.inserir(dict(p)) for p in payloads]
            return _FakeResponse(criadas)

        if self._op == "upsert":
            payloads = self._payload if isinstance(self._payload, list) else [self._payload]
            assert self._on_conflict is not None
            gravadas = [self._tabela.upsert(dict(p), self._on_conflict) for p in payloads]
            return _FakeResponse(gravadas)

        linhas = self._tabela.linhas_visiveis()  # RLS aplicada antes de qualquer .eq().
        for coluna, valor in self._filtros:
            linhas = [linha for linha in linhas if str(linha.get(coluna)) == valor]

        if self._op == "update":
            return _FakeResponse(self._tabela.atualizar(linhas, self._payload))
        if self._op == "delete":
            return _FakeResponse(self._tabela.excluir(linhas))

        if self._order_col is not None:
            linhas = sorted(linhas, key=lambda linha: linha[self._order_col], reverse=self._order_desc)
        if self._limit is not None:
            linhas = linhas[: self._limit]
        if self._single:
            return _FakeResponse(linhas[0] if linhas else None)
        return _FakeResponse(linhas)


# Nome da coluna "dono" por tabela — mesma informação que a policy RLS real
# usa em `using (auth.uid() = <coluna>)` (ver migrations).
_COLUNA_OWNER_POR_TABELA = {
    "profiles": "id",  # profiles.id É o user id (FK 1:1 pra auth.users).
    "condicoes_saude": "user_id",
    "pesagens": "user_id",
}


class FakeSupabaseClient:
    """Substitui `supabase._async.client.AsyncClient` nos testes de rota.

    Cada instância representa a conexão autenticada de UM usuário
    (`owner_id`) contra um `fake_store` compartilhado — exatamente como, em
    produção, dois usuários diferentes têm dois clients Postgrest
    diferentes (tokens diferentes) apontando pro mesmo Postgres.
    """

    def __init__(self, fake_store: dict[str, list[dict[str, Any]]], owner_id: str) -> None:
        self._fake_store = fake_store
        self._owner_id = owner_id

    def table(self, nome: str) -> _FakeQueryBuilder:
        linhas = self._fake_store.setdefault(nome, [])
        coluna_owner = _COLUNA_OWNER_POR_TABELA.get(nome, "user_id")
        return _FakeQueryBuilder(_FakeTable(linhas, coluna_owner, self._owner_id))


@pytest.fixture
def fake_store() -> dict[str, list[dict[str, Any]]]:
    """Armazenamento em memória (`{tabela: [linhas]}`), análogo ao Postgres,
    compartilhado entre os `FakeSupabaseClient` de diferentes usuários
    criados no mesmo teste — é isso que permite testar isolamento entre
    dois usuários (RLS) sem um Postgres real."""
    return {}


@pytest.fixture
async def make_authed_client(
    fake_store: dict[str, list[dict[str, Any]]],
) -> AsyncIterator[Callable[..., Coroutine[Any, Any, AsyncClient]]]:
    """Fábrica de clientes HTTP "autenticados como" usuários fake distintos.

    Usa `app.dependency_overrides[get_current_user]` (mecanismo padrão do
    FastAPI para testes) pra pular a validação real de Bearer token —
    equivalente, para fins destes testes, a já ter passado por
    `get_current_user` com sucesso.

    IMPORTANTE: `dependency_overrides` é estado global da instância `app`,
    não por cliente HTTP. Chamar a fábrica de novo troca "quem está
    autenticado" para TODAS as requisições seguintes, de qualquer client
    já criado — por isso, em testes de isolamento entre dois usuários, as
    chamadas de cada usuário devem ser feitas em sequência (nunca
    concorrentes), trocando de usuário entre uma chamada e outra.
    """
    clientes: list[AsyncClient] = []

    async def _factory(user_id: str, email: str | None = "user@example.com") -> AsyncClient:
        fake_user = User(id=user_id, email=email, supabase=FakeSupabaseClient(fake_store, user_id))
        app.dependency_overrides[get_current_user] = lambda: fake_user
        transport = ASGITransport(app=app)
        cliente = AsyncClient(transport=transport, base_url="http://test")
        clientes.append(cliente)
        return cliente

    yield _factory

    for cliente in clientes:
        await cliente.aclose()


def inserir_perfil(
    fake_store: dict[str, list[dict[str, Any]]],
    user_id: str,
    *,
    altura_cm: int | None = None,
    data_nascimento: str | None = None,
) -> None:
    """Insere/sobrescreve a linha de `profiles` de um usuário no `fake_store`.

    `data_nascimento` é string ISO (`"YYYY-MM-DD"`) — mesmo formato que o
    Postgrest devolve e que `PerfilRow`/`repository.obter_perfil` esperam.
    """
    linhas = fake_store.setdefault("profiles", [])
    linhas[:] = [linha for linha in linhas if linha.get("id") != user_id]
    linhas.append({"id": user_id, "altura_cm": altura_cm, "data_nascimento": data_nascimento})


def inserir_condicoes_saude(
    fake_store: dict[str, list[dict[str, Any]]],
    user_id: str,
    *,
    esta_gestante: bool = False,
    condicoes: list[str] | None = None,
) -> None:
    """Insere/sobrescreve a linha de `condicoes_saude` de um usuário.

    `condicoes` espelha a coluna real `condicoes text[] not null default
    '{}'` (`supabase/migrations/20260716000000_init_profiles_goals.sql`) —
    default lista vazia, igual ao banco. Usado pra preparar o cenário do
    "UPSERT não deve zerar outros campos" (ver
    `tests/test_perfil_router.py::TestAtualizarCondicoesSaude`).
    """
    linhas = fake_store.setdefault("condicoes_saude", [])
    linhas[:] = [linha for linha in linhas if linha.get("user_id") != user_id]
    linhas.append(
        {"user_id": user_id, "esta_gestante": esta_gestante, "condicoes": condicoes or []}
    )


def inserir_pesagem(
    fake_store: dict[str, list[dict[str, Any]]],
    user_id: str,
    *,
    peso_kg: float,
    registrada_em: datetime,
) -> dict[str, Any]:
    """Insere uma pesagem diretamente no `fake_store` (sem passar pelas
    validações de `service.py` — útil pra preparar cenário de teste)."""
    agora_iso = registrada_em.isoformat()
    linha = {
        "id": str(uuid4()),
        "user_id": user_id,
        "peso_kg": peso_kg,
        "registrada_em": agora_iso,
        "created_at": agora_iso,
        "updated_at": agora_iso,
    }
    fake_store.setdefault("pesagens", []).append(linha)
    return linha
