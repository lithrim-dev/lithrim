/* label.jsx — shadcn/ui label (copy-in) over @radix-ui/react-label, brand-bridged. */
import * as LabelPrimitive from "@radix-ui/react-label";
import { cn } from "../../lib/utils.js";

export function Label({ className, ...props }) {
  return (
    <LabelPrimitive.Root
      className={cn(
        "text-xs font-medium uppercase tracking-wide text-muted-foreground font-[family-name:var(--font-mono)] peer-disabled:cursor-not-allowed peer-disabled:opacity-70",
        className,
      )}
      {...props}
    />
  );
}
