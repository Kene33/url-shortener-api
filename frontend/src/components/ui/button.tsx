import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-panel border text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-60",
  {
    variants: {
      variant: {
        primary: "border-accent bg-accent px-4 py-2 text-white hover:opacity-95",
        secondary: "border-border bg-panel px-4 py-2 text-text hover:bg-muted",
        ghost: "border-transparent bg-transparent px-3 py-2 text-subtle hover:bg-muted",
        danger: "border-danger bg-danger px-4 py-2 text-white hover:opacity-95",
      },
      size: {
        sm: "h-9 gap-2 px-3 text-xs",
        md: "h-10 gap-2 px-4",
        lg: "h-11 gap-2 px-5",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  },
);

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants>;

export function Button({ className, variant, size, ...props }: ButtonProps) {
  return <button className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}
