# Delta.AI

**Medir a mudança. Não julgar o caminho.**

Plataforma de acompanhamento de emagrecimento com coach de IA contextualizado, análise mensal por foto e habit tracker de treinos. Feito pro mercado brasileiro, com respeito à LGPD e ao processo emocional de quem tá tentando mudar.

> `∆` = mudança. Todo dia é um delta pequeno. O app mede, o coach acompanha, você decide.

---

## Status

🚧 **Em desenvolvimento — MVP** 🚧

Roadmap público em [`docs/roadmap.md`](./docs/roadmap.md). Plano de negócio completo em [`docs/plano-de-negocio.md`](./docs/plano-de-negocio.md).

---

## O que faz

- **Cálculos personalizados**: IMC, TMB, GET, meta calórica, macros e hidratação recomendada, com curva de perda de peso realista.
- **Registro diário**: refeições (base TACO + Open Food Facts), água, peso, humor e energia.
- **Habit tracker de treinos**: rotina semanal, check-ins, streaks e histórico visual.
- **Fotos de progresso**: upload mensal padronizado com overlay de silhueta, comparação lado a lado e evolução de medidas.
- **Coach IA (Grok)**: chat contextual que sabe o teu histórico, sugere receitas com o que você tem em casa e responde dentro do teu orçamento calórico — nunca prescreve, nunca diagnostica.
- **Notificações inteligentes**: email e push com base no comportamento real, não spam motivacional.
- **Relatório mensal**: PDF pronto pra levar ao médico ou nutricionista.

---

## Stack

| Camada         | Tecnologia                                 |
|----------------|--------------------------------------------|
| Frontend       | Next.js 15 (App Router) + Tailwind + shadcn/ui |
| Backend        | FastAPI (Python 3.12)                      |
| Banco de dados | Supabase Postgres com Row Level Security   |
| Storage        | Supabase Storage (fotos criptografadas)    |
| Auth           | Supabase Auth + Google OAuth               |
| IA             | Grok (xAI) via wrapper com anonimização    |
| Emails         | Resend                                     |
| Push           | OneSignal                                  |
| Monitoramento  | Sentry                                     |
| Deploy         | Vercel (frontend) + Fly.io GRU (backend)   |

MVP inteiro roda em free tier. Análise de custos em [`docs/costs/`](./docs/costs/).

---

## Arquitetura

```
delta-ai/
├── app/                    # FastAPI backend
│   ├── modules/            # Domínios: perfil, nutricao, treinos, fotos, chat, notificacoes
│   ├── ai/                 # Wrapper Grok + anonimizador (LGPD)
│   ├── db/                 # Cliente Supabase + helpers RLS
│   └── main.py
├── web/                    # Next.js frontend
├── supabase/migrations/    # Migrations SQL
├── specs/                  # Specs técnicas de features
├── docs/                   # ADRs, arquitetura, plano
└── .claude/agents/         # Sub-agentes de desenvolvimento
```

Diagrama completo em [`docs/arquitetura.md`](./docs/arquitetura.md).

### Fluxo crítico do chat IA

Toda mensagem passa por três estágios antes de sair da nossa infra:

1. **Contexto compactado**: perfil despersonalizado + histórico compactado (últimas 10 msgs + resumo).
2. **Anonimização**: remoção de nome, email, ID, CPF e qualquer PII detectável.
3. **Chamada ao Grok**: via wrapper interno (`app/ai/grok_client.py`), nunca direto.

O anonimizador é auditado em cada release e tem teste automatizado com prompts adversariais.

---

## Começando

### Pré-requisitos

