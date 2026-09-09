#!/usr/bin/env python
"""The clean optimize path on RAGTruth, download to scorecard, in one reproducible command.

Steps (each idempotent; ``--from STEP`` resumes):
  download   the two upstream files into out/ragtruth/
  slice      the natural test cut (--slice N --natural) + the optimizer corpus (--calib-out)
  ingest     the cut into the active workspace through the native front door
  judge      author/refresh the detector role (the paper's Appendix D prompt) and pin its model
  before     grade the cut (in-process, judge cache off) and score it: the baseline row
  optimize   DSPy BootstrapFewShot on the TRAIN-split calibration rows, held-out = the test cut
  pin        copy the compiled demos into the workspace out dir (production grades pick them up)
  after      grade the cut again and score it: the optimized row

Hygiene the script enforces rather than asks for:
  * a grade with ``summary.cache_replays > 0`` is refused (not a measurement);
  * ``summary.judge_errors`` (provider refusals etc.) is reported next to every score, never hidden;
  * the judge model must be pinned explicitly (``--model``), never the workspace's floating global;
  * the optimizer refuses to train on non-calibration rows (judge_optimize), and its result carries
    a provenance manifest (train/held-out ids, corpus + prompt + demo hashes, demos_out_of_sample).

Usage (a stack up via ``make up``; provider connected; a dated deployment name in hand):
    python scripts/ragtruth_cycle.py --model azure/gpt-4.1-2025-04-14 --per-task 150
    python scripts/ragtruth_cycle.py --model ... --from optimize        # resume
    python scripts/ragtruth_cycle.py --model ... --dry-run              # print the plan only
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STEPS = ("download", "slice", "ingest", "judge", "before", "optimize", "pin", "after")
ROLE = "ragtruth_detector"
LENS = ["SOURCE_CONTRADICTION", "UNSUPPORTED_ASSERTION"]
ROLE_PROMPT = (
    "YOU ARE THE RAGTRUTH HALLUCINATION DETECTOR — the prompt-based detector from RAGTruth "
    "(Niu et al., arXiv:2401.00396, Appendix D), run as a reviewer.\n\n"
    "The source material is given as the transcript: a news article (summarization), related "
    "passages (question answering), or structured business data in JSON (data-to-text writing). "
    "The artifact is the generated response: a summary, an answer, or an overview article.\n\n"
    "Your task is to determine whether the response contains either or both of the following two "
    "types of hallucinations:\n"
    "1. conflict: instances where the response presents direct contraction or opposition to the "
    "source; raise SOURCE_CONTRADICTION.\n"
    "2. baseless info: instances where the response includes information which is not "
    "substantiated by or inferred from the source; raise UNSUPPORTED_ASSERTION.\n\n"
    'In JSON source data, "null" or "None" represents an unknown value rather than a negation.\n\n'
    "Compile every hallucinated span you find as a finding with its code and the exact span "
    "quoted from the response. If there are no hallucinations, raise no finding and approve. "
    "Report no self-rated confidence."
)


# --------------------------------------------------------------------------- #
# pure helpers (unit-tested offline)
# --------------------------------------------------------------------------- #
def floor_reading(scorecard: dict) -> str:
    """The honest two-line read of the scorecard's three verdict-accuracy numbers (READ-ATTRIB-1):
    the floor's effect is post MINUS no_floor; pre-vs-post mixes in the voting-rule-vs-rescore gap."""
    f = scorecard.get("floor") or {}
    pre, post, nofl = (
        f.get("verdict_accuracy_pre_floor"),
        f.get("verdict_accuracy_post_floor"),
        f.get("verdict_accuracy_no_floor"),
    )
    if post is None or nofl is None:
        return "floor effect: not attributable (no_floor rescore absent on this run)"
    delta = round(100 * (post - nofl), 1)
    clears = f.get("gold_defect_clears") or []
    lines = [
        f"floor effect: {delta:+.1f} pts verdict accuracy (with floor {100 * post:.1f} vs without "
        f"{100 * nofl:.1f}); enforced {f.get('enforced')}, cleared {f.get('cleared')}, "
        f"inconclusive {f.get('inconclusive')}; genuine defects cleared by the floor: {len(clears)}",
    ]
    if pre is not None:
        lines.append(
            f"reviewers' voting rule alone: {100 * pre:.1f} (the gap to {100 * post:.1f} is the "
            "voting-rule-vs-rescore difference, NOT a floor effect)"
        )
    return "\n".join(lines)


