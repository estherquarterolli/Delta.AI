# supabase/migrations/ — Migrations SQL

Migrations versionadas, geradas via `supabase migration new <nome>`
e aplicadas com `supabase db push` (produção, via CI) ou
`supabase db reset` (local, recria o banco do zero aplicando todas
as migrations em ordem).

Convenção de nome: `<timestamp>_<descricao_curta>.sql` (gerado
automaticamente pelo CLI).

Toda migration que cria tabela com `user_id` deve incluir a RLS
policy correspondente na mesma migration. Dono: `supabase-architect`.
