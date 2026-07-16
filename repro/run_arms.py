#!/usr/bin/env python3
"""Arm-matrix driver for the clean public-cut rerun (docs/reproduction/RUN_PLAN_PUBLIC_CUT.md).

Reads repro/arms.json and, per arm x ontology-arm, authors ONE workspace by REUSING
repro/setup_streams.setup_workspace (identical floor + corpus, $0), then applies the arm's
per-role provider binds via POST /v1/roles/bind ($0; the key is reused from the stored
provider, never sent here).

ADDITIVE by design: this file and arms.json do NOT modify or run the deposited 5-stream study
scripts. The deposited reproduction (setup_streams main, cohort_runner, consolidate over the
fixed streams) is untouched and stays byte-reproducible.

Modes (author first, then grade, then score):
  (default)   AUTHOR + bind every ready arm x ontology-arm workspace             ($0)
  --grade     GRADE the PAID cohort for the already-authored arm workspace(s). Does NOT
              re-author (no re-ingest, can't trip the case-count assert); reuses
              cohort_runner.run_stream; strictly sequential. Clear the DSPy cache and confirm
              cost_tokens>0 on one case BEFORE using this (see the plan's Stage 5).
  --score     SCORE ($0 replay) the already-authored/graded arm workspace(s):
              POST /v1/cases/grade live:False -> scorecard_<ws>.json.
  --arm ID    restrict to a single arm id
  --ontology armT|armR         restrict to a single ontology arm
  --class registered|exploratory   restrict to a class (the 5 published study streams vs the
              unregistered post-study cells). REGISTERED reproduces the roster-structure study;
              EXPLORATORY (CoT, OpenBio, per-flag Composo) must not be quoted as study results.
  --dry-run   print the plan; makes zero HTTP calls

Env (shared with setup_streams / cohort_runner, read at import):
  LITHRIM_REPRO_BASE (default http://localhost:8787), LITHRIM_REPRO_CORPUS_DIR,
  LITHRIM_REPRO_WS_SUFFIX, LITHRIM_REPRO_PHYSICIAN_CASES, LITHRIM_REPRO_OUT, LITHRIM_REPRO_ACTOR.
Set LITHRIM_REPRO_CORPUS_DIR BEFORE running so the reused setup_streams ingests the right corpus
(the public-cut clean run uses repro/corpus_v2, the scrubbed corpus).
"""
import json
import os
import sys
from pathlib import Path

REPRO_DIR = Path(__file__).resolve().parent
REPO_ROOT = REPRO_DIR.parent
ARMS_PATH = Path(os.environ.get("LITHRIM_ARMS_FILE", REPRO_DIR / "arms.json"))
WS_SUFFIX = os.environ.get("LITHRIM_REPRO_WS_SUFFIX", "")

sys.path.insert(0, str(REPRO_DIR))
import setup_streams as S  # noqa: E402 — reuse the proven authoring seam ($0)

# Make corpus selection self-contained: build CORPUS_FILES from LITHRIM_REPRO_CORPUS_DIR here and
# override setup_streams' module global, so the driver works against ANY setup_streams version —
# including public-cut's, which predates the LITHRIM_REPRO_CORPUS_DIR seam and would otherwise
# hardcode repro/corpus (the v1, unscrubbed corpus) and silently ignore corpus_v2.
_CORPUS_DIR = os.environ.get("LITHRIM_REPRO_CORPUS_DIR", str(REPRO_DIR / "corpus"))
_PHYSICIAN = os.environ.get("LITHRIM_REPRO_PHYSICIAN_CASES", "")
S.CORPUS_FILES = [
    (str(Path(_CORPUS_DIR) / "upcoded_positives.jsonl"), 22, "native"),
    (str(Path(_CORPUS_DIR) / "clean_generalization_negatives.jsonl"), 22, "native"),
]
if _PHYSICIAN:
    S.CORPUS_FILES.append((_PHYSICIAN, 10, "template"))


def load_arms():
    return json.loads(ARMS_PATH.read_text())


def ontology_for(cfg, onto_key):
    return json.loads((REPO_ROOT / cfg["ontology_files"][onto_key]).read_text())


def _resolve_lens(tok):
    # Reuse the study's exact lens sets from setup_streams; "FULL" and explicit lists pass through.
    if tok == "FULL" or isinstance(tok, list):
        return tok
    table = {"RISK": S.RISK_LENS, "POLICY": S.POLICY_LENS, "FAITH": S.FAITH_LENS}
    if tok not in table:
        print(f"unknown lens token {tok!r}; use FULL/RISK/POLICY/FAITH or an explicit code list")
        sys.exit(1)
    return table[tok]


def build_stream(arm, cfg, onto_key):
    ws = f"{arm['id']}-{onto_key}{WS_SUFFIX}"
    if arm["prompt"] == "specialist":
        prompt = None  # setup_workspace applies per-role SPECIALIST_PROMPTS keyed off the role suffix
    else:
        prompt = cfg["prompts"][arm["prompt"]] + (cfg["cot_suffix"] if arm.get("cot") else "")
    judges = [{"role": j["role"], "lens": _resolve_lens(j["lens"]), "k": j["k"], "temperature": j["temperature"]}
              for j in arm["judges"]]
    return {"ws": ws, "judges": judges, "prompt": prompt}


