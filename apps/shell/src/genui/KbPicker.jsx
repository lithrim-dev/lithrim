/* KbPicker.jsx — generative-UI input component (tool-kb_picker, SPEC §5b).

   Picks the KB bindings for EvalProfile.kb_bindings. The grounding KB is an
   external vector index (namespace-based); rerank is settled OFF for these
   structured KBs. No KB-list endpoint exists yet, so the available namespaces
   are representative — the widget's job is to collect the binding selection +
   return it via onResult(). No persistence.

   Built on shadcn primitives + the @theme token bridge. */
import { useState } from "react";
import { Button } from "../components/ui/button.jsx";
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "../components/ui/card.jsx";
import { Label } from "../components/ui/label.jsx";
import { Separator } from "../components/ui/separator.jsx";
import { Switch } from "../components/ui/switch.jsx";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select.jsx";
import { Icon } from "../icons.jsx";
import { registerTool } from "./registry.js";

const NAMESPACES = [
  { id: "policy-docs", label: "Policy docs", on: true },
  { id: "style-guide", label: "Style guide", on: true },
  { id: "product-faq", label: "Product FAQ", on: false },
  { id: "past-tickets", label: "Resolved tickets", on: false },
];

export default function KbPicker({ index = "knowledge-base", onResult }) {
  const [bindings, setBindings] = useState(NAMESPACES);
  const [topK, setTopK] = useState("5");
  const [rerank, setRerank] = useState(false); // settled OFF for structured KBs
  const [returned, setReturned] = useState(false);

  const toggle = (id, v) => setBindings((bs) => bs.map((b) => (b.id === id ? { ...b, on: v } : b)));

  const apply = () => {
    const result = {
      kb_bindings: bindings.filter((b) => b.on).map((b) => ({ index, namespace: b.id })),
      top_k: Number(topK),
      rerank,
    };
    setReturned(true);
    onResult?.(result);
  };

  const selectedCount = bindings.filter((b) => b.on).length;

  return (
    <Card className="my-3">
      <CardHeader>
        <span className="text-primary"><Icon name="book" size={15} /></span>
        <CardTitle>Knowledge base</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <Label>Knowledge topics ({selectedCount} selected)</Label>
        <div className="flex flex-col gap-1">
          {bindings.map((b) => (
            <label key={b.id} className="flex items-center gap-2.5 rounded-[var(--radius-sm)] border border-border bg-background px-2.5 py-2">
              <div className="min-w-0 flex-1">
                <div className="text-[13px] font-medium text-foreground">{b.label}</div>
                <div className="font-[family-name:var(--font-mono)] text-[10.5px] text-muted-foreground">{b.id}</div>
              </div>
              <Switch checked={b.on} onCheckedChange={(v) => toggle(b.id, v)} aria-label={`bind ${b.id}`} />
            </label>
          ))}
        </div>
        <Separator />
        <div className="flex items-end gap-4">
          <div className="flex w-28 flex-col gap-1.5">
            <Label>Top-K</Label>
            <Select value={topK} onValueChange={setTopK}>
              <SelectTrigger aria-label="top k"><SelectValue /></SelectTrigger>
              <SelectContent>
                {["3", "5", "8", "12"].map((k) => <SelectItem key={k} value={k}>{k}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <label className="flex items-center gap-2 pb-1.5">
            <Switch checked={rerank} onCheckedChange={setRerank} aria-label="rerank" />
            <span className="text-[12px] text-muted-foreground">Rerank</span>
          </label>
        </div>
      </CardContent>
      <CardFooter>
        <span className="font-[family-name:var(--font-mono)] text-[10.5px] text-muted-foreground">
          {returned ? "bound to profile ✓" : ""}
        </span>
        <Button className="ml-auto" size="sm" onClick={apply} disabled={selectedCount === 0}>Bind KB</Button>
      </CardFooter>
    </Card>
  );
}

registerTool("tool-kb_picker", KbPicker);
