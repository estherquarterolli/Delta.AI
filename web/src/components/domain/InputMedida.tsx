import { InputHTMLAttributes, forwardRef } from "react";
import clsx from "clsx";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";

interface InputMedidaProps extends InputHTMLAttributes<HTMLInputElement> {
  /** Rótulo visível, ex.: "Peso". */
  label: string;
  /** Unidade exibida ao lado do campo, ex.: "kg", "cm", "ml". */
  unidade: string;
  /** Mensagem de erro de validação (pt-BR), exibida inline. */
  erro?: string;
  /** id único do campo — necessário pra associar label + erro via aria. */
  id: string;
}

/**
 * Input numérico com unidade fixa ao lado (kg, cm, ml) — componente de
 * domínio reutilizável em qualquer tela que colete uma medida corporal.
 */
export const InputMedida = forwardRef<HTMLInputElement, InputMedidaProps>(
  ({ label, unidade, erro, id, className, ...props }, ref) => {
    const erroId = erro ? `${id}-erro` : undefined;
    return (
      <div>
        <Label htmlFor={id}>{label}</Label>
        <div className="relative">
          <Input
            ref={ref}
            id={id}
            type="number"
            inputMode="decimal"
            step="0.1"
            aria-invalid={erro ? "true" : undefined}
            aria-describedby={erroId}
            className={clsx("pr-14", className)}
            {...props}
          />
          <span
            aria-hidden="true"
            className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm text-neutral-400"
          >
            {unidade}
          </span>
        </div>
        {erro && (
          <p id={erroId} className="mt-1.5 text-sm text-rose-600 dark:text-rose-400">
            {erro}
          </p>
        )}
      </div>
    );
  }
);
InputMedida.displayName = "InputMedida";
