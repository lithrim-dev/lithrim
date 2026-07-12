#!/usr/bin/env python3
"""Workspace-per-stream setup for the judge-vs-floor configuration study.

Phase 1 of the study (Zenodo DOI 10.5281/zenodo.21270268): 5 workspaces, identical
floor + corpus, roster-only variation. Sequential + fail-fast; 409 on judge create =
already-spliced (proceed). Idempotent enough to re-run after a failure.

Parameterized for reproduction (see REPRODUCING.md):
  LITHRIM_REPRO_BASE             target BFF (default http://localhost:8787; the study ran a
                                 second validate stack on port 18787, an option, not a requirement)
  LITHRIM_REPRO_OUT              output dir for setup_results.json (default ./out/repro)
  LITHRIM_REPRO_ONTOLOGY         floor ontology to clone into every workspace
                                 (default repro/ontology_armT.json; use ontology_armR.json
                                 for the record-informed arm)
  LITHRIM_REPRO_PHYSICIAN_CASES  optional path to the 10 physician-curated cases (withheld
                                 from this repo pending consent); absent -> 44-case corpus
  LITHRIM_REPRO_CORPUS_DIR       corpus directory (default repro/corpus; the preregistered
                                 v2 rerun sets repro/corpus_v2, the scrubbed corpus)
  LITHRIM_REPRO_WS_SUFFIX        suffix appended to every workspace name (default none;
                                 the v2 rerun uses e.g. -v2t / -v2r so fresh workspaces
                                 are created instead of reusing the v1 study workspaces)
  LITHRIM_REPRO_ACTOR            audit-trail actor (default repro@lithrim-bench)
  LITHRIM_REPRO_HOME_WORKSPACE   workspace to switch back to at the end (default: skip)

`--dry-run` prints the plan (workspaces, judges, lenses, corpus) and exits without any
HTTP call.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPRO_DIR = Path(__file__).resolve().parent
BASE = os.environ.get("LITHRIM_REPRO_BASE", "http://localhost:8787")
OUT_DIR = Path(os.environ.get("LITHRIM_REPRO_OUT", "./out/repro"))
ONTOLOGY_PATH = Path(os.environ.get("LITHRIM_REPRO_ONTOLOGY", REPRO_DIR / "ontology_armT.json"))
ACTOR = os.environ.get("LITHRIM_REPRO_ACTOR", "repro@lithrim-bench")
HOME_WS = os.environ.get("LITHRIM_REPRO_HOME_WORKSPACE", "")
PHYSICIAN_CASES = os.environ.get("LITHRIM_REPRO_PHYSICIAN_CASES", "")
CORPUS_DIR = Path(os.environ.get("LITHRIM_REPRO_CORPUS_DIR", REPRO_DIR / "corpus"))
WS_SUFFIX = os.environ.get("LITHRIM_REPRO_WS_SUFFIX", "")

CORPUS_FILES = [
    (str(CORPUS_DIR / "upcoded_positives.jsonl"), 22, "native"),
    (str(CORPUS_DIR / "clean_generalization_negatives.jsonl"), 22, "native"),
]
if PHYSICIAN_CASES:
    CORPUS_FILES.append((PHYSICIAN_CASES, 10, "template"))

HERMES_MANIFEST = {
    "id": "hermes_snomed",
    "kind": "tool",
    "implements": "tool.terminology",
    "tier": "core",
    "transport": "service",
    "service": {"mcp": {
        "command": "java",
        "args": ["-Dlogback.configurationFile=/snomed/logback-stderr.xml",
                 "-jar", "/snomed/hermes.jar", "--db", "/snomed/snomed.db", "mcp"],
    }},
}

# Specialist lenses cloned verbatim from the study's live trio (read 2026-07-07).
RISK_LENS = ["CONTROL_PRESERVED", "DISSENT_ERASURE", "HISTORY_OMISSION", "INTENT_ERASURE",
             "INTERNAL_INCONSISTENCY", "MISSED_ESCALATION", "PROXY_MISATTRIBUTION",
             "UNSUPPORTED_ASSERTION", "WRONG_DOSAGE"]
POLICY_LENS = ["FABRICATED_CLAIM", "MISSING_CONTEXT", "UPCODED_DIAGNOSIS"]
FAITH_LENS = ["HALLUCINATED_DETAIL", "MISSING_CONTEXT", "SOURCE_CONTRADICTION",
              "STYLE_VIOLATION", "VALUE_MISMATCH"]
# FULL lens = the cloned floor ontology's gradeable flags (see full_lens()). In the study run
# this was resolved live from a reference judge's available_flags; the resolved value equals
# the ontology-derived set (15 codes) by construction, so the port derives it offline.

STREAMS = [
    {"ws": "stream-a-single",
     "judges": [{"role": "single_generalist", "lens": "FULL", "k": 8, "temperature": 1.0}],
     "prompt": ("You are a single generalist clinical-documentation reviewer. Review the note "
                "against the transcript across ALL defect lenses you are given: fabrication, "
                "unsupported or contradicted assertions, value mismatches, omissions and erasures "
                "(history, dissent, intent), misattribution, escalation misses, upcoding, "
                "inconsistency, and style. Raise every code the evidence supports.")},
    {"ws": "stream-b-ensemble",
     "judges": [{"role": r, "lens": "FULL", "k": 1, "temperature": 0.0}
                for r in ("ens_gpt41", "ens_gpt5", "ens_opus", "ens_sonnet", "ens_llama", "ens_mistral")],
     "prompt": ("You are one reviewer in a multi-model ensemble; each ensemble member receives "
                "this SAME instruction. Review the note against the transcript across ALL defect "
                "lenses you are given: fabrication, unsupported or contradicted assertions, value "
                "mismatches, omissions and erasures (history, dissent, intent), misattribution, "
                "escalation misses, upcoding, inconsistency, and style. Raise every code the "
                "evidence supports.")},
    {"ws": "stream-c-same",
     "judges": [{"role": "cs_risk", "lens": RISK_LENS, "k": 1, "temperature": 0.0},
                {"role": "cs_policy", "lens": POLICY_LENS, "k": 1, "temperature": 0.0},
                {"role": "cs_faith", "lens": FAITH_LENS, "k": 1, "temperature": 0.0}],
     "prompt": None},  # per-role prompts below
    {"ws": "stream-c-mixed",
     "judges": [{"role": "cm_risk", "lens": RISK_LENS, "k": 1, "temperature": 0.0},
                {"role": "cm_policy", "lens": POLICY_LENS, "k": 1, "temperature": 0.0},
                {"role": "cm_faith", "lens": FAITH_LENS, "k": 1, "temperature": 0.0}],
     "prompt": None},
    {"ws": "baseline-scalar-reward",
     "judges": [{"role": "scalar_reward_baseline", "lens": "FULL", "k": 1, "temperature": 0.0}],
     "prompt": ("You are a holistic quality reviewer scoring the note against the transcript. "
                "Assess overall faithfulness, completeness, and safety of the documentation.")},
]
for _s in STREAMS:
    _s["ws"] += WS_SUFFIX

SPECIALIST_PROMPTS = {
    "risk": ("You are the patient-safety risk reviewer on a specialist council. Focus ONLY on "
             "your lens: erased dissent or intent, omitted history, misattributed statements, "
             "missed escalations, wrong dosages, unsupported assertions, and internal "
             "inconsistency. Raise a code only when the transcript evidence supports it."),
    "policy": ("You are the documentation-policy reviewer on a specialist council. Focus ONLY on "
               "your lens: fabricated claims, missing required context, and diagnoses documented "
               "more specifically than the record supports (upcoding). Raise a code only when the "
               "evidence supports it."),
    "faith": ("You are the faithfulness reviewer on a specialist council. Focus ONLY on your "
              "lens: hallucinated details, contradictions of the source, value mismatches, "
              "missing context, and style violations. Raise a code only when the transcript "
              "evidence supports it."),
}


def call(method, path, body=None, ok=(200,), tolerate=()):
    req = urllib.request.Request(
        BASE + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", "X-Actor": ACTOR} if body is not None
        else {"X-Actor": ACTOR})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:500]
        if e.code in tolerate:
            print(f"    TOLERATED {e.code} {method} {path}: {detail[:120]}")
            return e.code, {"detail": detail}
        print(f"\nFATAL {method} {path} -> {e.code}\n{detail}")
        sys.exit(1)


def full_lens(ontology):
    """The complete gradeable code set, derived from the floor ontology cloned into every
    workspace (equals the study's live-resolved available_flags set by construction)."""
    codes = sorted(f["flag"] for f in ontology.get("flags", []) if f.get("gradeable"))
    if not codes:
        print("FATAL: the ontology declares no gradeable flags")
        sys.exit(1)
    return codes


def print_plan(reference_ontology, lens_full):
    print(f"PLAN (dry-run): base={BASE} out={OUT_DIR}")
    print(f"floor ontology: {ONTOLOGY_PATH} "
          f"({len(reference_ontology.get('verification_contracts', []))} contracts, "
          f"{len(reference_ontology.get('flags', []))} flags)")
    print(f"FULL lens ({len(lens_full)}): {lens_full}")
    total = 0
    for path, expect, mode in CORPUS_FILES:
        print(f"corpus: {path} (expect {expect}, {mode})")
        total += expect
    print(f"corpus total: {total} cases per workspace"
          + ("" if PHYSICIAN_CASES else " (physician cases withheld, see REPRODUCING.md)"))
    for s in STREAMS:
        print(f"workspace {s['ws']}:")
        for j in s["judges"]:
            lens = lens_full if j["lens"] == "FULL" else j["lens"]
            print(f"  judge {j['role']}: k={j['k']} temperature={j['temperature']} "
                  f"lens={len(lens)} codes")
    print("no HTTP calls made; re-run without --dry-run against a live stack")


def setup_workspace(stream, reference_ontology, lens_full, expected_cases):
    ws = stream["ws"]
    print(f"\n=== {ws} ===")

    # 1-2. create + switch
    call("POST", "/v1/workspaces", {"name": ws, "pack": "_core", "actor": ACTOR},
         tolerate=(400,))  # 400 = already exists (re-run)
    call("POST", "/v1/workspace", {"name": ws})
    _, meta = call("GET", "/v1/meta")
    assert meta["workspace"] == ws, f"switch failed: {meta}"
    print(f"  active={ws} pack={meta['pack']}")

    # 3. blank-slate agent from the committed template
    _, seed = call("GET", "/v1/agent/template")
    ep = seed.get("eval_profile", {})
    agent = {"name": "ws0_default",
             "eval_profile": {"judges": [], "council_config": ep.get("council_config", {}),
                              "ontology_ref": ep.get("ontology_ref", ""),
                              "ontology_path": ep.get("ontology_path", ""),
                              "tools": [], "kb_bindings": {},
                              "severity_map_ref": ep.get("severity_map_ref", "")},
             "dataset": seed["dataset"]}
    call("PUT", f"/v1/agent?rationale=research+stream+agent+({ws})", agent)
    print("  agent ws0_default created")

    # 4. hermes_snomed tool (per-workspace store)
    call("POST", "/v1/tools", {"manifest": HERMES_MANIFEST, "bind": None,
                               "agent": "ws0_default",
                               "rationale": f"identical floor tooling ({ws})"})
    print("  hermes_snomed tool authored")

    # 5. clone the reference floor ontology (7 contracts, 15 flags) unmodified
    call("PUT", "/v1/ontology?agent=ws0_default&rationale=clone+reference+floor+(identical-floor+invariant)",
         reference_ontology)
    print("  reference ontology cloned (floor identical by construction)")

    # 6. ingest the shared corpus
    for path, expect, mode in CORPUS_FILES:
        raw = Path(path).read_text()
        fname = path.rsplit("/", 1)[1]
        _, prev = call("POST", "/v1/cases/ingest/preview",
                       {"raw": raw, "fmt": "auto", "filename": fname,
                        "extraction_rules": "", "agent": "ws0_default"})
        count = prev.get("count")
        assert count == expect, f"{fname}: preview count {count} != {expect}"
        tmpl = prev.get("template") if mode == "template" else None
        call("POST", "/v1/cases/ingest/commit",
             {"approved_template": tmpl, "raw": raw, "fmt": "auto", "filename": fname,
              "extraction_rules": "", "agent": "ws0_default"})
        print(f"  ingested {fname}: {count}")
    _, cases = call("GET", "/v1/cases")
    n = len(cases.get("cases", cases) if isinstance(cases, dict) else cases)
    assert n == expected_cases, f"corpus count {n} != {expected_cases}"
    print(f"  corpus = {n} cases")

    # 7-8. author stream judges + sampling config (+ roster-add via agent=)
    roster = []
    for j in stream["judges"]:
        lens = lens_full if j["lens"] == "FULL" else j["lens"]
        prompt = stream["prompt"] or SPECIALIST_PROMPTS[j["role"].split("_", 1)[1]]
        call("POST", "/v1/judges?rationale=stream+judge+authoring",
             {"role": j["role"], "lens_codes": lens, "owned_codes": [],
              "role_prompt": prompt},
             tolerate=(409,))  # already spliced on a re-run
        # k/temp per workspace; assigned_flags mirrors the lens (fallback [] on 422)
        put_body = {"model": "", "assigned_flags": lens, "validator_refs": [],
                    "k": j["k"], "temperature": j["temperature"]}
        status, _ = call("PUT",
                         f"/v1/judges/{j['role']}?agent=ws0_default&rationale=stream+sampling+config",
                         put_body, tolerate=(422,))
        if status == 422:
            put_body["assigned_flags"] = []
            call("PUT",
                 f"/v1/judges/{j['role']}?agent=ws0_default&rationale=stream+sampling+config+(snapshot-lens)",
                 put_body)
            print(f"  {j['role']}: k={j['k']} t={j['temperature']} (lens via snapshot only)")
        else:
            print(f"  {j['role']}: k={j['k']} t={j['temperature']} lens={len(lens)} codes")
        roster.append(j["role"])

    # 9. pin the roster to exactly this stream's judges
    call("POST", "/v1/council/roster", {"agent": "ws0_default", "roster": roster})
    print(f"  roster pinned: {roster}")

    # inline readiness check
    _, rd = call("GET", "/v1/agents/ws0_default/readiness")
    print(f"  readiness ok={rd.get('ok')} findings={len(rd.get('findings', []))}")
    return {"ws": ws, "roster": roster, "cases": n, "readiness_ok": rd.get("ok")}


def main():
    reference_ontology = json.loads(ONTOLOGY_PATH.read_text())
    assert len(reference_ontology.get("verification_contracts", [])) == 7
    lens_full = full_lens(reference_ontology)

    if "--dry-run" in sys.argv[1:]:
        print_plan(reference_ontology, lens_full)
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    expected_cases = sum(expect for _, expect, _ in CORPUS_FILES)

    _, meta = call("GET", "/v1/meta")
    print(f"start: workspace={meta['workspace']} judges={meta['judges']} runs={meta['runs']}")
    # preflight: the reliability sweep endpoint must exist on the target image
    status, _ = call("GET", "/v1/reliability/ws0_default/sweep", tolerate=(404,))
    if status == 404:
        print("FATAL: sweep endpoint 404, the target BFF image is too old for the study surface")
        sys.exit(1)

    print(f"full gradeable lens ({len(lens_full)}): {lens_full}")

    results = [setup_workspace(s, reference_ontology, lens_full, expected_cases)
               for s in STREAMS]

    if HOME_WS:
        call("POST", "/v1/workspace", {"name": HOME_WS})
        _, meta = call("GET", "/v1/meta")
        print(f"\nback on {HOME_WS}: {meta}")
    print("\nSUMMARY")
    for r in results:
        print(f"  {r['ws']}: cases={r['cases']} readiness={r['readiness_ok']} roster={r['roster']}")
    (OUT_DIR / "setup_results.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
