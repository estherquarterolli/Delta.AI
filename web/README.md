# web/ — Frontend Next.js

Frontend do Delta.AI, Next.js 15 (App Router) + Tailwind, deployado
na Vercel (free tier, deploy automático via GitHub a cada push).

Dono: `frontend-engineer`.

## Rodando local

```
pnpm install
pnpm dev
```

Requer um `web/.env.local` com as variáveis públicas (ver
`.env.example` na raiz, seção "Frontend"): `NEXT_PUBLIC_SUPABASE_URL`,
`NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_URL`,
`NEXT_PUBLIC_ONESIGNAL_APP_ID`, `SENTRY_DSN_FRONTEND`.

Source maps são uploadados pro Sentry via CLI durante o build — essa
config é feita pelo `devops-engineer` quando o projeto Next.js for
inicializado neste diretório.
