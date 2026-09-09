#!/usr/bin/env python
"""EXPERIMENTAL: an Azure OpenAI fine-tuning client used once for the pilot; not part of the
product (Lithrim is not a training platform). Kept as a measured record, not a product verb.

Fine-tune a grader on the exported corpus (Azure OpenAI), then bind it back (FINETUNE-1).

Sub-commands, in the order a run goes:
  estimate   token count + list-price cost of a training file; no network, no spend
  upload     upload the training (and optional validation) JSONL to the Files API
  submit     create the fine-tuning job (PAID; refuses without --confirm-cost)
  status     poll a job; prints status, trained tokens, the resulting model name
  bind       after the operator has DEPLOYED the fine-tuned model (management plane, portal
             or `az cognitiveservices account deployment create`): probe it through the BFF
             provider config and bind it to a judge role

What the trained model learns: the paper's Appendix D prompt -> {"hallucination list": [...]}
(the export's azure-chat format). Its faithful evaluation is therefore
``python examples/ragtruth/arms/paper_prompt.py --deployment <name>``, scored by
``lithrim score --slice ... --predictions ...``. Binding it as a council judge is a SECOND row and a mismatch by construction
(the council asks the DSPy signature, not the prompt it was trained on); the report says so.

Credentials come from the workspace's provider file (AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY),
never from the manifest. Usage:
    set -a; . ./.provider_env; set +a
    python examples/ragtruth/arms/finetune_azure.py estimate --training out/ragtruth/export/train_supervised_azure-chat.jsonl
    python examples/ragtruth/arms/finetune_azure.py upload   --training ... [--validation ...]
    python examples/ragtruth/arms/finetune_azure.py submit   --training-file-id file-... --base gpt-4.1-mini-2025-04-14 --epochs 3 --confirm-cost
    python examples/ragtruth/arms/finetune_azure.py status   --job ftjob-...
    python examples/ragtruth/arms/finetune_azure.py bind     --deployment my-ft-deployment --role trained_grader
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
API_VERSION = os.environ.get("LITHRIM_FT_API_VERSION", "2025-04-01-preview")
# USD per 1M training tokens, list price (Azure OpenAI fine-tuning); hosting is per hour on top.
TRAINING_PRICE = {"gpt-4.1-mini": 5.00, "gpt-4.1": 25.00, "gpt-4o-mini": 3.00, "gpt-4o": 25.00}
HOSTING_PER_HOUR = {"gpt-4.1-mini": 1.70, "gpt-4.1": 1.70, "gpt-4o-mini": 1.70, "gpt-4o": 1.70}


# --------------------------------------------------------------------------- #
# pure helpers (tested offline)
# --------------------------------------------------------------------------- #
def estimate_tokens(path: Path) -> dict:
    """Rows and an approximate token count (chars/4) of a chat-format training file."""
    rows = chars = 0
    for line in path.open():
        if not line.strip():
            continue
        row = json.loads(line)
        rows += 1
        chars += sum(len(m.get("content") or "") for m in row.get("messages") or [])
    return {"rows": rows, "chars": chars, "tokens_estimate": int(chars / 4)}


def price_key(base: str) -> str | None:
    b = base.lower()
    for key in sorted(TRAINING_PRICE, key=len, reverse=True):
        if b.startswith(key):
            return key
    return None


def cost_estimate(tokens: int, base: str, epochs: int) -> dict:
    key = price_key(base)
    if key is None:
        return {"base": base, "priced": False}
    train = tokens / 1e6 * TRAINING_PRICE[key] * epochs
    return {
        "base": base,
        "priced": True,
        "epochs": epochs,
        "training_tokens_total": tokens * epochs,
        "training_usd_list": round(train, 2),
        "hosting_usd_per_hour": HOSTING_PER_HOUR[key],
        "note": "training at list price; hosting bills per hour from deployment until deleted",
    }


def job_body(
    training_file_id: str,
    base: str,
    epochs: int,
    suffix: str,
    validation_file_id: str | None,
    training_type: str | None = None,
) -> dict:
    body = {
        "model": base,
        "training_file": training_file_id,
        "hyperparameters": {"n_epochs": epochs},
        "suffix": suffix,
    }
    if validation_file_id:
        body["validation_file"] = validation_file_id
    if (
        training_type
    ):  # Azure: Standard (regional) | GlobalStandard (global training) | DeveloperTier
        body["trainingType"] = training_type
    return body


def live_jobs(listing: dict, suffix: str) -> list[dict]:
    """Jobs with this suffix that are not terminal: a second submit of the same corpus is a
    duplicate spend (live-caught 2026-09-09: a trial loop created two jobs), never silent."""
    return [
        j
        for j in listing.get("data") or []
        if j.get("suffix") == suffix and j.get("status") not in ("succeeded", "failed", "cancelled")
    ]


def bind_bodies(deployment: str, role: str) -> tuple[dict, dict, dict]:
    """The three BFF calls that bind a deployed fine-tune as a judge: the provider probe
    (grading plane, azure, per-role), the role's model pin, and the roster."""
    probe = {"plane": "grading", "provider": "azure", "role": role, "model": deployment}
    pin = {
        "model": deployment,
        "assigned_flags": ["SOURCE_CONTRADICTION", "UNSUPPORTED_ASSERTION"],
        "validator_refs": [],
    }
    roster = {"agent": "ws0_default", "roster": [role]}
    return probe, pin, roster


