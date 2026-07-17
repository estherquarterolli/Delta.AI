# Cálculo de IMC

**Status**: APROVADO PARA MERGE (backend + frontend com 4 estados + endpoint de escrita de esta_gestante + 86 testes verdes + security-reviewer aprovou em 2026-07-17; follow-ups não-bloqueantes: M1 RLS real em CI, I1 sanitizar log de auth, I2 GET de esta_gestante)

> Esta é a primeira feature end-to-end do produto (spec → dados → backend →
> frontend → testes). Servirá de modelo de fluxo de trabalho pras próximas
> specs.
>
> **Bloqueios atuais** (atualizado em 2026-07-17 após respostas do product
> owner às 3 perguntas da versão anterior deste spec):
> 1. Depende de `specs/2026-07-17-registro-de-peso.md` (tabela `pesagens`,
>    ainda não implementada) — o IMC não usa mais
>    `profiles.peso_inicial_kg`, e sim o peso da pesagem mais recente. Ver
>    "Fonte do peso (revisado)".
> 2. Depende de uma migration aditiva pra suportar elegibilidade por idade/
>    gestação (campo de gestação não existe hoje no schema). Ver
>    "Dependência de schema — elegibilidade por idade/gestação".
>
> Este spec só avança pra `READY_FOR_ARCH` depois que o `supabase-architect`
> confirmar/implementar os dois pontos acima, e só vira `READY_FOR_BUILD`
> depois que ambas as migrations existirem e `backend-engineer` confirmar
> que a função de "pesagem mais recente" (do spec de registro de peso) está
> disponível pra consumo.

## Contexto

O app coleta altura no onboarding (`public.profiles.altura_cm`) e, a
partir de `specs/2026-07-17-registro-de-peso.md`, passa a coletar peso de
forma contínua via pesagens periódicas. O IMC é o primeiro indicador
derivado exibido no app, combinando esses dois dados — e o primeiro
indicador de saúde que precisa de uma checagem de elegibilidade (idade,
gestação) antes de exibir uma classificação, pra não aplicar uma faixa de
referência de adulto a alguém pra quem ela não é válida.

## User story

Como usuária/usuário autenticado, adulto e não gestante, com altura e ao
menos uma pesagem registradas, quero ver meu IMC atual e sua classificação,
para entender rapidamente minha situação de peso em relação à altura, num
formato compreensível, sem jargão médico e sem que o app tente me
diagnosticar quando a informação disponível não é suficiente ou adequada
pra isso.

## Investigação do estado atual do banco (atualizada)

Verificado em `supabase/migrations/`:

- `public.profiles.altura_cm` — `integer`, nullable, `CHECK altura_cm
  between 50 and 250`. Já existe. Continua sendo a fonte de altura.
