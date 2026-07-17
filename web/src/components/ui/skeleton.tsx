import { HTMLAttributes } from "react";
import clsx from "clsx";

/** Placeholder de carregamento — nunca deixar a tela em branco durante
 * fetch (regra explícita do frontend-engineer). */
export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden="true"
      className={clsx(
        "animate-pulse rounded-xl bg-neutral-200 dark:bg-neutral-800",
        className
      )}
      {...props}
    />
  );
}