def arm_attestation(model: str, model_version: str | None, upgrade_policy: str | None) -> dict:
    """What pins this arm's model, recorded next to every result (REL-OPS-1 O4 equivalent).

    O4 is a NAME heuristic (a date token in the model id). An Azure deployment name carries no
    date, but the deployment itself has a model version and an upgrade policy; a deployment set
    to no auto-upgrade is pinned in fact. So either the name is dated, or the operator attests
    the deployment's version and policy (read from the portal or ``az cognitiveservices account
    deployment show``). Neither -> refuse: a floating alias cannot anchor a before/after."""
    from lithrim_bench.harness.model_policy import is_dated_model_id

    dated = is_dated_model_id(model)
    attested = bool(model_version) and bool(upgrade_policy)
    if not dated and not attested:
        raise SystemExit(
            f"REFUSING: model {model!r} is a floating alias (O4) and no attestation was given; "
            "pass --model-version and --upgrade-policy (e.g. 2025-04-14 NoAutoUpgrade) read from "
            "the deployment, or use a dated model id"
        )
    pinned_by = "dated model id" if dated else "operator attestation"
    no_drift = ("noautoupgrade", "no-auto-upgrade", "none")
    unverified = ("unverified", "unknown", "tbd")
    if attested and upgrade_policy and upgrade_policy.lower() in unverified:
        pinned_by = "attestation PENDING (version/policy unverified; fill in from the deployment)"
    elif attested and upgrade_policy and upgrade_policy.lower() not in no_drift:
        pinned_by = "operator attestation (WARNING: upgrade policy allows silent version drift)"
    return {
        "model": model,
        "dated_model_id": dated,
        "azure_model_version": model_version,
        "upgrade_policy": upgrade_policy,
        "pinned_by": pinned_by,
    }


def check_measurement(summary: dict) -> str:
    """Refuse a batch that is not an independent measurement; report refusals, never hide them."""
    if summary.get("cache_replays"):
        raise SystemExit(
            f"REFUSING to score: {summary['cache_replays']} case(s) were cache replays "
            "(a paid grade that spent nothing); this batch is not a measurement."
        )
    errs = int(summary.get("judge_errors") or 0)
    if summary.get("errors"):
        raise SystemExit(f"REFUSING to score: {summary['errors']} case(s) failed to grade.")
    return (
        f"independent measurement: {summary.get('graded')} graded, {errs} judge call(s) "
        "refused/failed (decided without that vote; a refused positive is a miss)"
    )


