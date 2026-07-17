# ERD — Schema do banco (Supabase Postgres)

Dono: `supabase-architect`. Atualizado a cada migration que altera schema.

Migrations de origem deste diagrama:
[`supabase/migrations/20260716000000_init_profiles_goals.sql`](../supabase/migrations/20260716000000_init_profiles_goals.sql),
[`supabase/migrations/20260717090000_profiles_add_atividade_consentimento.sql`](../supabase/migrations/20260717090000_profiles_add_atividade_consentimento.sql),
[`supabase/migrations/20260717120000_create_pesagens.sql`](../supabase/migrations/20260717120000_create_pesagens.sql)
e
[`supabase/migrations/20260717130000_condicoes_saude_add_gestante.sql`](../supabase/migrations/20260717130000_condicoes_saude_add_gestante.sql).

## Diagrama

```mermaid
erDiagram
    USERS ||--o| PROFILES : "1:1 (id = id)"
    USERS ||--o| CONDICOES_SAUDE : "1:1 (id = user_id)"
    USERS ||--o| RESTRICOES_ALIMENTARES : "1:1 (id = user_id)"
    USERS ||--o{ GOALS : "1:N (id = user_id)"
    USERS ||--o{ PESAGENS : "1:N (id = user_id)"

    USERS {
        uuid id PK
        text email "gerenciado pelo Supabase Auth"
    }

    PROFILES {
        uuid id PK_FK "-> auth.users.id, on delete cascade"
        text sexo "CHECK: masculino|feminino|outro|prefiro_nao_informar"
        date data_nascimento "nullable, sanity range 1900-01-01..hoje"
        int altura_cm "nullable, CHECK 50..250"
        text nivel_atividade "nullable, CHECK sedentario|leve|moderado|intenso|muito_intenso"
        numeric peso_inicial_kg "nullable, CHECK 20..400, baseline do onboarding"
        timestamptz aceite_termos_em "nullable no banco, obrigatorio a nivel de app (ver nota abaixo)"
        bool aceite_data_sharing_ia "NOT NULL default false, opt-in pra IA"
        timestamptz created_at
        timestamptz updated_at
    }

    CONDICOES_SAUDE {
        uuid user_id PK_FK "-> auth.users.id, on delete cascade"
        text_array condicoes "default '{}', texto livre — SENSIVEL LGPD art 5 II"
        bool esta_gestante "NOT NULL default false — SENSIVEL LGPD art 5 II"
        timestamptz created_at
        timestamptz updated_at
    }

    RESTRICOES_ALIMENTARES {
        uuid user_id PK_FK "-> auth.users.id, on delete cascade"
        text_array restricoes "default '{}', texto livre — tratado como sensivel"
        timestamptz created_at
        timestamptz updated_at
    }

    GOALS {
        uuid id PK "default gen_random_uuid()"
        uuid user_id FK "-> auth.users.id, on delete cascade, indexado"
        numeric peso_inicial_kg "CHECK 20..400"
        numeric peso_meta_kg "CHECK 20..400"
        date prazo_data "data alvo, not null"
        text status "CHECK ativa|concluida|cancelada|expirada, default ativa"
        timestamptz created_at
        timestamptz updated_at
    }

    PESAGENS {
        uuid id PK "default gen_random_uuid()"
        uuid user_id FK "-> auth.users.id, on delete cascade, indice composto"
        numeric peso_kg "CHECK 20..400"
        timestamptz registrada_em "CHECK <= now(), quando a pesagem foi feita (distinto de created_at)"
        timestamptz created_at
        timestamptz updated_at
    }
```

Nota sobre a notação acima: `USERS` é `auth.users` (schema gerenciado pelo
Supabase Auth, fora do controle deste repo — listado aqui só pra mostrar a
relação). Todas as demais tabelas vivem no schema `public`.

## Tabelas e colunas

### `public.profiles`

Extensão 1:1 de `auth.users`. Auto-criada no signup via trigger
`on_auth_user_created` (`handle_new_user`, `SECURITY DEFINER`). Guarda
apenas atributos **não-sensíveis** de perfil — dado de saúde vive em tabelas
separadas (ver abaixo).

