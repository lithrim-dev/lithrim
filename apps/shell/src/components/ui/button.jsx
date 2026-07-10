/* button.jsx — shadcn/ui button (copy-in), brand-bridged via theme.css @theme tokens.
   Variants resolve to the shell's coral accent + surface tokens (not shadcn defaults). */
import { cva } from "class-variance-authority";
import { cn } from "../../lib/utils.js";

export const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[var(--radius-sm)] text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:opacity-90",
        secondary: "bg-secondary text-secondary-foreground border border-border hover:border-border-strong",
        outline: "border border-border bg-background text-foreground hover:bg-secondary",
        ghost: "text-foreground hover:bg-muted",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-8 px-3.5",
        sm: "h-7 px-2.5 text-xs",
        lg: "h-10 px-5",
        icon: "h-8 w-8",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export function Button({ className, variant, size, type = "button", ...props }) {
  return (
    <button type={type} className={cn(buttonVariants({ variant, size }), className)} {...props} />
  );
}
