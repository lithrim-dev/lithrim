"""The product loop against a running stack: load, configure, grade, calibrate, re-grade.

Steps (each idempotent; ``run --from STEP`` resumes):
  download   the dataset's files into the data dir (the adapter's job)
  slice      the test cut (--per-task) + the optimizer corpus (calibration + test rows)
  ingest     the cut into the active workspace through the native front door
  judge      author/refresh the judge from its definition file and pin its model
  before     grade the cut (in-process, judge cache off) and score it: the baseline row
  optimize   DSPy BootstrapFewShot on the calibration rows, held-out = the test cut
  pin        copy the compiled demos into the workspace out dir through the pin gate
  after      grade the cut again and score it: the optimized row
  calib      grade the calibration slice so every case leaves a gold-mismatch row (opt-in)
  enrich     bootstrap demos from the calibration cases the judge got wrong (opt-in)

Hygiene the loop enforces rather than asks for:
  * a grade with ``summary.cache_replays > 0`` is refused (not a measurement);
  * ``summary.judge_errors`` (provider refusals etc.) is reported next to every score, never hidden;
  * the judge model must be pinned explicitly (``--model``), never the workspace's floating global;
  * the optimizer refuses to train on non-calibration rows (judge_optimize), and its result carries
    a provenance manifest (train/held-out ids, corpus + prompt + demo hashes, demos_out_of_sample);
  * a demo set is pinned only if its held-out score is not below the pinned set's (``pin_gate``).

Nothing here names a dataset: the adapter slices it, the judge file defines the reviewer, and
the importer manifest says where a case keeps its source id, task, and gold spans.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
from pathlib import Path

from . import http, scoring
from .adapters import load_adapter

REPO_ROOT = Path(__file__).resolve().parents[2]
STEPS = (
    "download",
    "slice",
    "ingest",
    "judge",
    "before",
    "optimize",
    "pin",
    "after",
    "calib",
    "enrich",
)

# The product loop is six verbs: load, configure, grade, calibrate, re-grade, export. The
# steps are the same loop at finer grain; the verbs are accepted as --from/--to aliases.
VERB_ALIASES = {
    "load": "download",  # download + slice + ingest
    "configure": "judge",  # judge role, model pin, roster
    "grade": "before",
    "calibrate": "optimize",  # optimize + the gated pin
    "re-grade": "after",
    "regrade": "after",
}


def load_judge(path: Path) -> dict:
    """A judge definition file: ``{role, lens_codes, role_prompt[, owned_codes]}``."""
    judge = json.loads(Path(path).read_text())
    missing = [k for k in ("role", "lens_codes", "role_prompt") if not judge.get(k)]
    if missing:
        raise SystemExit(f"judge file {path} lacks {missing}")
    judge.setdefault("owned_codes", [])
    return judge


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
    the deployment's version and policy. Neither -> refuse: a floating alias cannot anchor a
    before/after."""
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


def observed_served(matrix: list[dict]) -> dict[str, int]:
    """SERVED-MODEL-1: the served model versions the provider actually answered with across a
    graded cohort (``votes[].served_model``), counted. More than one distinct version inside a
    single arm means the deployment moved mid-run; None entries are votes with no observation."""
    counts: dict[str, int] = {}
    for row in matrix:
        for v in row.get("votes") or []:
            key = str(v.get("served_model") or "None")
            counts[key] = counts.get(key, 0) + 1
    return counts


