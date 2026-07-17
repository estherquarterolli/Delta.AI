"""Verificação de conectividade com o Postgres (Supabase) via `DATABASE_URL`.

Só usado pelo `GET /health/db`. Não é o cliente de aplicação — esse é
responsabilidade do `supabase-architect` (schema/RLS) junto com os
repositories de cada módulo, que devem usar o client Supabase com o
token do usuário, nunca conexão direta com `service_role`.
"""

from __future__ import annotations

import asyncpg

from app.config import get_settings


class DatabaseUnavailableError(Exception):
    """Levantado quando o Postgres não está configurado ou não responde.

    A mensagem é sempre curta e segura pra virar `detail` de resposta
    HTTP — nunca inclui a connection string.
    """


async def check_db_connection() -> None:
    """Abre uma conexão curta com o Postgres e roda `SELECT 1`.

    Levanta `DatabaseUnavailableError` se `DATABASE_URL` não estiver
    configurada ou se a conexão/consulta falhar por qualquer motivo.
    """
    settings = get_settings()
    if not settings.database_url:
        raise DatabaseUnavailableError("DATABASE_URL não configurada")

    try:
        conn = await asyncpg.connect(settings.database_url, timeout=5)
    except Exception as exc:
        raise DatabaseUnavailableError("não foi possível conectar ao banco") from exc

    try:
        await conn.fetchval("SELECT 1")
    except Exception as exc:
        raise DatabaseUnavailableError("falha ao executar consulta de verificação") from exc
    finally:
        await conn.close()
