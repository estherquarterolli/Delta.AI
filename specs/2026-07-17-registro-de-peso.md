# Registro de Peso (Pesagens)

**Status**: APROVADO PARA MERGE (backend + frontend + 86 testes verdes + security-reviewer aprovou em 2026-07-17; follow-up não-bloqueante M1: validar RLS real em CI)

> Esta spec nasceu como pré-requisito bloqueante de
> `specs/2026-07-17-calculo-imc.md`: a decisão de produto foi de que o IMC
> deve usar o peso mais recente registrado pelo usuário, não o
> `profiles.peso_inicial_kg` (baseline única do onboarding). Como isso
> exige tabela nova (mudança de schema) e é, em si, uma funcionalidade
> completa — registrar, listar e corrigir pesagens ao longo do tempo — foi
> desacoplada da spec de IMC em vez de virar uma seção dentro dela.
>
> **Por que spec separado, e não seção de pré-requisito dentro do spec de
> IMC**: CLAUDE.md estabelece "1 spec por feature" e um fluxo padrão
> (`product-spec` → `supabase-architect` → `backend-engineer`/
> `frontend-engineer` → `test-engineer` → `security-reviewer`) por feature.
> Registro de peso tem seu próprio ciclo de vida de dado (histórico,
> correção/edição de entradas passadas, RLS própria, tela própria de
> "registrar peso hoje") independente do IMC — o IMC é só **um consumidor**
> desse dado, não o único. Tratar como seção de outra spec misturaria
> critérios de aceitação de duas features com ritmos de entrega diferentes
> e dificultaria o `security-reviewer` avaliar cada uma isoladamente.
> Ordem de execução: **este spec primeiro** (schema → backend → frontend →
> testes), IMC depois, consumindo o que este spec expõe.

## Contexto

O app registra hoje apenas um peso "de baseline" (`profiles.peso_inicial_kg`,
informado uma vez no onboarding). Para qualquer cálculo que dependa do peso
*atual* do usuário (IMC sendo o primeiro caso, mas também futura evolução
de peso/gráficos e progresso em relação a `goals`), é necessário um
histórico de pesagens que o usuário alimenta periodicamente.

## User story

Como usuária/usuário, quero registrar meu peso sempre que me pesar e ver
minhas pesagens anteriores, para acompanhar minha evolução ao longo do
tempo e permitir que o app use meu peso mais recente em outros cálculos
(ex.: IMC).

## Objetivo e escopo

**Dentro do escopo (MVP mínimo pra desbloquear o IMC e cobrir o caso de
uso central):**
- Registrar uma nova pesagem (peso + data/hora).
- Listar o histórico de pesagens do usuário (mais recente primeiro).
- Expor, de forma reutilizável por outros módulos (ex.: `perfil/imc`), a
  pesagem mais recente do usuário.
- Editar e excluir uma pesagem própria (correção de erro de digitação é
  operação comum e dado de saúde — usuário tem direito de corrigir/excluir
  o próprio dado, LGPD art. 18).

**Fora de escopo nesta primeira versão** (ver seção dedicada mais abaixo).

## Modelo de dados proposto (para confirmação do `supabase-architect`)

> `product-spec` não escreve SQL nem decide definitivamente o schema — a
> proposta abaixo é o requisito funcional pro `supabase-architect` desenhar
> a migration. Nome de tabela, tipos exatos e índices ficam a critério
> dele, desde que o contrato funcional abaixo seja atendido.

- **Tabela sugerida**: `public.pesagens`. Uma linha por pesagem (histórico
  completo, mesmo padrão já usado em `public.goals` — nunca UPDATE de um
  valor "atual", sempre INSERT de um novo registro; edição só corrige uma
  linha existente, não empilha regra de "qual é a atual").
