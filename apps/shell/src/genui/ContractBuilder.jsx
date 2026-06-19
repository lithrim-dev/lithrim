/* ContractBuilder.jsx — generative-UI input component (tool-contract_builder, §5b).

   Authors a verification contract in the WS-3a structural-floor shape
   (claim → tool-query → verdict). Mirrors the ontology verification_contracts entry:
       { contract_type, flag_code, question, params, version }
   The active pack may ship seeded contracts or be floor-less; this widget authors
   net-new — no seeded example to clone (expected).

   EVAL-FLOW (W1b): "Add contract" now PERSISTS the contract to the active agent's ontology
   verification_contracts via POST /v1/grounding-contract (the SAME audited write path the
   add_grounding_contract chat tool uses; idempotent replace-by-flag-code), THEN fires
   onResult() — so the rail's Ground-truth step ticks honestly (W1a reads that store). A 404
   (unknown flag) / 422 surfaces inline; nothing fires onResult on a failed write. Built on
   shadcn primitives + the @theme token bridge; the Preview opens the built contract in a Dialog. */
import { useState } from "react";
import { putGroundingContract } from "../bff.js";
import { Button } from "../components/ui/button.jsx";
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "../components/ui/card.jsx";
import { Input } from "../components/ui/input.jsx";
import { Label } from "../components/ui/label.jsx";
import { Separator } from "../components/ui/separator.jsx";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select.jsx";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogTrigger } from "../components/ui/dialog.jsx";
import { Icon } from "../icons.jsx";
import { registerTool } from "./registry.js";

// FAUTH-1 (R4): the inline type list is scoped to contract_types with a REGISTERED engine
// executor — surfacing the builder inline makes this selectable by a non-coder, and an
// unregistered type makes ground() RAISE at grade time (grounding.py:592-600). presence_check is
// the always-registered core suppress executor; snomed_subsumption + record_presence are the
// pack-registered grounding types add_grounding_contract advertises. The prior list's
// negation_check / code_match / range_check have NO executor (the footgun) — removed. The deeper
// registration GATE (refuse a free-text/LLM executor; refuse a type with no executor for the
// active pack) is FAUTH-2/G3, not this cycle.
export const CONTRACT_TYPES = ["presence_check", "snomed_subsumption", "record_presence"];

function Field({ label, children }) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label>{label}</Label>
      {children}
    </div>
  );
}

