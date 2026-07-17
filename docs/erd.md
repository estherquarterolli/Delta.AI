# ERD — Schema do banco (Supabase Postgres)

Dono: `supabase-architect`. Atualizado a cada migration que altera schema.

Migration de origem deste diagrama: [`supabase/migrations/20260716000000_init_profiles_goals.sql`](../supabase/migrations/20260716000000_init_profiles_goals.sql).

## Diagrama

```mermaid
erDiagram
    USERS ||--o| PROFILES : "1:1 (id = id)"
    USERS ||--o| CONDICOES_SAUDE : "1:1 (id = user_id)"
    USERS ||--o| RESTRICOES_ALIMENTARES : "1:1 (id = user_id)"
    USERS ||--o{ GOALS : "1:N (id = user_id)"

    USERS {
        uuid id PK
        text email "gerenciado pelo Supabase Auth"
    }

    PROFILES {
        uuid id PK_FK "-> auth.users.id, on delete cascade"
        text sexo "CHECK: masculino|feminino|outro|prefiro_nao_informar"
        date data_nascimento "nullable, sanity range 1900-01-01..hoje"
        int altura_cm "nullable, CHECK 50..250"
        timestamptz created_at
        timestamptz updated_at
    }

    CONDICOES_SAUDE {
        uuid user_id PK_FK "-> auth.users.id, on delete cascade"
        text_array condicoes "default '{}', texto livre — SENSIVEL LGPD art 5 II"
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
| `id`              | `uuid`        | PK, FK `auth.users(id)` ON DELETE CASCADE                                | — |
| `sexo`            | `text`        | CHECK IN (`masculino`, `feminino`, `outro`, `prefiro_nao_informar`), nullable | Dado pessoal comum; não é atributo médico. |
| `data_nascimento` | `date`        | CHECK entre `1900-01-01` e hoje, nullable                                 | Usado só pra derivar idade sob demanda; idade nunca é armazenada calculada. |
| `altura_cm`       | `integer`     | CHECK entre 50 e 250, nullable                                            | — |
| `created_at`      | `timestamptz` | NOT NULL, default `now()`                                                | — |
| `updated_at`      | `timestamptz` | NOT NULL, default `now()`, mantido por trigger                           | — |

RLS: `select_own_profiles`, `insert_own_profiles`, `update_own_profiles`,
`delete_own_profiles` — todas com `auth.uid() = id`.

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
| `created_at` | `timestamptz` | NOT NULL, default `now()`                                        | — |
| `updated_at` | `timestamptz` | NOT NULL, default `now()`, mantido por trigger                   | — |

RLS: `select_own_condicoes_saude`, `insert_own_condicoes_saude`,
`update_own_condicoes_saude`, `delete_own_condicoes_saude` — todas com
`auth.uid() = user_id`.

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

## Funções e triggers auxiliares

- `public.set_updated_at()` — trigger `BEFORE UPDATE` que seta `updated_at
  = now()`. Aplicada em `profiles`, `condicoes_saude`,
  `restricoes_alimentares` e `goals`.
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
