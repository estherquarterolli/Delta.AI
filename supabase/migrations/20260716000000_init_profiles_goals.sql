-- =============================================================================
-- Migration: init_profiles_goals
-- Autor: supabase-architect
-- Data: 2026-07-16
--
-- Propósito
--   Primeira migration do projeto. Cria a base de dados de usuário:
--     - public.profiles                 -> extensão 1:1 de auth.users (dados
--                                          de perfil não-sensíveis: sexo,
--                                          data de nascimento, altura)
--     - public.condicoes_saude          -> dado de saúde SENSÍVEL (LGPD art.
--                                          5º, II), isolado em tabela própria
--     - public.restricoes_alimentares   -> restrições/alergias alimentares,
--                                          também isolado em tabela própria
--     - public.goals                    -> metas de emagrecimento (histórico)
--
-- Regras aplicadas (ver CLAUDE.md e .claude/agents/supabase-architect.md):
--   - RLS habilitada em toda tabela user-scoped, sem exceção.
--   - Nenhuma policy usa service_role.
--   - FK de dado de usuário sempre com ON DELETE CASCADE.
--   - Dado sensível (condições de saúde) em tabela separada de `profiles`,
--     pra permitir "deletar conta = deletar limpo" e evolução independente
--     (ex.: criptografia adicional, retenção diferenciada) sem tocar no
--     restante do perfil.
--   - Colunas de medida com unidade explícita no nome (altura_cm, peso_kg).
--   - created_at/updated_at timestamptz default now() + trigger em toda
--     tabela.
--
-- Reversibilidade
--   Esta é a migration inicial (banco vazio antes dela) — não há estado
--   anterior pra migrar de volta. Rollback documentado, caso necessário:
--     drop trigger if exists on_auth_user_created on auth.users;
--     drop table if exists public.goals;
--     drop table if exists public.restricoes_alimentares;
--     drop table if exists public.condicoes_saude;
--     drop table if exists public.profiles;
--     drop function if exists public.handle_new_user();
--     drop function if exists public.set_updated_at();
--
-- Idempotência
--   Statements usam IF NOT EXISTS / CREATE OR REPLACE / DROP ... IF EXISTS
--   antes de CREATE onde aplicável, pra permitir reexecução segura (ex.: em
--   caso de apply parcial). `supabase db reset` já garante banco limpo antes
--   de reaplicar todas as migrations em ordem; isso é uma camada extra de
--   segurança, não uma dependência do fluxo normal.
-- =============================================================================

-- Garante gen_random_uuid() disponível. Em Postgres 13+ já é nativo, mas o
-- guard idempotente custa nada e protege contra imagens mais antigas.
create extension if not exists pgcrypto;

-- -----------------------------------------------------------------------------
-- Função utilitária: mantém updated_at sempre atual em UPDATE.
-- Reaproveitada por todas as tabelas desta migration.
-- -----------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

comment on function public.set_updated_at() is
  'Trigger BEFORE UPDATE que atualiza updated_at = now() em qualquer tabela que a utilize.';


