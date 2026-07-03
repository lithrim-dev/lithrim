/* FlagEditor.jsx — generative-UI input component (tool-flag_editor, SPEC §5b).

   The ontology editor's first appearance. Reads the agent's committed ontology via
   GET /v1/ontology and surfaces TWO distinct things, per the ontology's actual schema:

     1. per-flag {tier, gradeable, owner_roles}  — gradeable/tier are editable,
        owner_roles shown read-only (ground-truth ownership per the invariant);
     2. the GLOBAL severity_map {block_at_or_above, warn_above, weights{HIGH/MED/LOW}}.

   Severity is NOT a per-flag field — the HIGH/MEDIUM/LOW weights are global. Two
   distinct return paths (WS-5d): the edited config is returned via onResult() into
   conversation/UI state, AND "Persist draft" writes it via PUT /v1/ontology to a
   BFF-local working copy (NOT the committed seed — drafts do not feed an eval run;
   S-BS-26). Built on shadcn primitives + the @theme token bridge. */
import { useEffect, useState } from "react";
import { getOntology, putOntology } from "../bff.js";
import { Button } from "../components/ui/button.jsx";
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "../components/ui/card.jsx";
import { Label } from "../components/ui/label.jsx";
import { Separator } from "../components/ui/separator.jsx";
import { Slider } from "../components/ui/slider.jsx";
import { Switch } from "../components/ui/switch.jsx";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select.jsx";
import { Icon } from "../icons.jsx";
import { friendlyError } from "./copy.js";
import { registerTool } from "./registry.js";

const TIERS = ["TIER_1", "TIER_2", "TIER_3", "none"];

function ThresholdRow({ label, value, onChange }) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between">
        <Label>{label}</Label>
        <span className="font-[family-name:var(--font-mono)] text-[13px] font-semibold text-foreground">{value.toFixed(2)}</span>
      </div>
      <Slider min={0} max={1} step={0.05} value={[value]} onValueChange={([v]) => onChange(v)} aria-label={label} />
    </div>
  );
}

