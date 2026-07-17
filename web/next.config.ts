import type { NextConfig } from "next";

/**
 * Configuração mínima do Next.js. Uploads de source map pro Sentry e
 * qualquer config de deploy (Vercel) ficam a cargo do `devops-engineer`
 * quando o projeto for conectado à Vercel — ver `web/README.md`.
 */
const nextConfig: NextConfig = {
  reactStrictMode: true,
};

export default nextConfig;
