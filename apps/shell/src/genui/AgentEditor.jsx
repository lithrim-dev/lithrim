/* AgentEditor.jsx — generative-UI input component (tool-agent_editor, UAP-1 R1).

   The config-plane write surface: load an assembled Agent via GET /v1/agent, edit the
   eval-profile (judges + ontology_ref + tools + kb_bindings), and PUT /v1/agent to
   persist it to the config plane. The write is attributed — the SME handle rides the
   X-Actor header (the §2B audit "who") + an optional rationale (the "why"). NEVER
   writes the committed seed; the BFF writes the (non-committed) config DB only.

   All fetches route through bff.js (S-BS-50 — no hardcoded :8787). Minimal by intent:
   UAP-1 is the write-path + audit foundation, not the full JudgeEditor (UAP-2). */
import { useEffect, useState } from "react";
import { getAgent, putAgent } from "../bff.js";
import { Button } from "../components/ui/button.jsx";
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "../components/ui/card.jsx";
import { Input } from "../components/ui/input.jsx";
import { Label } from "../components/ui/label.jsx";
import { Separator } from "../components/ui/separator.jsx";
import { Icon } from "../icons.jsx";
import { friendlyError } from "./copy.js";
import { registerTool } from "./registry.js";

const csv = (xs) => (xs || []).join(", ");
const parseCsv = (s) => s.split(",").map((x) => x.trim()).filter(Boolean);

export default function AgentEditor({ agent = "ws0_default", onResult }) {
  const [status, setStatus] = useState("loading"); // loading | ready | error
  const [error, setError] = useState(null);
  const [raw, setRaw] = useState(null); // the full loaded Agent — merged back on save
  const [judges, setJudges] = useState("");
  const [tools, setTools] = useState("");
  const [ontologyRef, setOntologyRef] = useState("");
  const [actor, setActor] = useState("");
  const [rationale, setRationale] = useState("");
  const [save, setSave] = useState({ state: "idle", msg: "" }); // idle|saving|saved|error

  useEffect(() => {
    let live = true;
    getAgent(agent)
      .then((a) => {
        if (!live) return;
        setRaw(a);
        const ep = a.eval_profile || {};
        setJudges(csv(ep.judges));
        setTools(csv(ep.tools));
        setOntologyRef(ep.ontology_ref || "");
        setStatus("ready");
      })
      .catch((e) => {
        if (!live) return;
        setError(String(e.message || e));
        setStatus("error");
      });
    return () => { live = false; };
  }, [agent]);

  if (status === "loading")
    return <Card><CardContent className="text-xs text-muted-foreground">Loading agent…</CardContent></Card>;
  if (status === "error")
    return (
      <Card>
        <CardContent className="text-xs text-[color:var(--accent-ink)]">
          {friendlyError(error)}
        </CardContent>
      </Card>
    );

  // Merge the edits back into the FULL loaded Agent so the PUT body round-trips through
  // the BFF's agent_from_dict validator (a partial body → 422).
  const edited = () => ({
    ...raw,
    eval_profile: {
      ...(raw.eval_profile || {}),
      judges: parseCsv(judges),
      tools: parseCsv(tools),
      ontology_ref: ontologyRef,
    },
  });

  const persist = async () => {
    setSave({ state: "saving", msg: "saving…" });
    try {
      const body = edited();
      const res = await putAgent(body, { actor: actor || undefined, rationale });
      setSave({ state: "saved", msg: `saved ✓ as ${res.actor?.id || "dev-default"}` });
      onResult?.(body);
      return res;
    } catch (e) {
      setSave({ state: "error", msg: friendlyError(e) });
    }
  };

  return (
    <Card className="my-3">
      <CardHeader>
        <span className="text-primary"><Icon name="layers" size={15} /></span>
        <CardTitle>Agent · {raw.name}</CardTitle>
        <span className="text-[10.5px] text-muted-foreground">
          saved + logged (who &amp; why)
        </span>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="ae-judges">Reviewers</Label>
          <Input id="ae-judges" value={judges} onChange={(e) => setJudges(e.target.value)}
            placeholder="risk_judge, policy_judge, faithfulness_judge" />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="ae-tools">Fact-checks</Label>
          <Input id="ae-tools" value={tools} onChange={(e) => setTools(e.target.value)}
            placeholder="kb_grounding, presence_check" />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="ae-ont">Checklist</Label>
          <Input id="ae-ont" value={ontologyRef} onChange={(e) => setOntologyRef(e.target.value)}
            placeholder="_core/1" />
        </div>
        <Separator />
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ae-actor">Your name</Label>
            <Input id="ae-actor" value={actor} onChange={(e) => setActor(e.target.value)}
              placeholder="you@example.com" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ae-why">Reason for this change</Label>
            <Input id="ae-why" value={rationale} onChange={(e) => setRationale(e.target.value)}
              placeholder="why this change" />
          </div>
        </div>
      </CardContent>
      <CardFooter>
        <span
          className={
            "font-[family-name:var(--font-mono)] text-[10.5px] " +
            (save.state === "error" ? "text-[color:var(--accent-ink)]" : "text-muted-foreground")
          }
        >
          {save.state !== "idle" ? save.msg : "Saved to this workspace when you click Save"}
        </span>
        <Button className="ml-auto" size="sm" onClick={persist} disabled={save.state === "saving"}>
          {save.state === "saving" ? "Saving…" : "Save agent"}
        </Button>
      </CardFooter>
    </Card>
  );
}

registerTool("tool-agent_editor", AgentEditor);
