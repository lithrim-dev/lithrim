"""Council batch through the running BFF: create/switch a workspace, ingest gold-stripped rows,
grade each case FRESH (paid, in-process trio), keep a freshness sentinel per record, and always
switch the app back to the home workspace. Keys stay inside the BFF; this file never sees one."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

GOLD_KEYS = {
    "expected_safety_flags",
    "expected_compliance_verdict",
    "expected_artifact_verdict",
    "clean_negative",
    "multi_defect",
    "severity",
    "injection_recipes",
    "label_justification",
    "ground_truth_basis",
    "annotation_source",
    "labels",
}
AGENT = "ws0_default"


def gold_leak(rows) -> list[tuple[str, str]]:
    leaks = []
    for r in rows:
        for k in sorted(GOLD_KEYS & set(r)):
            leaks.append((r.get("case_id"), k))
        if "labels" in (r.get("ragtruth") or {}):
            leaks.append((r.get("case_id"), "ragtruth.labels"))
    return leaks


def check_fresh(record: dict) -> dict:
    prov = ((record or {}).get("result") or {}).get("provenance") or {}
    total = ((prov.get("cost_tokens") or {}).get("total")) or 0
    reasons = []
    if not total:
        reasons.append("cost_tokens.total == 0 (replayed or no model call)")
    if prov.get("replay_of"):
        reasons.append(f"replay_of={prov.get('replay_of')}")
    if prov.get("council_error"):
        reasons.append("council_error=True")
    return {
        "ok": not reasons,
        "reasons": reasons,
        "cost_total": total,
        "cost_tokens": prov.get("cost_tokens"),
        "replay_of": prov.get("replay_of"),
        "council_error": bool(prov.get("council_error")),
        "model_bindings": prov.get("model_bindings"),
        "pipeline_run_id": prov.get("pipeline_run_id"),
        "timestamp": prov.get("timestamp"),
    }


def expected_count(n_ingested: int, pinned: int = 0) -> int:
    return n_ingested + pinned


def bff_call(method: str, path: str, body=None, tolerate=()):
    base = os.environ.get("LITHRIM_BFF_URL", "http://localhost:8787")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    tok = os.environ.get("LITHRIM_BFF_TOKEN")
    if tok:
        req.add_header("Authorization", f"Bearer {tok}")
    try:
        timeout = float(os.environ.get("LITHRIM_BFF_TIMEOUT", "600"))
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode(errors="replace")
        if exc.code in tolerate:
            return exc.code, {"detail": payload}
        raise RuntimeError(f"{method} {path} -> {exc.code}: {payload[:300]}") from None


def grade_cases(
    call, ids, *, ceiling: int, out_dir: Path, abort_after_initial_failures: int = 3
) -> dict:
    runs = Path(out_dir) / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    report = {
        "ok": 0,
        "failed": [],
        "not_fresh": [],
        "paid_calls": 0,
        "stopped_reason": None,
        "aborted": False,
        "cost_total": 0,
        "model_bindings": None,
        "per_case": [],
    }
    t0 = time.time()
    for i, cid in enumerate(ids, 1):
        if report["paid_calls"] >= ceiling:
            report["stopped_reason"] = "ceiling"
            break
        t1 = time.time()
        report["paid_calls"] += 1
        try:
            _, rec = call(
                "POST",
                "/v1/run-eval",
                {"agent": AGENT, "live": True, "in_process": True, "confirm": True, "case_id": cid},
            )
        except Exception as exc:  # noqa: BLE001 — one case never kills the batch; it is RETAINED
            report["failed"].append({"case_id": cid, "error": f"{type(exc).__name__}: {exc}"[:300]})
            if i == abort_after_initial_failures and report["ok"] == 0:
                report.update(stopped_reason="initial_failures", aborted=True)
                break
            continue
        fresh = check_fresh(rec)
        (runs / f"{cid}.json").write_text(json.dumps(rec, indent=1))
        row = {"case_id": cid, "secs": round(time.time() - t1, 1), **fresh}
        report["per_case"].append(row)
        if not fresh["ok"]:
            report["not_fresh"].append({"case_id": cid, "reasons": fresh["reasons"]})
            continue
        report["ok"] += 1
        report["cost_total"] += fresh["cost_total"]
        report["model_bindings"] = report["model_bindings"] or fresh["model_bindings"]
    report["secs"] = round(time.time() - t0)
    return report


def _snapshot_lenses() -> dict:
    snap = json.loads(
        (Path(__file__).resolve().parents[2] / "packs/_core/taxonomy_snapshot.json").read_text()
    )
    return {role: list(codes) for role, codes in (snap.get("lenses") or {}).items()}


def set_judge_lens(call, role: str, *, drop: set, snapshot_lens: dict) -> list:
    """Round-trip edit of ONE judge's lens in the active workspace: GET the judge, set
    ``assigned_flags`` to the snapshot lens minus ``drop``, PUT it back with every other field
    preserved, then GET again and REFUSE if a dropped code is still present."""
    _, cur = call("GET", f"/v1/judges/{role}?agent={AGENT}")
    target = [c for c in snapshot_lens[role] if c not in drop]
    body = {
        k: cur.get(k)
        for k in (
            "k",
            "temperature",
            "criterion",
            "display_name",
            "model",
            "provider",
            "validator_refs",
        )
    }
    body = {k: v for k, v in body.items() if v is not None}
    body["assigned_flags"] = target
    call(
        "PUT",
        f"/v1/judges/{role}?agent={AGENT}&rationale=arm+v2+lens+minus+{'+'.join(sorted(drop))}",
        body,
    )
    _, after = call("GET", f"/v1/judges/{role}?agent={AGENT}")
    still = sorted(set(after.get("assigned_flags") or []) & drop) or (
        [] if after.get("assigned_flags") else sorted(drop)
    )
    if still:
        raise RuntimeError(f"{role}: lens still carries {still} after PUT; refusing to grade")
    return target


def set_judge_binding(
    call, role: str, *, provider: str, model: str, endpoint: str, api_version: str = ""
) -> dict:
    """Round-trip edit of ONE judge's deployment binding in the active workspace: GET the judge,
    set provider / model / endpoint / api_version, PUT it back with every other field preserved,
    then GET again and REFUSE if the binding did not stick. A key never rides the request."""
    _, cur = call("GET", f"/v1/judges/{role}?agent={AGENT}")
    body = {
        k: cur.get(k)
        for k in (
            "k",
            "temperature",
            "criterion",
            "display_name",
            "validator_refs",
            "assigned_flags",
        )
    }
    body = {k: v for k, v in body.items() if v is not None}
    body.update(provider=provider, model=model, endpoint=endpoint, api_version=api_version)
    call(
        "PUT",
        f"/v1/judges/{role}?agent={AGENT}&rationale=arm+v3+rebind+{role}+to+{provider}+{model}",
        body,
    )
    _, after = call("GET", f"/v1/judges/{role}?agent={AGENT}")
    got = {k: after.get(k) for k in ("provider", "model", "endpoint")}
    if got != {"provider": provider, "model": model, "endpoint": endpoint}:
        raise RuntimeError(f"{role} binding did not stick: {got}")
    return {
        "role": role,
        **got,
        "api_version": after.get("api_version"),
        "k": after.get("k"),
        "temperature": after.get("temperature"),
    }


def _ingest(call, path: Path) -> int:
    raw = path.read_text()
    rows = [json.loads(ln) for ln in raw.splitlines() if ln.strip()]
    leaks = gold_leak(rows)
    if leaks:
        raise RuntimeError(f"gold would reach the reviewer: {leaks[:5]}")
    body = {
        "raw": raw,
        "fmt": "auto",
        "filename": path.name,
        "extraction_rules": "",
        "agent": AGENT,
    }
    _, prev = call("POST", "/v1/cases/ingest/preview", body)
    if prev.get("count") != len(rows):
        raise RuntimeError(f"{path.name}: preview count {prev.get('count')} != {len(rows)}")
    call("POST", "/v1/cases/ingest/commit", {"approved_template": None, **body})
    return [r["case_id"] for r in rows]


def run(
    call,
    *,
    ws: str,
    ingest_files,
    grade_ids,
    ceiling: int,
    out_dir: Path,
    home_ws: str,
    actor: str = "ragtruth-pilot@lithrim-bench",
    abort_after_initial_failures: int = 3,
    raise_on_abort: bool = False,
    drop_codes: set | None = None,
    snapshot_lens: dict | None = None,
    pack: str = "_core",
    rebind: list | None = None,
) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=False)
    report: dict = {"workspace": ws, "home_ws": home_ws}
    try:
        call(
            "POST",
            "/v1/workspaces",
            {"name": ws, "pack": pack, "actor": actor},
            tolerate=(400, 409),
        )
        call("POST", "/v1/workspace", {"name": ws})
        _, meta = call("GET", "/v1/workspaces")
        if meta.get("active") != ws:
            raise RuntimeError(f"switch failed: active={meta.get('active')}")
        _, seed = call("GET", "/v1/agent/template")
        ep = seed.get("eval_profile", {})
        call(
            "PUT",
            f"/v1/agent?rationale=ragtruth+data2txt+pilot+({ws})",
            {
                "name": AGENT,
                "eval_profile": {
                    "judges": [],
                    "council_config": ep.get("council_config", {}),
                    "ontology_ref": ep.get("ontology_ref", ""),
                    "ontology_path": ep.get("ontology_path", ""),
                    "tools": [],
                    "kb_bindings": {},
                    "severity_map_ref": ep.get("severity_map_ref", ""),
                },
                "dataset": seed["dataset"],
            },
        )
        if rebind:
            report["rebind"] = [set_judge_binding(call, **b) for b in rebind]
        _, rd = call("GET", f"/v1/agents/{AGENT}/readiness")
        if not rd.get("ok"):
            raise RuntimeError(f"readiness not ok: {rd.get('findings')}")
        if drop_codes:
            lens = snapshot_lens or _snapshot_lenses()
            report["lens"] = {
                role: set_judge_lens(call, role, drop=set(drop_codes), snapshot_lens=lens)
                for role, codes in lens.items()
                if set(codes) & set(drop_codes)
            }
        ingested: list[str] = [cid for p in ingest_files for cid in _ingest(call, Path(p))]
        if ingest_files:
            _, cases = call("GET", "/v1/cases")
            rows = cases.get("cases", cases) if isinstance(cases, dict) else cases
            listed = {r.get("case_id") for r in rows}
            missing = [cid for cid in ingested if cid not in listed]
            if missing:
                raise RuntimeError(
                    f"{len(missing)} ingested case(s) not listed by /v1/cases: {missing[:5]}"
                )
            report["corpus_listed"] = len(rows)
        report["ingested"] = len(ingested)
        report["grade"] = grade_cases(
            call,
            list(grade_ids),
            ceiling=ceiling,
            out_dir=out_dir,
            abort_after_initial_failures=abort_after_initial_failures,
        )
        if report["grade"]["aborted"] and raise_on_abort:
            raise RuntimeError("aborted: initial cases all failed")
        return report
    finally:
        try:
            call("POST", "/v1/workspace", {"name": home_ws})
        finally:
            (out_dir / "report.json").write_text(json.dumps(report, indent=1, default=str))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--ingest", action="append", default=[])
    ap.add_argument(
        "--grade", required=True, help="jsonl whose case_id column lists the cases to grade"
    )
    ap.add_argument(
        "--ceiling", type=int, required=True, help="hard cap on PAID /v1/run-eval calls"
    )
    ap.add_argument("--out", required=True, help="new directory; never overwritten")
    ap.add_argument("--home-ws", required=True)
    ap.add_argument("--pack", default="_core", help="pack id the workspace is created on")
    ap.add_argument(
        "--drop-code",
        action="append",
        default=[],
        help="remove this flag code from every judge lens that carries it (workspace-scoped)",
    )
    ap.add_argument(
        "--rebind",
        nargs=5,
        action="append",
        default=[],
        metavar=("ROLE", "PROVIDER", "MODEL", "ENDPOINT", "API_VERSION"),
        help="workspace-scoped deployment binding for one judge role",
    )
    a = ap.parse_args()
    ids = [json.loads(ln)["case_id"] for ln in Path(a.grade).read_text().splitlines() if ln.strip()]
    rep = run(
        bff_call,
        ws=a.workspace,
        ingest_files=a.ingest,
        grade_ids=ids,
        ceiling=a.ceiling,
        out_dir=Path(a.out),
        home_ws=a.home_ws,
        drop_codes=set(a.drop_code) or None,
        pack=a.pack,
        rebind=[
            dict(zip(("role", "provider", "model", "endpoint", "api_version"), r, strict=True))
            for r in a.rebind
        ]
        or None,
    )
    g = rep["grade"]
    print(
        json.dumps(
            {
                "ok": g["ok"],
                "failed": len(g["failed"]),
                "not_fresh": len(g["not_fresh"]),
                "paid_calls": g["paid_calls"],
                "cost_total_tokens": g["cost_total"],
                "stopped": g["stopped_reason"],
                "secs": g["secs"],
                "out": a.out,
            }
        )
    )
    return 0 if (g["ok"] and not g["failed"] and not g["not_fresh"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
