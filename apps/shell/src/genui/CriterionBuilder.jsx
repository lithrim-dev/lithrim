/* CriterionBuilder.jsx — generative-UI input component (tool-criterion_builder, NARR-5-CRIT-b).

   Mints a new GRADEABLE criterion (a scoreable taxonomy code the council can RAISE) by filling a
   card in the chat. SPINE/CONTAINMENT invariant: "Add criterion" PERSISTS via POST /v1/criterion
   (the sanctioned snapshot writer — splices the active tier:core pack's taxonomy snapshot tiers +
   lenses + tier1_owners + the ontology overlay, audited), THEN fires onResult(). The human's Save
   is the SOLE write of the contract-of-record; the agent never mints a code. A 409 (duplicate) /
   422 (non-core pack / unknown owner / bad tier / malformed code) surfaces inline; nothing fires
   onResult on a failed write. The mirror is ContractBuilder (a $0 surface; the human's Save writes). */
import { useState } from "react";
import { postCriterion } from "../bff.js";
import { Button } from "../components/ui/button.jsx";
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "../components/ui/card.jsx";
import { Input } from "../components/ui/input.jsx";
import { Label } from "../components/ui/label.jsx";
import { Separator } from "../components/ui/separator.jsx";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select.jsx";
import { Icon } from "../icons.jsx";
import { friendlyError } from "./copy.js";
import { registerTool } from "./registry.js";

// The three council tiers (the ontology-flag short form; the writer maps to the snapshot tier-set).
export const TIERS = ["TIER_1", "TIER_2", "TIER_3"];
// A taxonomy code is an uppercase-led SCREAMING_SNAKE token — mirror the server-side guard (F1) so
// the card gates Save locally and the human never round-trips a 422 for an obvious typo.
const CODE_RE = /^[A-Z][A-Z0-9_]*$/;

function Field({ label, children }) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label>{label}</Label>
      {children}
    </div>
  );
}

// The registry spreads part.output = {agent, code, tier, owner_role, definition, when_to_use,
// when_NOT_to_use} as props (author_criterion's seed — the agent may DRAFT the criterion text;
// the human's Save stays the sole write). Defaults keep the direct-render / offline (vitest)
// paths working with no server.
export default function CriterionBuilder({ agent = "ws0_default", code: seedCode, tier: seedTier, owner_role: seedOwner, definition: seedDef, when_to_use: seedWhen, when_NOT_to_use: seedWhenNot, onResult }) {
  const [code, setCode] = useState(seedCode ?? "");
  const [tier, setTier] = useState(seedTier || "TIER_2");
  const [ownerRole, setOwnerRole] = useState(seedOwner ?? "");
  const [definition, setDefinition] = useState(seedDef ?? "");
  // CRITERION-TEXT-1: when_to_use is the lens line the owning judge's prompt renders — collect
  // it at mint time so the criterion is born with its text, not minted blank.
  const [whenToUse, setWhenToUse] = useState(seedWhen ?? "");
  const [whenNotToUse, setWhenNotToUse] = useState(seedWhenNot ?? "");
  const [returned, setReturned] = useState(false);
  const [persist, setPersist] = useState({ state: "idle", msg: "" }); // idle|saving|saved|error

  const criterion = {
    code: code.trim(),
    tier,
    owner_role: ownerRole.trim(),
    definition: definition.trim(),
    when_to_use: whenToUse.trim(),
    when_NOT_to_use: whenNotToUse.trim(),
  };
  const codeValid = CODE_RE.test(criterion.code);
  const valid = codeValid && criterion.owner_role;

  // Save IS the approval gate: only a successful audited mint fires onResult (mirrors ContractBuilder).
  const apply = async () => {
    setPersist({ state: "saving", msg: "minting…" });
    try {
      await postCriterion(criterion, agent);
      setPersist({ state: "saved", msg: "criterion minted ✓" });
      setReturned(true);
      onResult?.(criterion);
    } catch (e) {
      setPersist({ state: "error", msg: friendlyError(e) });
    }
  };

  return (
    <Card className="my-3">
      <CardHeader>
        <span className="text-primary"><Icon name="shield" size={15} /></span>
        <CardTitle>Gradeable criterion</CardTitle>
        <span className="font-[family-name:var(--font-mono)] text-[10.5px] text-muted-foreground">a scoreable code the council can raise</span>
      </CardHeader>
      <CardContent className="flex flex-col gap-3.5">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Code">
            <Input value={code} onChange={(e) => setCode(e.target.value)} placeholder="EVERY_DOSE_IN_SOAP" aria-label="criterion code" aria-invalid={code.length > 0 && !codeValid} />
          </Field>
          <Field label="Tier">
            <Select value={tier} onValueChange={setTier}>
              <SelectTrigger aria-label="tier"><SelectValue /></SelectTrigger>
              <SelectContent>
                {TIERS.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
              </SelectContent>
            </Select>
          </Field>
        </div>
        <Field label="Owner · production judge">
          <Input value={ownerRole} onChange={(e) => setOwnerRole(e.target.value)} placeholder="faithfulness_judge" aria-label="owner role" />
        </Field>
        <Field label="Definition">
          <Input value={definition} onChange={(e) => setDefinition(e.target.value)} placeholder="Every dose stated in the transcript must appear in the SOAP." aria-label="definition" />
        </Field>
        <Field label="When to use — the lens the owning judge reads">
          <textarea
            value={whenToUse}
            onChange={(e) => setWhenToUse(e.target.value)}
            rows={3}
            spellCheck={false}
            aria-label="when to use"
            placeholder="1) A dose stated in the transcript is absent from the note."
            className="resize-y rounded-[var(--radius-sm)] border border-border bg-background px-3 py-2 text-[12px] leading-snug text-foreground"
          />
        </Field>
        <Field label="When NOT to use">
          <textarea
            value={whenNotToUse}
            onChange={(e) => setWhenNotToUse(e.target.value)}
            rows={2}
            spellCheck={false}
            aria-label="when NOT to use"
            placeholder="The dose appears with different but equivalent units."
            className="resize-y rounded-[var(--radius-sm)] border border-border bg-background px-3 py-2 text-[12px] leading-snug text-foreground"
          />
        </Field>
        {code.length > 0 && !codeValid && <span className="text-[10.5px] text-[color:var(--accent-ink)]">Code must be UPPER_SNAKE (e.g. EVERY_DOSE_IN_SOAP)</span>}
        <Separator />
        <Field label="What this does">
          <div className="flex items-center gap-2 text-[12px] text-muted-foreground">
            <span className="rounded-[var(--radius-sm)] bg-secondary px-2 py-0.5 text-[color:var(--teal)]">snapshot</span>
            <Icon name="arrowR" size={13} />
            <span className="rounded-[var(--radius-sm)] bg-secondary px-2 py-0.5 text-[color:var(--teal)]">owner lens</span>
            <span className="ml-1">the judge may then raise it (audited)</span>
          </div>
        </Field>
      </CardContent>
      <CardFooter>
        <span
          className={
            "font-[family-name:var(--font-mono)] text-[10.5px] " +
            (persist.state === "error" ? "text-[color:var(--accent-ink)]" : "text-muted-foreground")
          }
        >
          {persist.state !== "idle" ? persist.msg : returned ? "criterion minted ✓" : "net-new gradeable criterion"}
        </span>
        <Button className="ml-auto" size="sm" onClick={apply} disabled={!valid || persist.state === "saving"}>
          {persist.state === "saving" ? "Minting…" : "Add criterion"}
        </Button>
      </CardFooter>
    </Card>
  );
}

registerTool("tool-criterion_builder", CriterionBuilder);
