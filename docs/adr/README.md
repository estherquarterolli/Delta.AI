# docs/adr/ — Architecture Decision Records

Um arquivo por decisão arquitetural relevante, nome
`YYYY-MM-DD-titulo.md`. Usado principalmente pra justificar:

- Uso de `SUPABASE_SERVICE_ROLE_KEY` fora do fluxo padrão (regra do CLAUDE.md: só em cron job justificado aqui).
- Mudanças de infra com impacto de custo ou arquitetura (ex.: trocar de provedor, escalar VM, adicionar serviço externo).

Sem template fixo — o objetivo é registrar contexto, decisão e
consequências de forma curta e objetiva.