def cohort_summary(grade: dict, slice_rows: list[dict] | None = None) -> dict:
    """The cohort-shape numbers a write-up quotes from one grade response: reviewer states,
    flag precision/recall, verdict accuracy, auto-clear purity (cleared cases that are human-
    clean), floor counts, genuine defects the floor cleared, judge errors, cache replays."""
    rows = grade.get("matrix") or []
    sc = grade.get("scorecard") or {}
    gold = {r["case_id"]: bool(r.get("expected_safety_flags")) for r in (slice_rows or [])}
    states: dict[str, int] = {}
    cleared_clean = cleared_total = 0
    for r in rows:
        st = ((r.get("review") or {}).get("state") or "UNKNOWN").upper()
        states[st] = states.get(st, 0) + 1
        if st == "CLEARED" and r["case_id"] in gold:
            cleared_total += 1
            cleared_clean += 0 if gold[r["case_id"]] else 1
    floor = sc.get("floor") or {}
    return {
        "states": states,
        "flag_precision": (sc.get("flag") or {}).get("precision"),
        "flag_recall": (sc.get("flag") or {}).get("recall"),
        "verdict_accuracy": sc.get("verdict_accuracy"),
        "auto_clear_purity": (f"{cleared_clean}/{cleared_total}" if cleared_total else None),
        "floor": {k: floor.get(k) for k in ("enforced", "cleared", "inconclusive")},
        "gold_defect_clears": len(floor.get("gold_defect_clears") or []),
        "judge_errors": (grade.get("summary") or {}).get("judge_errors"),
        "cache_replays": (grade.get("summary") or {}).get("cache_replays"),
    }


def enriched_calibration_ids(gold_rows: list[dict], calibration_ids: set[str]) -> list[str]:
    """ENRICH-1: the calibration cases whose gold-mismatch row says the judge DISAGREED with
    the label and MISSED at least one code (the graded meta-labels feeding the next
    optimization). Newest row per case wins; order is the log's own (stable)."""
    latest: dict[str, dict] = {}
    for r in gold_rows:
        if r.get("schema_version") != "gold-mismatch/1" or r.get("case_id") not in calibration_ids:
            continue
        latest[r["case_id"]] = r  # later rows overwrite: the newest run's comparison wins
    return [cid for cid, r in latest.items() if not r.get("agrees_with_gold") and r.get("missed")]


def contrastive_calibration_ids(gold_rows: list[dict], calibration_ids: set[str]) -> list[str]:
    """CONTRASTIVE-1: calibration cases from BOTH sides of the boundary, interleaved in equal
    number: cases the judge under-called (a missed code) and cases it over-called (a spurious
    code, nothing missed). Newest row per case wins. The bootstrap walks the trainset in this
    order, so a nailed miss-case yields a positive demo and a nailed spurious-case a clean one."""
    latest: dict[str, dict] = {}
    for r in gold_rows:
        if r.get("schema_version") != "gold-mismatch/1" or r.get("case_id") not in calibration_ids:
            continue
        latest[r["case_id"]] = r
    missed = [c for c, r in latest.items() if not r.get("agrees_with_gold") and r.get("missed")]
    spurious = [
        c
        for c, r in latest.items()
        if not r.get("agrees_with_gold") and r.get("spurious") and not r.get("missed")
    ]
    n = min(len(missed), len(spurious))
    out: list[str] = []
    for a, b in zip(missed[:n], spurious[:n], strict=False):
        out += [a, b]
    return out


def heldout_split_for(rows: list[dict]) -> str:
    """HOLDOUT-DEV-1: the split the optimizer holds out on: ``dev`` when the corpus carries a dev
    slice carved from the calibration split, else ``test`` (a corpus built before the carve)."""
    return "dev" if any(r.get("split") == "dev" for r in rows) else "test"


def build_enriched_corpus(calib_rows: list[dict], chosen: set[str]) -> list[dict]:
    """The optimizer corpus for the enriched round: calibration rows restricted to ``chosen``
    (the mismatch cases), the held-out rows (dev, or test in an older corpus) unchanged. The
    optimizer's own holdout gate still applies."""
    return [r for r in calib_rows if r["split"] != "calibration" or r["case_id"] in chosen]


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


