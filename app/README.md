# app/ — Backend FastAPI

Backend do Delta.AI, em Python 3.12 + FastAPI, deployado no Fly.io
(região `gru`, São Paulo).

## Estrutura

- `main.py` — monta a aplicação, health check (`/health`), registra routers.
- `modules/` — domínios de negócio (perfil, nutrição, treinos, fotos, chat, notificações). Dono: `backend-engineer`.
- `ai/` — wrapper do Grok (xAI) e anonimizador. Dono: `ai-integration`.
- `db/` — conexão com Supabase e helpers de RLS. Dono: `supabase-architect` (schema) + `backend-engineer` (uso).
- `requirements.txt` — dependências Python.

## Rodando local

```
docker compose up          # backend com hot reload (ver docker-compose.yml na raiz)
```

Requer Supabase local rodando (`supabase start`, na raiz) e um `.env`
preenchido a partir de `.env.example` (raiz).

## Decisão de infra (devops-engineer)

Optamos por um `Dockerfile` na raiz do repo, com contexto `.` (copia
`app/` pra dentro da imagem), em vez de um Dockerfile dentro de
`app/`. Isso mantém paridade entre o build usado no
`docker-compose.yml` local e o build usado pelo Fly.io em produção —
mesmo Dockerfile, mesmo comportamento, sem duplicação.