- **Colunas sugeridas**:
  - `id` — identificador da pesagem.
  - `user_id` — FK `auth.users(id)`, `ON DELETE CASCADE` (mesmo padrão de
    `goals`/`condicoes_saude`), indexado.
  - `peso_kg` — `numeric(5,2)`, mesma faixa de sanidade já usada em
    `profiles.peso_inicial_kg`/`goals` (`CHECK entre 20 e 400`), pra manter
    consistência de validação entre as tabelas de peso do projeto.
  - `registrada_em` — timestamp de **quando a pesagem foi feita**
    (informado pelo usuário, pode ser retroativo — ex. "me pesei ontem de
    manhã"), distinto de `created_at` (quando a linha foi inserida no
    banco). O IMC e qualquer "peso mais recente" devem ordenar por
    `registrada_em`, não por `created_at`.
  - `created_at` / `updated_at` — padrão do projeto (trigger
    `set_updated_at`).
- **RLS**: own-row, mesmo padrão de `goals`/`condicoes_saude`/
  `restricoes_alimentares` — `select/insert/update/delete` com
  `auth.uid() = user_id`. Sem uso de `service_role`.
- **Índice sugerido**: `(user_id, registrada_em desc)` — suporta
  diretamente a query "pesagem mais recente do usuário" e a listagem de
  histórico paginada, sem scan.
- **Isolamento de dado sensível**: peso corporal já é tratado no projeto
  como "dado de saúde indireto" (ver `docs/erd.md`, notas de
  `profiles.peso_inicial_kg` e `goals.peso_inicial_kg`). Consistente com
  isso, `pesagens` deve seguir o mesmo padrão de isolamento por FK própria
  com `ON DELETE CASCADE` (não é dado tão sensível quanto
  `condicoes_saude`, que fica em tabela ainda mais isolada — peso já tem
  precedente de ficar em `profiles`/`goals` — mas o histórico têmporal é
  informação nova o suficiente pra justificar tabela própria em vez de
  virar array em `profiles`).

## Contrato mínimo que o módulo de IMC (e outros consumidores futuros)
   pode assumir

- Existe uma função/service (ex. `obter_pesagem_mais_recente(user_id)`) que
  retorna a pesagem mais recente do usuário por `registrada_em`, ou `None`
  se o usuário nunca registrou nenhuma pesagem.
- "Peso mais recente" = pesagem com maior `registrada_em` (não
  `created_at`) para aquele `user_id`.
- Se não houver nenhuma pesagem, o consumidor (IMC) deve tratar isso como
  dado ausente — equivalente a "campo faltante" — nunca como erro
  inesperado (`500`).

## Critérios de aceitação

- [ ] Usuário autenticado consegue criar uma pesagem (`peso_kg`,
      `registrada_em` opcional — default "agora" se omitido) e recebe a
      pesagem criada de volta.
- [ ] `peso_kg` fora da faixa 20–400 é rejeitado com `422` antes de tocar
      o banco (validação de aplicação, além do `CHECK` do banco).
- [ ] `registrada_em` no futuro é rejeitado com `422` (não é possível
      registrar uma pesagem "de amanhã").
- [ ] Usuário autenticado consegue listar suas próprias pesagens, ordenadas
      da mais recente pra mais antiga.
- [ ] Usuário autenticado consegue editar e excluir uma pesagem própria.
- [ ] Usuário autenticado **nunca** vê, edita ou exclui pesagem de outro
      usuário (RLS + teste de integração com dois usuários).
- [ ] Existe uma função reutilizável que retorna a pesagem mais recente de
      um usuário (ou ausência dela), usada pelo módulo de IMC sem ele
      precisar conhecer o schema de `pesagens` diretamente (encapsulamento
      via `app/modules/perfil` ou módulo próprio, a definir com
      `backend-engineer`).
- [ ] Requisição sem token de autenticação válido recebe `401` em todas as
      rotas deste módulo.

## Fluxo de dados

- **Entrada**: peso (kg) e, opcionalmente, data/hora da pesagem, informados
  pelo próprio usuário autenticado.
- **Processamento**: validação de faixa e de "não é data futura"; escrita
  em `pesagens`.
- **Saída**: a pesagem criada/editada (JSON) e a listagem de histórico.
- **Persistência**: sim — histórico completo em `public.pesagens`, nunca
  sobrescrito (edição altera a linha específica editada, exclusão remove a
  linha específica; nenhuma pesagem "resume" outra).

