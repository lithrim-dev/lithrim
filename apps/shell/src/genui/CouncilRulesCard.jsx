/* CouncilRulesCard.jsx — datapoint component (tool-council_rules, UI-JOURNEY-1 B10).
   How the council decides, from GET /v1/council/rules: the frozen consensus rules in plain
   words (evidence not votes, the tier rules, the withstands gate for a hesitant or contradicted
   judge, too few answers, the floor, the absolute-two corroboration), plus the pack's panel and
   this agent's roster. A description of the byte-frozen seam, never an edit of it. */
import { registerTool } from "./registry.js";

export default function CouncilRulesCard({ pack, panel = [], reviewer_roster = null, rules = [], min_valid_judges } = {}) {
  if (!rules.length) {
    return (
      <div className="rounded-[var(--radius)] border border-border bg-card p-3 text-[12.5px] text-muted-foreground" data-testid="council-rules-empty">
        No council rules loaded yet.
      </div>
    );
  }
  return (
    <div className="rounded-[var(--radius)] border border-border bg-card p-3" data-testid="council-rules">
      <div className="mb-1 flex items-baseline justify-between">
        <div className="text-[13px] font-semibold">How the council decides</div>
        <div className="font-mono text-[10.5px] text-muted-foreground">{pack}{min_valid_judges ? ` · needs ${min_valid_judges} answers` : ""}</div>
      </div>
      <div className="mb-2 text-[11.5px] text-muted-foreground" data-testid="council-roster">
        Panel: {panel.join(", ") || "—"}{reviewer_roster && reviewer_roster.length ? ` · this agent runs: ${reviewer_roster.join(", ")}` : " · this agent runs the full panel"}
      </div>
      <ol className="flex flex-col gap-1.5">
        {rules.map((r) => (
          <li key={r.name} className="text-[12px] leading-snug" data-testid={`council-rule-${r.name.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}`}>
            <span className="font-semibold text-foreground">{r.name}.</span> <span className="text-muted-foreground">{r.text}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

registerTool("tool-council_rules", CouncilRulesCard);
