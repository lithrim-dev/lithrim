"""Export the graded corpus as labeled rows, with a split gate and label-basis tiers (EXPORT-1).

One row per graded labeled case, assembled from three sources the harness already writes:
the workspace corrections log (the ``gold-mismatch/1`` row: expected/raised/missed/spurious,
agreement, split, human spans, judge rollout), the run blob it names (floor dispositions per
contract, judge evidence spans, served model, latency), and the slice file (the artifact and
source text, source id, task). The dataset vocabulary comes from the ``kind: importer``
manifest, so every row carries both our codes and the dataset's terms.

Label-basis tiers, per row:
  floor-proved      a deterministic contract enforced a block on this case
  expert-confirmed  a human override row exists for this case (none until overrides are
                    routed into the corrections log; the tier is present and empty, never minted)
  judge-only        the judge's verdict with no deterministic proof

Split gate: ``--split calibration`` (the training export) refuses to include any row whose
``split`` is not ``calibration``; ``--split test`` is for reporting only and is never written
in a training format. A row with no split is excluded from a training export.

Training filter (``--filter``): ``supervised`` keeps rows whose codes agree with the human
label plus floor-proved rows; ``silver`` keeps floor-proved and judge-only rows without a
human check (the unlabeled-workflow setting).

Formats: ``generic`` (everything, JSONL) | ``paper`` (reference, response, labels
[{start,end,text,label_type}] in the dataset's training classes) | ``chat`` (chat-completion
fine-tuning JSONL: a prompt module's ``fill_prompt(task, source, response)`` as the user turn,
``{"hallucination list": [...]}`` as the assistant turn).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sqlite3
from pathlib import Path

from lithrim_bench.harness.plugins import (
    case_generator_model,
    case_gold_spans,
    case_source_id,
    case_task,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def locate(quote: str, text: str) -> tuple[int, int] | None:
    q = quote.strip().strip('"').strip("'")
    if not q:
        return None
    i = text.find(q)
    if i < 0:
        i = text.lower().find(q.lower())
    return (i, i + len(q)) if i >= 0 else None


def label_tier(floor_enforced: bool, expert_confirmed: bool) -> str:
    if floor_enforced:
        return "floor-proved"
    if expert_confirmed:
        return "expert-confirmed"
    return "judge-only"


def build_row(case: dict, gold: dict, blob: dict | None, vocab, *, pack: str | None = None) -> dict:
    """One export row (the generic shape). ``blob`` may be None for a run no longer on file."""
    artifact = case["artifacts"][0]["content"]
    grounded = (blob or {}).get("grounded") or {}
    floor = []
    for b in grounded.get("floor_blocks") or []:
        floor.append(
            {
                "contract": b.get("contract"),
                "contract_type": b.get("contract_type"),
                "flag": b.get("flag"),
                "disposition": b.get("disposition"),
                "injected": bool(b.get("injected")),
                "evidence": b.get("evidence"),
            }
        )
    for p in grounded.get("floor_passes") or []:
        floor.append(
            {
                "contract": p.get("contract"),
                "contract_type": p.get("contract_type"),
                "flag": p.get("flag"),
                "disposition": p.get("disposition") or "PASS",
                "injected": False,
                "evidence": p.get("evidence"),
            }
        )
    sem = ((blob or {}).get("stage_results") or {}).get("semantic") or {}
    judge_spans = []
    for ev in sem.get("evidence") or []:
        for sp in ev.get("spans") or []:
            q = (sp.get("quote") or "").strip()
            rng = locate(q, artifact) if q else None
            judge_spans.append(
                {
                    "judge": ev.get("judge"),
                    "code": ev.get("violation_code"),
                    "quote": q,
                    "start": rng[0] if rng else None,
                    "end": rng[1] if rng else None,
                    "located": rng is not None,
                }
            )
    votes = sem.get("judge_votes") or gold.get("rollout") or []
    v0 = votes[0] if votes else {}
    floor_enforced = any(f["injected"] for f in floor)
    tier = label_tier(floor_enforced, expert_confirmed=False)
    return {
        "case_id": case["case_id"],
        "source_id": case_source_id(case, pack=pack),
        "task_type": case_task(case, pack=pack),
        "generator_model": case_generator_model(case, pack=pack),
        # the slice declares the split (a case ingested before the field existed has none)
        "split": case.get("split") or gold.get("split"),
        "ground_truth_basis": gold.get("ground_truth_basis") or case.get("ground_truth_basis"),
        "vocabulary": vocab.id,
        "ontology_version": gold.get("ontology_version"),
        "contract_versions": gold.get("contract_versions") or [],
        "pipeline_run_id": gold.get("pipeline_run_id"),
        "graded_at": gold.get("ts"),
        "response": artifact,
        "source": case["transcript"],
        "source_kind": case.get("source_kind"),
        "judge": {
            "codes": gold.get("raised_codes") or [],
            "codes_dataset_terms": {
                c: vocab.terms_for(c) for c in (gold.get("raised_codes") or [])
            },
            "spans": judge_spans,
            "verdict": gold.get("final_verdict"),
            "reason": v0.get("reason"),
            "model": v0.get("model"),
            "served_model": v0.get("served_model"),
            "confidence": v0.get("confidence"),
            "latency_ms": v0.get("latency_ms"),
        },
        "floor": floor,
        "human": {
            "codes": gold.get("expected_codes") or [],
            "spans": gold.get("gold_spans") or case_gold_spans(case, pack=pack) or [],
        },
        "agrees_with_gold": gold.get("agrees_with_gold"),
        "missed": gold.get("missed") or [],
        "spurious": gold.get("spurious") or [],
        "label_basis": tier,
    }


def passes_filter(row: dict, mode: str) -> bool:
    if mode == "all":
        return True
    if row["label_basis"] == "floor-proved":
        return True
    if mode == "supervised":
        return bool(row.get("agrees_with_gold"))
    if mode == "silver":
        return row["label_basis"] in ("judge-only", "expert-confirmed")
    raise ValueError(mode)


def training_labels(row: dict, mode: str, vocab) -> list[dict]:
    """The spans a training row carries: the human spans under ``supervised`` (they are the
    label), the judge's located spans under ``silver`` (there is no human label to use). The
    class name is the dataset's own (``training_classes`` on the importer manifest)."""
    if mode == "supervised":
        out = []
        for lab in row["human"]["spans"]:
            code = lab.get("code") or ""
            out.append(
                {
                    "start": lab.get("start"),
                    "end": lab.get("end"),
                    "text": lab.get("text"),
                    "label_type": vocab.training_class_for(code)
                    if code
                    else (lab.get("label_type") or "").lower(),
                }
            )
        return out
    return [
        {
            "start": s["start"],
            "end": s["end"],
            "text": s["quote"],
            "label_type": vocab.training_class_for(s["code"]) if s.get("code") else "",
        }
        for s in row["judge"]["spans"]
        if s["located"]
    ]