def summarize_optimize(opt_dir: Path, role: str) -> str:
    """One line from the optimizer's three files: the result (config, delta, manifest) plus the
    two score files (``run_optimize`` keeps baseline/optimized OUT of result_*.json)."""
    result = json.load((opt_dir / f"result_dspy3b_{role}.json").open())
    scores = {
        k: json.load((opt_dir / f"score_{k}_dspy3b_{role}.json").open())
        for k in ("baseline", "optimized")
    }
    m = result.get("manifest") or {}
    cc = result.get("compile_config") or {}
    return (
        f"optimize: {cc.get('n_demos_bootstrapped')} demos ({cc.get('n_positive_demos')} positive) "
        f"from {m.get('demo_source_ids')}, out_of_sample={m.get('demos_out_of_sample')}; held-out "
        f"{result.get('n_heldout')}: graded {scores['baseline'].get('graded', 0):.2f} -> "
        f"{scores['optimized'].get('graded', 0):.2f}, precision {scores['baseline'].get('precision', 0):.2f} -> "
        f"{scores['optimized'].get('precision', 0):.2f}, recall {scores['baseline'].get('recall', 0):.2f} -> "
        f"{scores['optimized'].get('recall', 0):.2f}; refused {scores['baseline'].get('errors')} -> "
        f"{scores['optimized'].get('errors')}; model {m.get('model')}"
    )


def pin_gate(
    candidate_graded: float | None, pinned_graded: float | None, *, force: bool = False
) -> str:
    """PIN-GATE-1: the engine's gate (``judge_optimize.pin_gate``) with the CLI's semantics: a
    refusal is a SystemExit, a forced pin names --force-pin in its message."""
    from lithrim_bench.runtime.council.judge_optimize import pin_gate as _gate

    ok, reason = _gate(candidate_graded, pinned_graded, force=force)
    if not ok:
        raise SystemExit(reason + " (--force-pin to override)")
    return reason.replace("by force", "by --force-pin")


def plan(start: str, stop: str) -> tuple[str, ...]:
    """The steps a ``--from``/``--to`` pair (verbs accepted) runs, in order."""
    start = VERB_ALIASES.get(start, start)
    stop = VERB_ALIASES.get(stop, stop)
    if stop == "optimize":  # "calibrate" means optimize AND the gated pin
        stop = "pin"
    return STEPS[STEPS.index(start) : STEPS.index(stop) + 1]


# --------------------------------------------------------------------------- #
# the steps (each takes the namespace ``a`` the CLI builds)
# --------------------------------------------------------------------------- #
_post = http.post
_put = http.put


def _run(cmd: list[str], env: dict | None = None) -> None:
    print("$", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, env=env)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.open() if line.strip()]


def _adapter(a):
    if not getattr(a, "adapter", None):
        raise SystemExit("this step needs a dataset adapter (--adapter path/to/adapter.py)")
    if getattr(a, "_adapter_module", None) is None:
        a._adapter_module = load_adapter(a.adapter)
    return a._adapter_module


def step_download(a) -> None:
    adapter = _adapter(a)
    download = getattr(adapter, "download", None)
    if callable(download):
        download(a.data_dir)
    else:
        print(f"adapter {a.adapter} has no download(); expecting the files under {a.data_dir}")


def step_slice(a) -> None:
    adapter = _adapter(a)
    cases = adapter.slice_cases(a.data_dir, per_task=a.per_task, split="test", natural=True)
    _write_jsonl(a.slice, cases)
    print(f"wrote {a.slice}: {len(cases)} test cases")
    rows = adapter.calibration_corpus(a.data_dir, per_task=a.per_task, test_cases=cases)
    _write_jsonl(a.calib, rows)
    n_cal = sum(1 for r in rows if r.get("split") == "calibration")
    held = heldout_split_for(rows)
    print(f"wrote {a.calib}: {n_cal} calibration + {len(rows) - n_cal} {held} rows (the pin gate's held-out)")


def _ingest(a, path: Path) -> int:
    raw = path.read_text()
    prev = _post(
        a.bff, "/v1/cases/ingest/preview", {"raw": raw, "filename": path.name, "agent": a.agent}
    )
    if not prev.get("native"):
        raise SystemExit("the slice must ingest through the native path (no mapper, labels kept)")
    res = _post(
        a.bff,
        "/v1/cases/ingest/commit",
        {
            "raw": raw,
            "filename": path.name,
            "agent": a.agent,
            "approved_template": prev.get("template"),
        },
    )
    return len(res.get("cases", []))


def step_ingest(a) -> None:
    n = _ingest(a, a.slice)
    print(f"ingested {n} labeled cases into agent {a.agent}")


