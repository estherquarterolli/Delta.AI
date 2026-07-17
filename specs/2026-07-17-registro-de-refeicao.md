# Registro de Refeição (Nutrição)

**Status**: DRAFT — bloqueado em 1 ponto genuinamente dependente do product
owner (origem do dataset TACO, ver "Questões abertas"). Todo o resto desta
spec não está bloqueado: tem um default proposto suficiente para
`supabase-architect` e `backend-engineer` começarem o trabalho.

## Contexto

O app hoje não tem nenhum jeito do usuário registrar o que comeu. Pra
sustentar o objetivo central do produto (emagrecimento), é preciso um
registro alimentar básico: o usuário busca um alimento, informa a
quantidade, e o app soma calorias/macros do dia e compara com uma meta. A
meta calórica *real* (calculada a partir de perfil/objetivo/TDEE) é uma
feature própria, ainda não especificada — nesta spec ela é um valor
mockado fixo, isolado num único ponto do código, para que a troca futura
pela meta real seja uma substituição trivial (ver "Meta calórica —
mock isolado").

## User story

Como usuária/usuário autenticado, quero registrar o que comi (alimento +
quantidade) e ver o total de calorias e macros do meu dia comparado com uma
meta, para acompanhar minha alimentação diária sem precisar calcular nada
manualmente.

## Investigação do estado atual do banco e do repositório

Verificado antes de escrever esta spec:

- `supabase/migrations/`: existem `profiles`, `condicoes_saude`,
  `restricoes_alimentares`, `goals`, `pesagens` (ver `docs/erd.md`). **Não
  existe** nenhuma tabela de alimentos, refeições, nutrição ou qualquer
  coisa relacionada a TACO. Esta é a primeira migration do domínio de
  nutrição.
- `app/modules/README.md` já **prevê** o domínio `nutricao/` ("refeições,
  alimentos, registro alimentar") na lista de domínios planejados, mas o
  diretório `app/modules/nutricao/` **não existe** ainda — é só a entrada
  no README, sem código.
- Busquei no repositório inteiro (`supabase/`, `app/`, `docs/`, raiz) por
  qualquer arquivo de dataset TACO (`*.csv`, `*.json`, `*taco*`) — **nenhum
  arquivo-fonte da TACO existe no repo hoje**. A única menção a "TACO" no
  código é um comentário de migration (`20260716000000_init_profiles_goals.sql`,
  seção `restricoes_alimentares`) especulando que um "motor de
  receitas/alimentos da TACO/Open Food Facts" poderia vir no futuro — não é
  um dado, é uma nota de intenção. Isso confirma que a importação da TACO é
  trabalho novo, não algo já resolvido em outro lugar do projeto (ver
  "Questões abertas").
- Padrão de módulo de referência a seguir: `app/modules/perfil/` (IMC) e o
  módulo de `pesagens` que ele consome — router + schemas Pydantic +
  `service.py` (orquestração) + `repository.py` (acesso a dados via RLS,
  nunca `service_role`). Esta spec segue a mesma divisão de
  responsabilidade.

## Objetivo e escopo

**Dentro do escopo:**
- Tabela de referência `alimentos` (base TACO, ou um subconjunto dela —
  ver "Questões abertas") com valores nutricionais por 100g.
- Tabela `refeicoes` — um item de comida registrado pelo usuário
  (alimento + quantidade + horário).
- `POST /nutricao/refeicoes` — registrar um item consumido.
- `GET /nutricao/hoje` — refeições do dia + totais agregados + comparação
  com a meta calórica (mockada, 2000 kcal).
- `GET /nutricao/alimentos/busca?q=...` — busca textual de alimento na
  base de referência.
- Tela de registro (busca de alimento + input de quantidade) e card de
  resumo do dia no frontend.
- RLS em `refeicoes` (own-row). Postura de leitura em `alimentos`
  (tabela de referência compartilhada, ver seção dedicada).
- Testes dos três endpoints e da fórmula de agregação de calorias/macros.

**Fora de escopo** — ver seção dedicada mais abaixo.

## Modelo de dados proposto (para confirmação do `supabase-architect`)

> Como nos specs anteriores, `product-spec` não decide SQL final — a
> proposta abaixo é o requisito funcional. Nomes de tabela, tipos exatos,
> índices e a extensão `unaccent` (ver busca) ficam a critério do
> `supabase-architect`, desde que o contrato funcional seja atendido.

### Tabela `alimentos` — dado de referência, NÃO user-scoped

**Decisão explícita, diferente de todas as tabelas existentes no
projeto**: `alimentos` é uma base de dados **compartilhada** — todos os
usuários leem exatamente a mesma tabela, não há `user_id`, e ninguém
insere/edita/exclui um alimento pelo app (a base é importada uma vez, via
seed/migration/script, não pelo usuário final). Isso é categoricamente
diferente do padrão "own-row com 4 policies" usado em `profiles`,
`condicoes_saude`, `restricoes_alimentares`, `goals` e `pesagens` — não há
"linha do próprio usuário" aqui, porque a linha não pertence a usuário
nenhum.

Implicação de RLS (a confirmar com `supabase-architect`, mas o
enquadramento é este): `alimentos` deve ter RLS **habilitada** (regra do
projeto: "toda tabela tem RLS", CLAUDE.md) mas com uma policy de
**leitura pública para o papel `authenticated`** (não `anon` — todas as
rotas deste app exigem login, mesmo padrão dos demais endpoints), e
**nenhuma policy de insert/update/delete para `authenticated`** — só quem
roda a migration/script de import (via conexão administrativa, fora da
aplicação) pode escrever. Isso não é o mesmo que usar `service_role` em
runtime da aplicação (proibido pelo CLAUDE.md fora de cron job com ADR) —
é escrita feita uma vez, fora do caminho de requisição normal, igual a
qualquer outra migration/seed do projeto.

**Colunas mínimas necessárias para esta feature** (nomes exatos a
critério do `supabase-architect`):
- `id` — identificador do alimento.
- `nome` — nome do alimento como aparece na TACO (ex.: "Arroz, integral,
  cozido"). É o campo buscado por `GET /nutricao/alimentos/busca`.
- `kcal_100g` — calorias por 100g.
- `proteina_g_100g` — proteína (g) por 100g.
- `carboidrato_g_100g` — carboidrato (g) por 100g.
- `gordura_g_100g` — gordura (g) por 100g.

Colunas adicionais que a TACO também fornece (ex.: fibra, sódio, cálcio,
categoria/grupo alimentar) **não são exigidas por esta spec** — podem ser
adicionadas depois sem quebrar nada (migration aditiva), mas não bloqueiam
esta entrega, já que o fluxo pedido (soma de calorias e macros básicos)
não depende delas.

### Tabela `refeicoes` — user-scoped, mesmo padrão de `pesagens`

**Decisão de modelagem — 1 linha = 1 item de comida consumido, não uma
refeição composta**: uma linha em `refeicoes` representa **um alimento**
com uma quantidade e um horário (ex.: "150g de arroz integral cozido às
12:30"). "O dia" (o que `GET /nutricao/hoje` mostra) é a agregação de
todas as linhas do usuário naquela data — não existe um agrupador
intermediário "café da manhã"/"almoço"/"jantar" nesta versão.

Justificativa: é o modelo mais simples que atende exatamente o fluxo
pedido pelo product owner ("usuário registra o que comeu, o app soma
calorias e macros do dia") sem introduzir uma segunda entidade
(refeição-agrupador com N itens) que a solicitação não pediu e que
adicionaria uma tela e um fluxo de criação extra (criar a refeição, depois
adicionar itens a ela) sem benefício claro pro MVP. Agrupar por
"café/almoço/janta" na UI é puramente cosmético e pode ser feito depois
com uma coluna opcional (`tipo_refeicao`, nullable) numa migration
aditiva, sem alterar o modelo de agregação — fica registrado como
possível evolução em "Fora de escopo", não como decisão travada.

**Colunas sugeridas**:
- `id` — identificador do registro.
- `user_id` — FK `auth.users(id)` `ON DELETE CASCADE`, mesmo padrão de
  `pesagens`/`goals`.
- `alimento_id` — FK `alimentos(id)`. Sem `ON DELETE CASCADE` no sentido
  de apagar refeições do usuário se um alimento de referência for
  removido — recomendação: `ON DELETE RESTRICT` (a base TACO não deveria
  perder linhas depois que usuários já as referenciaram; se um alimento
  precisar ser corrigido, é `UPDATE`, não `DELETE`+`INSERT`). Decisão
  final de constraint a cargo do `supabase-architect`.
- `quantidade_g` — `numeric`, quantidade consumida em **gramas** (ver
  "Unidades e agregação" abaixo). Proposta de `CHECK` de sanidade: entre
  `1` e `5000` (5kg de um único item é uma folga generosa acima de
  qualquer porção realista, mesmo padrão de "barra erro grosseiro de
  digitação" já usado em `peso_kg`/`altura_cm`).
- `consumida_em` — timestamp de **quando o alimento foi consumido**
  (informado pelo usuário, pode ser retroativo — "esqueci de registrar o
  almoço"), distinto de `created_at`. Mesmo padrão exato de
  `pesagens.registrada_em`: default `now()`, `CHECK (consumida_em <=
  now())` no banco além da validação `422` de aplicação.
- `created_at` / `updated_at` — padrão do projeto (trigger
  `set_updated_at`).

**RLS**: own-row, mesmo padrão de `pesagens` — `select/insert/update/delete`
com `auth.uid() = user_id`. Sem `service_role`.

**Índice sugerido**: `(user_id, consumida_em desc)` — mesmo raciocínio do
índice de `pesagens`: cobre tanto "refeições de hoje do usuário" (filtro
por `user_id` + faixa de data) quanto ordenação cronológica, sem sort
adicional. Índice adicional em `alimento_id` se o `supabase-architect`
julgar necessário para joins (`refeicoes` → `alimentos` ao montar a
resposta com nome do alimento).

## Unidades e agregação

**Decisão — quantidade em gramas, não em porções.** A TACO fornece
valores por 100g; pedir "porções" ao usuário exigiria uma tabela adicional
de "tamanho de porção por alimento" (que a TACO não padroniza de forma
uniforme) e uma camada de conversão porção→grama antes de qualquer cálculo
— complexidade que o fluxo pedido não justifica no MVP. Gramas é a unidade
nativa da fonte de dados e a mais direta de validar/testar.

**Fórmula de agregação (explícita, testável)** — para cada refeição
`r` do usuário no dia:

```
kcal(r)         = alimento.kcal_100g          * r.quantidade_g / 100
proteina_g(r)   = alimento.proteina_g_100g    * r.quantidade_g / 100
carboidrato_g(r)= alimento.carboidrato_g_100g * r.quantidade_g / 100
gordura_g(r)    = alimento.gordura_g_100g     * r.quantidade_g / 100
```

E os totais do dia são a soma sobre todas as refeições `r` do usuário
com `consumida_em` na data do dia:

```
total_kcal_dia          = Σ kcal(r)
total_proteina_g_dia    = Σ proteina_g(r)
total_carboidrato_g_dia = Σ carboidrato_g(r)
total_gordura_g_dia     = Σ gordura_g(r)
```

Arredondamento: valores por item e totais do dia arredondados para **1
casa decimal** na resposta da API (mesmo padrão do IMC), sem arredondar
intermediariamente durante a soma (soma os valores em precisão total,
arredonda só no output).

## O que é "hoje" — fuso horário

**Decisão**: diferente do cálculo de idade do IMC (que usa data UTC do
servidor sem problema, porque erro de fuso ali só importaria num raro
"virou o dia" perto do aniversário), aqui o fuso **importa**: o produto é
100% mercado brasileiro, e UTC está 3h adiante de `America/Sao_Paulo`
(BRT/BRST). Sem ajuste, uma refeição registrada às 21h–23h59 (horário de
Brasília) apareceria como "de ontem" ou "de hoje" de forma inconsistente
com a percepção do próprio usuário, contaminando a comparação com a meta
diária logo na primeira janela de uso comum (jantar).

**Default proposto**: `"hoje"` em `GET /nutricao/hoje` é calculado no
servidor convertendo o timestamp atual (e o de cada `consumida_em`) para
`America/Sao_Paulo` antes de derivar a data civil, não usando a data UTC
diretamente. Não é configurável por usuário nesta versão (o app não tem
suporte a fuso horário customizado — mercado único, decisão aceitável pro
MVP). Isso é implementado na camada de service (Python), sem exigir
mudança de tipo de coluna no banco (`consumida_em` continua `timestamptz`,
que já guarda o instante absoluto — a conversão de fuso é só na leitura).

## Meta calórica — mock isolado

**Decisão explícita pedida pelo product owner**: a meta calórica real
(TDEE, objetivo de emagrecimento, etc.) é de **outra feature, ainda não
especificada**. Nesta spec, a meta é um valor fixo mockado de **2000
kcal**.

Para que a substituição futura seja trivial, a meta deve vir de **um
único ponto isolado no código** — proposta:
- Uma constante `META_KCAL_DIARIA_MOCK = 2000` em um módulo próprio (ex.:
  `app/modules/nutricao/metas.py`), com uma função
  `obter_meta_kcal_diaria(user) -> float` que hoje só retorna a constante,
  ignorando `user`.
- `GET /nutricao/hoje` chama essa função, nunca lê a constante direto —
  assim, quando a feature de meta real existir, só essa função muda de
  implementação (passa a consultar o módulo de metas real), e nada no
  endpoint de nutrição precisa ser tocado.
- A resposta do endpoint deve deixar claro que a meta é mockada nesta
  versão (ver contrato do endpoint, campo `meta_kcal_origem`), para que o
  frontend possa, se quiser, sinalizar isso ao usuário (opcional, decisão
  de UX de `frontend-engineer`) e para que não haja ambiguidade futura
  sobre por que o valor não reflete o perfil do usuário.

## Busca de alimentos (`GET /nutricao/alimentos/busca`)

- **Autenticação**: obrigatória (mesmo padrão de todas as rotas do
  backend) — alimento em si não é dado sensível do usuário, mas a rota não
  fica pública porque nenhuma rota do produto é pública hoje, e não há
  necessidade de abrir exceção.
- **Mínimo de caracteres**: `q` com menos de 2 caracteres é rejeitado com
  `422` (evita varredura de tabela inteira por engano/vazio e resultados
  sem utilidade prática).
- **Limite de resultados**: `20` por request, sem paginação nesta versão
  (a lista de alimentos que combinam com um termo de busca curto raramente
  passa disso de forma útil; se passar, o usuário refina o termo).
- **Case-insensitive**: nativo de `ILIKE`, sem decisão adicional
  necessária.
- **Acento-insensitive**: nomes da TACO têm acento (ex.: "Feijão",
  "Mão-de-vaca") e o usuário digitando num teclado de celular frequentemente
  omite acentos. Proposta: habilitar a extensão `unaccent` do Postgres
  (disponível no Supabase gerenciado, mesmo padrão de `pgcrypto` já
  habilitado em `20260716000000_init_profiles_goals.sql`) e comparar
  `unaccent(nome) ilike unaccent('%' || q || '%')`, opcionalmente com um
  índice funcional/trigram se a performance exigir (decisão de índice a
  cargo do `supabase-architect`; com ~600 linhas de TACO isso é
  irrelevante em volume, mas o padrão de comparação acento-insensível
  importa desde já para a experiência de busca).
- Sem resultados → `200` com lista vazia, nunca erro.

## Critérios de aceitação

- [ ] Usuário autenticado consegue registrar uma refeição (`alimento_id`,
      `quantidade_g`, `consumida_em` opcional — default "agora" se
      omitido) e recebe o registro criado de volta, incluindo o
      `kcal`/macros calculados para aquele item.
- [ ] `quantidade_g` fora da faixa 1–5000 é rejeitado com `422` antes de
      tocar o banco.
- [ ] `consumida_em` no futuro é rejeitado com `422`.
- [ ] `alimento_id` inexistente é rejeitado com `422`/`404` (a definir o
      código exato com `backend-engineer`; nunca cria a linha nem
      levanta `500`).
- [ ] `GET /nutricao/hoje` retorna a lista de refeições do dia (fuso
      `America/Sao_Paulo`), os totais agregados de kcal e dos três
      macros, a meta mockada (`2000`) e o saldo (quanto falta ou quanto
      excedeu), calculados pela fórmula explícita definida em "Unidades e
      agregação" — coberto por teste unitário de agregação com valores
      conhecidos.
- [ ] Usuário sem nenhuma refeição registrada no dia recebe `200` com
      lista vazia e totais zerados (nunca erro).
- [ ] `GET /nutricao/alimentos/busca?q=...` com `q` de 1 caractere ou
      vazio recebe `422`.
- [ ] Busca por termo sem acento encontra alimento cujo nome tem acento
      na base (ex.: buscar `"feijao"` encontra `"Feijão"`) — coberto por
      teste de integração.
- [ ] Busca retorna no máximo 20 resultados.
- [ ] Usuário autenticado só vê, edita ou exclui as próprias refeições —
      nunca de outro usuário (RLS + teste de integração com dois
      usuários).
- [ ] Todos os usuários autenticados conseguem ler a base `alimentos`
      (mesmos dados para todos) e **nenhum** usuário autenticado
      consegue inserir/editar/excluir um alimento via API (só a
      migration/seed consegue escrever) — coberto por teste de
      integração de RLS negativo.
- [ ] Requisição sem token de autenticação válido recebe `401` em todas
      as rotas deste módulo, incluindo a busca de alimentos.
- [ ] Trocar a origem da meta calórica (de mock para cálculo real) é
      possível alterando **apenas** a implementação de
      `obter_meta_kcal_diaria`, sem qualquer mudança no endpoint
      `GET /nutricao/hoje` ou na fórmula de agregação — validado por um
      teste que substitui a função mockada por um double e confirma que
      o endpoint reflete o novo valor sem alteração de código do
      endpoint.

## Contrato dos endpoints

### `POST /nutricao/refeicoes`

**Autenticação**: obrigatória.

**Request**:
```json
{
  "alimento_id": "uuid-do-alimento",
  "quantidade_g": 150,
  "consumida_em": "2026-07-17T12:30:00Z"
}
```
`consumida_em` é opcional (default: agora).

**Response 201 Created**:
```json
{
  "id": "uuid-da-refeicao",
  "alimento_id": "uuid-do-alimento",
  "alimento_nome": "Arroz, integral, cozido",
  "quantidade_g": 150,
  "consumida_em": "2026-07-17T12:30:00Z",
  "kcal": 224.5,
  "proteina_g": 4.7,
  "carboidrato_g": 46.7,
  "gordura_g": 1.8
}
```

**Response 422** — `quantidade_g` fora de faixa, `consumida_em` no
futuro, ou `alimento_id` que não existe na base. Corpo com `erro` e
`mensagem`, mesmo padrão dos outros endpoints do projeto.

**Response 401** — token ausente/inválido/expirado.

### `GET /nutricao/hoje`

**Autenticação**: obrigatória. Sem query params (data é sempre "hoje" no
fuso `America/Sao_Paulo`, calculada no servidor — ver seção dedicada;
sem suporte a consultar outro dia nesta versão).

**Response 200 OK**:
```json
{
  "data": "2026-07-17",
  "refeicoes": [
    {
      "id": "uuid-da-refeicao",
      "alimento_id": "uuid-do-alimento",
      "alimento_nome": "Arroz, integral, cozido",
      "quantidade_g": 150,
      "consumida_em": "2026-07-17T12:30:00Z",
      "kcal": 224.5,
      "proteina_g": 4.7,
      "carboidrato_g": 46.7,
      "gordura_g": 1.8
    }
  ],
  "totais": {
    "kcal": 224.5,
    "proteina_g": 4.7,
    "carboidrato_g": 46.7,
    "gordura_g": 1.8
  },
  "meta_kcal": 2000,
  "meta_kcal_origem": "mock_fixo",
  "kcal_restante": 1775.5,
  "excedeu_meta": false
}
```
- `meta_kcal_origem` é sempre `"mock_fixo"` nesta versão — campo existe
  desde já para não exigir mudança de contrato quando a meta real
  existir (nesse momento passará a `"calculada"` ou equivalente).
- `kcal_restante` = `meta_kcal - totais.kcal` (pode ser negativo).
- `excedeu_meta` = `totais.kcal > meta_kcal`.

**Response 401** — token ausente/inválido/expirado.

### `GET /nutricao/alimentos/busca?q=...`

**Autenticação**: obrigatória.

**Request**: query param `q` (string, mínimo 2 caracteres).

**Response 200 OK**:
```json
{
  "resultados": [
    {
      "id": "uuid-do-alimento",
      "nome": "Arroz, integral, cozido",
      "kcal_100g": 124,
      "proteina_g_100g": 2.6,
      "carboidrato_g_100g": 25.8,
      "gordura_g_100g": 1.0
    }
  ]
}
```
Máximo 20 itens em `resultados`. Lista vazia se nada combinar.

**Response 422** — `q` ausente ou com menos de 2 caracteres.

**Response 401** — token ausente/inválido/expirado.

## Edge cases e comportamento de erro

| Cenário | Camada | Comportamento esperado |
|---|---|---|
| `quantidade_g` fora de 1–5000 | endpoint | `422` |
| `consumida_em` no futuro | endpoint | `422` |
| `alimento_id` não existe | endpoint | `422`/`404` (definir código exato com `backend-engineer`), sem tocar o banco além da checagem |
| `q` com 0–1 caractere | endpoint | `422` |
| Busca sem resultado | endpoint | `200`, `resultados: []` |
| `GET /nutricao/hoje` sem nenhuma refeição no dia | endpoint | `200`, `refeicoes: []`, totais zerados, `kcal_restante = meta_kcal` |
| Refeição registrada exatamente à meia-noite BRT (fronteira do dia) | service | Contabilizada no dia civil de `America/Sao_Paulo` correspondente ao instante, não no dia UTC |
| Usuário tenta editar/excluir refeição de outro usuário | RLS | Nenhuma linha afetada/retornada (RLS bloqueia antes do banco responder) — não é `403` explícito, é ausência de linha, mesmo padrão de `pesagens` |
| Sem token de auth | endpoint | `401` em qualquer uma das três rotas |
| Tentativa de insert/update/delete em `alimentos` por usuário comum | RLS | Bloqueado pela policy (sem policy de escrita para `authenticated`) |

## Fluxo de dados

- **Entrada**: `alimento_id` (escolhido a partir da busca), `quantidade_g`
  e, opcionalmente, `consumida_em`, informados pelo usuário autenticado.
  Termo de busca `q` para consultar `alimentos`.
- **Processamento**: validação de faixa/data; busca do alimento
  referenciado para os valores por 100g; cálculo de kcal/macros do item
  (fórmula explícita acima); ao consultar `GET /nutricao/hoje`, agregação
  de todas as refeições do usuário no dia civil `America/Sao_Paulo` e
  comparação com a meta mockada.
- **Saída**: JSON de resposta de cada endpoint (contratos acima),
  consumido pela tela de registro e pelo card de resumo do dia.
- **Persistência**: sim, em `public.refeicoes` (histórico completo,
  nunca sobrescrito — mesmo padrão de `pesagens`/`goals`: edição altera a
  linha específica, exclusão remove a linha específica). `alimentos` é
  persistência de referência, escrita fora do caminho da aplicação (seed/
  import), lida por todos.

## Impacto LGPD

- **Toca dados sensíveis?** Sim. Registro alimentar recorrente é dado
  comportamental de saúde indireto — mesma classificação já dada a peso
  (`pesagens`) no projeto, e possivelmente mais revelador ao longo do
  tempo: um histórico denso de "o que, quanto e quando alguém come" pode
  expor padrões (déficit extremo, restrição severa, compulsão) que
  interessam diretamente aos guardrails de TCA já previstos no CLAUDE.md
  para o chat — mesmo que esta spec não tenha chat, o dado bruto que uma
  feature futura de detecção consumiria nasce aqui. Nenhum dado desta
  feature é enviado ao Grok nesta spec (ver "Fora de escopo").
  `alimentos` (a base TACO em si) **não** é dado do usuário — é dado
  público de referência, sem nenhuma informação pessoal.
- **RLS necessária em tabela nova?**
  - `refeicoes`: sim, own-row completo (select/insert/update/delete,
    `auth.uid() = user_id`), mesmo padrão de `pesagens`. Sem exceção, sem
    `service_role`.
  - `alimentos`: RLS habilitada, mas com policy de **leitura pública para
    `authenticated`**, sem policies de escrita para esse papel — postura
    diferente das demais tabelas do projeto porque o dado não é
    user-scoped (ver seção dedicada acima). Este enquadramento deve ser
    confirmado explicitamente pelo `supabase-architect` antes de
    `READY_FOR_BUILD`, por ser o primeiro caso do projeto de tabela sem
    `user_id` e RLS não own-row.
- **Requer consentimento explícito adicional?** Não além do consentimento
  geral já dado nos Termos de Uso (`profiles.aceite_termos_em`) — registrar
  o que comeu é extensão direta e esperada da funcionalidade central do
  produto (acompanhamento de emagrecimento), mesma lógica já aplicada ao
  registro de peso.
- Exclusão de conta deve apagar `refeicoes` do usuário — `ON DELETE
  CASCADE` na FK garante isso automaticamente ("deletar conta = deletar
  limpo"). `alimentos` nunca é apagada por exclusão de conta (não
  pertence a usuário nenhum).
- **Checklist explícito para `security-reviewer`** (marcado como
  obrigatório pelo product owner):
  - Confirmar as 4 policies own-row em `refeicoes` e ausência de
    `service_role` no caminho de runtime.
  - Confirmar que `alimentos` não permite escrita via `authenticated` e
    não expõe nenhum dado de outro usuário (não deveria ter `user_id` de
    forma alguma — checar se isso se mantém no schema final).
  - Confirmar que nenhum campo desta feature (alimento, quantidade,
    horário, totais do dia) é passado ao wrapper Grok em qualquer fluxo
    existente ou futuro próximo (checagem de escopo, não de código
    existente, já que não há integração de IA nesta spec).

## Impacto de custo (MVP free)

- **Novas chamadas Grok?** Nenhuma.
- **Novo storage?** Nenhum (Supabase Storage não é usado — tabelas
  Postgres comuns, dentro do free tier do Supabase).
- **Novos emails?** Nenhum.
- Custo adicional: leituras de `alimentos` (busca com `ILIKE`/`unaccent`,
  ~600 linhas — irrelevante em volume) e agregação de `refeicoes` por dia
  (uma query com filtro por `user_id` + faixa de data, já suportada pelo
  índice sugerido). Nenhum custo de serviço pago novo.

## Fora de escopo

- Cálculo da meta calórica real (TDEE, objetivo de emagrecimento) — feature
  própria futura; esta spec só consome um mock isolado (ver "Meta calórica
  — mock isolado"). Trocar o mock pela meta real é dependência explícita
  desta spec para a feature futura, não o inverso.
- Refeição composta/agrupador (ex.: "café da manhã" contendo múltiplos
  itens) — modelo atual é 1 linha = 1 item consumido; agrupamento por
  `tipo_refeicao` fica como possível migration aditiva futura, sem
  necessidade de alterar o modelo de agregação já definido.
- Import completo do dataset TACO via script robusto e reexecutável —
  nesta versão, a origem exata dos dados de `alimentos` é uma questão
  aberta (ver abaixo); o *mecanismo* de import de longo prazo (script
  versionado, atualização de dataset) é trabalho a especificar depois que
  a fonte for confirmada.
- Edição/exclusão de um alimento da base de referência pelo usuário
  final (só é possível via processo administrativo/migration).
- Paginação da busca de alimentos (limite fixo de 20 resultados, sem
  "próxima página" nesta versão).
- Consulta de dias anteriores/diferentes de "hoje" em `GET /nutricao/hoje`
  (sem parâmetro de data nesta versão — só o dia corrente no fuso
  `America/Sao_Paulo`).
- Gráficos/histórico de evolução nutricional ao longo do tempo (semana,
  mês).
- Qualquer recomendação de alimento, substituição ou ajuste de dieta
  baseado no registro (isso seria funcionalidade de IA/chat, fora de
  escopo aqui — nenhuma chamada Grok nesta feature).
- Detecção de padrão de risco alimentar (déficit extremo, restrição
  severa) a partir do histórico de `refeicoes` — mencionado como risco
  LGPD/produto na seção correspondente, mas o *tratamento* é feature
  própria futura.
- Fotos de refeição (registro por foto do prato) — módulo `fotos/` é
  outra spec.
- Alérgenos/restrições alimentares cruzados com o alimento buscado (ex.:
  avisar se o alimento bate com uma restrição já cadastrada em
  `restricoes_alimentares`) — cruzamento fica para spec futura.

## Dependências

- `supabase-architect`: **obrigatório antes de `READY_FOR_BUILD`**:
  1. Migration de `alimentos` (nome final, tipos, RLS de leitura pública
     para `authenticated` sem escrita, extensão `unaccent`) — decisão de
     schema explicitamente nova (primeira tabela de referência
     compartilhada do projeto, sem precedente direto a copiar).
  2. Migration de `refeicoes` (nome final, tipos, `CHECK`s, FK para
     `alimentos`, índice, RLS own-row).
  3. Confirmação por escrito (comentário de migration + atualização de
     `docs/erd.md`, mesmo padrão já seguido nas migrations anteriores) de
     que a postura de RLS de `alimentos` foi avaliada e aceita, já que é
     um desvio do padrão own-row usado em todo o resto do schema.
  4. Seed inicial de `alimentos` — ver "Questões abertas" para o que
     popular enquanto a fonte completa da TACO não está definida.
- `backend-engineer`: módulo `app/modules/nutricao/` — routers dos três
  endpoints, `service.py` (agregação, orquestração da busca), `metas.py`
  (mock isolado da meta calórica), `repository.py` (acesso a `alimentos`/
  `refeicoes` via RLS).
- `frontend-engineer`: tela de registro (busca de alimento + input de
  quantidade) e card de resumo do dia.
- `test-engineer`: testes unitários da fórmula de agregação (valores
  conhecidos, arredondamento) + testes de integração dos três endpoints
  (incluindo isolamento por RLS entre dois usuários em `refeicoes` e
  RLS negativo de escrita em `alimentos`) + teste de substituição do mock
  de meta calórica.
- `ai-integration`: **não aplicável** — sem chat, sem Grok nesta spec.
- `security-reviewer`: **obrigatório antes de merge** — tabela nova com
  dado comportamental de saúde indireto (`refeicoes`), RLS nova, e
  primeira tabela do projeto com postura de RLS não own-row (`alimentos`)
  a validar com atenção redobrada.

## Questões abertas (para o product owner)

1. **Origem do dataset TACO — bloqueante para o import completo, não
   para o início do trabalho.** Não encontrei nenhum arquivo-fonte da
   TACO (CSV/JSON) no repositório, nem menção a onde obtê-lo além do nome
   "TACO" em comentário de migration anterior. Preciso saber: existe um
   arquivo já preparado em algum lugar (ex.: já baixado, mas não
   commitado ainda) ou preciso partir do zero (ex.: a publicação oficial
   do NEPA/UNICAMP, normalmente distribuída como PDF/planilha, exigindo
   um trabalho de extração/estruturação antes de virar seed)?
   **Default proposto para não travar o fluxo**: `supabase-architect`
   cria um seed inicial pequeno e representativo (~30–50 alimentos comuns
   da dieta brasileira, com nome + kcal/proteína/carboidrato/gordura por
   100g, digitados manualmente a partir de valores públicos conhecidos da
   TACO) apenas para desbloquear `backend-engineer`/`frontend-engineer`/
   `test-engineer` imediatamente. O import completo (~600 alimentos) fica
   registrado como tarefa de acompanhamento separada, a ser fechada assim
   que a fonte de dados completa for confirmada — **não é este spec que
   deve travar esperando a resposta**, mas o import completo depende
   dela.
2. **Tolerância ao mock de meta calórica de 2000 kcal ficar visível ao
   usuário.** Proposto no contrato (`meta_kcal_origem: "mock_fixo"`) para
   uso interno/telemetria, mas não decidi se o frontend deve comunicar
   isso ao usuário final (ex.: "meta ainda não personalizada") ou
   simplesmente mostrar "2000 kcal" sem qualquer aviso, como se já fosse
   definitivo. **Default proposto**: não expor nenhum aviso ao usuário
   nesta versão (mostra só "meta: 2000 kcal", sem menção a mock) — evita
   dar a entender que o app está "quebrado" ou incompleto; `frontend-
   engineer` decide o texto exato, mas parte dessa premissa.
3. **Código de erro exato para `alimento_id` inexistente** (`422` vs
   `404`) — não é bloqueante, fica como decisão de `backend-engineer`
   respeitando o padrão de erro já usado no restante do backend
   (`PERFIL_INCOMPLETO` como modelo de formato de erro com campo `erro` +
   `mensagem`). Sinalizado aqui só para não ser esquecido, não para
   travar o início do trabalho.
