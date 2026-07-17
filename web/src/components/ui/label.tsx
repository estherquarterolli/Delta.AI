import { LabelHTMLAttributes } from "react";
import clsx from "clsx";

export function Label({ className, ...props }: LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label
      className={clsx(
        "mb-1.5 block text-sm font-medium text-neutral-700 dark:text-neutral-300",
        className
      )}
      {...props}
    />
  );
}
