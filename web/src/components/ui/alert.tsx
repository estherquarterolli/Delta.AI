import { HTMLAttributes } from "react";
import clsx from "clsx";

type Variant = "info" | "acolhimento" | "erro" | "sucesso";

interface AlertProps extends HTMLAttributes<HTMLDivElement> {
  variant?: Variant;
}

// Paleta deliberadamente sem vermelho de alarme pra estados esperados do
// produto (acolhimento) — só "erro" (falha real: rede, 401, 500) usa tom
// de atenção, e ainda assim moderado. Ver CLAUDE.md: "feedback emocional
// cuidadoso".
const VARIANT_CLASSES: Record<Variant, string> = {
  info: "border-neutral-200 bg-neutral-50 text-neutral-700 dark:border-neutral-700 dark:bg-neutral-800/60 dark:text-neutral-300",
  acolhimento:
    "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-800/50 dark:bg-amber-950/40 dark:text-amber-200",
  erro: "border-rose-200 bg-rose-50 text-rose-800 dark:border-rose-800/50 dark:bg-rose-950/40 dark:text-rose-200",
  sucesso:
    "border-acento-100 bg-acento-50 text-acento-700 dark:border-acento-700/40 dark:bg-acento-900/30 dark:text-acento-200",
};

export function Alert({ className, variant = "info", role, ...props }: AlertProps) {
  return (
    <div
      role={role ?? "status"}
      className={clsx(
        "rounded-xl border px-4 py-3 text-sm leading-relaxed",
        VARIANT_CLASSES[variant],
        className
      )}
      {...props}
    />
  );
}
