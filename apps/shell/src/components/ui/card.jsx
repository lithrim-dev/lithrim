/* card.jsx — shadcn/ui card (copy-in, plain divs), brand-bridged. */
import { cn } from "../../lib/utils.js";

export function Card({ className, ...props }) {
  return (
    <div
      className={cn("rounded-[var(--radius)] border border-border bg-card text-card-foreground shadow-[var(--shadow-card)]", className)}
      {...props}
    />
  );
}

export function CardHeader({ className, ...props }) {
  return <div className={cn("flex items-center gap-2 border-b border-border bg-secondary px-3.5 py-2.5", className)} {...props} />;
}

export function CardTitle({ className, ...props }) {
  return <div className={cn("text-[12.5px] font-semibold text-foreground", className)} {...props} />;
}

export function CardContent({ className, ...props }) {
  return <div className={cn("p-3.5", className)} {...props} />;
}

export function CardFooter({ className, ...props }) {
  return <div className={cn("flex items-center gap-2.5 border-t border-border bg-secondary px-3.5 py-2.5", className)} {...props} />;
}
