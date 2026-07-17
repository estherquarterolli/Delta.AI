import { InputHTMLAttributes, forwardRef } from "react";
import clsx from "clsx";

/**
 * Toggle acessível (checkbox estilizado como switch). Sem dependência de
 * Radix pra manter o bundle mínimo — usa `role="switch"` nativo via
 * `<input type="checkbox">` + `aria-checked` implícito do próprio input.
 */
export const Switch = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => {
    return (
      <span className="relative inline-flex h-7 w-12 shrink-0 items-center">
        <input
          ref={ref}
          type="checkbox"
          role="switch"
          className={clsx(
            "peer h-7 w-12 shrink-0 cursor-pointer appearance-none rounded-full bg-neutral-300 transition-colors checked:bg-acento-600 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-acento-500 dark:bg-neutral-700",
            className
          )}
          {...props}
        />
        <span
          aria-hidden="true"
          className="pointer-events-none absolute left-1 h-5 w-5 rounded-full bg-white shadow transition-transform peer-checked:translate-x-5"
        />
      </span>
    );
  }
);
Switch.displayName = "Switch";
