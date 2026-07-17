-- =============================================================================
-- Migration: create_pesagens
-- Autor: supabase-architect
-- Data: 2026-07-17
--
-- Propósito
--   Cria public.pesagens — histórico de pesagens do usuário (peso + data/
--   hora em que a pesagem foi feita). Pré-requisito bloqueante de
--   specs/2026-07-17-calculo-imc.md: o IMC passa a usar a pesagem mais
--   recente do usuário em vez de profiles.peso_inicial_kg (baseline única
--   do onboarding). Ver specs/2026-07-17-registro-de-peso.md.
--
-- Decisões de modelagem
--
--   Histórico (múltiplas linhas por usuário), nunca sobrescrito — mesmo
--   padrão já usado em public.goals. Uma nova pesagem é sempre um INSERT;
--   "corrigir uma pesagem" é um UPDATE na linha específica (ex.: erro de
--   digitação), não uma lógica de "qual é a atual" — isso é sempre derivado
--   por ORDER BY registrada_em desc LIMIT 1 (ver índice abaixo), nunca por
--   uma flag "é a mais recente" armazenada (que ficaria desatualizada a
--   cada INSERT/edição sem trigger extra).
--
--   registrada_em (timestamptz, not null, default now()) é distinto de
--   created_at: registrada_em é quando a pessoa se pesou (informado pelo
--   usuário, pode ser retroativo — "me pesei ontem de manhã"); created_at é
--   quando a linha foi gravada no banco. Todo consumidor de "peso mais
--   recente" (ex. módulo de IMC) deve ordenar por registrada_em, nunca por
--   created_at — reforçado em comment on column abaixo.
--
--   CHECK (registrada_em <= now()) — defesa em profundidade no banco além
--   da validação de aplicação (422 antes de tocar o banco, exigida pelo
--   spec). Mesmo padrão já usado em profiles.data_nascimento (CHECK contra
--   current_date nesta mesma base de código, ver
--   20260716000000_init_profiles_goals.sql) — não é a primeira vez que este
--   projeto usa uma função STABLE (now()/current_date) num CHECK constraint
--   pra impedir dado logicamente impossível ("pesagem de amanhã") mesmo se
--   a camada de aplicação tiver um bug. Reavaliado a cada INSERT/UPDATE da
--   linha (não é precomputado), então uma edição que tente mover
--   registrada_em pro futuro também é rejeitada.
--
--   peso_kg numeric(5,2) CHECK entre 20 e 400 — mesma faixa de sanidade já
--   usada em profiles.peso_inicial_kg e goals.peso_inicial_kg/peso_meta_kg,
--   por consistência de validação entre todas as tabelas de peso do
--   projeto (pedido explícito do spec de registro de peso).
--
--   Índice único (user_id, registrada_em desc), sem índice adicional
--   isolado em (user_id): como user_id é a coluna líder do índice
--   composto, ele já cobre eficientemente tanto "listar histórico de um
--   usuário" (where user_id = $1) quanto "pesagem mais recente de um
--   usuário" (where user_id = $1 order by registrada_em desc limit 1, sem
--   sort adicional — a ordem do índice já bate com a ordem pedida). Um
--   segundo índice só em (user_id) seria redundante (mesmo raciocínio que
--   dispensa idx_goals_user_id aqui, diferente de goals, que não tem
--   índice composto).
--
--   Isolamento de dado sensível: peso corporal já é tratado no projeto
--   como dado de saúde indireto (mesma classificação de
--   profiles.peso_inicial_kg/goals.*_kg em docs/erd.md). Segue o mesmo
--   padrão de isolamento por FK própria ON DELETE CASCADE das demais
--   tabelas user-scoped — não precisa do isolamento mais forte de
--   condicoes_saude (que guarda texto livre de condições médicas), mas
--   "deletar conta = deletar limpo" é garantido da mesma forma.
--
-- Reversibilidade
--   drop trigger if exists trg_pesagens_set_updated_at on public.pesagens;
--   drop table if exists public.pesagens;
--
-- Idempotência
--   create table/index if not exists + drop policy/trigger if exists antes
--   de recriar — mesmo padrão das migrations anteriores.
-- =============================================================================

create table if not exists public.pesagens (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null references auth.users (id) on delete cascade,

  peso_kg        numeric(5, 2) not null
                   check (peso_kg between 20 and 400),

  -- Quando a pesagem foi feita (informado pelo usuário, pode ser
  -- retroativo). Distinto de created_at — ver decisão de modelagem no
  -- header desta migration.
  registrada_em  timestamptz not null default now()
                   check (registrada_em <= now()),

  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

comment on table public.pesagens is
  'Histórico de pesagens do usuário (peso + data/hora em que a pesagem foi feita). Nunca sobrescrito — mesmo padrão de public.goals. Consumida pelo módulo de IMC via "pesagem mais recente" (ORDER BY registrada_em DESC LIMIT 1).';
comment on column public.pesagens.peso_kg is
  'Peso em kg. CHECK 20..400 — mesma faixa de profiles.peso_inicial_kg e goals.peso_inicial_kg/peso_meta_kg.';
comment on column public.pesagens.registrada_em is
  'Quando a pesagem foi feita (informado pelo usuário, pode ser retroativo). Distinto de created_at (quando a linha foi gravada no banco). "Peso mais recente" é sempre definido por MAX(registrada_em), nunca por created_at. CHECK <= now() é defesa em profundidade além da validação 422 de aplicação (não é possível registrar pesagem futura).';
comment on column public.pesagens.created_at is
  'Quando a linha foi inserida no banco — não usar pra ordenar "pesagem mais recente" (usar registrada_em).';

drop trigger if exists trg_pesagens_set_updated_at on public.pesagens;
create trigger trg_pesagens_set_updated_at
  before update on public.pesagens
  for each row
  execute function public.set_updated_at();

-- Suporta "pesagem mais recente do usuário" e listagem de histórico
-- paginada sem scan nem sort adicional (ver decisão de modelagem no
-- header). user_id como coluna líder também cobre queries que filtram só
-- por usuário, sem precisar de índice extra isolado em (user_id).
create index if not exists idx_pesagens_user_id_registrada_em
  on public.pesagens (user_id, registrada_em desc);

alter table public.pesagens enable row level security;

drop policy if exists "select_own_pesagens" on public.pesagens;
create policy "select_own_pesagens" on public.pesagens
  for select using (auth.uid() = user_id);

drop policy if exists "insert_own_pesagens" on public.pesagens;
create policy "insert_own_pesagens" on public.pesagens
  for insert with check (auth.uid() = user_id);

drop policy if exists "update_own_pesagens" on public.pesagens;
create policy "update_own_pesagens" on public.pesagens
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "delete_own_pesagens" on public.pesagens;
create policy "delete_own_pesagens" on public.pesagens
  for delete using (auth.uid() = user_id);
