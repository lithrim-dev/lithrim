#!/usr/bin/env python
"""EXPERIMENT ARM (kept as a measured record of the RAGTruth pilot, not a product verb).

The paper's own prompted baseline on our model: RAGTruth Appendix D, verbatim, per task.

This is the paper's METHOD reproduced outside the council: one direct model call per response
with the Appendix D detection prompt for its task (typos included), temperature 0, the output
parsed from the paper's ``{"hallucination list": [...]}`` format. No role framing, no demos,
no DSPy signature, no floor, no audit: the row it produces is "the paper's prompt on our
deployment", scored response-level (any span => hallucinated) and span-level by
``lithrim score --slice ... --predictions ...``. The spans are UNTYPED (the paper's format carries
no type), so there is no per-code row; the importer manifest names that class.

Population: ``--slice`` (a Lithrim slice file, e.g. the 450 natural cut) or ``--population
test`` (every quality-good test-split response, the paper's own evaluation population).
Resumable: ids already in ``--out`` are skipped. Refusals and parse failures are recorded per
row (``error``) and reported as their own count, never dropped.

Usage:
    python examples/ragtruth/arms/paper_prompt.py --slice out/ragtruth/slice_full.jsonl --out out/ragtruth/paper_prompt_450.jsonl
    python examples/ragtruth/arms/paper_prompt.py --population test --out out/ragtruth/paper_prompt_2700.jsonl
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Appendix D, Table 11 (arXiv:2401.00396), verbatim including "contraction" and "a empty list".
PROMPTS = {
    "QA": (
        "Below is a question:\n{question}\n"
        "Below are related passages:\n{passages}\n"
        "Below is an answer:\n{answer}\n"
        "Your task is to determine whether the answer contains either or both of the following two types of hallucinations:\n"
        "1. conflict: instances where the answer presents direct contraction or opposition to the passages;\n"
        "2. baseless info: instances where the answer includes information which is not substantiated by or inferred from the passages.\n"
        'Then, compile the labeled hallucinated spans into a JSON dict, with a key "hallucination list" and its value is a list of hallucinated spans. '
        'If there exist potential hallucinations, the output should be in the following JSON format: {{"hallucination list": [hallucination span1, hallucination span2, ...]}}. '
        'Otherwise, leave the value as a empty list as following: {{"hallucination list": []}}.\n'
        "Output:"
    ),
    "Data2txt": (
        "Below is a structured data in the JSON format:\n{business_info}\n"
        "Below is an overview article written in accordance with the structured data:\n{overview}\n"
        "Your task is to determine whether the overview contains either or both of the following two types of hallucinations:\n"
        "1. conflict: instances where the overview presents direct contraction or opposition to the structured data;\n"
        "2. baseless info: instances where the generated overview includes information which is not substantiated by or inferred from the structured data.\n"
        'In JSON, "null" or "None" represents an unknown value rather than a negation.\n'
        'Then, compile the labeled hallucinated spans into a JSON dict, with a key "hallucination list" and its value is a list of hallucinated spans. '
        'If there exist potential hallucinations, the output should be in the following JSON format: {{"hallucination list": [hallucination span1, hallucination span2, ...]}}. '
        'Otherwise, leave the value as a empty list as following: {{"hallucination list": []}}.\n'
        "Output:"
    ),
    "Summary": (
        "Below is the original news:\n{article}\n"
        "Below is a summary of the news:\n{summary}\n"
        "Your task is to determine whether the summary contains either or both of the following two types of hallucinations:\n"
        "1. conflict: instances where the summary presents direct contraction or opposition to the original news;\n"
        "2. baseless info: instances where the generated summary includes information which is not substantiated by or inferred from the original news.\n"
        'Then, compile the labeled hallucinated spans into a JSON dict, with a key "hallucination list" and its value is a list of hallucinated spans. '
        'If there exist potential hallucinations, the output should be in the following JSON format: {{"hallucination list": [hallucination span1, hallucination span2, ...]}}. '
        'Otherwise, leave the value as a empty list as following: {{"hallucination list": []}}.\n'
        "Output:"
    ),
}


def fill_prompt(task: str, source_info, response: str) -> str:
    if task == "QA":
        return PROMPTS["QA"].format(
            question=source_info["question"], passages=source_info["passages"], answer=response
        )
    if task == "Data2txt":
        return PROMPTS["Data2txt"].format(
            business_info=json.dumps(source_info, ensure_ascii=False), overview=response
        )
    if task == "Summary":
        return PROMPTS["Summary"].format(article=source_info, summary=response)
    raise ValueError(f"unknown task {task!r}")


_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$")


def parse_output(text: str) -> tuple[list[str] | None, str | None]:
    """The paper's ``{"hallucination list": [...]}``; tolerant to a code fence, single quotes
    (Python-literal style), and a trailing sentence after the JSON. Returns (spans, error)."""
    raw = _FENCE.sub("", text or "").strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end < 0:
        return None, "no JSON object in output"
    body = raw[start : end + 1]
    obj = None
    for loader in (json.loads, ast.literal_eval):
        try:
            obj = loader(body)
            break
        except Exception:  # noqa: BLE001 — try the next loader
            continue
    if not isinstance(obj, dict):
        return None, "output is not a JSON object"
    key = next(
        (k for k in obj if k.replace("_", " ").strip().lower() == "hallucination list"), None
    )
    if key is None:
        return None, "no 'hallucination list' key"
    spans = obj[key]
    if not isinstance(spans, list):
        return None, "'hallucination list' is not a list"
    return [str(s).strip() for s in spans if str(s).strip()], None


def build_lm(deployment: str | None = None):
    """The same deployment the judge uses (the workspace's provider config), cache OFF,
    reached as a plain chat model: the paper's prompt is the whole message. ``deployment``
    names another Azure deployment on the same resource (FINETUNE-1: the trained grader is
    evaluated through the very prompt it was trained on, not through the council)."""
    os.environ["LITHRIM_JUDGE_CACHE"] = "0"
    from lithrim_bench.runtime.council.judges_dspy import build_judge_lm

    if deployment:
        # the builder drops a `model` kwarg (a BYOC selector), so the override rides the
        # per-role binding contract (LITHRIM_LLM_*_<ROLE>) on a role of its own
        role = "ragtruth_paper_prompt_override"
        suffix = role.upper()
        os.environ[f"LITHRIM_LLM_PROVIDER_{suffix}"] = "azure"
        os.environ[f"LITHRIM_LLM_MODEL_{suffix}"] = deployment
        for src, dst in (
            ("AZURE_OPENAI_API_KEY", "API_KEY"),
            ("AZURE_OPENAI_ENDPOINT", "API_BASE"),
            ("AZURE_OPENAI_API_VERSION", "API_VERSION"),
        ):
            if os.environ.get(src):
                os.environ[f"LITHRIM_LLM_{dst}_{suffix}"] = os.environ[src]
        return build_judge_lm(role)
    return build_judge_lm("ragtruth_detector")


def call(lm, prompt: str) -> dict:
    t0 = time.time()
    n_before = len(getattr(lm, "history", []) or [])
    try:
        out = lm(messages=[{"role": "user", "content": prompt}], temperature=0)
        first = out[0] if isinstance(out, list) and out else out
        # dspy>=3 returns [{"text": ...}] (or plain strings on older versions); take the text
        text = (
            first.get("text", "")
            if isinstance(first, dict)
            else ("" if first is None else str(first))
        )
        err = None
    except Exception as exc:  # noqa: BLE001 — a refusal is a recorded row, never an abort
        text, err = "", f"{type(exc).__name__}: {str(exc)[:300]}"
    entry = (getattr(lm, "history", []) or [None] * (n_before + 1))[n_before:]
    entry = entry[-1] if entry else None
    resp = (entry or {}).get("response") if isinstance(entry, dict) else None
    usage = (entry or {}).get("usage") or {} if isinstance(entry, dict) else {}
    return {
        "raw_output": text,
        "error": err,
        "served_model": (entry or {}).get("response_model") if isinstance(entry, dict) else None,
        "system_fingerprint": getattr(resp, "system_fingerprint", None),
        "prompt_tokens": int(usage.get("prompt_tokens") or 0) if isinstance(usage, dict) else 0,
        "completion_tokens": int(usage.get("completion_tokens") or 0)
        if isinstance(usage, dict)
        else 0,
        "latency_ms": int((time.time() - t0) * 1000),
    }


def population_rows(a) -> list[dict]:
    """Rows shaped {case_id, task_type, source_info, response} from a slice or the test split."""
    sources = {
        d["source_id"]: d
        for d in (json.loads(line) for line in (a.data_dir / "source_info.jsonl").open())
    }
    if a.slice:
        rows = []
        for line in a.slice.open():
            c = json.loads(line)
            src = sources[c["ragtruth"]["source_id"]]
            rows.append(
                {
                    "case_id": c["case_id"],
                    "task_type": src["task_type"],
                    "source_info": src["source_info"],
                    "response": c["artifacts"][0]["content"],
                    "labels": c["ragtruth"]["labels"],
                }
            )
        return rows
    rows = []
    for line in (a.data_dir / "response.jsonl").open():
        r = json.loads(line)
        if r.get("split") != "test" or r.get("quality") != "good":
            continue
        src = sources[r["source_id"]]
        rows.append(
            {
                "case_id": f"ragtruth_{r['id']}",
                "task_type": src["task_type"],
                "source_info": src["source_info"],
                "response": r["response"],
                "labels": [
                    {k: lab[k] for k in ("start", "end", "text", "label_type") if k in lab}
                    for lab in (r.get("labels") or [])
                ],
            }
        )
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--slice", type=Path, default=None)
    ap.add_argument("--population", choices=["test"], default=None)
    ap.add_argument("--data-dir", type=Path, default=REPO_ROOT / "out/ragtruth")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=0, help="stop after N rows (smoke)")
    ap.add_argument(
        "--deployment",
        default=None,
        help="an Azure deployment name on the workspace's resource (e.g. a fine-tuned grader)",
    )
    a = ap.parse_args()
    if bool(a.slice) == bool(a.population):
        sys.exit("pass exactly one of --slice or --population")
    rows = population_rows(a)
    done = set()
    if a.out.exists():
        done = {json.loads(line)["case_id"] for line in a.out.open() if line.strip()}
    todo = [r for r in rows if r["case_id"] not in done]
    if a.limit:
        todo = todo[: a.limit]
    print(f"population {len(rows)} | already done {len(done)} | to run {len(todo)}", flush=True)
    if not todo:
        return 0
    lm = build_lm(a.deployment)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    n_err = 0
    with a.out.open("a") as fh:
        for i, r in enumerate(todo, 1):
            res = call(lm, fill_prompt(r["task_type"], r["source_info"], r["response"]))
            spans, perr = (None, None) if res["error"] else parse_output(res["raw_output"])
            err = res["error"] or perr
            n_err += bool(err)
            fh.write(
                json.dumps(
                    {
                        "case_id": r["case_id"],
                        "task_type": r["task_type"],
                        "method": "paper_prompt_verbatim",
                        "deployment": a.deployment,
                        "hallucinated": (bool(spans) if spans is not None else None),
                        "spans": spans or [],
                        "labels": r["labels"],
                        "response": r["response"],
                        **res,
                        "error": err,  # the model error, else the parse error, else None
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            fh.flush()
            if i % 25 == 0 or i == len(todo):
                print(
                    f"  {i}/{len(todo)} done, {n_err} error(s), last served {res['served_model']}",
                    flush=True,
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