| Coluna            | Tipo          | Constraint                                                              | Nota LGPD |
|-------------------|---------------|--------------------------------------------------------------------------|-----------|
| `id`                     | `uuid`        | PK, FK `auth.users(id)` ON DELETE CASCADE                                | — |
| `sexo`                   | `text`        | CHECK IN (`masculino`, `feminino`, `outro`, `prefiro_nao_informar`), nullable | Dado pessoal comum; não é atributo médico. |
| `data_nascimento`        | `date`        | CHECK entre `1900-01-01` e hoje, nullable                                 | Usado só pra derivar idade sob demanda; idade nunca é armazenada calculada. |
| `altura_cm`              | `integer`     | CHECK entre 50 e 250, nullable                                            | — |
| `nivel_atividade`        | `text`        | CHECK IN (`sedentario`,`leve`,`moderado`,`intenso`,`muito_intenso`), nullable | Usado no cálculo de TDEE. |
| `peso_inicial_kg`        | `numeric(5,2)`| CHECK entre 20 e 400, nullable                                            | Dado de saúde indireto (peso corporal); acessível só via RLS do próprio usuário. |
| `aceite_termos_em`       | `timestamptz` | **NULLABLE no banco** (obrigatório só a nível de aplicação — ver nota abaixo) | Timestamp do consentimento aos Termos/Privacidade — obrigatório de produto/LGPD, mas não pode ser NOT NULL no Postgres sem quebrar o signup atual. |
| `aceite_data_sharing_ia` | `boolean`     | NOT NULL, default `false`                                                 | Opt-in explícito pra compartilhar dado anonimizado com o wrapper de IA (Grok). |
| `created_at`             | `timestamptz` | NOT NULL, default `now()`                                                | — |
| `updated_at`             | `timestamptz` | NOT NULL, default `now()`, mantido por trigger                           | — |

RLS: `select_own_profiles`, `insert_own_profiles`, `update_own_profiles`,
`delete_own_profiles` — todas com `auth.uid() = id`. Colunas novas herdam
essas mesmas policies (RLS é por linha, não por coluna); nenhuma policy
nova foi necessária nesta migration.

> Nota de migration ([`20260717090000_profiles_add_atividade_consentimento.sql`](../supabase/migrations/20260717090000_profiles_add_atividade_consentimento.sql)):
> `restricoes_alimentares` e `condicoes_medicas` **não** foram adicionadas
> como colunas desta tabela (conforme chegou a ser solicitado numa spec),
> por contrariar a regra não-negociável de isolar dado sensível de saúde em
> tabela própria (ver `condicoes_saude` e `restricoes_alimentares` abaixo).
> `sexo` também não foi renomeado para o par `M`/`F`/`outro` solicitado —
> os valores atuais já são um superconjunto semântico. Adicionalmente,
> `aceite_termos_em` foi pedido como NOT NULL, mas isso foi **testado
> localmente e revertido**: a trigger `handle_new_user()` (que auto-cria
> `profiles(id)` no signup) passa a falhar contra um NOT NULL sem default,
> quebrando a criação de conta inteira. A coluna ficou NULLABLE;
> consentimento obrigatório é enforced pela aplicação. Todos os três
> desvios foram sinalizados de volta pro `product-spec`.

### `public.condicoes_saude`

**Dado sensível (LGPD art. 5º, II)** — condições médicas relevantes (ex.:
diabetes, hipertensão). Isolado de `profiles` numa tabela própria pra
garantir "deletar conta = deletar limpo" e permitir tratamento diferenciado
no futuro (criptografia extra, retenção, auditoria) sem tocar no restante
do perfil.

| Coluna       | Tipo          | Constraint                                                    | Nota LGPD |
|--------------|---------------|-----------------------------------------------------------------|-----------|
| `user_id`    | `uuid`        | PK, FK `auth.users(id)` ON DELETE CASCADE                        | Chave de um dado de saúde — nunca exposto sem RLS. |
| `condicoes`  | `text[]`      | NOT NULL, default `'{}'`                                          | **SENSÍVEL.** Texto livre informado pelo usuário. |
| `esta_gestante` | `boolean`  | NOT NULL, default `false`                                         | **SENSÍVEL (LGPD art. 5º, II).** Indica gestação atual, autodeclarada. Usada pela elegibilidade do cálculo de IMC (`specs/2026-07-17-calculo-imc.md`). |
| `created_at` | `timestamptz` | NOT NULL, default `now()`                                        | — |
| `updated_at` | `timestamptz` | NOT NULL, default `now()`, mantido por trigger                   | — |