def to_paper(row: dict, mode: str, vocab) -> dict:
    return {
        "reference": row["source"],
        "response": row["response"],
        "task_type": row["task_type"],
        "labels": training_labels(row, mode, vocab),
        "label_basis": row["label_basis"],
        "case_id": row["case_id"],
    }


def to_chat(row: dict, mode: str, fill_prompt, vocab) -> dict:
    labels = training_labels(row, mode, vocab)
    src = json.loads(row["source"]) if row["source_kind"] == "record" else row["source"]
    prompt = fill_prompt(row["task_type"], src, row["response"])
    target = json.dumps(
        {"hallucination list": [lab["text"] for lab in labels if lab.get("text")]},
        ensure_ascii=False,
    )
    return {
        "messages": [{"role": "user", "content": prompt}, {"role": "assistant", "content": target}]
    }


def gold_from_blob(case: dict, blob: dict, *, pack: str | None = None) -> dict | None:
    """The ``gold-mismatch/1`` row for a graded labeled case, rebuilt from its run blob when the
    corrections log has none (a service export reads the run store directly; the pipeline writes
    the log row itself). Same builder as the log, so the two never drift."""
    import types

    from lithrim_bench.harness.correction import build_gold_mismatch

    grounded = blob.get("grounded") or {}
    stage = blob.get("stage_results") or {}
    votes = (stage.get("semantic") or {}).get("judge_votes") or []
    active = blob.get("findings") or []
    active_codes = [
        f if isinstance(f, str) else (f.get("code") or f.get("flag") or f.get("violation_code"))
        for f in active
    ]
    if not any(active_codes):
        active_codes = sorted({str(c) for v in votes for c in (v.get("findings") or []) if c})
    row = build_gold_mismatch(
        case=case,
        result=stage,
        final_verdict=grounded.get("verdict") or blob.get("verdict"),
        active_codes=[c for c in active_codes if c],
        ontology=types.SimpleNamespace(
            ontology_version=blob.get("ontology_version")
            or (blob.get("grade_config") or {}).get("ontology_version")
        ),
        contract_versions=grounded.get("contract_versions") or blob.get("contract_versions") or (),
        case_id=case.get("case_id"),
        agent_id=blob.get("agent_id"),
        pipeline_run_id=blob.get("pipeline_run_id"),
        pack=pack,
    )
    if row is not None:
        row["ts"] = blob.get("timestamp")
    return row


def export_rows(
    cases: dict[str, dict],
    gold: dict[str, dict],
    blobs: dict[str, dict],
    vocab,
    *,
    split: str,
    filter_mode: str = "supervised",
    fmt: str = "generic",
    fill_prompt=None,
    pack: str | None = None,
) -> tuple[list[dict], list[dict]]:
    """The export as (generic rows, rows in ``fmt``): one row per graded labeled case on
    ``split`` that passes ``filter_mode``; an ungraded case is no row, never fabricated. A
    training format off the calibration split is refused (``ValueError``)."""
    if fmt != "generic" and split != "calibration":
        raise ValueError(
            "REFUSING: a training format may only be written from the calibration split"
        )
    if fmt == "chat" and fill_prompt is None:
        raise ValueError("--format chat needs --prompt-module")
    rows = []
    for cid, case in cases.items():
        g = gold.get(cid)
        if g is None:
            continue
        row = build_row(case, g, blobs.get(g.get("pipeline_run_id")), vocab, pack=pack)
        if row["split"] != split:
            continue
        if passes_filter(row, filter_mode):
            rows.append(row)
    if fmt == "generic":
        out = rows
    elif fmt == "paper":
        out = [to_paper(r, filter_mode, vocab) for r in rows]
    else:
        out = [to_chat(r, filter_mode, fill_prompt, vocab) for r in rows]
    return rows, out


