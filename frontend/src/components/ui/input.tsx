import type { InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-10 w-full rounded-panel border border-border bg-panel px-3 text-sm text-text placeholder:text-subtle",
        className,
      )}
      {...props}
    />
  );
}
