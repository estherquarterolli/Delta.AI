import { InputHTMLAttributes, forwardRef } from "react";
import clsx from "clsx";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => {
    return (
      <input
        ref={ref}
        className={clsx(
          "min-h-11 w-full rounded-xl border border-neutral-300 bg-white px-3 py-2 text-base text-neutral-900 placeholder:text-neutral-400 focus-visible:border-acento-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-acento-500/40 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-100",
          className
        )}
        {...props}
      />
    );
  }
);
Input.displayName = "Input";
