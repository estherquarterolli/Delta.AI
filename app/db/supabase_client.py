"""Factory do client Supabase (assíncrono) usado pelas rotas autenticadas.

Todo client criado aqui é autenticado com o Bearer token do próprio usuário
(nunca `SUPABASE_SERVICE_ROLE_KEY`) — toda query feita com ele passa pelo
PostgREST com esse token no header `Authorization`, então as RLS policies
(`auth.uid() = user_id`) já criadas pelo `supabase-architect` decidem o que
cada usuário pode ver/alterar. Nenhum módulo de `app/modules/` deve
construir um client Supabase por conta própria — sempre via aqui.
"""

from __future__ import annotations

from supabase import create_async_client
from supabase._async.client import AsyncClient

from app.config import get_settings


class SupabaseNaoConfiguradoError(Exception):
    """Levantado quando `SUPABASE_URL`/`SUPABASE_ANON_KEY` não estão configuradas.

    Mensagem sempre curta e segura pra virar `detail` de resposta HTTP —
    nunca inclui as próprias chaves.
    """


async def criar_supabase_client(access_token: str) -> AsyncClient:
    """Cria um client Supabase autenticado como o usuário do `access_token`.

    Usa sempre `SUPABASE_ANON_KEY` (respeita RLS) e injeta o token do
    próprio usuário no PostgREST via `postgrest.auth(access_token)`, pra
    que `auth.uid()` dentro das policies resolva pro usuário correto.
    """
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise SupabaseNaoConfiguradoError("SUPABASE_URL/SUPABASE_ANON_KEY não configuradas.")

    client = await create_async_client(settings.supabase_url, settings.supabase_anon_key)
    client.postgrest.auth(access_token)
    return client