-- =============================================================================
-- TABELA: profiles
--
-- Extensão 1:1 de auth.users. Guarda apenas atributos de perfil NÃO
-- sensíveis do ponto de vista de dado de saúde (LGPD art. 5º, II). Dados de
-- saúde (condições, restrições alimentares) ficam em tabelas próprias — ver
-- condicoes_saude e restricoes_alimentares abaixo.
--
-- Decisão de modelagem — `sexo`: CHECK constraint sobre text, não ENUM.
--   Um tipo ENUM do Postgres exige `ALTER TYPE ... ADD VALUE` pra adicionar
--   opção nova (ex.: incluir mais uma categoria de gênero no futuro), e essa
--   alteração não pode rodar dentro da mesma transação que a usa em alguns
--   fluxos, complicando migrations aditivas simples. Um CHECK constraint é
--   alterado com um `ALTER TABLE ... DROP CONSTRAINT ... ADD CONSTRAINT ...`
--   direto, sem lock de catálogo especial e sem risco de enum "travado" em
--   uso por outras colunas/tabelas. Pro volume e estabilidade do MVP, a
--   flexibilidade de evolução > a validação extra de um tipo enum nativo.
--
-- Colunas de onboarding (sexo, data_nascimento, altura_cm) são NULLABLE:
-- o cadastro via Google OAuth cria a linha de profiles automaticamente
-- (ver trigger handle_new_user mais abaixo) só com `id` preenchido; o resto
-- é completado depois, no fluxo de onboarding do app.
-- =============================================================================
create table if not exists public.profiles (
  id              uuid primary key references auth.users (id) on delete cascade,

  sexo            text
                    check (
                      sexo is null
                      or sexo in ('masculino', 'feminino', 'outro', 'prefiro_nao_informar')
                    ),

  data_nascimento date
                    check (
                      data_nascimento is null
                      or (data_nascimento >= date '1900-01-01' and data_nascimento <= current_date)
                    ),

  -- altura em centímetros (inteiro). Faixa plausível: 50cm (bebê/nanismo
  -- extremo) a 250cm (recorde humano documentado é ~272cm; 250 cobre
  -- praticamente todo caso real de usuário adulto do app e ainda barra erro
  -- grosseiro de digitação, ex. "170" digitado como "17000").
  altura_cm       integer
                    check (
                      altura_cm is null
                      or altura_cm between 50 and 250
                    ),

  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

comment on table public.profiles is
  'Extensão 1:1 de auth.users com atributos de perfil não-sensíveis. Dados de saúde ficam em tabelas separadas (condicoes_saude, restricoes_alimentares).';
comment on column public.profiles.sexo is
  'CHECK constraint (não enum) por flexibilidade de evolução — ver comentário da migration.';
comment on column public.profiles.data_nascimento is
  'Idade é sempre derivada a partir desta data, nunca armazenada calculada.';
comment on column public.profiles.altura_cm is
  'Altura em centímetros, inteiro.';

drop trigger if exists trg_profiles_set_updated_at on public.profiles;
create trigger trg_profiles_set_updated_at
  before update on public.profiles
  for each row
  execute function public.set_updated_at();

alter table public.profiles enable row level security;

-- Padrão de policy do projeto usa `user_id`, mas em `profiles` o próprio
-- `id` É o user id (FK 1:1 pra auth.users) — por isso as policies abaixo
-- comparam auth.uid() = id em vez de auth.uid() = user_id.
drop policy if exists "select_own_profiles" on public.profiles;
create policy "select_own_profiles" on public.profiles
  for select using (auth.uid() = id);

drop policy if exists "insert_own_profiles" on public.profiles;
create policy "insert_own_profiles" on public.profiles
  for insert with check (auth.uid() = id);

drop policy if exists "update_own_profiles" on public.profiles;
create policy "update_own_profiles" on public.profiles
  for update using (auth.uid() = id) with check (auth.uid() = id);

drop policy if exists "delete_own_profiles" on public.profiles;
create policy "delete_own_profiles" on public.profiles
  for delete using (auth.uid() = id);


-- =============================================================================
-- TABELA: condicoes_saude
--
-- Dado de saúde SENSÍVEL (LGPD art. 5º, II) — ex.: diabetes, hipertensão.
-- Isolado de `profiles` numa tabela própria, com sua própria FK
-- ON DELETE CASCADE pra auth.users, garantindo que deletar a conta apaga
-- esse dado de forma limpa e independente do restante do perfil. Isso
-- também deixa a porta aberta pra tratamento diferenciado no futuro
-- (criptografia adicional em repouso, política de retenção própria,
-- auditoria de acesso mais rígida) sem migrar `profiles` inteira.
--
-- Decisão de modelagem — array (text[]) em vez de tabela normalizada:
--   Pro MVP, o app não precisa de taxonomia canônica de condições (nem
--   busca cross-user, nem metadado por condição como gravidade/data de
--   diagnóstico). Uma tabela de catálogo + tabela de junção seria
--   normalização prematura. `text[]` guarda a lista informada pelo próprio
--   usuário em texto livre com uma única linha por usuário (1:1, mesmo
--   padrão de `profiles`), sem joins extras nas leituras mais comuns
--   (montar o perfil completo do usuário). Se no futuro for necessário
--   normalizar (i18n, busca estruturada, matching com regras de nutrição),
--   isso é uma migration aditiva nova, sem quebrar o que já existe.
-- =============================================================================
create table if not exists public.condicoes_saude (
  user_id     uuid primary key references auth.users (id) on delete cascade,
  condicoes   text[] not null default '{}'::text[],
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

comment on table public.condicoes_saude is
  'Dado de saúde sensível (LGPD art. 5º, II) — condições médicas relevantes (ex.: diabetes, hipertensão). Tabela separada de profiles para isolamento e "deletar conta = deletar limpo".';
comment on column public.condicoes_saude.condicoes is
  'Lista em texto livre informada pelo usuário. Ver decisão de modelagem no header desta migration.';

drop trigger if exists trg_condicoes_saude_set_updated_at on public.condicoes_saude;
create trigger trg_condicoes_saude_set_updated_at
  before update on public.condicoes_saude
  for each row
  execute function public.set_updated_at();

alter table public.condicoes_saude enable row level security;

drop policy if exists "select_own_condicoes_saude" on public.condicoes_saude;
create policy "select_own_condicoes_saude" on public.condicoes_saude
  for select using (auth.uid() = user_id);

drop policy if exists "insert_own_condicoes_saude" on public.condicoes_saude;
create policy "insert_own_condicoes_saude" on public.condicoes_saude
  for insert with check (auth.uid() = user_id);

drop policy if exists "update_own_condicoes_saude" on public.condicoes_saude;
create policy "update_own_condicoes_saude" on public.condicoes_saude
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "delete_own_condicoes_saude" on public.condicoes_saude;
create policy "delete_own_condicoes_saude" on public.condicoes_saude
  for delete using (auth.uid() = user_id);


-- =============================================================================
-- TABELA: restricoes_alimentares
--
-- Restrições/alergias alimentares (ex.: vegetariano, sem lactose, alergia a
-- amendoim). Mesma decisão de modelagem de condicoes_saude (array de texto
-- livre, 1 linha por usuário) e mesmo isolamento em tabela própria: alergia
-- alimentar é, em si, dado de saúde (pode revelar condição médica, ex.
-- doença celíaca), então recebe o mesmo tratamento cauteloso de
-- `condicoes_saude` em vez de virar coluna em `profiles`.
--
-- Tabela separada de condicoes_saude (em vez de uma única tabela genérica
-- de "dados de saúde" com duas colunas array) porque os dois conceitos têm
-- trajetórias de evolução diferentes: restrições alimentares tendem a
-- ganhar estrutura própria mais cedo (ex.: relacionar com motor de receitas/
-- alimentos da TACO/Open Food Facts), enquanto condições médicas tendem a
-- precisar de tratamento de sensibilidade/consentimento próprio. Manter
-- tabelas separadas desde já custa pouco e evita um refactor de split
-- depois.
-- =============================================================================
create table if not exists public.restricoes_alimentares (
  user_id     uuid primary key references auth.users (id) on delete cascade,
  restricoes  text[] not null default '{}'::text[],
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

comment on table public.restricoes_alimentares is
  'Restrições/alergias alimentares do usuário. Tratado como dado sensível (pode revelar condição de saúde) e isolado de profiles pelo mesmo motivo de condicoes_saude.';
comment on column public.restricoes_alimentares.restricoes is
  'Lista em texto livre informada pelo usuário (ex.: vegetariano, sem lactose, alergia a amendoim).';

drop trigger if exists trg_restricoes_alimentares_set_updated_at on public.restricoes_alimentares;
create trigger trg_restricoes_alimentares_set_updated_at
  before update on public.restricoes_alimentares
  for each row
  execute function public.set_updated_at();

alter table public.restricoes_alimentares enable row level security;

drop policy if exists "select_own_restricoes_alimentares" on public.restricoes_alimentares;
create policy "select_own_restricoes_alimentares" on public.restricoes_alimentares
  for select using (auth.uid() = user_id);

drop policy if exists "insert_own_restricoes_alimentares" on public.restricoes_alimentares;
create policy "insert_own_restricoes_alimentares" on public.restricoes_alimentares
  for insert with check (auth.uid() = user_id);

drop policy if exists "update_own_restricoes_alimentares" on public.restricoes_alimentares;
create policy "update_own_restricoes_alimentares" on public.restricoes_alimentares
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "delete_own_restricoes_alimentares" on public.restricoes_alimentares;
create policy "delete_own_restricoes_alimentares" on public.restricoes_alimentares
  for delete using (auth.uid() = user_id);


-- =============================================================================
-- TABELA: goals (metas de emagrecimento)
--
-- Decisão de modelagem — histórico (múltiplas metas) em vez de 1 meta única:
--   Usuário pode redefinir a meta ao longo do tempo (perder peso, depois
--   manter, depois nova meta de perda). Modelar como histórico permite
--   mostrar evolução de metas na timeline do app e não perde contexto
--   quando o usuário muda de objetivo. Pra garantir que só exista UMA meta
--   "ativa" por vez (o app sempre sabe qual meta corrente usar pros
--   cálculos de progresso), usamos uma coluna `status` + um unique index
--   PARCIAL em (user_id) where status = 'ativa' — isso é reforçado pelo
--   próprio Postgres, não só por lógica de aplicação.
--
-- Decisão de modelagem — `prazo` como `date` (data alvo), não duração:
--   Guardar uma data alvo explícita (`prazo_data`) é mais direto de usar do
--   que uma duração (ex. "12 semanas"): pra virar data alvo, uma duração
--   sempre precisaria de uma data de referência (created_at? data que o
--   usuário definiu a meta?), o que é ambíguo se a meta for editada depois.
--   Com `date` fica trivial calcular "dias restantes", disparar lembretes
--   (OneSignal) e consultar metas vencidas (`prazo_data < current_date`).
--
-- peso_inicial_kg / peso_meta_kg: faixa 20kg–400kg cobre praticamente todo
-- caso real de usuário adulto e barra erro grosseiro de digitação, sem
-- embutir regra de negócio (ex. "meta sempre menor que inicial") que pode
-- mudar (ver nota de premissa no resumo final).
-- =============================================================================
create table if not exists public.goals (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid not null references auth.users (id) on delete cascade,

  peso_inicial_kg  numeric(5, 2) not null
                     check (peso_inicial_kg between 20 and 400),

  peso_meta_kg     numeric(5, 2) not null
                     check (peso_meta_kg between 20 and 400),

  prazo_data       date not null,

  status           text not null default 'ativa'
                     check (status in ('ativa', 'concluida', 'cancelada', 'expirada')),

  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);

comment on table public.goals is
  'Metas de emagrecimento do usuário. Histórico (múltiplas linhas por usuário); apenas uma pode estar com status = ativa por vez (unique index parcial).';
comment on column public.goals.prazo_data is
  'Data alvo pra atingir a meta (não duração) — ver decisão de modelagem no header da migration.';
comment on column public.goals.status is
  'ativa: meta corrente em uso pros cálculos de progresso. Só uma ativa por usuário (ver goals_unique_active_per_user).';

drop trigger if exists trg_goals_set_updated_at on public.goals;
create trigger trg_goals_set_updated_at
  before update on public.goals
  for each row
  execute function public.set_updated_at();

-- Índice de suporte a busca/join por usuário (FK não é indexada
-- automaticamente pelo Postgres, diferente de PK).
create index if not exists idx_goals_user_id on public.goals (user_id);

-- Garante no nível do banco que só existe 1 meta ativa por usuário —
-- reforça a regra de negócio "uma meta corrente por vez" mesmo se a
-- camada de aplicação tiver um bug.
create unique index if not exists goals_unique_active_per_user
  on public.goals (user_id)
  where (status = 'ativa');

alter table public.goals enable row level security;

drop policy if exists "select_own_goals" on public.goals;
create policy "select_own_goals" on public.goals
  for select using (auth.uid() = user_id);

drop policy if exists "insert_own_goals" on public.goals;
create policy "insert_own_goals" on public.goals
  for insert with check (auth.uid() = user_id);

drop policy if exists "update_own_goals" on public.goals;
create policy "update_own_goals" on public.goals
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "delete_own_goals" on public.goals;
create policy "delete_own_goals" on public.goals
  for delete using (auth.uid() = user_id);


-- =============================================================================
-- Auto-provisionamento de profiles no signup (padrão Supabase de profile 1:1)
--
-- Sem isso, toda linha nova em auth.users (signup via Google OAuth) não
-- teria profile correspondente até o app criar uma explicitamente, deixando
-- uma janela onde `select` em profiles pro usuário recém-criado retorna
-- vazio. A trigger roda com SECURITY DEFINER pra poder inserir em
-- public.profiles a partir de um evento em auth.users, contornando RLS só
-- nesse contexto controlado (nunca é chamada diretamente pela aplicação).
--
-- PREMISSA A REVISAR COM O TIME: isso assume que a criação da linha de
-- profiles deve ser responsabilidade do banco (trigger), não do
-- backend/onboarding do FastAPI. Se o time preferir que o backend
-- controle esse insert explicitamente (ex. pra já gravar sexo/altura no
-- mesmo request do onboarding), esta trigger deve ser removida em migration
-- própria — sinalizando de volta pro product-spec / backend-engineer.
-- =============================================================================
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (id)
  values (new.id)
  on conflict (id) do nothing;
  return new;
end;
$$;

comment on function public.handle_new_user() is
  'SECURITY DEFINER: cria a linha de profiles correspondente a cada novo usuário em auth.users. Único uso legítimo de bypass de RLS nesta migration — ver premissa sinalizada no header.';

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row
  execute function public.handle_new_user();