- Node.js 20+ e pnpm
- Python 3.12+
- Docker e Docker Compose
- Supabase CLI ([instruções](https://supabase.com/docs/guides/cli))
- Conta no [xAI](https://x.ai/api) pra chave da API do Grok (créditos gratuitos disponíveis via data-sharing program)

### Setup local

```bash
# Clonar
git clone https://github.com/<seu-usuario>/delta-ai.git
cd delta-ai

# Backend
cp .env.example .env
# preencher as variáveis (Supabase URL, chaves, Grok API key)

# Subir Supabase local + backend
docker compose up -d
supabase db reset       # aplica migrations
uvicorn app.main:app --reload

# Em outro terminal: frontend
cd web
pnpm install
pnpm dev
```

Frontend em `http://localhost:3000`, backend em `http://localhost:8000`, Supabase Studio em `http://localhost:54323`.

### Variáveis de ambiente

Ver [`.env.example`](./.env.example) pra lista completa. As sensíveis:

- `SUPABASE_SERVICE_ROLE_KEY` — só no servidor, jamais no cliente
- `GROK_API_KEY` — só no servidor
- `RESEND_API_KEY` — só no servidor

---

## Desenvolvimento com Claude Code

Este repositório usa [Claude Code](https://docs.claude.com/en/docs/claude-code/overview) com uma equipe de sub-agentes especializados. O agente principal (Opus) orquestra, e sub-agentes Sonnet executam tarefas focadas.

Sub-agentes disponíveis em [`.claude/agents/`](./.claude/agents/):

| Agente               | Responsabilidade                                  |
|----------------------|---------------------------------------------------|
| `product-spec`       | Requisição → spec técnico com critérios de aceite |
| `supabase-architect` | Schema, migrations, RLS policies                  |
| `backend-engineer`   | FastAPI, módulos, business logic                  |
| `frontend-engineer`  | Next.js, telas, formulários                       |
| `ai-integration`     | Wrapper Grok, prompts, anonimizador, guardrails   |
| `test-engineer`      | pytest + Playwright, cobertura                    |
| `security-reviewer`  | Audita LGPD, RLS, anonimização, secrets           |
| `devops-engineer`    | Fly.io, Vercel, CI/CD, monitoramento              |

Fluxo de desenvolvimento e guia de orquestração em [`WORKFLOW.md`](./WORKFLOW.md).

Para começar:

```bash
claude --model opus
```

O Claude Code lê `CLAUDE.md` automaticamente como contexto persistente do projeto.

---

## Segurança, LGPD e ética

Dados de saúde são **dados sensíveis** pela LGPD (art. 5º, II). Este projeto trata isso a sério:

- ✅ Row Level Security em toda tabela user-scoped, sem exceção.
- ✅ Anonimização obrigatória antes de qualquer chamada à IA externa.
- ✅ Storage privado com URLs assinadas de curta duração (≤ 15min).
- ✅ Endpoint de deleção total de conta (perfil, refeições, fotos, chat).
- ✅ Consentimento explícito no cadastro, com termo específico pra dados de saúde.
- ✅ Auditoria de segurança obrigatória em toda PR que toque dado sensível.

### Guardrails do bot

O coach IA **nunca**:

- Diagnostica condições médicas.
- Prescreve medicamentos ou doses de suplementos.
- Sugere déficit calórico maior que 25% do GET.
- Recomenda eliminar grupo alimentar sem indicação médica documentada.

E **sempre**:

- Detecta padrões preocupantes (déficit extremo, sinais de TCAn, sofrimento psicológico) e redireciona pra profissional ou canais de acolhimento (ABRATA, CAPS).
- Exibe disclaimer visível: "não substitui orientação médica ou nutricional".

Detalhes em [`docs/security/guardrails.md`](./docs/security/guardrails.md).

---

## Testes

```bash
# Backend
pytest                    # roda tudo
pytest --cov=app          # com cobertura
pytest tests/test_ai_guardrails.py -v   # só os guardrails da IA

# Frontend
cd web
pnpm test                 # unit
pnpm test:e2e             # Playwright
```

Meta de cobertura: 70% em `app/modules/`, 90% em `app/ai/`.

---

## Contribuindo

Este projeto está em fase inicial e as contribuições externas ainda não estão abertas. Assim que o MVP for lançado publicamente, vou publicar as diretrizes de contribuição.

Se você encontrou este repositório e tem interesse, abra uma issue pra conversar.

---

## Roadmap resumido

- **Mês 1-3**: MVP fechado (cálculos, registro, habit tracker, fotos, chat básico)
- **Mês 4-6**: Receitas geradas, integração Google Fit, relatório PDF, launch público grátis
- **Mês 7+**: Founders deal + plano premium, análise de foto por IA, marketplace de nutricionistas

Roadmap completo em [`docs/roadmap.md`](./docs/roadmap.md).

---

## Licença

Este projeto é privado durante o MVP. A licença será definida antes do launch público (provavelmente uma licença dual: código aberto pra partes não-comerciais, código proprietário pra funcionalidades de produto).

---

## Créditos

Construído com carinho no Rio de Janeiro. Coach IA rodando em Grok (xAI). Base alimentar TACO (Unicamp).

Para dúvidas, sugestões ou parcerias: abra uma issue ou entre em contato.

---

<sub>Delta.AI — porque toda mudança grande começa com uma medida pequena.</sub>
