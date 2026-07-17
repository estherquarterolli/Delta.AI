# supabase/ — Schema, migrations e storage

Dono: `supabase-architect`.

- `migrations/` — migrations SQL versionadas (schema + RLS policies). Aplicadas via `supabase db push` (CI) ou `supabase db reset` (local).
- Config de Storage (buckets, políticas de acesso a fotos com URL assinada expirando em ≤ 15min) também é definida aqui, no `config.toml` gerado por `supabase init`.

## Local

```
supabase start   # sobe Postgres/Auth/Storage local (Docker), orquestrado pela Supabase CLI
supabase status  # mostra URLs e keys locais pra preencher o .env
```

Toda tabela com `user_id` precisa de RLS policy pra select/insert/
update/delete — regra não-negociável do projeto (ver CLAUDE.md da
raiz).

## Backup

Supabase Free faz snapshot diário automático. O procedimento de
restauração é documentado pelo `devops-engineer` assim que o projeto
Supabase for provisionado (painel Supabase → Database → Backups →
Restore, ou via `pg_restore` a partir do dump baixado).