def step_judge(a) -> None:
    j = a.judge_def
    body = {
        "role": j["role"],
        "lens_codes": j["lens_codes"],
        "owned_codes": j.get("owned_codes") or [],
        "role_prompt": j["role_prompt"],
    }
    try:
        _post(a.bff, "/v1/judges?rationale=lithrim%20configure", body, timeout=120)
        print(f"authored judge {j['role']}")
    except urllib.error.HTTPError as exc:
        if exc.code != 409:
            raise
        print(f"judge {j['role']} exists")
    _put(
        a.bff,
        f"/v1/judges/{j['role']}?rationale=pin%20the%20arm%27s%20model",
        {"model": a.model, "assigned_flags": j["lens_codes"], "validator_refs": []},
    )
    _post(a.bff, "/v1/council/roster", {"agent": a.agent, "roster": [j["role"]]}, timeout=120)
    print(f"pinned {j['role']} to {a.model}; roster = [{j['role']}]")


def _grade_cohort(a, ids: list[str]) -> dict:
    """GRADE-JOB-1: grade through the BFF's background job and poll it, printing progress; a
    server without the job route (no job_id in the answer) is graded synchronously. ``a.resume_job``
    continues an interrupted job instead of starting one."""
    import time

    body = {"agent": a.agent, "in_process": True, "case_ids": ids, "background": True}
    if getattr(a, "resume_job", None):
        body = {"agent": a.agent, "resume": a.resume_job, "background": True}
        a.resume_job = None
    res = _post(a.bff, "/v1/cases/grade", body)
    if not res.get("job_id"):
        return res
    job_id = res["job_id"]
    print(f"grade job {job_id}: {res.get('done', 0)}/{res.get('total')} (resume with --resume-job {job_id})")
    last = -1
    while True:
        time.sleep(getattr(a, "poll_seconds", 5))
        job = http.get(a.bff, f"/v1/jobs/{job_id}", timeout=120)
        if job.get("done") != last:
            last = job.get("done")
            print(f"  graded {last}/{job.get('total')}", flush=True)
        if job.get("status") == "done":
            return job["result"]
        if job.get("status") != "running":
            raise SystemExit(f"grade job {job_id} {job.get('status')}: {job.get('error')}")


def _grade_and_score(a, tag: str) -> None:
    slice_rows = _read_jsonl(a.slice)
    ids = [r["case_id"] for r in slice_rows]
    res = _grade_cohort(a, ids)
    out = a.out / f"grade_{tag}.json"
    out.write_text(json.dumps(res, indent=1))
    print(check_measurement(res["summary"]))
    print("cohort:", json.dumps(cohort_summary(res, slice_rows)))
    served = observed_served(res.get("matrix") or [])
    print(f"served model versions observed: {served}")
    manifest_path = a.out / "arm_manifest.json"
    arm = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    arm.setdefault("served_models_observed", {})[tag] = served
    versions = [k for k in served if k != "None"]
    if len(versions) == 1 and not arm.get("dated_model_id"):
        arm["pinned_by"] = (
            f"served version observed on every vote: {versions[0]} (upgrade policy: {arm.get('upgrade_policy')})"
        )
    elif len(versions) > 1:
        arm["pinned_by"] = f"WARNING: {len(versions)} served versions inside one arm {versions}"
    manifest_path.write_text(json.dumps(arm, indent=2))
    print(floor_reading(res["scorecard"]))
    audits = scoring.audits_for_grade(a.bff, res, slice_rows)
    result = scoring.score(slice_rows, audits, pack=getattr(a, "pack", None))
    vocab = scoring.resolve_vocabulary(getattr(a, "vocabulary", None), getattr(a, "pack", None))
    text = scoring.render(result, vocab)
    print(text)
    (a.out / f"score_{tag}.txt").write_text(text + "\n")


def step_before(a) -> None:
    role = a.judge_def["role"]
    demos = list(a.workspace_out.glob(f"compiled_demos_*_{role}.json"))
    if demos and getattr(a, "tag_before", "before") == "before":
        raise SystemExit(
            f"demos already pinned ({demos[0].name}); remove them for a baseline grade"
        )
    _grade_and_score(a, getattr(a, "tag_before", "before"))