# --------------------------------------------------------------------------- #
# Azure OpenAI data plane (urllib; credentials from the environment)
# --------------------------------------------------------------------------- #
def _creds() -> tuple[str, str]:
    endpoint = (os.environ.get("AZURE_OPENAI_ENDPOINT") or "").rstrip("/")
    key = os.environ.get("AZURE_OPENAI_API_KEY") or ""
    if not endpoint or not key:
        sys.exit(
            "AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_API_KEY are not set (source the provider file)"
        )
    return endpoint, key


def _request(
    method: str,
    url: str,
    *,
    key: str,
    body: bytes | None = None,
    content_type: str = "application/json",
) -> dict:
    req = urllib.request.Request(
        url, data=body, method=method, headers={"api-key": key, "Content-Type": content_type}
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as exc:
        sys.exit(f"{method} {url} -> HTTP {exc.code}: {exc.read().decode()[:1500]}")


def upload_file(path: Path, *, endpoint: str, key: str) -> dict:
    boundary = "----lithrim-finetune"
    data = path.read_bytes()
    body = (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="purpose"\r\n\r\nfine-tune\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
            "Content-Type: application/jsonl\r\n\r\n"
        ).encode()
        + data
        + f"\r\n--{boundary}--\r\n".encode()
    )
    return _request(
        "POST",
        f"{endpoint}/openai/files?api-version={API_VERSION}",
        key=key,
        body=body,
        content_type=f"multipart/form-data; boundary={boundary}",
    )


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("estimate")
    e.add_argument("--training", type=Path, required=True)
    e.add_argument("--base", default="gpt-4.1-mini-2025-04-14")
    e.add_argument("--epochs", type=int, default=3)
    u = sub.add_parser("upload")
    u.add_argument("--training", type=Path, required=True)
    u.add_argument("--validation", type=Path, default=None)
    s = sub.add_parser("submit")
    s.add_argument("--training-file-id", required=True)
    s.add_argument("--validation-file-id", default=None)
    s.add_argument("--base", default="gpt-4.1-mini-2025-04-14")
    s.add_argument("--epochs", type=int, default=3)
    s.add_argument("--suffix", default="lithrim-ragtruth")
    s.add_argument(
        "--training-tokens", type=int, default=0, help="from `estimate`, for the cost line"
    )
    s.add_argument(
        "--training-type",
        default=None,
        help="Azure trainingType: Standard | GlobalStandard | DeveloperTier",
    )
    s.add_argument(
        "--allow-duplicate", action="store_true", help="submit even if a same-suffix job is live"
    )
    s.add_argument("--confirm-cost", action="store_true")
    st = sub.add_parser("status")
    st.add_argument("--job", required=True)
    st.add_argument("--wait", action="store_true", help="poll every 60 s until terminal")
    b = sub.add_parser("bind")
    b.add_argument("--deployment", required=True)
    b.add_argument("--role", default="trained_grader")
    b.add_argument("--bff", default="http://localhost:8787")
    b.add_argument("--confirm-cost", action="store_true", help="the probe makes one paid call")
    a = ap.parse_args()

    if a.cmd == "estimate":
        est = estimate_tokens(a.training)
        print(
            json.dumps({**est, **cost_estimate(est["tokens_estimate"], a.base, a.epochs)}, indent=2)
        )
        return 0
    endpoint, key = _creds() if a.cmd in ("upload", "submit", "status") else ("", "")
    if a.cmd == "upload":
        out = {"training": upload_file(a.training, endpoint=endpoint, key=key)}
        if a.validation:
            out["validation"] = upload_file(a.validation, endpoint=endpoint, key=key)
        print(
            json.dumps(
                {
                    k: {"id": v.get("id"), "status": v.get("status"), "bytes": v.get("bytes")}
                    for k, v in out.items()
                },
                indent=2,
            )
        )
        return 0
    if a.cmd == "submit":
        est = (
            cost_estimate(a.training_tokens, a.base, a.epochs)
            if a.training_tokens
            else {"priced": False}
        )
        if not a.confirm_cost:
            sys.exit(
                f"REFUSING to submit a paid fine-tuning job: {json.dumps(est)}; re-run with --confirm-cost"
            )
        live = live_jobs(
            _request(
                "GET", f"{endpoint}/openai/fine_tuning/jobs?api-version={API_VERSION}", key=key
            ),
            a.suffix,
        )
        if live and not a.allow_duplicate:
            sys.exit(
                f"REFUSING: {len(live)} job(s) with suffix {a.suffix!r} already pending/running "
                f"{[j['id'] for j in live]}; cancel them or pass --allow-duplicate"
            )
        body = job_body(
            a.training_file_id, a.base, a.epochs, a.suffix, a.validation_file_id, a.training_type
        )
        job = _request(
            "POST",
            f"{endpoint}/openai/fine_tuning/jobs?api-version={API_VERSION}",
            key=key,
            body=json.dumps(body).encode(),
        )
        print(
            json.dumps(
                {
                    "job": job.get("id"),
                    "status": job.get("status"),
                    "model": job.get("model"),
                    "cost_estimate": est,
                },
                indent=2,
            )
        )
        return 0
    if a.cmd == "status":
        while True:
            job = _request(
                "GET",
                f"{endpoint}/openai/fine_tuning/jobs/{a.job}?api-version={API_VERSION}",
                key=key,
            )
            print(
                json.dumps(
                    {
                        k: job.get(k)
                        for k in ("id", "status", "fine_tuned_model", "trained_tokens", "error")
                    }
                )
            )
            if not a.wait or job.get("status") in ("succeeded", "failed", "cancelled"):
                return 0
            time.sleep(60)
    if a.cmd == "bind":
        probe, pin, roster = bind_bodies(a.deployment, a.role)
        if not a.confirm_cost:
            sys.exit(
                f"REFUSING: the provider probe makes one paid call; bodies would be {json.dumps([probe, pin, roster])}; re-run with --confirm-cost"
            )

        def post(path, body, method="POST"):
            req = urllib.request.Request(
                a.bff + path,
                data=json.dumps(body).encode(),
                method=method,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.loads(r.read())

        # the role must exist: author it if absent (same lens as the detector, no demos)
        try:
            post(
                "/v1/judges",
                {
                    "role": a.role,
                    "lens_codes": pin["assigned_flags"],
                    "owned_codes": [],
                    "role_prompt": "YOU ARE THE TRAINED GRADER: a model fine-tuned on this workspace's exported corpus. Raise SOURCE_CONTRADICTION for a conflict with the source and UNSUPPORTED_ASSERTION for baseless information, each on an evidence span.",
                },
            )
        except urllib.error.HTTPError as exc:
            if exc.code != 409:
                raise
        probe["api_key"] = os.environ.get("AZURE_OPENAI_API_KEY", "")
        probe["endpoint"] = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
        probe["api_version"] = os.environ.get("AZURE_OPENAI_API_VERSION", "")
        print(
            "probe:",
            json.dumps(
                {k: v for k, v in post("/v1/provider/config", probe).items() if k != "api_key"}
            ),
        )
        print(
            "pin:",
            json.dumps(
                post(
                    f"/v1/judges/{a.role}?rationale=bind%20the%20trained%20grader",
                    pin,
                    method="PUT",
                )
            ),
        )
        print("roster:", json.dumps(post("/v1/council/roster", roster)))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
