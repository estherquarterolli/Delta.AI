"use client";

import { useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabase";

interface AuthSessionState {
  session: Session | null;
  /** `true` enquanto a sessão inicial ainda não foi resolvida. */
  carregando: boolean;
}

/**
 * Hook único de leitura de sessão Supabase (login) — usado pelo guard de
 * `(app)/layout.tsx` e pela tela de login pra redirecionar quem já está
 * autenticado. Não é usado por telas de domínio (perfil, peso), que só
 * precisam do JWT via `lib/api.ts`.
 */
export function useAuthSession(): AuthSessionState {
  const [session, setSession] = useState<Session | null>(null);
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setCarregando(false);
    });

    const { data: listener } = supabase.auth.onAuthStateChange((_event, novaSessao) => {
      setSession(novaSessao);
    });

    return () => {
      listener.subscription.unsubscribe();
    };
  }, []);

  return { session, carregando };
}
