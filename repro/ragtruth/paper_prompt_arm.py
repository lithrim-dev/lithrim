"""RAGTruth Table 11 detection prompt on a modern model: the paper's zero-shot baseline, re-run.

``run`` sends one user turn per record (no system prompt, temperature 0, k = 1) through the same
endpoints the council uses, resumably, and never reads gold. ``score`` applies the paper's rules:
response level = non-empty "hallucination list"; span level = pooled char overlap with the human
spans. Malformed outputs and transport failures are retained as records, never dropped.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from repro.ragtruth.score_reviewer import load_labels, prf

# Niu et al. 2024, Appendix D, Table 11, "Data-to-text writing", verbatim.
TABLE11_DATA2TXT = (
    "Below is a structured data in the JSON format:\n"
    "{business info}\n"
    "Below is an overview article written in accordance with the structured data:\n"
    "{overview}\n"
    "Your task is to determine whether the overview contains either or both of the following two "
    "types of hallucinations:\n"
    "1. conflict: instances where the overview presents direct contraction or opposition to the "
    "structured data;\n"
    "2. baseless info: instances where the generated overview includes information which is not "
    "substantiated by or inferred from the structured data.\n"
    'In JSON, "null" or "None" represents an unknown value rather than a negation.\n'
    "Then, compile the labeled hallucinated spans into a JSON dict, with a key "
    '"hallucination list" and its value is a list of hallucinated spans. If there exist potential '
    "hallucinations, the output should be in the following JSON format: "
    '{"hallucination list": [hallucination span1, hallucination span2, ...]}. Otherwise, leave the '
    'value as a empty list as following: {"hallucination list": []}.\n'
    "Output:\n"
)

GOLD_KEYS = frozenset(
    {
        "labels",
        "expected_safety_flags",
        "expected_artifact_verdict",
        "expected_compliance_verdict",
        "injection_recipes",
        "label_justification",
    }
)
RETRY_STATUS = {429, 500, 502, 503, 504}
# Cloudflare-fronted endpoints (featherless) answer 403 "error code: 1010" to the bare urllib agent.
USER_AGENT = "lithrim-bench/0.1 (paper-prompt-arm)"


def build_prompt(record: str, response: str) -> str:
    return TABLE11_DATA2TXT.replace("{business info}", record).replace("{overview}", response)


def load_cases(path, only=None) -> list[dict]:
    cases = []
    for ln in Path(path).read_text().splitlines():
        if not ln.strip():
            continue
        row = json.loads(ln)
        cid = row.get("case_id")
        leaked = GOLD_KEYS & set(row)
        if leaked:
            raise ValueError(f"row {cid} carries gold keys {sorted(leaked)}; refusing")
        if only is not None and cid not in only:
            continue
        cases.append(
            {
                "case_id": cid,
                "record": row["transcript"],
                "response": row["artifacts"][0]["content"],
                "meta": row.get("ragtruth") or {},
            }
        )
    return cases


_SPAN_KEYS = ("span", "text", "hallucination", "hallucinated_span", "content")


def _objects(text: str):
    """Every balanced JSON object in ``text``: fenced blocks first, then a brace scan."""
    for m in re.finditer(r"```(?:json)?\s*(.*?)```", text, flags=re.I | re.S):
        yield m.group(1).strip()
    dec = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _ = dec.raw_decode(text[i:])
        except ValueError:
            continue
        yield obj


def _spans(items) -> list[str] | None:
    out = []
    for it in items:
        if isinstance(it, str):
            out.append(it)
        elif isinstance(it, dict):
            val = next((it[k] for k in _SPAN_KEYS if isinstance(it.get(k), str)), None)
            if val is None:
                return None
            out.append(val)
        else:
            return None
    return out


def parse_output(text: str | None) -> dict:
    """The paper's answer shape, read leniently: the LAST JSON object carrying a
    "hallucination list" wins (a model's final answer); list items may be bare span strings
    (the paper's format) or objects carrying the span under a text key."""
    t = (text or "").strip()
    found = None
    shape_error = None
    for cand in _objects(t):
        obj = cand
        if isinstance(cand, str):
            try:
                obj = json.loads(cand)
            except ValueError:
                continue
        if not isinstance(obj, dict) or "hallucination list" not in obj:
            continue
        items = obj.get("hallucination list")
        spans = _spans(items) if isinstance(items, list) else None
        if spans is None:
            shape_error = "wrong shape"
            continue
        found = spans
    if found is not None:
        return {"valid": True, "spans": found, "error": None}
    return {"valid": False, "spans": [], "error": shape_error or "not json"}


def response_level(parsed: dict) -> str:
    if not parsed.get("valid"):
        return "invalid"
    return "halu" if parsed.get("spans") else "clean"


def load_env_from_cmd(cmd: str) -> list[str]:
    """Load KEY=VALUE lines from a command's stdout into the environment; values never printed."""
    out = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True).stdout
    names = []
    for ln in out.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#") or "=" not in ln:
            continue
        if ln.startswith("export "):
            ln = ln[len("export ") :]
        k, v = ln.split("=", 1)
        os.environ[k.strip()] = v.strip().strip("'\"")
        names.append(k.strip())
    return names


def make_call(
    provider: str, base: str, model: str, api_version: str | None, key: str, *, timeout=180
):
    base = base.rstrip("/")
    if provider == "azure":
        url = f"{base}/openai/deployments/{model}/chat/completions?api-version={api_version}"
        headers = {"api-key": key}
    else:
        url = f"{base}/chat/completions"
        if api_version:  # Azure AI inference (OpenAI-shaped) wants the query too
            url += f"?api-version={api_version}"
        headers = {"Authorization": f"Bearer {key}", "api-key": key}
    headers["Content-Type"] = "application/json"
    headers["User-Agent"] = USER_AGENT

    def call(prompt: str) -> dict:
        body: dict = {"messages": [{"role": "user", "content": prompt}], "temperature": 0}
        if provider != "azure":
            body["model"] = model
        dropped = False
        out = None
        for attempt in range(5):
            req = urllib.request.Request(
                url, data=json.dumps(body).encode(), headers=headers, method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    out = json.loads(resp.read().decode())
                break
            except urllib.error.HTTPError as e:
                text = e.read().decode(errors="replace")
                if e.code == 400 and "temperature" in text and "temperature" in body:
                    body.pop("temperature")
                    dropped = True
                    continue
                if e.code in RETRY_STATUS and attempt < 4:
                    time.sleep(min(60, 3 * 2**attempt))
                    continue
                raise RuntimeError(f"HTTP {e.code}: {text[:300]}") from None
            except (urllib.error.URLError, TimeoutError, OSError):
                if attempt < 4:
                    time.sleep(min(60, 3 * 2**attempt))
                    continue
                raise
        if out is None:
            raise RuntimeError("no response after retries")
        choice = (out.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content")
        if isinstance(content, list):
            content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        return {
            "content": content or "",
            "usage": out.get("usage") or {},
            "model": out.get("model"),
            "fingerprint": out.get("system_fingerprint"),
            "finish_reason": choice.get("finish_reason"),
            "temperature_dropped": dropped,
        }

    return call


def run(
    cases,
    call,
    *,
    out_dir,
    model,
    provider,
    endpoint_host,
    api_version,
    ceiling=None,
    abort_after_initial_failures=3,
) -> dict:
    out_dir = Path(out_dir)
    runs = out_dir / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    rep = {
        "model": model,
        "provider": provider,
        "endpoint_host": endpoint_host,
        "api_version": api_version,
        "prompt": "RAGTruth Table 11 data-to-text, verbatim",
        "n_cases": len(cases),
        "ok": 0,
        "invalid": 0,
        "errors": 0,
        "skipped_existing": 0,
        "temperature_dropped": 0,
        "tokens": {"prompt": 0, "completion": 0, "total": 0},
        "stopped": None,
        "started": datetime.now(timezone.utc).isoformat(),
    }
    done = 0
    for case in cases:
        if ceiling is not None and done >= ceiling:
            rep["stopped"] = "ceiling"
            break
        p = runs / f"{case['case_id']}.json"
        if p.exists():
            rep["skipped_existing"] += 1
            continue
        prompt = build_prompt(case["record"], case["response"])
        rec = {
            "case_id": case["case_id"],
            "model": model,
            "provider": provider,
            "endpoint_host": endpoint_host,
            "api_version": api_version,
            "request": {
                "system_prompt": None,
                "temperature": 0,
                "k": 1,
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "prompt_chars": len(prompt),
            },
            "meta": case.get("meta") or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        t0 = time.time()
        try:
            r = call(prompt)
            parsed = parse_output(r["content"])
            rec.update(
                raw=r["content"],
                parsed=parsed,
                response_level=response_level(parsed),
                usage=r.get("usage") or {},
                model_reported=r.get("model"),
                fingerprint=r.get("fingerprint"),
                finish_reason=r.get("finish_reason"),
                temperature_dropped=bool(r.get("temperature_dropped")),
                error=None,
            )
            rep["ok"] += 1
            if not parsed["valid"]:
                rep["invalid"] += 1
            if rec["temperature_dropped"]:
                rep["temperature_dropped"] += 1
            for k, src in (("prompt", "prompt_tokens"), ("completion", "completion_tokens")):
                rep["tokens"][k] += int(rec["usage"].get(src) or 0)
            rep["tokens"]["total"] += int(rec["usage"].get("total_tokens") or 0)
        except Exception as e:  # noqa: BLE001 - a failed call is a retained record, not a crash
            rec.update(
                raw=None,
                parsed=None,
                response_level="error",
                usage={},
                error=f"{type(e).__name__}: {e}"[:500],
            )
            rep["errors"] += 1
        rec["latency_ms"] = int((time.time() - t0) * 1000)
        if GOLD_KEYS & set(rec):
            raise RuntimeError("record would carry gold keys")
        p.write_text(json.dumps(rec, indent=1))
        done += 1
        if rep["ok"] == 0 and rep["errors"] >= abort_after_initial_failures:
            rep["stopped"] = "initial_failures"
            break
    rep["finished"] = datetime.now(timezone.utc).isoformat()
    (out_dir / "report.json").write_text(json.dumps(rep, indent=1))
    return rep


def span_overlap(rows) -> dict:
    pred_n = gold_n = overlap = 0
    for r in rows:
        text = r["response"]
        pred: set[int] = set()
        for s in r["pred"]:
            if not s:
                continue
            start = text.find(s)
            while start != -1:
                pred.update(range(start, start + len(s)))
                start = text.find(s, start + 1)
        gold: set[int] = set()
        for s, e in r["gold"]:
            gold.update(range(int(s), int(e)))
        pred_n += len(pred)
        gold_n += len(gold)
        overlap += len(pred & gold)
    p = overlap / pred_n if pred_n else 0.0
    rc = overlap / gold_n if gold_n else 0.0
    return {
        "pred_chars": pred_n,
        "gold_chars": gold_n,
        "overlap_chars": overlap,
        "precision": round(p, 4),
        "recall": round(rc, 4),
        "f1": round(2 * p * rc / (p + rc), 4) if p + rc else 0.0,
    }


def _load_runs(dirs) -> dict[str, dict]:
    recs = {}
    for d in dirs:
        for p in glob.glob(str(Path(d) / "*.json")):
            recs[Path(p).stem] = json.loads(Path(p).read_text())
    return recs


def score(run_dirs, *, labels, raw=None) -> dict:
    golds = load_labels(labels)
    recs = _load_runs(run_dirs)
    ids = sorted(set(recs) & set(golds))
    for c in ids:
        if recs[c].get("raw") is not None:
            recs[c]["parsed"] = parse_output(recs[c]["raw"])
            recs[c]["response_level"] = response_level(recs[c]["parsed"])
    rl = {c: recs[c].get("response_level") for c in ids}
    gg = [golds[c]["halu"] for c in ids]

    def preds(mode):
        return [
            "halu"
            if rl[c] == "halu" or (mode == "invalid_as_halu" and rl[c] in ("invalid", "error"))
            else "clean"
            for c in ids
        ]

    resp = {mode: prf(preds(mode), gg) for mode in ("invalid_as_clean", "invalid_as_halu")}
    per_gen = {}
    for g in sorted({golds[c]["model"] for c in ids}):
        sub = [c for c in ids if golds[c]["model"] == g]
        sg = [golds[c]["halu"] for c in sub]
        pr = prf(["halu" if rl[c] == "halu" else "clean" for c in sub], sg)
        per_gen[g] = {
            "n": len(sub),
            "base_rate": round(sum(sg) / len(sub), 4),
            "precision": pr["precision"],
            "recall": pr["recall"],
            "f1": pr["f1"],
        }
    out = {
        "n": len(ids),
        "positives": sum(gg),
        "base_rate": round(sum(gg) / len(ids), 4) if ids else 0.0,
        "invalid": sum(1 for c in ids if rl[c] == "invalid"),
        "errors": sum(1 for c in ids if rl[c] == "error"),
        "response_level": resp,
        "per_generator": per_gen,
        "tokens_total": sum(
            int((recs[c].get("usage") or {}).get("total_tokens") or 0) for c in ids
        ),
        "latency_ms_mean": round(sum(recs[c].get("latency_ms") or 0 for c in ids) / len(ids))
        if ids
        else 0,
        "limitation": "Paper rule: non-empty hallucination list = hallucinated; unparseable output "
        "is reported under both readings; human response-level gold; precision with base rate.",
    }
    if raw:
        rows = []
        by_id = {}
        for ln in Path(raw).read_text().splitlines():
            if ln.strip():
                r = json.loads(ln)
                by_id[str(r["id"])] = r
        for c in ids:
            r = by_id.get(c.replace("ragtruth_", ""))
            if r is None:
                continue
            parsed = recs[c].get("parsed") or {}
            rows.append(
                {
                    "response": r["response"],
                    "pred": parsed.get("spans") or [] if parsed.get("valid") else [],
                    "gold": [(lab["start"], lab["end"]) for lab in r.get("labels") or []],
                }
            )
        out["span_level"] = dict(span_overlap(rows), rows=len(rows))
    return out


def render(rep: dict, title: str) -> str:
    lines = [
        f"# {title}",
        "",
        f"n = {rep['n']}, positives {rep['positives']}, base rate "
        f"{rep['base_rate']}, invalid outputs {rep['invalid']}, errors {rep['errors']}, "
        f"tokens {rep['tokens_total']:,}, mean latency {rep['latency_ms_mean']} ms",
        "",
        "| reading | P | R | F1 | false clears | false blocks |",
        "|---|---|---|---|---|---|",
    ]
    for mode, v in rep["response_level"].items():
        lines.append(
            f"| {mode} | {v['precision']} | {v['recall']} | {v['f1']} | {v['false_clears']} | "
            f"{v['false_blocks']} |"
        )
    if rep.get("span_level"):
        s = rep["span_level"]
        lines += [
            "",
            f"Span level (pooled chars over {s['rows']} rows): P {s['precision']} / "
            f"R {s['recall']} / F1 {s['f1']} (pred {s['pred_chars']:,}, gold "
            f"{s['gold_chars']:,}, overlap {s['overlap_chars']:,})",
        ]
    lines += ["", "| generator | n | base rate | P | R | F1 |", "|---|---|---|---|---|---|"]
    for g, v in rep["per_generator"].items():
        lines.append(
            f"| {g} | {v['n']} | {v['base_rate']} | {v['precision']} | {v['recall']} | {v['f1']} |"
        )
    lines += ["", rep["limitation"], ""]
    return "\n".join(lines)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--provider", choices=("azure", "openai_compatible"), required=True)
    r.add_argument("--model", required=True)
    r.add_argument("--base", help="endpoint base; default from the provider's env var")
    r.add_argument("--api-version", help="azure only; default AZURE_OPENAI_API_VERSION")
    r.add_argument("--key-env", help="env var holding the key; default per provider")
    r.add_argument("--cases", required=True, help="gold-stripped ingest jsonl")
    r.add_argument("--only", help="jsonl whose case_ids select a subset (pilot)")
    r.add_argument("--out", required=True)
    r.add_argument("--ceiling", type=int)
    r.add_argument("--env-cmd", help="command whose stdout holds KEY=VALUE lines to load")
    r.add_argument("--timeout", type=float, default=180)
    s = sub.add_parser("score")
    s.add_argument("--runs", action="append", required=True)
    s.add_argument("--labels", required=True)
    s.add_argument("--raw", help="RAGTruth response.jsonl for span-level scoring")
    s.add_argument("--out", required=True)
    s.add_argument("--title", default="Paper-prompt arm")
    a = ap.parse_args(argv)
    if a.cmd == "score":
        rep = score(a.runs, labels=a.labels, raw=a.raw)
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "report.json").write_text(json.dumps(rep, indent=1))
        (out / "REPORT.md").write_text(render(rep, a.title))
        print(
            json.dumps(
                {k: rep[k] for k in ("n", "invalid", "errors")}
                | {"invalid_as_clean": rep["response_level"]["invalid_as_clean"]["f1"]}
            )
        )
        return
    if a.env_cmd:
        load_env_from_cmd(a.env_cmd)
    if a.provider == "azure":
        base = a.base or os.environ.get("AZURE_OPENAI_ENDPOINT", "")
        api_version = a.api_version or os.environ.get("AZURE_OPENAI_API_VERSION", "")
        key = os.environ.get(a.key_env or "AZURE_OPENAI_API_KEY", "")
    else:
        base = a.base or os.environ.get("OPENAI_COMPATIBLE_API_BASE", "")
        api_version = a.api_version or None
        key = os.environ.get(a.key_env or "OPENAI_COMPATIBLE_API_KEY", "")
    if not base or not key:
        raise SystemExit("endpoint base or key missing (env not loaded?)")
    only = None
    if a.only:
        only = {
            json.loads(ln)["case_id"] for ln in Path(a.only).read_text().splitlines() if ln.strip()
        }
    cases = load_cases(a.cases, only=only)
    call = make_call(a.provider, base, a.model, api_version, key, timeout=a.timeout)
    rep = run(
        cases,
        call,
        out_dir=a.out,
        model=a.model,
        provider=a.provider,
        endpoint_host=urlsplit(base).netloc,
        api_version=api_version,
        ceiling=a.ceiling,
    )
    print(
        json.dumps(
            {
                k: rep[k]
                for k in ("ok", "invalid", "errors", "skipped_existing", "tokens", "stopped")
            }
        )
    )


if __name__ == "__main__":
    main()