# --------------------------------------------------------------------------- #
# the steps
# --------------------------------------------------------------------------- #
def _post(bff: str, path: str, body: dict, timeout: float = 36000) -> dict:
    req = urllib.request.Request(
        bff + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _put(bff: str, path: str, body: dict) -> dict:
    req = urllib.request.Request(
        bff + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def _run(cmd: list[str], env: dict | None = None) -> None:
    print("$", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, env=env)


def step_download(a) -> None:
    _run(
        [
            sys.executable,
            "scripts/ragtruth_cases.py",
            "--download",
            "--out",
            str(a.out / "_probe.jsonl"),
        ]
    )


def step_slice(a) -> None:
    _run(
        [
            sys.executable,
            "scripts/ragtruth_cases.py",
            "--slice",
            str(a.per_task),
            "--natural",
            "--out",
            str(a.slice),
            "--calib-out",
            str(a.calib),
        ]
    )


def step_ingest(a) -> None:
    raw = a.slice.read_text()
    prev = _post(
        a.bff, "/v1/cases/ingest/preview", {"raw": raw, "filename": a.slice.name, "agent": a.agent}
    )
    assert prev.get("native"), (
        "the slice must ingest through the native path (no mapper, labels kept)"
    )
    res = _post(
        a.bff,
        "/v1/cases/ingest/commit",
        {
            "raw": raw,
            "filename": a.slice.name,
            "agent": a.agent,
            "approved_template": prev.get("template"),
        },
    )
    print(f"ingested {len(res.get('cases', []))} labeled cases into agent {a.agent}")


def step_judge(a) -> None:
    body = {"role": ROLE, "lens_codes": LENS, "owned_codes": [], "role_prompt": ROLE_PROMPT}
    try:
        _post(a.bff, "/v1/judges?rationale=RAGTruth%20cycle", body, timeout=120)
        print(f"authored judge {ROLE}")
    except urllib.error.HTTPError as exc:
        if exc.code != 409:
            raise
        print(f"judge {ROLE} exists")
    _put(
        a.bff,
        f"/v1/judges/{ROLE}?rationale=pin%20the%20arm%27s%20model",
        {"model": a.model, "assigned_flags": LENS, "validator_refs": []},
    )
    _post(a.bff, "/v1/council/roster", {"agent": a.agent, "roster": [ROLE]}, timeout=120)
    print(f"pinned {ROLE} to {a.model}; roster = [{ROLE}]")


def _grade_and_score(a, tag: str) -> None:
    ids = [json.loads(line)["case_id"] for line in a.slice.open()]
    res = _post(a.bff, "/v1/cases/grade", {"agent": a.agent, "in_process": True, "case_ids": ids})
    out = a.out / f"grade_{tag}.json"
    out.write_text(json.dumps(res, indent=1))
    print(check_measurement(res["summary"]))
    print(floor_reading(res["scorecard"]))
    _run(
        [
            sys.executable,
            "scripts/ragtruth_score.py",
            "--slice",
            str(a.slice),
            "--bff",
            a.bff,
            "--agent",
            a.agent,
        ]
    )


def step_before(a) -> None:
    demos = list(a.workspace_out.glob(f"compiled_demos_*_{ROLE}.json"))
    if demos:
        raise SystemExit(
            f"demos already pinned ({demos[0].name}); remove them for a baseline grade"
        )
    _grade_and_score(a, "before")


def step_optimize(a) -> None:
    env = dict(os.environ)
    env.setdefault("LITHRIM_BENCH_PACK_OVERLAY_DIR", str(REPO_ROOT / "out" / "pack_overlay"))
    cmd = [
        sys.executable,
        "scripts/optimize_judge.py",
        "--role",
        ROLE,
        "--corpus",
        str(a.calib),
        "--out",
        str(a.out / "optimize"),
        "--confirm-cost",
    ]
    if a.heldout_cap:
        cmd += ["--limit", str(a.heldout_cap)]
    _run(cmd, env=env)
    result = json.load((a.out / "optimize" / f"result_dspy3b_{ROLE}.json").open())
    m = result.get("manifest") or {}
    print(
        f"optimize: demos {result['compile_config'].get('n_demos_bootstrapped')}, "
        f"out_of_sample={m.get('demos_out_of_sample')}, baseline errors {result['baseline'].get('errors')}, "
        f"optimized errors {result['optimized'].get('errors')}, delta {result.get('delta', {}).get('graded')}"
    )
    if not m.get("demos_out_of_sample"):
        raise SystemExit("REFUSING to pin: a compiled demo does not trace to a calibration row")


def step_pin(a) -> None:
    src = a.out / "optimize" / f"compiled_demos_dspy3b_{ROLE}.json"
    a.workspace_out.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, a.workspace_out / src.name)
    print(f"pinned {src.name} into {a.workspace_out}")


def step_after(a) -> None:
    _grade_and_score(a, "after")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--model", required=True, help="the judge model to pin, e.g. a DATED Azure deployment"
    )
    ap.add_argument(
        "--model-version", default=None, help="the deployment's model version (attested)"
    )
    ap.add_argument(
        "--upgrade-policy", default=None, help="the deployment's version-upgrade policy"
    )
    ap.add_argument("--per-task", type=int, default=150)
    ap.add_argument("--heldout-cap", type=int, default=150, help="optimizer --limit (0 = no cap)")
    ap.add_argument("--bff", default="http://localhost:8787")
    ap.add_argument("--agent", default="ws0_default")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "out" / "ragtruth")
    ap.add_argument(
        "--workspace-out", type=Path, default=REPO_ROOT / "out" / "workspaces" / "default" / "out"
    )
    ap.add_argument("--from", dest="start", choices=STEPS, default=STEPS[0])
    ap.add_argument("--to", dest="stop", choices=STEPS, default=STEPS[-1])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    a.slice = a.out / "slice_full.jsonl"
    a.calib = a.out / "calib_ragtruth.jsonl"
    todo = STEPS[STEPS.index(a.start) : STEPS.index(a.stop) + 1]
    arm = arm_attestation(a.model, a.model_version, a.upgrade_policy)
    print(
        f"plan: {' -> '.join(todo)} | model {a.model} ({arm['pinned_by']}) | per task {a.per_task} "
        f"| held-out cap {a.heldout_cap}"
    )
    if a.dry_run:
        return 0
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "arm_manifest.json").write_text(json.dumps(arm, indent=2))
    for name in todo:
        print(f"\n=== {name} ===", flush=True)
        globals()[f"step_{name}"](a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
