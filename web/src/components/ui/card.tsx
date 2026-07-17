import { HTMLAttributes } from "react";
import clsx from "clsx";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={clsx(
        "rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900",
        className
      )}
      {...props}
    />
  );
}
