/* ToolBuilder.jsx — generative-UI input component (tool-tool_builder, TOOL-AUTHOR-1).

   DECLARE a kind:tool connector (an MCP server / API connector / KB / terminology service) into
   the active workspace's config plane — the SPINE move mirroring ContractBuilder/JudgeBuilder:
   the human fills the card, "Create tool" PERSISTS via POST /v1/tools (the audited writer), then
   onResult() fires. The safety thesis (SPEC_TOOL_AUTHORING §1): you DECLARE a connector, you never
   upload code — custom execution stays behind your own MCP/HTTP transport; Lithrim calls it and
   treats the output as untrusted. Bind a tool to a judge's flag afterwards via the contract builder
   (contract_type mcp_call, or snomed_subsumption for the SNOMED instance).

   "Test connection" health-checks a stdio-MCP connector (POST /v1/tools/test → list_tools) so you
   see it's reachable before you save. Built on the shadcn primitives + the @theme token bridge. */
import { useState } from "react";
import { createTool, testTool } from "../bff.js";
import { Button } from "../components/ui/button.jsx";
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "../components/ui/card.jsx";
import { Input } from "../components/ui/input.jsx";
import { Label } from "../components/ui/label.jsx";
import { Separator } from "../components/ui/separator.jsx";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select.jsx";
import { Icon } from "../icons.jsx";
import { friendlyError } from "./copy.js";
import { registerTool } from "./registry.js";

// The kind:tool sub-kinds (the `implements` string — MCP is the standard). api_connector is listed
// now so the owner's next tool is declare-and-wire, not a UI rebuild.
const IMPLEMENTS = [
  ["tool.mcp_server", "MCP server (stdio)"],
  ["tool.terminology", "Terminology / SNOMED (MCP)"],
  ["tool.kb_query", "Knowledge base (service)"],
  ["tool.api_connector", "API connector (HTTP)"],
];
// stdio-MCP sub-kinds carry service.mcp {command,args}; the others carry service.default_base_url.
const isStdioMcp = (impl) => impl === "tool.mcp_server" || impl === "tool.terminology";

function Field({ label, children }) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label>{label}</Label>
      {children}
    </div>
  );
}

export default function ToolBuilder({ agent = "ws0_default", seed, onResult }) {
  const [id, setId] = useState(seed?.id ?? "");
  const [implementsKind, setImplementsKind] = useState(seed?.implements ?? "tool.mcp_server");
  const [command, setCommand] = useState(seed?.command ?? "");
  const [args, setArgs] = useState(seed?.args ?? ""); // space-separated → array
  const [baseUrl, setBaseUrl] = useState(seed?.base_url ?? "");
  const [persist, setPersist] = useState({ state: "idle", msg: "" }); // idle|saving|saved|error
  const [test, setTest] = useState({ state: "idle", msg: "" }); // idle|testing|ok|fail

  const stdio = isStdioMcp(implementsKind);
  const service = stdio
    ? { mcp: { command: command.trim(), args: args.trim() ? args.trim().split(/\s+/) : [] } }
    : { default_base_url: baseUrl.trim() };
  const manifest = {
    id: id.trim(),
    kind: "tool",
    tier: "core",
    transport: "service",
    implements: implementsKind,
    service,
  };
  const valid = manifest.id && (stdio ? command.trim() : baseUrl.trim());

  const runTest = async () => {
    setTest({ state: "testing", msg: "connecting…" });
    try {
      const r = await testTool(manifest);
      setTest(
        r.ok
          ? { state: "ok", msg: `✓ reachable · ${(r.tools || []).length} tool(s): ${(r.tools || []).slice(0, 6).join(", ")}` }
          : { state: "fail", msg: `⚠ ${r.error || "not reachable"}` },
      );
    } catch (e) {
      setTest({ state: "fail", msg: `⚠ ${friendlyError(e)}` });
    }
  };

  const save = async () => {
    setPersist({ state: "saving", msg: "saving…" });
    try {
      await createTool({ manifest, agent });
      setPersist({ state: "saved", msg: "tool added ✓" });
      onResult?.({ tool_id: manifest.id, manifest });
    } catch (e) {
      setPersist({ state: "error", msg: friendlyError(e) });
    }
  };

  return (
    <Card className="my-3">
      <CardHeader>
        <span className="text-primary"><Icon name="layers" size={15} /></span>
        <CardTitle>Connect a tool</CardTitle>
        <span className="font-semibold text-[11px] text-primary">MCP / API connector</span>
        <span className="font-[family-name:var(--font-mono)] text-[10.5px] text-muted-foreground">declare · don't upload code</span>
      </CardHeader>
      <CardContent className="flex flex-col gap-3.5">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Tool id">
            <Input value={id} onChange={(e) => setId(e.target.value)} placeholder="e.g. my_hermes" aria-label="tool id" />
          </Field>
          <Field label="Kind">
            <Select value={implementsKind} onValueChange={setImplementsKind}>
              <SelectTrigger aria-label="implements"><SelectValue /></SelectTrigger>
              <SelectContent>
                {IMPLEMENTS.map(([v, lbl]) => <SelectItem key={v} value={v}>{lbl}</SelectItem>)}
              </SelectContent>
            </Select>
          </Field>
        </div>
        {stdio ? (
          <div className="grid grid-cols-2 gap-3">
            <Field label="Command">
              <Input value={command} onChange={(e) => setCommand(e.target.value)} placeholder="hermes" aria-label="command" />
            </Field>
            <Field label="Args (space-separated)">
              <Input value={args} onChange={(e) => setArgs(e.target.value)} placeholder="--db /path/snomed.db mcp" aria-label="args" />
            </Field>
          </div>
        ) : (
          <Field label="Base URL">
            <Input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="http://localhost:8585" aria-label="base url" />
          </Field>
        )}
        <div className="rounded-[var(--radius-sm)] border border-border bg-secondary px-3 py-2 text-[11.5px] leading-relaxed text-muted-foreground">
          You're <strong className="text-foreground">declaring a connector</strong>, not uploading code — Lithrim calls it over its transport and treats the output as untrusted. After saving, bind it to a judge's flag in the fact-check builder ({stdio ? "mcp_call / snomed_subsumption" : "mcp_call"}).
        </div>
        {stdio && (
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={runTest} disabled={!valid || test.state === "testing"}>
              <Icon name="spark" size={13} /> {test.state === "testing" ? "Connecting…" : "Test connection"}
            </Button>
            {test.state !== "idle" && test.state !== "testing" && (
              <span data-testid="tool-test-result" className={"text-[10.5px] " + (test.state === "ok" ? "text-[color:var(--teal)]" : "text-[color:var(--accent-ink)]")}>{test.msg}</span>
            )}
          </div>
        )}
      </CardContent>
      <Separator />
      <CardFooter>
        <span className={"font-[family-name:var(--font-mono)] text-[10.5px] " + (persist.state === "error" ? "text-[color:var(--accent-ink)]" : "text-muted-foreground")}>
          {persist.state !== "idle" ? persist.msg : "per-workspace · audited"}
        </span>
        <Button className="ml-auto" data-testid="tool-save" size="sm" onClick={save} disabled={!valid || persist.state === "saving"}>
          {persist.state === "saving" ? "Saving…" : "Create tool"}
        </Button>
      </CardFooter>
    </Card>
  );
}

registerTool("tool-tool_builder", ToolBuilder);
