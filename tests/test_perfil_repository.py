"""Testes de `app/modules/perfil/repository.py` contra o `FakeSupabaseClient`
(ver `tests/conftest.py`) — cobre especificamente o ponto crítico sinalizado
pelo `supabase-architect`: ausência de linha em `condicoes_saude` deve ser
tratada como `esta_gestante = False`, nunca como erro.
"""

from __future__ import annotations

from datetime import date

from app.db.auth import User
from app.modules.perfil.repository import obter_esta_gestante, obter_perfil
from tests.conftest import FakeSupabaseClient, inserir_condicoes_saude, inserir_perfil


def _usuario(fake_store: dict, user_id: str = "user-1") -> User:
    return User(id=user_id, email=None, supabase=FakeSupabaseClient(fake_store, user_id))


class TestObterEstaGestante:
    async def test_sem_linha_em_condicoes_saude_retorna_false_sem_erro(
        self, fake_store: dict
    ) -> None:
        # Nenhuma linha inserida pra este usuário em `condicoes_saude`.
        resultado = await obter_esta_gestante(_usuario(fake_store))

        assert resultado is False

    async def test_com_linha_esta_gestante_true(self, fake_store: dict) -> None:
        inserir_condicoes_saude(fake_store, "user-1", esta_gestante=True)

        resultado = await obter_esta_gestante(_usuario(fake_store))

        assert resultado is True

    async def test_com_linha_esta_gestante_false(self, fake_store: dict) -> None:
        inserir_condicoes_saude(fake_store, "user-1", esta_gestante=False)

        resultado = await obter_esta_gestante(_usuario(fake_store))

        assert resultado is False

    async def test_linha_de_outro_usuario_nao_e_visivel(self, fake_store: dict) -> None:
        inserir_condicoes_saude(fake_store, "outro-user", esta_gestante=True)

        resultado = await obter_esta_gestante(_usuario(fake_store, "user-1"))

        assert resultado is False


class TestObterPerfil:
    async def test_sem_linha_em_profiles_retorna_none(self, fake_store: dict) -> None:
        resultado = await obter_perfil(_usuario(fake_store))

        assert resultado is None

    async def test_com_linha_completa(self, fake_store: dict) -> None:
        inserir_perfil(fake_store, "user-1", altura_cm=173, data_nascimento="1990-01-01")

        resultado = await obter_perfil(_usuario(fake_store))

        assert resultado is not None
        assert resultado.altura_cm == 173
        assert resultado.data_nascimento == date(1990, 1, 1)

    async def test_linha_de_outro_usuario_nao_e_visivel(self, fake_store: dict) -> None:
        inserir_perfil(fake_store, "outro-user", altura_cm=180, data_nascimento="1985-05-05")

        resultado = await obter_perfil(_usuario(fake_store, "user-1"))

        assert resultado is None
