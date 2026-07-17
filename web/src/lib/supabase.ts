import { createClient } from "@supabase/supabase-js";

/**
 * Client Supabase do browser — usado exclusivamente para autenticação
 * (login, sessão, JWT). Chamadas de dados do produto (pesagens, perfil,
 * IMC) NUNCA usam este client diretamente; passam por `lib/api.ts`, que
 * fala com o backend FastAPI (ver CLAUDE.md: regra de encapsulamento do
 * `frontend-engineer`).
 *
 * `NEXT_PUBLIC_SUPABASE_ANON_KEY` respeita RLS — segura para o client,
 * nunca é um segredo de servidor.
 */

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  // Não derruba o build (variáveis podem não existir ainda em dev sem
  // `.env.local` configurado), mas avisa alto no console do browser.
  console.warn(
    "NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY não configuradas — ver web/.env.example."
  );
}

export const supabase = createClient(supabaseUrl ?? "", supabaseAnonKey ?? "", {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
  },
});