- `public.profiles.data_nascimento` — `date`, nullable, `CHECK` de faixa
  plausível. Já existe — usada agora pra calcular idade (ver "Elegibilidade
  por idade/gestação").
- `public.profiles.peso_inicial_kg` — existe, mas **deixou de ser usada por
  esta feature** (decisão do product owner: é a baseline do onboarding, não
  o peso atual — ver "Fonte do peso (revisado)"). Continua existindo e
  sendo usada em outros contextos (ex.: possível referência histórica em
  `goals`), só não é mais insumo do cálculo de IMC.
- **Não existe** hoje nenhuma coluna equivalente a "gestante"/"gravidez" em
  `profiles`, `condicoes_saude` ou em qualquer outra tabela. Isso é uma
  lacuna de schema nova, tratada abaixo.
- **Não existe** hoje a tabela de pesagens — está especificada e é
  pré-requisito bloqueante em `specs/2026-07-17-registro-de-peso.md`.

## Objetivo e escopo

**Dentro do escopo:**
- Calcular o IMC do usuário autenticado a partir de `profiles.altura_cm` e
  da **pesagem mais recente** do usuário (via módulo de registro de peso).
- Checar elegibilidade por idade (a partir de `profiles.data_nascimento`) e
  por gestação (novo campo, ver abaixo) antes de exibir uma classificação
  de adulto.
- Classificar o resultado numa das 6 faixas padrão da OMS, quando elegível.
- Expor o resultado via `GET /perfil/imc`.
- Exibir o resultado (ou o bloqueio de elegibilidade, com mensagem
  acolhedora) numa tela dedicada do app, com disclaimer padrão do produto.

**Fora de escopo** (ver seção dedicada "Fora de escopo" mais abaixo).

## Fonte do peso (revisado)

**Decisão do product owner**: o IMC não deve usar `profiles.peso_inicial_kg`.
Deve usar o peso da **pesagem mais recente** do usuário, obtida via a
função/service definida em `specs/2026-07-17-registro-de-peso.md`
("Contrato mínimo que o módulo de IMC... pode assumir").

Implicações:
- O módulo de IMC (`app/modules/perfil/`) passa a ter uma dependência de
  runtime no módulo de pesagens (chamada de função/service, não acesso
  direto à tabela — encapsulamento a definir com `backend-engineer`).
- "Peso mais recente" é definido por `registrada_em` (não `created_at`),
  conforme já especificado no spec de pesagens.
- Se o usuário nunca registrou nenhuma pesagem, isso é tratado como perfil
  incompleto (`422`), nunca como erro (`500`) — ver "Contrato do endpoint".
- A resposta do endpoint passa a incluir `pesagem_registrada_em`, pra a
  tela poder mostrar "IMC calculado com base no seu peso de dd/mm", já que
  o peso usado pode não ser "de hoje".

## Dependência de schema — elegibilidade por idade/gestação

**O que já existe**: `profiles.data_nascimento` (nullable) é suficiente
pra calcular idade — não precisa de coluna nova.

**O que falta**: não existe hoje nenhum jeito de saber se a usuária está
gestante. Isso é uma lacuna de dado nova, introduzida por esta spec (a
funcionalidade de elegibilidade é nova, não existia antes).

**Proposta (para confirmação do `supabase-architect`, não uma decisão
final deste spec)**:
- Nome/local sugerido: `esta_gestante` (`boolean`, `not null default
  false`), seguindo o mesmo padrão já usado pra
  `profiles.aceite_data_sharing_ia` (booleano com default seguro,
  opt-in/declarativo).
- **Local sugerido — a decidir pelo `supabase-architect`**: gestação é
  dado de saúde (LGPD art. 5º, II), potencialmente mais sensível que altura/
  peso (pode revelar tentativa de gravidez, tratamento de fertilidade, etc.
  se cruzado com outros dados). O projeto já tem um padrão estabelecido de
  isolar dado de saúde sensível fora de `profiles` (`condicoes_saude`,
  `restricoes_alimentares` — ver justificativa nas migrations existentes).
  Por consistência com esse padrão, a sugestão deste spec é que o campo
  viva em `public.condicoes_saude` (nova coluna) em vez de em
  `public.profiles`, mas essa é uma decisão de modelagem do
  `supabase-architect`, não do `product-spec` — confirmar antes de
  qualquer migration.
- **Default proposto (pra não travar o fluxo até existir uma tela
  específica de pergunta)**: `false`. Ou seja, na ausência de informação, o
  app assume "não gestante" — mesmo risco que já existe hoje (o app não
  sabe disso de nenhuma forma), não é uma regressão. Consequência aceita:
  o bloqueio de gestante só funciona pra quem efetivamente informar `true`
  em algum lugar da UI.
- **Onde o usuário informa isso**: não existe hoje nenhuma tela que
  pergunte isso. Proposta de menor escopo: adicionar como um campo a mais
  na tela de edição de perfil já existente (mesmo tipo de adição já feita
  antes pra `nivel_atividade`), não uma tela nova — a decidir com
  `frontend-engineer`/`backend-engineer` como item pequeno de escopo desta
  entrega, não uma feature própria (diferente do registro de peso, que
  tem CRUD e tela próprios o suficiente para justificar spec separado).
- **Consentimento**: coletar gestação por texto explícito ("Você está
  gestante atualmente?") deve ter uma linha de contexto na UI explicando
  por que é perguntado (afeta cálculos de saúde do app), mas não abre, na
  avaliação deste spec, um fluxo de consentimento formal separado do aceite
  geral de Termos — é o mesmo tratamento dado a `condicoes_saude` hoje.

## Regras de negócio do cálculo

### Elegibilidade (checada antes da fórmula)

Calculada nesta ordem, só depois de confirmar que altura, peso (pesagem) e
data de nascimento estão disponíveis (ver "Contrato do endpoint" pra
comportamento de dado incompleto):

1. **Idade** = anos completos entre `profiles.data_nascimento` e a data
   atual (UTC, servidor). Se idade `< 18` → `elegivel: false`,
   `motivo_bloqueio: "menor_de_18"`.
2. **Gestação**: se `esta_gestante = true` → `elegivel: false`,
   `motivo_bloqueio: "gestante"`. (Checado mesmo que a pessoa também seja
   menor de 18 — nesse caso `motivo_bloqueio` prioriza `"menor_de_18"`,
   primeira condição que bater.)
3. Caso contrário → `elegivel: true`, segue pro cálculo normal.

**Comportamento quando não elegível — bloqueio total, não apenas aviso.**
Decisão deste spec (critério clínico mais defensável, alinhado ao guardrail
do CLAUDE.md de nunca diagnosticar e sempre acolher): o endpoint **não
calcula nem retorna o número do IMC** nesses casos, só a mensagem de
acolhimento. Justificativa: mesmo o valor numérico bruto, sem a
classificação OMS, pode ser mal interpretado por quem o vê (ex.: uma
gestante comparando o número com uma faixa "normal" que não se aplica ao
seu momento, gerando ansiedade — mesmo risco que os guardrails de chat já
tratam pra padrões de restrição alimentar). É mais seguro não exibir nada
além da orientação de procurar um profissional (pediatra, para menores;
pré-natal, para gestantes) do que exibir um número fora de contexto.

Idade exatamente igual a 18 anos (18 anos completos) é considerada
**elegível** (adulto).

### Fórmula (quando elegível)

```
IMC = peso_kg / (altura_m ^ 2)
```

- `peso_kg` vem da pesagem mais recente do usuário (ver "Fonte do peso
  (revisado)").
- `altura_m` é derivada de `profiles.altura_cm / 100`.
- Resultado arredondado pra **1 casa decimal** na resposta da API (ex.:
  `23.4`). Cálculo interno sem arredondamento intermediário.

### Unidades — decisão e justificativa

Sem mudança em relação à versão anterior deste spec: peso em kg (unidade
nativa da pesagem, `numeric(5,2)`), altura em cm no banco (convertida pra
metros só no momento do cálculo).

### Faixas de classificação (padrão OMS/Ministério da Saúde, pt-BR)

| Faixa de IMC (kg/m²)        | `classificacao` (enum)   | `classificacao_label` (pt-BR) |
|-----------------------------|---------------------------|--------------------------------|
| IMC < 18.5                  | `abaixo_do_peso`          | Abaixo do peso                |
| 18.5 ≤ IMC < 25.0            | `peso_normal`              | Peso normal                   |
| 25.0 ≤ IMC < 30.0            | `sobrepeso`                | Sobrepeso                     |
| 30.0 ≤ IMC < 35.0            | `obesidade_grau_1`         | Obesidade grau I              |
| 35.0 ≤ IMC < 40.0            | `obesidade_grau_2`         | Obesidade grau II             |
| IMC ≥ 40.0                   | `obesidade_grau_3`         | Obesidade grau III            |

Cortes numéricos são os padrão da Organização Mundial da Saúde. Limite
inferior de cada faixa é inclusivo (`≥`). Sem mudanças em relação à versão
anterior — só se aplicam quando `elegivel: true`.

### Disclaimer obrigatório na tela

Mantido da versão anterior: texto visível equivalente a "IMC é um
indicador geral e não substitui avaliação médica/nutricional individual",
nunca linguagem de diagnóstico. Quando `elegivel: false`, o disclaimer é
substituído/complementado pela mensagem de acolhimento específica do
`motivo_bloqueio` (ver exemplos no contrato do endpoint).

## Critérios de aceitação

- [ ] Usuário autenticado, adulto (≥18), não gestante, com `altura_cm`
      preenchido e ao menos uma pesagem registrada, recebe `200` com
      `elegivel: true`, `imc` (float, 1 decimal), `classificacao` e
      `classificacao_label` corretos.
- [ ] Valores de borda exatos de IMC (18.5, 25.0, 30.0, 35.0, 40.0) caem na
      faixa superior (inclusiva) — coberto por teste unitário de
      `calcular_imc`.
- [ ] Usuário com idade calculada `< 18` recebe `200` com `elegivel: false`,
      `motivo_bloqueio: "menor_de_18"`, `imc: null`, e mensagem de
      acolhimento sugerindo profissional (pediatra/nutricionista) — nunca
      um número de IMC.
- [ ] Usuária com `esta_gestante = true` recebe `200` com `elegivel: false`,
      `motivo_bloqueio: "gestante"`, `imc: null`, e mensagem de acolhimento
      sugerindo acompanhamento no pré-natal — nunca um número de IMC.
- [ ] Idade calculada exatamente `18` anos é tratada como elegível (não
      bloqueada) — coberto por teste unitário de borda.
- [ ] Usuário sem `altura_cm`, sem `data_nascimento`, ou sem nenhuma
      pesagem registrada recebe `422 PERFIL_INCOMPLETO` com
      `campos_faltantes` listando exatamente o que falta (ver contrato).
- [ ] Requisição sem token de autenticação válido recebe `401` e não
      executa nenhuma leitura em `profiles`/pesagens.
- [ ] Requisição autenticada só recebe dado do próprio usuário — nunca de
      outro `user_id` (RLS existente + RLS de `pesagens`), coberto por
      teste de integração com dois usuários.
- [ ] `calcular_imc(peso_kg, altura_cm)` é função pura, sem I/O, testável
      isoladamente, e permanece sem conhecimento de elegibilidade (a
      checagem de idade/gestação é responsabilidade da camada de
      service/router, não da função de cálculo — mantém a função de
      cálculo simples e coesa).
- [ ] `calcular_imc` levanta erro explícito para `altura_cm <= 0` e
      `peso_kg <= 0`.
- [ ] O valor de IMC calculado **não é persistido** em nenhuma tabela.
- [ ] Tela `/perfil/imc` renderiza os três estados (elegível com resultado,
      bloqueado por idade, bloqueado por gestação, perfil incompleto) com
      textos e CTAs distintos — nunca reaproveita a tela de erro genérica
      pros estados de bloqueio de elegibilidade (são estados esperados do
      produto, não falhas).

## Contrato do endpoint

### `GET /perfil/imc`

**Autenticação**: obrigatória (Bearer token do Supabase Auth) — mesma nota
da versão anterior sobre ser a primeira rota autenticada do backend.

**Request**: sem body, sem query params.

**Response 200 OK — elegível**
```json
{
  "elegivel": true,
  "motivo_bloqueio": null,
  "mensagem": null,
  "imc": 23.4,
  "classificacao": "peso_normal",
  "classificacao_label": "Peso normal",
  "peso_kg": 70.0,
  "altura_cm": 173,
  "pesagem_registrada_em": "2026-07-15T08:00:00Z",
  "calculado_em": "2026-07-17T14:32:00Z"
}
```

**Response 200 OK — bloqueado por elegibilidade** (idade ou gestação;
mesmo HTTP status, porque o request foi processado com sucesso — a
"resposta" é o bloqueio em si, não uma falha):
```json
{
  "elegivel": false,
  "motivo_bloqueio": "gestante",
  "mensagem": "Durante a gestação, o IMC padrão não é um indicador adequado — o ganho de peso esperado varia bastante de pessoa para pessoa. Recomendamos acompanhar seu peso com o pré-natal.",
  "imc": null,
  "classificacao": null,
  "classificacao_label": null,
  "peso_kg": null,
  "altura_cm": null,
  "pesagem_registrada_em": null,
  "calculado_em": "2026-07-17T14:32:00Z"
}
```
`motivo_bloqueio: "menor_de_18"` usa mensagem equivalente sugerindo
pediatra/nutricionista. `peso_kg`/`altura_cm`/`pesagem_registrada_em` são
omitidos (`null`) mesmo quando os dados existem — reforça a decisão de
"bloqueio total, não parcial" (ver "Regras de negócio").

**Response 422 Unprocessable Entity** — perfil incompleto:
```json
{
  "erro": "PERFIL_INCOMPLETO",
  "mensagem": "Complete seu perfil para calcular o IMC.",
  "campos_faltantes": ["altura_cm", "data_nascimento", "peso"]
}
```
- `campos_faltantes` pode conter `altura_cm`, `data_nascimento` e/ou
  `peso`. **`peso` é um nome lógico**, não o nome de uma coluna — significa
  "nenhuma pesagem registrada ainda" (o dado mora em `pesagens`, não em
  `profiles`, mas a API não expõe esse detalhe de schema pro frontend).
- Nota: `esta_gestante` **nunca** aparece em `campos_faltantes` — tem
  default `false` (ver "Dependência de schema"), então nunca é "faltante",
  só potencialmente incorreto por omissão (aceito, ver seção de decisões).

**Response 401 Unauthorized** — token ausente/inválido/expirado.

**Response 500 Internal Server Error** — caso defensivo (dado corrompido
fora da faixa fisiológica esperada). Mesmo tratamento da versão anterior.

### `calcular_imc(peso_kg: float, altura_cm: float) -> tuple[float, Classificacao]`

Sem mudanças — permanece função pura, sem qualquer conhecimento de idade,
gestação ou origem do peso. A checagem de elegibilidade e a busca do peso
mais recente ficam na camada de service/router de `app/modules/perfil/`,
que orquestra: buscar perfil → buscar pesagem mais recente → checar
completude → checar elegibilidade → só então chamar `calcular_imc`.

## Edge cases e comportamento de erro

| Cenário | Camada | Comportamento esperado |
|---|---|---|
| `altura_cm` nulo | endpoint | `422 PERFIL_INCOMPLETO` (`campos_faltantes` inclui `altura_cm`) |
| `data_nascimento` nula | endpoint | `422 PERFIL_INCOMPLETO` (`campos_faltantes` inclui `data_nascimento`) — necessária pra checar elegibilidade por idade |
| Nenhuma pesagem registrada | endpoint | `422 PERFIL_INCOMPLETO` (`campos_faltantes` inclui `peso`) |
| Múltiplos campos faltando ao mesmo tempo | endpoint | `422` único, `campos_faltantes` lista todos |
| Idade `< 18` | endpoint | `200`, `elegivel: false`, `motivo_bloqueio: "menor_de_18"`, sem número |
| `esta_gestante = true` | endpoint | `200`, `elegivel: false`, `motivo_bloqueio: "gestante"`, sem número |
| Idade `< 18` **e** `esta_gestante = true` | endpoint | `200`, `elegivel: false`, `motivo_bloqueio: "menor_de_18"` (idade checada primeiro) |
| `altura_cm = 0` (não deveria existir, CHECK exige ≥50) | função pura | `ValueError` → endpoint responde `500` + log Sentry |
| `peso_kg` negativo (não deveria existir, CHECK exige ≥20) | função pura | `ValueError` → endpoint responde `500` + log Sentry |
| Sem token de auth | endpoint | `401`, nenhuma query executada |
| Usuário sem linha em `profiles` (não deveria acontecer) | endpoint | Tratar como perfil incompleto (`422`) |

## Fluxo de dados

- **Entrada**: nenhuma entrada nova do usuário nesta tela — consome
  `profiles.altura_cm`, `profiles.data_nascimento`, o novo campo de
  gestação (local a definir pelo `supabase-architect`) e a pesagem mais
  recente do módulo de pesagens.
- **Processamento**: backend busca esses quatro insumos (via RLS,
  `auth.uid()`), checa completude, checa elegibilidade, e só então aplica
  `calcular_imc`.
- **Saída**: JSON de resposta do endpoint (ver contrato acima), consumido
  pela tela `web/src/app/(app)/perfil/imc/page.tsx`.
- **Persistência**: **nenhuma** nova. O IMC calculado não é gravado em
  nenhuma tabela — é derivado em tempo real a cada request.

## Impacto LGPD

- **Toca dados sensíveis?** Sim, e agora em grau maior que a versão
  anterior deste spec:
  - Peso (via pesagens) e altura — dado de saúde indireto, como já
    avaliado.
  - **Gestação** (`esta_gestante`) — dado de saúde sensível (LGPD art. 5º,
    II), potencialmente mais sensível que peso/altura isoladamente. É dado
    **novo**, nunca antes coletado pelo produto — diferente de peso/altura,
    que já existiam. Recomendação deste spec (a confirmar com
    `supabase-architect`): tratar com o mesmo isolamento já usado pra
    `condicoes_saude`/`restricoes_alimentares`, não como coluna solta em
    `profiles`.
  - Data de nascimento já existia e já é dado pessoal comum (não sensível
    por si só), mas passa a alimentar uma decisão de saúde (elegibilidade)
    — não é coleta nova, é novo *uso* de dado já existente.
- **RLS necessária em tabela nova?** Depende da decisão do
  `supabase-architect` sobre onde `esta_gestante` mora:
  - Se for coluna em tabela já existente com RLS (`profiles` ou
    `condicoes_saude`) → não precisa de RLS nova (herda a policy da
    tabela).
  - A tabela `pesagens` (spec separado) **precisa** de RLS própria — já
    coberto no spec de registro de peso.
- **Requer consentimento explícito adicional?** Recomendação: não um fluxo
  de consentimento formal *separado*, mas a UI que pergunta
  `esta_gestante` deve deixar explícito o motivo da pergunta (mesmo padrão
  de transparência já aplicado a `condicoes_saude`). Ponto de atenção
  novo: como é a primeira vez que o produto pergunta algo tão sensível de
  forma direta (vs. texto livre em `condicoes_saude`), vale alinhamento
  com `security-reviewer` antes do merge sobre se o texto de consentimento
  geral (`aceite_termos_em`) é suficiente ou se merece uma linha de
  consentimento específica no momento da pergunta.
- Resultado do IMC continua não persistido — reduz a superfície de risco
  desta parte específica da feature.

## Impacto de custo (MVP free)

- **Novas chamadas Grok?** Nenhuma.
- **Novo storage?** Nenhum (tabela `pesagens` é Postgres comum, sem
  Supabase Storage).
- **Novos emails?** Nenhum.
- Custo adicional: duas leituras extras por request (`profiles` completo +
  pesagem mais recente de `pesagens`, esta última já otimizada por índice
  `(user_id, registrada_em desc)` proposto no spec de pesagens). Ainda
  dentro do free tier, sem chamadas a serviços pagos.

## Fora de escopo

- Histórico de IMC ao longo do tempo (série temporal de avaliações
  passadas) — o valor nunca é persistido; ficaria pra spec futura, se
  necessário.
- Edição de peso/altura/gestação nesta tela — feita nos fluxos próprios
  (registro de peso, edição de perfil).
- Curvas de crescimento/percentil específicas pra menores de 18 anos — o
  app bloqueia em vez de calcular, não implementa a alternativa clínica
  correta pra essa faixa.
- Qualquer recomendação nutricional, de treino ou de meta calórica baseada
  no resultado do IMC.
- Notificação push/email quando a classificação mudar.
- Envio do resultado do IMC ou de `esta_gestante`/idade pro chat de IA
  (Grok) ou uso como contexto de IA.
- Detecção proativa de gestação a partir de outros sinais (ex.: padrão de
  peso) — o dado só existe se o próprio usuário informar.

## Dependências

- `supabase-architect`: **obrigatório antes de `READY_FOR_BUILD`** (não é
  mais só confirmação — há mudança de schema real):
  1. Migration da tabela `pesagens` (spec separado
     `specs/2026-07-17-registro-de-peso.md`).
  2. Migration aditiva pra suportar elegibilidade por gestação (decidir
     nome/local exato de `esta_gestante`, coerente com o padrão de
     isolamento de dado sensível já usado no schema atual).
- `backend-engineer`: implementa `app/modules/perfil/calculos.py` (função
  pura, sem mudança de responsabilidade), a camada de service que orquestra
  perfil + pesagem mais recente + elegibilidade, o router/schemas
  Pydantic, e a dependency de autenticação (primeira rota autenticada do
  backend). Depende do módulo de pesagens (spec separado) já ter a função
  de "pesagem mais recente" pronta.
- `frontend-engineer`: tela `web/src/app/(app)/perfil/imc/page.tsx` com os
  quatro estados (elegível, bloqueado por idade, bloqueado por gestação,
  perfil incompleto), e o campo pequeno de `esta_gestante` na tela de
  edição de perfil existente (fora da tela de IMC em si).
- `test-engineer`: testes unitários de `calcular_imc` (faixas, bordas,
  valores inválidos) + testes unitários de elegibilidade (idade <18, =18,
  gestante) + testes de integração da rota (200 elegível, 200 bloqueado
  por cada motivo, 422 com cada combinação de campo faltante, 401,
  isolamento por RLS).
- `ai-integration`: **não aplicável** — sem chat, sem Grok.
- `security-reviewer`: **obrigatório antes de merge** — tabela nova
  (`pesagens`), campo de saúde sensível novo (`esta_gestante`), e primeira
  vez que o produto bloqueia ativamente uma funcionalidade por dado de
  saúde (checar se a lógica de bloqueio é robusta contra bypass via
  manipulação de request).

## Decisões assumidas nesta revisão (defaults propostos, não bloqueiam)

Diferente da versão anterior, estas não são perguntas em aberto — são
decisões já tomadas neste spec, com justificativa, seguindo a orientação
recebida de não travar o fluxo de novo. Listadas aqui pra transparência e
fácil override futuro, caso o product owner discorde depois de ver a
implementação:

1. **`esta_gestante` default `false`** quando não informado, em vez de
   exigir que o usuário responda antes de liberar qualquer uso do app.
   Risco aceito: usuárias gestantes que não informarem continuam vendo a
   classificação de adulto normalmente (mesmo estado de risco que existe
   hoje, sem regressão).
2. **Local de coleta de `esta_gestante`**: tela de edição de perfil
   existente (adição pequena de campo), não uma tela/fluxo novo dedicado.
3. **Bloqueio de elegibilidade é total** (sem número de IMC), não um aviso
   acompanhando o número — ver justificativa clínica na seção "Regras de
   negócio".
4. **Prioridade de motivo de bloqueio**: se as duas condições baterem
   (menor de 18 e gestante), `motivo_bloqueio` reporta `"menor_de_18"`.
5. **Corte de idade**: 18 anos completos já é elegível (não bloqueado).

Nenhuma dessas decisões impede o início do trabalho de
`supabase-architect`/`backend-engineer`/`frontend-engineer` — se o product
owner quiser mudar alguma depois, é um ajuste de spec pontual, não um novo
ciclo de bloqueio completo.