export default function FlagEditor({ agent = "ws0_default", onResult }) {
  const [status, setStatus] = useState("loading"); // loading | ready | error
  const [error, setError] = useState(null);
  const [raw, setRaw] = useState(null); // the full loaded ontology — merged back on persist
  const [severity, setSeverity] = useState(null);
  const [flags, setFlags] = useState([]);
  const [returned, setReturned] = useState(false);
  const [persist, setPersist] = useState({ state: "idle", msg: "" }); // idle|saving|saved|error
  const [openText, setOpenText] = useState(() => new Set()); // flag codes with the text editor expanded
  // R1b: which case fields fold into the judge-visible grading context (comma-separated names).
  const [contextFields, setContextFields] = useState("");

  useEffect(() => {
    let live = true;
    getOntology(agent)
      .then((ont) => {
        if (!live) return;
        setRaw(ont);
        setSeverity(ont.severity_map || { block_at_or_above: 0.5, warn_above: 0, weights: {} });
        setContextFields((ont.grading_context_fields || []).join(", "));
        setFlags(
          (ont.flags || []).map((f) => ({
            flag: f.flag,
            category: f.category,
            tier: f.tier || "none",
            gradeable: !!f.gradeable,
            owner_roles: f.owner_roles || [],
            // CRITERION-TEXT-1: the criterion text is editable — when_to_use is the lens
            // line the owning judge's prompt renders, so rewording it IS the calibration edit.
            definition: f.definition || "",
            when_to_use: f.when_to_use || "",
            when_NOT_to_use: f.when_NOT_to_use || "",
          })),
        );
        setStatus("ready");
      })
      .catch((e) => {
        if (!live) return;
        setError(friendlyError(e));
        setStatus("error");
      });
    return () => { live = false; };
  }, [agent]);

  if (status === "loading")
    return <Card><CardContent className="text-xs text-muted-foreground">Loading your checks…</CardContent></Card>;
  if (status === "error")
    return (
      <Card>
        <CardContent className="text-xs text-[color:var(--accent-ink)] font-[family-name:var(--font-mono)]">
          We couldn't load your checks. Please try again.
        </CardContent>
      </Card>
    );

  const setWeight = (k, v) => setSeverity((s) => ({ ...s, weights: { ...s.weights, [k]: v } }));
  const setFlag = (i, patch) => setFlags((fs) => fs.map((f, j) => (j === i ? { ...f, ...patch } : f)));

  const toggleText = (code) =>
    setOpenText((s) => {
      const next = new Set(s);
      next.has(code) ? next.delete(code) : next.add(code);
      return next;
    });

  const apply = () => {
    const result = {
      severity_map: severity,
      flags: flags.map(({ flag, tier, gradeable, owner_roles, definition, when_to_use, when_NOT_to_use }) => ({
        flag,
        tier: tier === "none" ? null : tier,
        gradeable,
        owner_roles,
        definition,
        when_to_use,
        when_NOT_to_use,
      })),
    };
    setReturned(true);
    onResult?.(result);
  };

  const parsedContextFields = () =>
    contextFields.split(",").map((s) => s.trim()).filter(Boolean);

  // Merge the edits back into the FULL loaded ontology (so the PUT body round-trips
  // through the BFF's ontology.from_dict validator) and persist to the working copy.
  // Distinct from apply(): apply() returns into setup state; persist() writes a draft.
  const edited = () => ({
    ...raw,
    severity_map: severity,
    grading_context_fields: parsedContextFields(),
    flags: (raw.flags || []).map((rf) => {
      const e = flags.find((f) => f.flag === rf.flag);
      return e
        ? {
            ...rf,
            tier: e.tier === "none" ? null : e.tier,
            gradeable: e.gradeable,
            definition: e.definition,
            when_to_use: e.when_to_use,
            when_NOT_to_use: e.when_NOT_to_use,
          }
        : rf;
    }),
  });

  const persistEdit = async () => {
    setPersist({ state: "saving", msg: "saving…" });
    try {
      const res = await putOntology(edited(), agent);
      setPersist({ state: "saved", msg: "draft saved ✓" });
      return res;
    } catch (e) {
      setPersist({ state: "error", msg: friendlyError(e) });
    }
  };

  return (
    <Card className="my-3">
      <CardHeader>
        <span className="text-primary"><Icon name="flag" size={15} /></span>
        <CardTitle>Checks &amp; severity</CardTitle>
        <span className="font-[family-name:var(--font-mono)] text-[10.5px] text-muted-foreground">
          {flags.length} flags · editable draft
        </span>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <section className="flex flex-col gap-3">
          <Label>Severity map (global)</Label>
          <ThresholdRow label="Block at or above" value={severity.block_at_or_above ?? 0.5} onChange={(v) => setSeverity((s) => ({ ...s, block_at_or_above: v }))} />
          <ThresholdRow label="Warn above" value={severity.warn_above ?? 0} onChange={(v) => setSeverity((s) => ({ ...s, warn_above: v }))} />
          <div className="grid grid-cols-3 gap-3">
            {["HIGH", "MEDIUM", "LOW"].map((k) => (
              <ThresholdRow key={k} label={`weight · ${k}`} value={severity.weights?.[k] ?? 0} onChange={(v) => setWeight(k, v)} />
            ))}
          </div>
        </section>

        <Separator />

        {/* R1b: which case fields (beyond the transcript) the reviewers see as SOURCE RECORD
            sections at grade time — e.g. a problem list or account record the case carries. */}
        <section className="flex flex-col gap-1.5">
          <Label>Grading context fields</Label>
          <input
            value={contextFields}
            onChange={(e) => setContextFields(e.target.value)}
            spellCheck={false}
            aria-label="grading context fields"
            placeholder="comma-separated case fields, e.g. patient_profile"
            className="rounded-[var(--radius-sm)] border border-border bg-background px-2.5 py-1.5 text-[11.5px] text-foreground"
          />
          <span className="text-[10.5px] text-muted-foreground">
            Case fields folded into what reviewers read, alongside the transcript
          </span>
        </section>

        <Separator />

        <section className="flex flex-col gap-2">
          <Label>Flags (tier · gradeable · owners)</Label>
          <div className="flex max-h-64 flex-col gap-1 overflow-y-auto pr-1">
            {flags.map((f, i) => (
              <div key={f.flag} className="flex flex-col rounded-[var(--radius-sm)] border border-border bg-background px-2.5 py-2">
                <div className="flex items-center gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-[family-name:var(--font-mono)] text-[12px] font-medium text-foreground">{f.flag}</div>
                    <div className="truncate text-[10.5px] text-muted-foreground">
                      {f.owner_roles.length ? f.owner_roles.join(" · ") : "no owner"}
                    </div>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-7 px-2 text-[10.5px]"
                    onClick={() => toggleText(f.flag)}
                    aria-label={`edit criterion text for ${f.flag}`}
                    aria-expanded={openText.has(f.flag)}
                  >
                    <Icon name="pencil" size={12} />
                  </Button>
                  <div className="w-28 shrink-0">
                    <Select value={f.tier} onValueChange={(v) => setFlag(i, { tier: v })}>
                      <SelectTrigger className="h-7" aria-label={`tier for ${f.flag}`}><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {TIERS.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <Switch checked={f.gradeable} onCheckedChange={(v) => setFlag(i, { gradeable: v })} aria-label={`gradeable ${f.flag}`} />
                </div>
                {openText.has(f.flag) && (
                  /* CRITERION-TEXT-1: when_to_use is what the owning judge's prompt renders —
                     the reword→re-run calibration edit happens here. */
                  <div className="mt-2 flex flex-col gap-2 border-t border-border pt-2">
                    <div className="flex flex-col gap-1">
                      <Label className="text-[10.5px]">When to use — the lens the owning judge reads</Label>
                      <textarea
                        value={f.when_to_use}
                        onChange={(e) => setFlag(i, { when_to_use: e.target.value })}
                        rows={3}
                        spellCheck={false}
                        aria-label={`when to use for ${f.flag}`}
                        className="resize-y rounded-[var(--radius-sm)] border border-border bg-background px-2.5 py-1.5 text-[11.5px] leading-snug text-foreground"
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <Label className="text-[10.5px]">When NOT to use</Label>
                      <textarea
                        value={f.when_NOT_to_use}
                        onChange={(e) => setFlag(i, { when_NOT_to_use: e.target.value })}
                        rows={2}
                        spellCheck={false}
                        aria-label={`when NOT to use for ${f.flag}`}
                        className="resize-y rounded-[var(--radius-sm)] border border-border bg-background px-2.5 py-1.5 text-[11.5px] leading-snug text-foreground"
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <Label className="text-[10.5px]">Definition</Label>
                      <textarea
                        value={f.definition}
                        onChange={(e) => setFlag(i, { definition: e.target.value })}
                        rows={2}
                        spellCheck={false}
                        aria-label={`definition for ${f.flag}`}
                        className="resize-y rounded-[var(--radius-sm)] border border-border bg-background px-2.5 py-1.5 text-[11.5px] leading-snug text-foreground"
                      />
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      </CardContent>
      <CardFooter>
        <span
          className={
            "font-[family-name:var(--font-mono)] text-[10.5px] " +
            (persist.state === "error" ? "text-[color:var(--accent-ink)]" : "text-muted-foreground")
          }
        >
          {persist.state !== "idle"
            ? persist.msg
            : returned
              ? "saved ✓"
              : "returns into setup · draft-persists to a working copy"}
        </span>
        <Button
          className="ml-auto"
          size="sm"
          variant="ghost"
          onClick={persistEdit}
          disabled={persist.state === "saving"}
        >
          {persist.state === "saving" ? "Saving…" : "Persist draft"}
        </Button>
        <Button size="sm" onClick={apply}>Apply config</Button>
      </CardFooter>
    </Card>
  );
}

registerTool("tool-flag_editor", FlagEditor);