## Impacto LGPD

- **Toca dados sensíveis?** Sim — peso corporal ao longo do tempo é dado de
  saúde indireto (mesma classificação já usada pra
  `profiles.peso_inicial_kg`/`goals.peso_inicial_kg` no `docs/erd.md`), e um
  histórico é potencialmente mais revelador que um único valor de baseline
  (ex.: permite inferir padrão de perda/ganho rápido, possível sinal de
  TCA — CLAUDE.md pede atenção a esse padrão no chat; aqui não há chat,
  mas o dado bruto que alimentaria essa detecção futura nasce nesta
  feature).
- **RLS necessária em tabela nova?** Sim — `pesagens` é tabela nova
  user-scoped, RLS own-row obrigatória em todas as operações (select,
  insert, update, delete), sem exceção e sem uso de `service_role`.
- **Requer consentimento explícito adicional?** Não além do consentimento
  geral já dado nos Termos de Uso/Privacidade no onboarding
  (`profiles.aceite_termos_em`) — registrar peso é extensão direta e
  esperada da funcionalidade central do app (a mesma finalidade de
  "acompanhamento de peso" que já motivou a coleta de
  `peso_inicial_kg`), não uma finalidade nova. Nenhum dado desta tabela é
  enviado à IA (Grok) nesta spec.
- Exclusão de conta deve apagar `pesagens` do usuário — `ON DELETE CASCADE`
  na FK garante isso automaticamente, sem lógica de aplicação adicional
  ("deletar conta = deletar limpo", mesmo padrão já usado em
  `goals`/`condicoes_saude`).

## Impacto de custo (MVP free)

- **Novas chamadas Grok?** Nenhuma.
- **Novo storage?** Nenhum (Supabase Storage não é usado — é uma tabela
  Postgres comum, dentro do free tier do Supabase).
- **Novos emails?** Nenhum nesta versão (lembrete de "hora de se pesar" via
  OneSignal/Resend está fora de escopo — ver abaixo).

## Fora de escopo

- Lembretes/notificações push ou email pra registrar peso periodicamente.
- Gráfico de evolução de peso (visualização) — a listagem crua do
  histórico é suficiente pro consumo do IMC; visualização é feature de UX
  própria, futura.
- Detecção de padrão de risco (perda/ganho muito rápido, possível sinal de
  TCA) a partir do histórico — mencionado como risco LGPD/produto acima,
  mas o *tratamento* desse risco (alertas, acolhimento) é feature própria
  futura, não desta spec.
- Import de pesagens de dispositivos externos (balança smart, Apple
  Health/Google Fit).
- Qualquer relação direta desta tabela com `goals` (ex.: marcar automatico
  meta como concluída quando uma pesagem bate a meta) — fica pra spec de
  evolução de metas.

## Dependências

- `supabase-architect`: **obrigatório antes de `READY_FOR_BUILD`** — desenhar
  e aplicar a migration de `pesagens` (nome final, tipos, índices, RLS)
  seguindo o contrato funcional proposto acima. Nenhuma implementação de
  backend/frontend começa antes dessa migration existir.
- `backend-engineer`: módulo de pesagens (rotas de criar/listar/editar/
  excluir) + a função/service de "pesagem mais recente" que o módulo de
  IMC vai consumir.
- `frontend-engineer`: tela de registrar pesagem + listagem de histórico
  (fora de escopo: gráfico).
- `test-engineer`: testes unitários de validação (faixa, data futura) e
  integração (CRUD completo + isolamento por RLS entre usuários).
- `ai-integration`: **não aplicável**.
- `security-reviewer`: **obrigatório antes de merge** — tabela nova com
  dado de saúde indireto e RLS nova.

## Dependência reversa

`specs/2026-07-17-calculo-imc.md` está bloqueado por esta spec: o backend
do IMC só deve começar depois que `pesagens` (schema + função de "pesagem
mais recente") estiver implementada e testada.
