# app/modules/ — Domínios de negócio

Cada domínio é um módulo isolado com seu próprio router, schemas
(Pydantic) e lógica de negócio. Dono: `backend-engineer`.

Domínios previstos (criados conforme as specs chegam em `specs/`):

- `perfil/` — dados de perfil, objetivo, peso, medidas.
- `nutricao/` — refeições, alimentos, registro alimentar.
- `treinos/` — plano e registro de treinos.
- `fotos/` — upload e evolução de fotos (URLs assinadas, expiração ≤ 15min).
- `chat/` — conversa com a IA (usa `app/ai/grok_client.py`, nunca chama o Grok direto).
- `notificacoes/` — push (OneSignal) e email (Resend).

## Regras

- Nenhum módulo importa o SDK do Grok diretamente — sempre via `app/ai/`.
- Nenhum módulo usa `SUPABASE_SERVICE_ROLE_KEY` fora de cron jobs justificados em ADR (`docs/adr/`).
- Toda query respeita RLS (helpers em `app/db/`).
