/* utils.js — the shadcn `cn()` helper: merge conditional class lists and resolve
   Tailwind utility conflicts (last-wins). Used by components/ui/* + genui/*. */
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}