RLS: `select_own_condicoes_saude`, `insert_own_condicoes_saude`,
`update_own_condicoes_saude`, `delete_own_condicoes_saude` — todas com
`auth.uid() = user_id`. `esta_gestante` não precisou de policy nova (RLS é
por linha, não por coluna) — ver
[`20260717130000_condicoes_saude_add_gestante.sql`](../supabase/migrations/20260717130000_condicoes_saude_add_gestante.sql).

> Nota de migration ([`20260717130000_condicoes_saude_add_gestante.sql`](../supabase/migrations/20260717130000_condicoes_saude_add_gestante.sql)):
> o spec de IMC sugeriu `condicoes_saude` como local de `esta_gestante`, mas
> pediu confirmação de que a tabela é 1:1 por usuário antes de assumir que
> uma coluna boolean encaixa (a preocupação era: se fosse "uma linha por
> condição", um boolean solto não faria sentido). Investigação confirmou
> que `condicoes_saude` tem `user_id` como **primary key** — 1 linha por
> usuário, com a lista de condições já vivendo dentro dessa única linha na
> coluna `condicoes text[]`. Não há conflito estrutural: `esta_gestante`
> é uma coluna escalar adicional na mesma linha, mesmo padrão já usado em
> `profiles.aceite_data_sharing_ia`. Confirmado o local sugerido pelo spec,
> por já ter RLS própria, FK `ON DELETE CASCADE` própria, e por ser a
> classe correta de sensibilidade (dado de saúde LGPD art. 5º, II) — sem
> necessidade de criar tabela dedicada só para 1 boolean.

### `public.restricoes_alimentares`

Restrições/alergias alimentares (ex.: vegetariano, sem lactose, alergia a
amendoim). Tratado como dado sensível (alergia pode revelar condição de
saúde, ex. doença celíaca) e isolado em tabela própria pelo mesmo motivo de
`condicoes_saude`.

| Coluna       | Tipo          | Constraint                                                  | Nota LGPD |
|--------------|---------------|-----------------------------------------------------------------|-----------|
| `user_id`    | `uuid`        | PK, FK `auth.users(id)` ON DELETE CASCADE                        | — |
| `restricoes` | `text[]`      | NOT NULL, default `'{}'`                                          | **Tratado como sensível.** Texto livre informado pelo usuário. |
| `created_at` | `timestamptz` | NOT NULL, default `now()`                                        | — |
| `updated_at` | `timestamptz` | NOT NULL, default `now()`, mantido por trigger                   | — |

RLS: `select_own_restricoes_alimentares`,
`insert_own_restricoes_alimentares`, `update_own_restricoes_alimentares`,
`delete_own_restricoes_alimentares` — todas com `auth.uid() = user_id`.

### `public.goals`

Metas de emagrecimento. Modelada como **histórico** (múltiplas linhas por
usuário) com apenas uma meta `ativa` por vez, garantido por unique index
parcial (não só por lógica de aplicação).

| Coluna            | Tipo            | Constraint                                                                 | Nota LGPD |
|-------------------|-----------------|-------------------------------------------------------------------------------|-----------|
| `id`              | `uuid`          | PK, default `gen_random_uuid()`                                                | — |
| `user_id`         | `uuid`          | NOT NULL, FK `auth.users(id)` ON DELETE CASCADE, índice `idx_goals_user_id`    | — |
| `peso_inicial_kg` | `numeric(5,2)`  | NOT NULL, CHECK entre 20 e 400                                                 | Dado de saúde indireto (peso corporal); acessível só via RLS do próprio usuário. |
| `peso_meta_kg`    | `numeric(5,2)`  | NOT NULL, CHECK entre 20 e 400                                                 | Idem acima. |
| `prazo_data`      | `date`          | NOT NULL — data alvo, não duração                                              | — |
| `status`          | `text`          | NOT NULL, default `'ativa'`, CHECK IN (`ativa`,`concluida`,`cancelada`,`expirada`) | — |
| `created_at`      | `timestamptz`   | NOT NULL, default `now()`                                                      | — |
| `updated_at`      | `timestamptz`   | NOT NULL, default `now()`, mantido por trigger                                 | — |

Índice único parcial: `goals_unique_active_per_user` em `(user_id) WHERE
status = 'ativa'` — impede duas metas ativas simultâneas pro mesmo usuário.

RLS: `select_own_goals`, `insert_own_goals`, `update_own_goals`,
`delete_own_goals` — todas com `auth.uid() = user_id`.

> Nota de spec: uma solicitação recebida em 2026-07-17 pedia `goals` com
> colunas `prazo_semanas` (int) e `ativa` (bool) em vez de `prazo_data` e
> `status`. Como a tabela já cumpre a mesma necessidade funcional (uma meta
> ativa por vez, histórico completo) com um desenho já justificado e em uso,
> a mudança de nome/tipo **não** foi aplicada unilateralmente — sinalizada
> de volta pro `product-spec` pra confirmação antes de qualquer rename.

### `public.pesagens`

Histórico de pesagens do usuário (peso + data/hora em que a pesagem foi
feita). Modelada como **histórico** (múltiplas linhas por usuário, nunca
sobrescrito) — mesmo padrão de `goals`: uma nova pesagem é sempre um
`INSERT`; edição corrige a linha específica, exclusão remove a linha
específica; "peso mais recente" é sempre derivado por
`ORDER BY registrada_em DESC LIMIT 1`, nunca por uma flag armazenada.
Consumida pelo módulo de IMC (`specs/2026-07-17-calculo-imc.md`) em
substituição a `profiles.peso_inicial_kg` (que continua existindo como
baseline do onboarding, mas deixou de alimentar o cálculo de IMC).

| Coluna          | Tipo            | Constraint                                                              | Nota LGPD |
|-----------------|-----------------|----------------------------------------------------------------------------|-----------|
| `id`            | `uuid`          | PK, default `gen_random_uuid()`                                            | — |
| `user_id`       | `uuid`          | NOT NULL, FK `auth.users(id)` ON DELETE CASCADE                             | — |
| `peso_kg`       | `numeric(5,2)`  | NOT NULL, CHECK entre 20 e 400                                              | Dado de saúde indireto (peso corporal); acessível só via RLS do próprio usuário. |
| `registrada_em` | `timestamptz`   | NOT NULL, default `now()`, CHECK `<= now()`                                | Quando a pesagem foi feita (informado pelo usuário, pode ser retroativo). Distinto de `created_at`. |
| `created_at`    | `timestamptz`   | NOT NULL, default `now()`                                                  | — |
| `updated_at`    | `timestamptz`   | NOT NULL, default `now()`, mantido por trigger                             | — |

Índice `idx_pesagens_user_id_registrada_em` em `(user_id, registrada_em
desc)` — suporta tanto a listagem de histórico por usuário quanto a query
de "pesagem mais recente" (`WHERE user_id = $1 ORDER BY registrada_em DESC
LIMIT 1`) via index scan puro, sem sort adicional (confirmado localmente
via `EXPLAIN`). Não há índice isolado em `(user_id)`: como `user_id` é a
coluna líder do índice composto, ele já cobre queries que filtram só por
usuário.

RLS: `select_own_pesagens`, `insert_own_pesagens`, `update_own_pesagens`,
`delete_own_pesagens` — todas com `auth.uid() = user_id`.

## Funções e triggers auxiliares

- `public.set_updated_at()` — trigger `BEFORE UPDATE` que seta `updated_at
  = now()`. Aplicada em `profiles`, `condicoes_saude`,
  `restricoes_alimentares`, `goals` e `pesagens`.
- `public.handle_new_user()` (`SECURITY DEFINER`) + trigger
  `on_auth_user_created` em `auth.users` — cria automaticamente a linha de
  `profiles` (só com `id`) no signup. Único ponto desta migration que
  contorna RLS, e só nesse contexto controlado (nunca chamado pela
  aplicação diretamente).

## Storage

Ainda não provisionado nesta migration. Buckets `progress-photos` e
`reports` (privados, policy por prefixo `<user_id>/`, URL assinada ≤ 15min)
serão adicionados em migration própria quando a feature de fotos/relatórios
for especificada.
