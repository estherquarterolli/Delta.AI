import { ButtonHTMLAttributes, forwardRef } from "react";
import clsx from "clsx";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "destructive";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
}

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary:
    "bg-acento-600 text-white hover:bg-acento-700 focus-visible:outline-acento-600 disabled:bg-acento-600/50",
  secondary:
    "bg-neutral-100 text-neutral-900 hover:bg-neutral-200 dark:bg-neutral-800 dark:text-neutral-100 dark:hover:bg-neutral-700",
  ghost:
    "bg-transparent text-neutral-700 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800",
  destructive: "bg-red-600 text-white hover:bg-red-700 disabled:bg-red-600/50",
};

/** Classes de botão reutilizáveis fora de um `<button>` real — ex.:
 * `<Link>` estilizado como CTA (não pode ser um `<button>` aninhado). */
export function buttonClasses(variant: ButtonVariant = "primary", className?: string) {
  return clsx(
    "inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-70",
    VARIANT_CLASSES[variant],
    className
  );
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", disabled, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled}
        className={buttonClasses(variant, className)}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";
