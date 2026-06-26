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
import { useEffect, useState } from "react";
import { putGroundingContract, getGroundingContractTypes } from "../bff.js";
import { Button } from "../components/ui/button.jsx";
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "../components/ui/card.jsx";
import { Input } from "../components/ui/input.jsx";
import { Label } from "../components/ui/label.jsx";
import { Separator } from "../components/ui/separator.jsx";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select.jsx";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogTrigger } from "../components/ui/dialog.jsx";
import { Icon } from "../icons.jsx";
import { flagLabel, friendlyError } from "./copy.js";
import { registerTool } from "./registry.js";

// Plain DISPLAY labels for the contract-type keys (the underlying value/key is unchanged — these
// only relabel what the user reads in the Select). Unmapped keys fall through to the raw key.
const CONTRACT_TYPE_LABELS = {
  presence_check: "Must be in the record",
  snomed_subsumption: "Medical-term match",
  record_presence: "Was actually recorded",
};
const contractTypeLabel = (t) => CONTRACT_TYPE_LABELS[t] || t;

// FAUTH-2 (G3): the inline type list is now driven LIVE by the active pack's registered executor
// keys (GET /v1/grounding-contract/types → suppress ∪ floor), fetched on mount — retiring the
// hand-maintained static guard (S-BS-FAUTH1-1). This list below is the OFFLINE / first-paint /
// fetch-reject FALLBACK only (the pane-mounted + scripted-showcase paths run with no server).
// presence_check is the always-registered core suppress executor; snomed_subsumption +
// record_presence are the pack-registered grounding types add_grounding_contract advertises; the
// broken negation_check / code_match / range_check (no executor → ground() raises) stay out.
// The author-time GATE now also exists server-side: _put_grounding_contract refuses an
// unregistered contract_type with a 422 (FAUTH-2) — so an off-list type can't be pinned even if
// it reaches the wire. (The deeper oracle_kind executor-marker gate is FAUTH-2b, cross-repo.)
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
// FAUTH-3 (G2, the ASSIST keystone): the agent's assist may also spread ``suggested_params`` (a
// prose→params draft) + ``question`` — DRAFT seeds that PRE-FILL the EDITABLE params/question
// fields. They are defaults only: the human edits them and the human's Save is the sole audited
// write (surfacing the pre-filled card writes NOTHING). Absent → the byte-identical FAUTH-1 behavior.
export default function ContractBuilder({ agent = "ws0_default", flagCode: seedFlag, flag_code, suggested_params, question: seedQuestion, contract_type: seedType, onResult }) {
  // FAUTH-3 / S-BS-143: the agent-chosen DIRECTION seeds the type — value_presence (FLOOR, can flip
  // APPROVE→BLOCK) vs presence_check (SUPPRESS, the back-compat default when no type is seeded).
  const [contractType, setContractType] = useState(seedType || "presence_check");
  // FAUTH-2 (G3): the type list is driven by the active pack's registered executors; init to the
  // static fallback so first paint + offline (vitest / scripted-showcase) never crash, then
  // replace it with the live set on a resolved fetch (keep the fallback on reject). S-BS-143: always
  // keep the SEEDED type selectable (merge it in) so a non-coder can keep/re-pick the agent's choice
  // even if the live/fallback set omits it (e.g. a pack-specific floor type).
  const withSeed = (types) => (seedType && !types.includes(seedType) ? [...types, seedType] : types);
  const [contractTypes, setContractTypes] = useState(withSeed(CONTRACT_TYPES));
  useEffect(() => {
    let live = true;
    getGroundingContractTypes()
      .then((r) => { if (live && Array.isArray(r?.contract_types) && r.contract_types.length) setContractTypes(withSeed(r.contract_types)); })
      .catch(() => {}); // offline / first paint → keep the static fallback
    return () => { live = false; };
  }, []);
  const [flagCode, setFlagCode] = useState(seedFlag ?? flag_code ?? "");
  const [question, setQuestion] = useState(seedQuestion ?? "");
  // FAUTH-3: pre-fill the editable params from the agent's suggested_params draft; else the inert default.
  const [paramsText, setParamsText] = useState(
    suggested_params ? JSON.stringify(suggested_params, null, 2) : '{\n  "source": "response.claims"\n}',
  );
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

  // INLINE-IMPACT-1: a live plain-English restatement so authoring reads as writing a GUARDRAIL, not
  // filling a form — updates as the human edits. value_presence (FLOOR) blocks on an absent stated
  // value; everything else is the suppress/floor default phrasing.
  const fc = flagLabel(contract.flag_code) || "this check";
  const src = params.source_path || params.med_source || params.source || "the source";
  const ruleEnglish =
    contractType === "value_presence"
      ? `Fact-check for ${fc}: require that a value matching /${params.value_regex || "…"}/ stated in "${src}" is recorded in the note.` +
        `${contract.question ? ` Check: ${contract.question}` : ""} If it's missing, flag the result automatically — no model call.`
      : `Rule for ${fc}: ${contract.question || "verify the flagged claim"} — checked against "${src}". A violation flags the result automatically — no model call.`;

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
      setPersist({ state: "error", msg: friendlyError(e) });
    }
  };

  return (
    <Card className="my-3">
      <CardHeader>
        <span className="text-primary"><Icon name="shield" size={15} /></span>
        <CardTitle>Fact-check</CardTitle>
        <span className="font-semibold text-[11px] text-primary">Automated fact-check</span>
        {suggested_params && (
          <span className="rounded-full bg-secondary px-2 py-0.5 text-[10px] text-muted-foreground">AI-suggested</span>
        )}
        <span className="font-[family-name:var(--font-mono)] text-[10.5px] text-muted-foreground">claim → check → result</span>
      </CardHeader>
      <CardContent className="flex flex-col gap-3.5">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Claim · flag code">
            <Input value={flagCode} onChange={(e) => setFlagCode(e.target.value)} placeholder='e.g. "Medication not in transcript"' aria-label="flag code" />
          </Field>
          <Field label="Tool query · type">
            <Select value={contractType} onValueChange={setContractType}>
              <SelectTrigger aria-label="contract type"><SelectValue /></SelectTrigger>
              <SelectContent>
                {contractTypes.map((t) => <SelectItem key={t} value={t}>{contractTypeLabel(t)}</SelectItem>)}
              </SelectContent>
            </Select>
          </Field>
        </div>
        <Field label="Question">
          <Input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Is the flagged medication actually present in the transcript?" aria-label="question" />
        </Field>
        {/* INLINE-IMPACT-1: the rule in plain English, live — authoring reads as writing a guardrail. */}
        <div data-testid="rule-in-english" className="rounded-[var(--radius-sm)] border border-border bg-secondary px-3 py-2 text-[12px] leading-relaxed text-foreground">
          {ruleEnglish}
        </div>
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
        <Field label="Result direction">
          <div className="flex items-center gap-2 text-[12px] text-muted-foreground">
            <span className="rounded-[var(--radius-sm)] bg-secondary px-2 py-0.5 text-[color:var(--teal)]">Passed</span>
            <Icon name="arrowR" size={13} />
            <span className="rounded-[var(--radius-sm)] bg-accent px-2 py-0.5 text-[color:var(--accent-ink)]">Flagged on violation</span>
            <span className="ml-1">automated fact-check</span>
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
              <DialogDescription>The fact-check this adds.</DialogDescription>
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
