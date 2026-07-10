/* dialog.jsx — shadcn/ui dialog (copy-in) over @radix-ui/react-dialog, brand-bridged. */
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { Icon } from "../../icons.jsx";
import { cn } from "../../lib/utils.js";

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;

export function DialogContent({ className, children, ...props }) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-[3000] bg-[rgba(26,40,69,0.32)] backdrop-blur-[1px]" />
      <DialogPrimitive.Content
        className={cn(
          "fixed left-1/2 top-1/2 z-[3001] w-full max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-[var(--radius)] border border-border bg-background p-5 shadow-[var(--shadow-pop)] focus:outline-none",
          className,
        )}
        {...props}
      >
        {children}
        <DialogPrimitive.Close className="absolute right-3 top-3 inline-flex h-7 w-7 items-center justify-center rounded-[var(--radius-sm)] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus:outline-none">
          <Icon name="close" size={15} />
        </DialogPrimitive.Close>
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

export function DialogHeader({ className, ...props }) {
  return <div className={cn("mb-3 flex flex-col gap-1", className)} {...props} />;
}

export function DialogTitle({ className, ...props }) {
  return <DialogPrimitive.Title className={cn("text-sm font-semibold text-foreground", className)} {...props} />;
}

export function DialogDescription({ className, ...props }) {
  return <DialogPrimitive.Description className={cn("text-xs text-muted-foreground", className)} {...props} />;
}