def step_optimize(a) -> None:
    role = a.judge_def["role"]
    env = dict(os.environ)
    env.setdefault("LITHRIM_BENCH_PACK_OVERLAY_DIR", str(REPO_ROOT / "out" / "pack_overlay"))
    opt_dir = getattr(a, "out_optimize", None) or a.out / "optimize"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "optimize_judge.py"),
        "--role",
        role,
        "--corpus",
        str(a.calib),
        "--out",
        str(opt_dir),
        "--heldout-split",
        heldout_split_for(_read_jsonl(a.calib)),
        "--confirm-cost",
    ]
    if a.heldout_cap:
        cmd += ["--limit", str(a.heldout_cap)]
    cmd += list(getattr(a, "optimize_extra", []) or [])
    _run(cmd, env=env)
    print(summarize_optimize(opt_dir, role))
    result = json.load((opt_dir / f"result_dspy3b_{role}.json").open())
    if not (result.get("manifest") or {}).get("demos_out_of_sample"):
        raise SystemExit("REFUSING to pin: a compiled demo does not trace to a calibration row")


def step_pin(a) -> None:
    from lithrim_bench.runtime.council.judge_optimize import pin_demos

    role = a.judge_def["role"]
    opt_dir = getattr(a, "out_optimize", None) or a.out / "optimize"
    pin = pin_demos(opt_dir, a.workspace_out, role, force=getattr(a, "force_pin", False))
    if not pin["pinned"]:
        raise SystemExit(pin["reason"] + " (--force-pin to override)")
    print(f"{pin['reason'].replace('by force', 'by --force-pin')}: {pin['demos_path']}")


def step_after(a) -> None:
    _grade_and_score(a, a.tag)


def step_calib(a) -> None:
    """Grade the CALIBRATION slice (split=calibration on every case) so each case leaves a
    gold-mismatch row in the workspace log; scored against its own human labels for the
    record. Output grade_calib.json."""
    train = a.out / "slice_train.jsonl"
    if not train.exists():
        adapter = _adapter(a)
        cases = adapter.slice_cases(a.data_dir, per_task=a.per_task, split="train", natural=True)
        _write_jsonl(train, cases)
    _ingest(a, train)
    saved_slice = a.slice
    a.slice = train
    try:
        _grade_and_score(a, "calib")
    finally:
        a.slice = saved_slice


def step_enrich(a) -> None:
    """ENRICH-1 / CONTRASTIVE-1: bootstrap demos from calibration cases the judge got wrong
    (miss-only, or both sides of the boundary interleaved with --contrastive), pin through
    the gate, and re-grade the test cut."""
    log = a.workspace_out / "corrections.ndjson"
    gold = _read_jsonl(log) if log.exists() else []
    calib_rows = _read_jsonl(a.calib)
    calibration_ids = {r["case_id"] for r in calib_rows if r["split"] == "calibration"}
    contrastive = getattr(a, "contrastive", False)
    ordered = (
        contrastive_calibration_ids(gold, calibration_ids)
        if contrastive
        else enriched_calibration_ids(gold, calibration_ids)
    )
    chosen = set(ordered)
    if not chosen:
        raise SystemExit(
            "no calibration gold-mismatch rows to learn from; run the calib step first"
        )
    kind = "contrastive" if contrastive else "enriched"
    enriched = a.out / f"calib_{kind}.jsonl"
    by_id = {r["case_id"]: r for r in calib_rows}
    # calibration rows in the CHOSEN order (the bootstrap walks the file), then the held-out rows
    _write_jsonl(
        enriched,
        [by_id[c] for c in ordered] + [r for r in calib_rows if r["split"] != "calibration"],
    )
    print(f"{kind} corpus: {len(chosen)} calibration cases + the held-out rows -> {enriched}")
    saved = a.calib
    a.calib = enriched
    try:
        a.out_optimize = a.out / f"optimize_{kind}"
        a.optimize_extra = ["--no-coverage-aware"] if contrastive else []
        step_optimize(a)
        step_pin(a)
    finally:
        a.calib = saved
    _grade_and_score(a, a.tag if a.tag != "after" else kind)


def run_steps(a, todo: tuple[str, ...]) -> int:
    """Print the plan, then run each step unless ``--dry-run``."""
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
