# Deploy do backend (Fly.io)

Guia reproduzível pra colocar o backend FastAPI (`app/`) no ar no Fly.io,
região `gru` (São Paulo). O `fly.toml` e o `Dockerfile` da raiz do repo já
estão prontos — este documento é só o passo a passo de execução manual, e
depois como o deploy automático via GitHub Actions funciona.

App Fly sugerido: **`delta-ai-api`** (domínio público esperado:
`https://delta-ai-api.fly.dev`). Confirme se esse nome está livre antes do
primeiro deploy — se não estiver, ajuste `app` em `fly.toml` e a variável
`NEXT_PUBLIC_API_URL` do frontend de acordo.

## 1. Pré-requisitos

1. Instalar o `flyctl`:
   - macOS/Linux: `curl -L https://fly.io/install.sh | sh`
   - Windows (PowerShell): `pwsh -Command "iwr https://fly.io/install.ps1 -useb | iex"`
   - ou via `winget install flyctl` / `scoop install flyctl`
2. Autenticar:
   ```bash
   fly auth login
   ```
3. Ter uma conta Fly.io com o app free tier (Hobby) habilitado.

## 2. Criar o app no Fly (sem sobrescrever o `fly.toml`)

O `fly.toml` da raiz **já existe e já está configurado** (app, região,
health check, VM). **Não rode `fly launch` interativo** — ele tende a
sobrescrever o `fly.toml` existente e recriar o Dockerfile. Em vez disso,
crie o app diretamente:

```bash
fly apps create delta-ai-api --org <sua-org>
```

Se preferir usar `fly launch`, use as flags que pulam a geração de
config e deploy automático, revisando o diff antes de confirmar:

```bash
fly launch --no-deploy --copy-config --name delta-ai-api --region gru
```

`--copy-config` reaproveita o `fly.toml` já commitado em vez de gerar um
novo.

## 3. Configurar os secrets

Nenhum secret vai em `fly.toml` nem em `Dockerfile`. Todos são setados via
`fly secrets set`, usando os nomes exatos do `.env.example`:

```bash
fly secrets set \
  SUPABASE_URL="https://xxxxx.supabase.co" \
  SUPABASE_ANON_KEY="..." \
  SUPABASE_SERVICE_ROLE_KEY="..." \
  DATABASE_URL="postgresql://postgres:senha@host:5432/postgres" \
  GROK_API_KEY="..." \
  GROK_API_BASE_URL="https://api.x.ai/v1" \
  RESEND_API_KEY="..." \
  ONESIGNAL_APP_ID="..." \
  ONESIGNAL_API_KEY="..." \
  SENTRY_DSN_BACKEND="..." \
  ENVIRONMENT="production" \
  FRONTEND_URL="https://SEU-DOMINIO.vercel.app" \
  --app delta-ai-api
```

Notas:

- `SUPABASE_SERVICE_ROLE_KEY` bypassa RLS — só deve ser lida por cron
  jobs explicitamente justificados em ADR (regra do CLAUDE.md). Não usar
  em request handler exposto a usuário.
- `ENVIRONMENT` e `FRONTEND_URL` não são secretos (não há dado sensível
  neles), mas usar `fly secrets set` pra eles também é conveniente: evita
  editar/redeployar o `fly.toml` toda vez que o domínio do frontend
  mudar. `FRONTEND_URL` alimenta o CORS do backend (`app/config.py`) —
  ajuste pro domínio real do deploy Vercel antes do primeiro deploy de
  produção, senão o frontend em produção é bloqueado por CORS.
