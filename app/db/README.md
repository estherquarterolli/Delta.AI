# app/db/ — Conexão Supabase + helpers de RLS

Dono: `supabase-architect` (schema/policies) + `backend-engineer` (uso no código).

Aqui fica a conexão com o Supabase (client via `SUPABASE_URL` +
`SUPABASE_ANON_KEY`) e helpers que garantem que toda query roda no
contexto do usuário autenticado, respeitando RLS.

`SUPABASE_SERVICE_ROLE_KEY` (bypassa RLS) só pode ser usado aqui
dentro de helpers específicos para cron jobs, e cada uso precisa
estar justificado em um ADR (`docs/adr/`).
