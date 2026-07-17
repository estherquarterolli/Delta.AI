# app/db/ — Conexão Supabase + helpers de RLS

Dono: `supabase-architect` (schema/policies) + `backend-engineer` (uso no código).

Aqui fica a conexão com o Supabase (client via `SUPABASE_URL` +
`SUPABASE_ANON_KEY`) e helpers que garantem que toda query roda no
contexto do usuário autenticado, respeitando RLS.

`SUPABASE_SERVICE_ROLE_KEY` (bypassa RLS) só pode ser usado aqui
dentro de helpers específicos para cron jobs, e cada uso precisa
estar justificado em um ADR (`docs/adr/`).

`health.py` é a exceção de escopo: só abre uma conexão via `asyncpg`
usando `DATABASE_URL` pra rodar `SELECT 1`, usado por `GET /health/db`
em `app/main.py`. Não é o client de aplicação nem passa por RLS —
é só verificação de disponibilidade do Postgres pro Fly.io/monitoring.

## Client de aplicação e autenticação (`supabase_client.py` + `auth.py`)

- `supabase_client.py` — única fábrica de client Supabase (assíncrono,
  `supabase-py`) do backend. Sempre usa `SUPABASE_ANON_KEY` e injeta o
  Bearer token do usuário autenticado no PostgREST, pra toda query
  respeitar RLS. Nenhum módulo constrói um client por conta própria.
- `auth.py` — dependency `get_current_user` (usada via
  `Depends(get_current_user)`), a primeira e única forma de autenticar
  uma rota no backend. Valida o Bearer token do Supabase Auth, retorna
  `401` se ausente/inválido/expirado, e devolve um `User` com `id`,
  `email` e o client Supabase já autenticado (reusado pelos
  `repository.py` de cada módulo, sem reconstruir a conexão a cada query).
