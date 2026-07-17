"use client";

import Link from "next/link";
import { useImc } from "@/hooks/usePerfil";
import { Card } from "@/components/ui/card";
import { Alert } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { Button, buttonClasses } from "@/components/ui/button";
import { formatarDataCurta } from "@/lib/format";
import type { CampoFaltante } from "@/lib/types";

const DISCLAIMER =
  "IMC é um indicador geral e não substitui avaliação médica ou nutricional individual.";

const CAMPO_PARA_ACAO: Record<CampoFaltante, { texto: string; href: string; cta: string }> = {
  peso: {
    texto: "Registrar seu peso",
    href: "/peso",
    cta: "Registrar pesagem",
  },
  altura_cm: {
    texto: "Informar sua altura",
    href: "/perfil",
    cta: "Completar perfil",
  },
  data_nascimento: {
    texto: "Informar sua data de nascimento",
    href: "/perfil",
    cta: "Completar perfil",
  },
};

export default function ImcPage() {
  const { imc, perfilIncompleto, erroInesperado, carregando, refazer } = useImc();

  if (carregando) {
    return (
      <div className="space-y-3" aria-busy="true" aria-label="Carregando seu IMC">
        <Skeleton className="h-6 w-40" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-16 w-full" />
      </div>
    );
  }

  // Estado 4: erro real (401/500/rede) — único estado que usa a tela de
  // erro genérica. Nunca reaproveitado pelos estados de bloqueio abaixo.
  if (erroInesperado) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-semibold">Seu IMC</h1>
        <Alert variant="erro">
          Não foi possível carregar seu IMC agora. Tente novamente em alguns instantes.
        </Alert>
        <Button variant="secondary" onClick={() => refazer()}>
          Tentar de novo
        </Button>
      </div>
    );
  }

  // Estado 3: perfil incompleto (422) — CTA de completude, não erro.
  if (perfilIncompleto) {
    const acoes = perfilIncompleto.campos_faltantes.map((campo) => CAMPO_PARA_ACAO[campo]);
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-semibold">Seu IMC</h1>
        <Card>
          <p className="mb-4 text-sm text-neutral-600 dark:text-neutral-300">
            {perfilIncompleto.mensagem}
          </p>
          <ul className="mb-4 space-y-1 text-sm text-neutral-500 dark:text-neutral-400">
            {acoes.map((acao) => (
              <li key={acao.href + acao.texto}>• {acao.texto}</li>
            ))}
          </ul>
          <div className="flex flex-wrap gap-2">
            {/* Evita botões duplicados quando duas ações apontam pra mesma rota (altura + data de nascimento -> /perfil). */}
            {Array.from(new Map(acoes.map((a) => [a.href, a])).values()).map((acao) => (
              <Link key={acao.href} href={acao.href} className={buttonClasses()}>
                {acao.cta}
              </Link>
            ))}
          </div>
        </Card>
      </div>
    );
  }

  if (!imc) {
    // Não deveria acontecer (loading/erro/incompleto cobrem os outros
    // casos), mas evita renderizar null silenciosamente.
    return (
      <Alert variant="erro">Não foi possível carregar seu IMC agora.</Alert>
    );
  }

  // Estado 2: bloqueado por idade ou gestação — acolhimento, sem número.
  if (!imc.elegivel) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-semibold">Seu IMC</h1>
        <Alert variant="acolhimento">{imc.mensagem}</Alert>
        <p className="text-xs text-neutral-500 dark:text-neutral-400">{DISCLAIMER}</p>
      </div>
    );
  }

  // Estado 1: elegível, com resultado.
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Seu IMC</h1>
      <Card>
        <p className="text-5xl font-semibold tabular-nums">{imc.imc?.toFixed(1)}</p>
        <p className="mt-1 text-lg text-neutral-700 dark:text-neutral-300">
          Sua faixa de IMC é: {imc.classificacao_label}
        </p>
        {imc.pesagem_registrada_em && (
          <p className="mt-3 text-sm text-neutral-500 dark:text-neutral-400">
            Com base no seu peso de {formatarDataCurta(imc.pesagem_registrada_em)}.
          </p>
        )}
      </Card>
      <p className="text-xs text-neutral-500 dark:text-neutral-400">{DISCLAIMER}</p>
    </div>
  );
}
