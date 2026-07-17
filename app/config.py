"""Configuração da aplicação via variáveis de ambiente.

Usa `pydantic-settings` pra carregar env vars com os mesmos nomes
definidos em `.env.example` (raiz). Tudo é opcional o suficiente pra
app subir sem crashar quando faltar alguma variável — importante pro
`GET /health` responder mesmo sem Supabase/Postgres configurado.
Rotas que realmente precisam de um valor específico (ex.: `/health/db`
precisa de `database_url`) validam isso no momento do uso.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

_LOCALHOST_FRONTEND = "http://localhost:3000"


class Settings(BaseSettings):
    """Variáveis de ambiente do backend (nomes espelham `.env.example`)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    database_url: str | None = None
    sentry_dsn_backend: str | None = None
    environment: str = "development"
    # Domínio de produção do frontend (Vercel). Default localhost pra dev.
    frontend_url: str = _LOCALHOST_FRONTEND

    @property
    def cors_origins(self) -> list[str]:
        """Origins liberadas no CORS: localhost:3000 sempre + `FRONTEND_URL` de prod."""
        origins = [_LOCALHOST_FRONTEND]
        if self.frontend_url and self.frontend_url not in origins:
            origins.append(self.frontend_url)
        return origins


@lru_cache
def get_settings() -> Settings:
    """Instância cacheada de `Settings` (lida das env vars uma vez por processo)."""
    return Settings()
