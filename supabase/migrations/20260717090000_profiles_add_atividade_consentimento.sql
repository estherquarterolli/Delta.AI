-- =============================================================================
-- Migration: profiles_add_atividade_consentimento
-- Autor: supabase-architect
-- Data: 2026-07-17
--
-- Propósito
--   Migration aditiva sobre public.profiles (criada em
--   20260716000000_init_profiles_goals.sql). Adiciona colunas pedidas para o
--   fluxo de onboarding/consentimento:
--     - nivel_atividade         -> nível de atividade física autodeclarado,
--                                  usado no cálculo de gasto calórico (TDEE).
--     - peso_inicial_kg         -> peso (kg) informado no onboarding —
--                                  baseline do usuário. Distinto do
--                                  peso_inicial_kg de cada linha em
--                                  public.goals (peso no momento em que
--                                  aquela meta específica foi criada).
--     - aceite_termos_em        -> timestamp do aceite dos Termos de
--                                  Uso/Política de Privacidade. Consentimento
--                                  obrigatório do ponto de vista de produto/
--                                  LGPD, mas coluna NULLABLE no banco — ver
--                                  desvio nº 4 abaixo (testado localmente;
--                                  NOT NULL quebra o signup existente).
--     - aceite_data_sharing_ia  -> consentimento explícito e opcional (opt-in,
--                                  default false) para compartilhar dados
--                                  anonimizados com o wrapper de IA (Grok) —
--                                  ver app/ai/grok_client.py e Anonymizer.
--
-- Decisões de modelagem
--
--   nivel_atividade: CHECK constraint sobre text, não ENUM nativo do
--   Postgres — mesma convenção já adotada pra `sexo` nesta tabela (ver
--   20260716000000_init_profiles_goals.sql). Um tipo ENUM nativo exige
--   `ALTER TYPE ... ADD VALUE` pra adicionar opção nova, o que não roda
--   dentro de transação em algumas versões e complica migrations aditivas
--   simples. CHECK constraint muda com `ALTER TABLE ... DROP/ADD
--   CONSTRAINT` direto, sem lock de catálogo especial. Consistência com o
--   restante do schema > validação extra de enum nativo.
--
--   aceite_termos_em NULLABLE no banco (não NOT NULL, apesar do pedido
--   original — ver desvio nº 4): testado localmente via `supabase start` +
--   simulação de signup (insert em auth.users). A tabela public.profiles já
--   tem a trigger on_auth_user_created/handle_new_user() (criada em
--   20260716000000_init_profiles_goals.sql) que roda em SECURITY DEFINER e
--   insere `public.profiles (id)` — só a coluna id — a cada novo usuário em
--   auth.users. Com aceite_termos_em NOT NULL sem default, esse insert
--   automático passa a falhar com "null value in column aceite_termos_em
--   violates not-null constraint", o que aborta a criação do próprio
--   auth.users (erro confirmado em teste local, reproduzido e revertido
--   nesta migration). Enforcement de "aceite obrigatório antes de usar o
--   app" fica a cargo da camada de aplicação (backend-engineer), não do
--   CHECK/NOT NULL do Postgres, até que a premissa já aberta no header da
--   migration original (mover a criação de profiles do trigger de banco pro
--   fluxo de onboarding do backend) seja resolvida — ver desvio nº 4.
--
-- Desvios sinalizados de volta pro product-spec (NÃO implementados nesta
-- migration — decisão deliberada do supabase-architect, ver resumo
-- reportado ao final da tarefa):
--
--   1. O pedido original também pedia `restricoes_alimentares` e
--      `condicoes_medicas` como colunas text[] dentro de `profiles`. Isso
--      contraria a regra não-negociável do projeto (CLAUDE.md: "Dados
--      sensíveis (condições médicas, fotos) em tabelas separadas — deletar
--      conta = deletar limpo"). Essas informações já existem, isoladas, em
--      public.condicoes_saude e public.restricoes_alimentares (criadas em
--      20260716000000_init_profiles_goals.sql, cada uma com sua própria FK
--      ON DELETE CASCADE e RLS própria) — não foram duplicadas aqui como
--      colunas de profiles.
--
--   2. O pedido original especificava `sexo` como enum 'M'/'F'/'outro'.
--      `profiles.sexo` já existe (CHECK constraint) com os valores
--      'masculino'/'feminino'/'outro'/'prefiro_nao_informar' — um
--      superconjunto semântico que já cobre o pedido. Não renomeado aqui
--      pra evitar migration destrutiva de valores já documentados em
--      docs/erd.md sem confirmação explícita do product-spec.
--
--   3. O pedido original especificava `goals` com colunas `peso_meta_kg`,
--      `prazo_semanas` (int) e `ativa` (bool). A tabela public.goals já
--      existente cobre a mesma necessidade funcional — uma única meta ativa
--      por usuário, garantida por unique index parcial (ver
--      goals_unique_active_per_user) — usando `peso_meta_kg`, `prazo_data`
--      (data alvo em vez de duração relativa em semanas, decisão já
--      justificada no header da migration original) e `status` (CHECK
--      'ativa'|'concluida'|'cancelada'|'expirada', mais expressivo que um
--      bool binário). Renomear essas colunas seria mudança estrutural
--      não-aditiva sobre uma tabela que já tem RLS e índice em produção
--      potencial — não foi feita sem confirmação explícita do product-spec.
--      public.goals NÃO é alterada nesta migration.
--
--   4. O pedido original especificava `aceite_termos_em` como NOT NULL.
--      Implementado inicialmente como tal, mas teste local (`supabase
--      start` + insert simulando signup em auth.users) reproduziu uma
--      quebra real: a trigger handle_new_user() já existente insere
--      public.profiles(id) sem nenhum outro campo, e falha contra um NOT
--      NULL sem default — travando a criação de conta inteira. Revertido
--      para NULLABLE nesta migration; consentimento obrigatório passa a ser
--      responsabilidade da camada de aplicação (bloquear uso do app até
--      aceite_termos_em ser preenchido no onboarding). Pedimos ao
--      product-spec/backend-engineer uma decisão sobre a premissa já aberta
--      na migration original: mover a criação de profiles do trigger de
--      banco pro backend (permitindo então reintroduzir NOT NULL com
--      segurança), ou manter nullable + enforcement de aplicação
--      permanentemente.
--
-- Reversibilidade
--   alter table public.profiles
--     drop column if exists nivel_atividade,
--     drop column if exists peso_inicial_kg,
--     drop column if exists aceite_termos_em,
--     drop column if exists aceite_data_sharing_ia;
--
-- Idempotência
--   `add column if not exists` protege contra reaplicação parcial.
-- =============================================================================

alter table public.profiles
  add column if not exists nivel_atividade text
    check (
      nivel_atividade is null
      or nivel_atividade in ('sedentario', 'leve', 'moderado', 'intenso', 'muito_intenso')
    );

alter table public.profiles
  add column if not exists peso_inicial_kg numeric(5, 2)
    check (peso_inicial_kg is null or peso_inicial_kg between 20 and 400);

alter table public.profiles
  add column if not exists aceite_termos_em timestamptz;

alter table public.profiles
  add column if not exists aceite_data_sharing_ia boolean not null default false;

comment on column public.profiles.nivel_atividade is
  'Nível de atividade física autodeclarado, usado no cálculo de gasto calórico (TDEE). CHECK constraint por consistência com sexo — ver decisão de modelagem no header desta migration.';
comment on column public.profiles.peso_inicial_kg is
  'Peso (kg) informado no onboarding/cadastro — baseline do usuário. Distinto do peso_inicial_kg de cada linha em public.goals (peso no momento em que aquela meta específica foi criada).';
comment on column public.profiles.aceite_termos_em is
  'Timestamp do aceite dos Termos de Uso/Política de Privacidade. Consentimento obrigatório do ponto de vista de produto/LGPD, mas NULLABLE no banco: a trigger handle_new_user() cria profiles(id) sem esse campo no signup — enforcement de "preenchido antes de usar o app" é responsabilidade da aplicação. Ver desvio nº 4 no header desta migration.';
comment on column public.profiles.aceite_data_sharing_ia is
  'Consentimento explícito (opt-in, default false) para compartilhar dados anonimizados com o wrapper de IA (Grok). Ver app/ai/grok_client.py e Anonymizer — nunca usado para chamar a IA diretamente sem passar por essa checagem na camada de aplicação.';

-- Nenhuma mudança de RLS necessária: profiles já tem RLS habilitada e
-- policies select/insert/update/delete escopadas por auth.uid() = id (RLS
-- é por linha, não por coluna — colunas novas herdam as policies
-- existentes automaticamente). O trigger trg_profiles_set_updated_at já
-- criado também cobre updates nestas novas colunas sem alteração.