- Hoje (`app/config.py`) o backend só lê efetivamente
  `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `DATABASE_URL`,
  `SENTRY_DSN_BACKEND`, `ENVIRONMENT` e `FRONTEND_URL`. As demais
  variáveis (`SUPABASE_SERVICE_ROLE_KEY`, `GROK_API_KEY`, `RESEND_API_KEY`,
  `ONESIGNAL_APP_ID`, `ONESIGNAL_API_KEY`) fazem parte do contrato de
  secrets do backend definido no `.env.example` e ainda serão consumidas
  à medida que os módulos (`app/ai`, notificações, etc.) forem
  implementados — já deixe setadas pra não precisar voltar aqui depois.
- **`GET /health` sobe e responde `200` sem nenhum secret setado** — é só
  um liveness check da aplicação (não toca banco). É o que o Fly usa pra
  decidir se reinicia a VM.
- `GET /health/db` testa a conexão real com o Postgres via
  `DATABASE_URL` (`app/db/health.py`) e responde `503` se a variável não
  estiver setada ou a conexão falhar — use como critério de "banco
  conectado", não de "app no ar".
- Pra atualizar um secret depois, basta rodar `fly secrets set` de novo
  com o novo valor — isso já dispara um novo release da VM.

## 4. Deploy manual

Com o Dockerfile e o `fly.toml` prontos:

```bash
fly deploy --app delta-ai-api
```

Isso builda a imagem (multi-stage, non-root, definida no `Dockerfile` da
raiz) remotamente nos builders do Fly e sobe a release.

## 5. Verificar

```bash
curl -i https://delta-ai-api.fly.dev/health
# esperado: HTTP 200, {"status":"ok","version":"0.0.1"}

curl -i https://delta-ai-api.fly.dev/health/db
# esperado com DATABASE_URL setado e Postgres alcançável: HTTP 200, {"status":"ok","db":"reachable"}
# esperado sem DATABASE_URL ou com banco fora do ar: HTTP 503
```

Outros comandos úteis pra depurar:

```bash
fly status --app delta-ai-api
fly logs --app delta-ai-api
fly machine list --app delta-ai-api
```

Como `min_machines_running = 0` (free tier), a primeira request depois de
um período ocioso pode demorar alguns segundos (cold start) enquanto a
máquina liga — isso é esperado, não é erro.

## 6. Deploy automático via GitHub Actions

O workflow `.github/workflows/backend-deploy.yml` roda `flyctl deploy
--remote-only` a cada push na branch `main` que toque `app/`, `Dockerfile`,
`.dockerignore` ou `fly.toml`.

Pra habilitar, gere um token de deploy (escopo restrito ao app, mais seguro
que o token pessoal de conta):

```bash
fly tokens create deploy --app delta-ai-api
```

Copie o token gerado e cadastre no repositório em:

**GitHub → Settings → Secrets and variables → Actions → New repository
secret**

- Nome: `FLY_API_TOKEN`
- Valor: o token gerado pelo comando acima

A partir daí, todo merge/push na `main` que mexa em backend dispara o
deploy automaticamente. O workflow `backend-ci.yml` (lint + testes) roda
em PRs e deve passar antes do merge — ele não bloqueia tecnicamente o
deploy (são workflows separados), então o ideal é só dar merge na main
com o PR verde.

## 7. Nota de custo (free tier)

- **Fly.io Hobby**: 1 VM `shared-cpu-1x` com 256MB (`fly.toml`), região
  `gru`. `auto_stop_machines` + `auto_start_machines` +
  `min_machines_running = 0` fazem a VM desligar quando não há tráfego,
  reduzindo consumo de horas de compute dentro da cota gratuita.
- **Ponto de estouro**: se o tráfego virar constante (VM nunca fica
  ociosa) ou se 256MB não for suficiente pra carga (OOM kills nos logs),
  isso é sinal pra escalar verticalmente primeiro (`memory = "512mb"` em
  `[[vm]]`) antes de considerar múltiplas máquinas.
- **Plano B**: aumentar `memory` em `[[vm]]` (ainda dentro do Hobby,
  verificar limite de horas/RAM do plano) ou revisar se algo está
  segurando a VM acordada sem necessidade (ex.: healthcheck de terceiro
  muito frequente, polling do frontend).

## 8. Restaurar backup do Supabase (referência)

O Supabase Free faz snapshot diário automaticamente. Pra restaurar:

1. No painel do Supabase → **Database → Backups**.
2. Escolher o snapshot desejado e restaurar (isso é uma operação do lado
   do Supabase — não depende do Fly.io nem deste repositório).
3. Depois de restaurar, confirmar que `DATABASE_URL` / `SUPABASE_URL` /
   chaves ainda são as mesmas (Supabase Free normalmente restaura no
   mesmo projeto, então os secrets do Fly não deveriam precisar mudar).
4. Rodar `curl https://delta-ai-api.fly.dev/health/db` pra confirmar que
   o backend voltou a falar com o banco restaurado (espera-se `200`).