def export_manifest(
    rows: list[dict], *, split: str, filter_mode: str, fmt: str, vocab, graded_from: str
) -> dict:
    tiers: dict[str, int] = {}
    for r in rows:
        tiers[r["label_basis"]] = tiers.get(r["label_basis"], 0) + 1
    return {
        "rows": len(rows),
        "split": split,
        "filter": filter_mode,
        "format": fmt,
        "tiers": tiers,
        "case_ids_sha256": hashlib.sha256(
            ",".join(sorted(r["case_id"] for r in rows)).encode()
        ).hexdigest(),
        "source_ids": sorted({r["source_id"] for r in rows if r.get("source_id")}),
        "vocabulary": vocab.id,
        "ontology_versions": sorted(
            {r["ontology_version"] for r in rows if r.get("ontology_version")}
        ),
        "contract_versions": sorted({v for r in rows for v in r.get("contract_versions") or []}),
        "served_models": sorted(
            {r["judge"]["served_model"] for r in rows if r["judge"].get("served_model")}
        ),
        "graded_from": graded_from,
    }


def load_inputs(a):
    cases = {json.loads(line)["case_id"]: json.loads(line) for line in a.slice.open()}
    gold: dict[str, dict] = {}
    for line in a.corrections.open():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("schema_version") == "gold-mismatch/1" and r.get("case_id") in cases:
            gold[r["case_id"]] = r  # newest row wins
    blobs: dict[str, dict] = {}
    if a.collections_db and a.collections_db.exists():
        con = sqlite3.connect(f"file:{a.collections_db}?mode=ro", uri=True)
        wanted = {g["pipeline_run_id"] for g in gold.values() if g.get("pipeline_run_id")}
        for (raw,) in con.execute("SELECT json FROM pipeline_runs"):
            d = json.loads(raw)
            if d.get("pipeline_run_id") in wanted:
                blobs[d["pipeline_run_id"]] = d
    return cases, gold, blobs


def _load_fill_prompt(spec: str):
    path = Path(spec) if Path(spec).exists() else REPO_ROOT / spec
    module_spec = importlib.util.spec_from_file_location("lithrim_prompt_module", path)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    fn = getattr(module, "fill_prompt", None)
    if not callable(fn):
        raise SystemExit(f"{spec} defines no fill_prompt(task, source, response)")
    return fn


def add_arguments(ap) -> None:
    ap.add_argument("--slice", type=Path, required=True)
    ap.add_argument(
        "--corrections",
        type=Path,
        default=REPO_ROOT / "out/workspaces/default/out/corrections.ndjson",
    )
    ap.add_argument(
        "--collections-db",
        type=Path,
        default=REPO_ROOT / "out/workspaces/default/collections.sqlite",
    )
    ap.add_argument("--split", choices=["calibration", "test"], required=True)
    ap.add_argument("--filter", choices=["all", "supervised", "silver"], default="supervised")
    ap.add_argument("--format", choices=["generic", "paper", "chat"], default="generic")
    ap.add_argument(
        "--prompt-module",
        default=None,
        help="with --format chat: a .py file defining fill_prompt(task, source, response)",
    )
    ap.add_argument(
        "--vocabulary",
        default=None,
        help="the kind:importer dataset (default: the pack's only importer)",
    )
    ap.add_argument("--pack", default=None)
    ap.add_argument("--out", type=Path, required=True)


def cmd_export(a) -> int:
    from .scoring import resolve_vocabulary

    vocab = resolve_vocabulary(a.vocabulary, a.pack)
    if vocab is None:
        raise SystemExit("no importer manifest to export against; pass --vocabulary")
    cases, gold, blobs = load_inputs(a)
    fill_prompt = None
    if a.format == "chat":
        if not a.prompt_module:
            raise SystemExit("--format chat needs --prompt-module")
        fill_prompt = _load_fill_prompt(a.prompt_module)
    try:
        rows, out_rows = export_rows(
            cases,
            gold,
            blobs,
            vocab,
            split=a.split,
            filter_mode=a.filter,
            fmt=a.format,
            fill_prompt=fill_prompt,
            pack=a.pack,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open("w") as fh:
        for out in out_rows:
            fh.write(json.dumps(out, ensure_ascii=False) + "\n")
    manifest = export_manifest(
        rows,
        split=a.split,
        filter_mode=a.filter,
        fmt=a.format,
        vocab=vocab,
        graded_from=str(a.corrections),
    )
    a.out.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2))
    print(
        json.dumps(
            {**manifest, "source_ids": f"{len(manifest['source_ids'])} (in the manifest file)"}
        )
    )
    return 0
