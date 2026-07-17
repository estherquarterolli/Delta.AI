"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuthSession } from "@/hooks/useAuthSession";
import { supabase } from "@/lib/supabase";
import { Skeleton } from "@/components/ui/skeleton";

const LINKS = [
  { href: "/peso", label: "Peso" },
  { href: "/perfil/imc", label: "IMC" },
  { href: "/perfil", label: "Perfil" },
];

/**
 * Layout da área autenticada: garante que só quem tem sessão Supabase
 * ativa vê as telas de domínio (peso, perfil, IMC), com nav simples.
 * Enquanto a sessão inicial está sendo resolvida, mostra skeleton —
 * nunca tela em branco.
 */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { session, carregando } = useAuthSession();

  useEffect(() => {
    if (!carregando && !session) {
      router.replace("/login");
    }
  }, [carregando, session, router]);

  if (carregando || !session) {
    return (
      <div className="mx-auto max-w-md space-y-3 px-4 py-8">
        <Skeleton className="h-8 w-1/2" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  return (
    <div className="mx-auto min-h-screen max-w-md pb-8">
      <header className="flex items-center justify-between border-b border-neutral-200 px-4 py-4 dark:border-neutral-800">
        <nav aria-label="Navegação principal" className="flex gap-4">
          {LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-sm font-medium text-neutral-600 hover:text-acento-600 dark:text-neutral-300 dark:hover:text-acento-500"
            >
              {link.label}
            </Link>
          ))}
        </nav>
        <button
          type="button"
          onClick={() => supabase.auth.signOut()}
          className="text-sm text-neutral-500 hover:text-neutral-800 dark:text-neutral-400 dark:hover:text-neutral-100"
        >
          Sair
        </button>
      </header>
      <main className="px-4 py-6">{children}</main>
    </div>
  );
}
