# App de Emagrecimento — Contexto do Projeto

App de acompanhamento de emagrecimento pro mercado brasileiro. MVP 100% free tier.
Plano de negócio completo em `docs/plano-de-negocio.md`. Arquitetura em `docs/arquitetura.md`.

## Stack

- **Backend**: FastAPI (Python 3.12) → Fly.io (região GRU)
- **Frontend**: Next.js 15 (App Router) + Tailwind → Vercel
- **DB**: Supabase Postgres com RLS em toda tabela user-scoped
- **Storage**: Supabase Storage (fotos criptografadas, URLs assinadas)
- **Auth**: Supabase Auth + Google OAuth
- **IA**: Grok (xAI) via wrapper interno com anonimização obrigatória
- **Email**: Resend
- **Push**: OneSignal
- **Monitoring**: Sentry

## Estrutura de diretórios

```
/
├── app/                    # FastAPI backend
│   ├── modules/            # Domínios: perfil, nutricao, treinos, fotos, chat, notificacoes
│   ├── ai/                 # Wrapper Grok + anonimizador
│   ├── db/                 # Conexão Supabase, helpers RLS
│   └── main.py
├── web/                    # Next.js frontend
├── supabase/migrations/    # Migrations SQL
├── specs/                  # Specs de features (input pra dev)
├── docs/                   # ADRs, arquitetura, plano
└── .claude/agents/         # Sub-agentes especializados
```

## Regras não-negociáveis

### LGPD e privacidade
- Dados de saúde = sensíveis (LGPD art. 5º, II). Consentimento explícito sempre.
- **NUNCA** chamar Grok direto de um módulo. Sempre via `app/ai/grok_client.py`.
- Wrapper OBRIGATORIAMENTE passa por `Anonymizer` antes de enviar.
- Anonymizer remove: nome, email, id do banco, cpf, telefone, endereço.
- Fotos: URLs assinadas com expiração ≤ 15min.

### Guardrails do bot
- Nunca diagnosticar condições médicas.
- Nunca prescrever medicamento ou dose de suplemento.
- Detectar padrões de TCAn (déficit extremo, obsessão) → acolher + sugerir profissional.
- Disclaimer visível: "não substitui orientação médica/nutricional".

### RLS obrigatório
- Toda tabela com `user_id` tem RLS policy pra select/insert/update/delete.
- Sem uso de `service_role` fora de cron jobs justificados em ADR.

### Custo (MVP 100% grátis)
- Cache agressivo em chamadas Grok (system prompt fixo, contexto compactado).
- Limite duro de 30 msgs/dia por usuário no chat.
- Compressão WebP (400KB max) pra fotos.
- Cada PR revisa impacto de custo.

## Sub-agentes disponíveis

Delegue via descrição — não faça o trabalho especializado você mesmo:

- `product-spec`: transforma requisição em spec técnico com critérios de aceitação
- `supabase-architect`: schema, migrations SQL, RLS policies, storage
- `backend-engineer`: FastAPI, módulos, business logic
- `frontend-engineer`: Next.js, React, Tailwind, formulários
- `ai-integration`: wrapper Grok, prompts, anonimizador, guardrails
- `test-engineer`: pytest + Playwright, cobertura
- `security-reviewer`: audita LGPD, RLS, anonimizador, secrets
- `devops-engineer`: Fly.io, Vercel, CI/CD, env vars, monitoring

## Fluxo padrão de feature

1. Receber requisição → invocar `product-spec` (cria arquivo em `specs/`)
2. Se toca dado → `supabase-architect` PRIMEIRO
3. `backend-engineer` + `frontend-engineer` em paralelo se possível
4. `ai-integration` se envolver chat/prompts
5. `test-engineer` sempre no fim
6. `security-reviewer` OBRIGATÓRIO antes de merge se toca dado sensível
7. `devops-engineer` se envolver deploy/config

## Comandos úteis

- `docker compose up` — backend local + Supabase local
- `pnpm dev` (em `web/`) — frontend local
- `pytest` — testes backend
- `pnpm test` — testes frontend
- `supabase db reset` — recria DB local com migrations

## Diretrizes gerais

- Português no código (variáveis de domínio: `Alimento`, `Refeicao`, `Treino`) e inglês em código técnico (`db`, `router`, `handler`).
- Nunca commite `.env` ou secret.
- Todo módulo tem README curto explicando responsabilidade.
- ADRs em `docs/adr/YYYY-MM-DD-titulo.md` pra decisões arquiteturais.
