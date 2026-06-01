/* input.jsx — shadcn/ui input (copy-in), brand-bridged. */
import { cn } from "../../lib/utils.js";

export function Input({ className, type = "text", ...props }) {
  return (
    <input
      type={type}
      className={cn(
        "flex h-8 w-full rounded-[var(--radius-sm)] border border-input bg-background px-2.5 text-sm text-foreground transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-ring/30 disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
}