def apply_binds(arm):
    for b in arm["binds"]:
        body = {"role": b["role"], "provider": b["provider"], "model": b["model"]}
        if b.get("endpoint"):
            body["endpoint"] = b["endpoint"]
        if b.get("api_version"):
            body["api_version"] = b["api_version"]
        status, _ = S.call("POST", "/v1/roles/bind", body, tolerate=(400, 422))
        note = "" if status == 200 else "  (provider not connected? bind will not grade)"
        print(f"    bind {b['role']} -> {b['provider']}:{b['model']} [{status}]{note}")


def score_arm(ws):
    S.call("POST", "/v1/workspace", {"name": ws})
    _, out = S.call("POST", "/v1/cases/grade", {"agent": "ws0_default", "live": False})
    S.OUT_DIR.mkdir(parents=True, exist_ok=True)
    (S.OUT_DIR / f"scorecard_{ws}.json").write_text(json.dumps(out.get("scorecard", out), indent=1))
    print(f"    $0 scorecard -> {S.OUT_DIR / ('scorecard_' + ws + '.json')}")


def print_plan(cfg, arms):
    print(f"PLAN base={S.BASE} corpus={os.environ.get('LITHRIM_REPRO_CORPUS_DIR', '(default)')} "
          f"suffix={WS_SUFFIX!r}")
    for a in arms:
        tag = "" if a.get("status", "ready") == "ready" else f"  [{a['status'].upper()}]"
        print(f"arm {a['id']} [{a.get('class', '?')}]{tag}: prompt={a['prompt']} "
              f"cot={bool(a.get('cot'))} ontology_arms={a['ontology_arms']}")
        for j in a["judges"]:
            print(f"    judge {j['role']}: k={j['k']} t={j['temperature']} lens={j['lens']}")
        for b in a["binds"]:
            ep = f" @ {b['endpoint']}" if b.get("endpoint") else ""
            print(f"    bind  {b['role']} -> {b['provider']}:{b['model']}{ep}")
    print("no HTTP calls made (dry-run)")


def _opt_value(argv, flag):
    if flag not in argv:
        return None
    i = argv.index(flag)
    if i + 1 >= len(argv) or argv[i + 1].startswith("--"):
        print(f"{flag} requires a value, e.g. {flag} arm-single-frontier-plain")
        sys.exit(1)
    return argv[i + 1]


def main():
    argv = sys.argv[1:]
    dry = "--dry-run" in argv
    grade = "--grade" in argv
    score = "--score" in argv
    only = _opt_value(argv, "--arm")
    onto_filter = _opt_value(argv, "--ontology")
    klass = _opt_value(argv, "--class")
    author = not (grade or score)  # default mode authors; --grade/--score act on an existing ws

    # Guardrail: a paid cohort must be scoped and individually authorized. Refuse an unscoped
    # --grade so one command cannot fire every arm x ontology cohort past a single sentinel
    # or authorization (see the SKILL's Stage 5).
    if grade and only is None:
        print("REFUSING --grade without --arm: each paid cohort must be scoped and sentinel-"
              "checked individually. Re-run e.g. --arm arm-single-frontier-plain --grade "
              "[--ontology armT].")
        sys.exit(1)

    cfg = load_arms()
    arms = [a for a in cfg["arms"]
            if (only is None or a["id"] == only) and (klass is None or a.get("class") == klass)]
    if not arms:
        print(f"no arm matches arm={only!r} class={klass!r}; "
              f"ids: {[a['id'] for a in cfg['arms']]}")
        sys.exit(1)

    if dry:
        print_plan(cfg, arms)
        return

    if grade:
        import cohort_runner as C  # noqa: E402 — reuse the proven per-case grading loop
        C.OUT_DIR.mkdir(parents=True, exist_ok=True)  # cohort_runner.log() opens progress.log here
        print("PAID MODE (--grade): confirm the DSPy cache was cleared and the cost_tokens>0 "
              "sentinel passed on one case FIRST. Grades the active workspace per arm, sequential.")

    for a in arms:
        if a.get("status", "ready") != "ready":
            print(f"\n=== SKIP {a['id']} (status={a.get('status')}: "
                  f"{a.get('blocked_reason', '')[:80]}) ===")
            continue
        onto_keys = [k for k in a["ontology_arms"] if onto_filter is None or k == onto_filter]
        for onto_key in onto_keys:
            ws = f"{a['id']}-{onto_key}{WS_SUFFIX}"
            print(f"\n=== {ws} ({a['id']} / {onto_key}) ===")
            # AUTHOR is a separate phase: --grade/--score operate on the already-authored ws and
            # never re-run setup_workspace, so a re-grade can't re-ingest cases or trip the
            # case-count assert. Author first (default mode), then grade, then score.
            if author:
                onto = ontology_for(cfg, onto_key)
                assert len(onto.get("verification_contracts", [])) == 7, \
                    f"{onto_key}: floor ontology must have 7 verification_contracts"
                lens_full = S.full_lens(onto)
                expected = sum(expect for _, expect, _ in S.CORPUS_FILES)
                stream = build_stream(a, cfg, onto_key)
                S.setup_workspace(stream, onto, lens_full, expected)
                apply_binds(a)
            if grade:
                C.run_stream(ws)
            if score:
                score_arm(ws)


if __name__ == "__main__":
    main()