// FAUTH-1 (G1): ``flagCode`` SEEDS the card pre-bound to the in-context flag — when the agent
// surfaces this inline (author_contract → tool-contract_builder), renderTool spreads
// part.output = {agent, flag_code} as props, so the wire key is ``flag_code`` (snake); accept
// either it or the camel ``flagCode`` (direct-render ergonomics). Defaults to "" (back-compat:
// the pane-mounted + scripted-showcase paths are unchanged). If left blank, the widget's own
// validation gates Save (R5).
export default function ContractBuilder({ agent = "ws0_default", flagCode: seedFlag, flag_code, onResult }) {
  const [contractType, setContractType] = useState("presence_check");
  const [flagCode, setFlagCode] = useState(seedFlag ?? flag_code ?? "");
  const [question, setQuestion] = useState("");
  const [paramsText, setParamsText] = useState('{\n  "source": "response.claims"\n}');
  const [version, setVersion] = useState("");
  const [returned, setReturned] = useState(false);
  const [persist, setPersist] = useState({ state: "idle", msg: "" }); // idle|saving|saved|error

  let params = {}, paramsValid = true;
  try { params = JSON.parse(paramsText || "{}"); } catch { paramsValid = false; }

  const contract = {
    contract_type: contractType,
    flag_code: flagCode.trim(),
    question: question.trim(),
    params,
    version: version.trim() || `${flagCode.trim() || "contract"}/v1`,
  };
  const valid = paramsValid && contract.flag_code && contract.question;

  // W1b: persist to ontology.verification_contracts (the grade's store) THEN signal up — the
  // save IS the approval gate (mirrors FlagEditor.persistEdit). Only a successful audited write
  // fires onResult, so the rail can never tick on an unsaved/failed contract (honest tick).
  const apply = async () => {
    setPersist({ state: "saving", msg: "saving…" });
    try {
      await putGroundingContract(contract, agent);
      setPersist({ state: "saved", msg: "added to setup ✓" });
      setReturned(true);
      onResult?.(contract);
    } catch (e) {
      setPersist({ state: "error", msg: String(e.message || e) });
    }
  };

  return (
    <Card className="my-3">
      <CardHeader>
        <span className="text-primary"><Icon name="shield" size={15} /></span>
        <CardTitle>Verification contract</CardTitle>
        <span className="font-[family-name:var(--font-mono)] text-[10.5px] text-muted-foreground">claim → tool-query → verdict</span>
      </CardHeader>
      <CardContent className="flex flex-col gap-3.5">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Claim · flag code">
            <Input value={flagCode} onChange={(e) => setFlagCode(e.target.value)} placeholder="MEDICATION_NOT_IN_TRANSCRIPT" aria-label="flag code" />
          </Field>
          <Field label="Tool query · type">
            <Select value={contractType} onValueChange={setContractType}>
              <SelectTrigger aria-label="contract type"><SelectValue /></SelectTrigger>
              <SelectContent>
                {CONTRACT_TYPES.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
              </SelectContent>
            </Select>
          </Field>
        </div>
        <Field label="Question">
          <Input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Is the flagged medication actually present in the transcript?" aria-label="question" />
        </Field>
        <Field label="Params (JSON)">
          <textarea
            className="min-h-[72px] w-full rounded-[var(--radius-sm)] border border-input bg-background px-2.5 py-2 font-[family-name:var(--font-mono)] text-[12px] text-foreground outline-none focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-ring/30 aria-[invalid=true]:border-[color:var(--accent)]"
            value={paramsText}
            onChange={(e) => setParamsText(e.target.value)}
            aria-invalid={!paramsValid}
            aria-label="params json"
          />
          {!paramsValid && <span className="text-[10.5px] text-[color:var(--accent-ink)]">Invalid JSON</span>}
        </Field>
        <Separator />
        <Field label="Verdict direction">
          <div className="flex items-center gap-2 text-[12px] text-muted-foreground">
            <span className="rounded-[var(--radius-sm)] bg-secondary px-2 py-0.5 text-[color:var(--teal)]">PASS</span>
            <Icon name="arrowR" size={13} />
            <span className="rounded-[var(--radius-sm)] bg-accent px-2 py-0.5 text-[color:var(--accent-ink)]">BLOCK on violation</span>
            <span className="ml-1">structural floor</span>
          </div>
        </Field>
      </CardContent>
      <CardFooter>
        <Dialog>
          <DialogTrigger asChild>
            <Button variant="ghost" size="sm" disabled={!valid}><Icon name="note" size={14} /> Preview</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Contract preview</DialogTitle>
              <DialogDescription>The verification_contracts entry this builds.</DialogDescription>
            </DialogHeader>
            <pre className="max-h-72 overflow-auto rounded-[var(--radius-sm)] border border-border bg-secondary p-3 font-[family-name:var(--font-mono)] text-[11.5px] text-foreground">
              {JSON.stringify(contract, null, 2)}
            </pre>
          </DialogContent>
        </Dialog>
        <span
          className={
            "font-[family-name:var(--font-mono)] text-[10.5px] " +
            (persist.state === "error" ? "text-[color:var(--accent-ink)]" : "text-muted-foreground")
          }
        >
          {persist.state !== "idle" ? persist.msg : returned ? "added to setup ✓" : "net-new contract"}
        </span>
        <Button className="ml-auto" size="sm" onClick={apply} disabled={!valid || persist.state === "saving"}>
          {persist.state === "saving" ? "Saving…" : "Add contract"}
        </Button>
      </CardFooter>
    </Card>
  );
}

registerTool("tool-contract_builder", ContractBuilder);
