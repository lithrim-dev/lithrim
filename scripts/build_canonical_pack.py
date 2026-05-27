#!/usr/bin/env python3
"""Author ``eval_pack=paper_v1_n12_canonical`` in lithrim-backend's Mongo.

Single-source-of-truth pack manifest: ``out/paper_v1_n12_canonical.spec.json``.
Picklist (case_ids under test):     ``/tmp/pilot_picklist.json``.

Path T closing condition (per REPORT_canonical_12_validation_2026-05-28.md §5
+ S-P1-14 closure §10): every case carries
``expected_safety_flags_strict`` plus ``expected_safety_flags_accepted_substitutes``
so the paper-bearing taxonomy-widening contract is explicit, not implicit.

Run:
    PYENV_VERSION=debuglithrim \\
    MONGODB_URI=mongodb://localhost:27017 \\
    S3_BUCKET_NAME=lithrim \\
    S3_ENDPOINT_URL=http://localhost:9000 \\
    AWS_ACCESS_KEY_ID=minioadmin \\
    AWS_SECRET_ACCESS_KEY=minioadmin \\
    LITHRIM_ORG_ID=69b82f072c01d1cc481da187 \\
    LITHRIM_AGENT_ID=69e8eed80774d8129275bb4a \\
    pyenv exec python scripts/build_canonical_pack.py

Halt-and-error if ``eval_pack=paper_v1_n12_canonical`` already exists in Mongo.
Never deletes any existing doc. Idempotent S3 uploads (overwrite same key) but
gated behind the Mongo halt-and-error so a partial re-run never produces
duplicate Mongo state.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import boto3
from bson import ObjectId
from pymongo import MongoClient

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lithrim_bench.picklist import resolve_case_fixtures  # noqa: E402

SPEC_PATH = REPO_ROOT / "out" / "paper_v1_n12_canonical.spec.json"
PICKLIST_PATH = Path("/tmp/pilot_picklist.json")
PACK_ID = "paper_v1_n12_canonical"


def _git_rev_parse() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, stderr=subprocess.DEVNULL
        )
        return out.decode().strip()
    except Exception:
        return "<unknown>"


def _build_eval_pack_doc(
    *,
    organization_id: str,
    eval_case_ids: list[str],
    bench_sha: str,
    spec: dict[str, Any],
    spec_hash: str,
) -> dict[str, Any]:
    """Construct the eval_pack Mongo doc.

    The Pydantic ``EvalPack`` model at
    ``lithrim-backend/app/models/eval_pack.py`` does not declare
    ``organization_id`` but every existing eval_pack in ``velto.eval_pack``
    carries it (see ``db.eval_pack.distinct("organization_id")``). We match
    that precedent by writing organization_id as a raw field.
    """
    now = dt.datetime.now(dt.timezone.utc)
    return {
        "pack_id": PACK_ID,
        "name": spec["name"],
        "description": spec.get("description"),
        "agent_type": None,
        "version": spec["version"],
        "status": "draft",
        "content_hash": spec_hash,
        "published_at": None,
        "organization_id": organization_id,
        "targets": {},
        "thresholds": {},
        "never_events": [],
        "eval_case_paths": [],
        "eval_case_ids": eval_case_ids,
        "jurisdiction": None,
        "threshold_config": {},
        "created_at": now,
        "metadata": {
            "paper": "paper-1-copilot",
            "source_picklist": str(PICKLIST_PATH),
            "source_commit_bench": bench_sha,
            "source_commit_backend": spec["source_commit_backend"],
            "spec_path": str(SPEC_PATH.relative_to(REPO_ROOT)),
            "case_count": spec["case_count"],
            "promotion_enum": spec["promotion_enum"],
            "authored_at": spec["authored_at"],
            "authored_by": spec["authored_by"],
        },
    }


def _verdict_list_to_singular(verdicts: list[str]) -> str:
    """Pick a singular expected_verdict to satisfy the required field.

    The existing EvalCase schema requires ``expected_verdict: str``. For the
    Path T multi-value contract we ALSO populate
    ``expected_compliance_verdict_list``; this returns the most informative
    singular value for the legacy field. Priority: reject > needs_review >
    approve (most restrictive wins for legacy reporting).
    """
    order = ("reject", "needs_review", "approve")
    for v in order:
        if v in verdicts:
            return v
    return verdicts[0] if verdicts else "approve"


def _build_eval_case_doc(
    *,
    organization_id: str,
    pack_id: str,
    case_spec: dict[str, Any],
    fixture: dict[str, Any],
    transcript_s3_key: str,
    artifacts_s3_key: str,
    bench_sha: str,
    created_by: str,
) -> dict[str, Any]:
    """Construct one eval_case Mongo doc per the EvalCase Pydantic schema.

    Required: organization_id, pack_id, source_conversation_id,
              transcript_s3_key, expected_verdict, created_by.

    Path T contract additive Optionals (added 2026-05-28 commit 3):
      paper_pick_label, expected_safety_flags_strict,
      expected_safety_flags_accepted_substitutes,
      expected_compliance_verdict_list, expected_structural_verdict.
    """
    now = dt.datetime.now(dt.timezone.utc)
    verdict_list = case_spec["expected_compliance_verdict_list"]
    return {
        "organization_id": organization_id,
        "pack_id": pack_id,
        "source_conversation_id": f"bench://{pack_id}/{case_spec['case_id']}",
        "source_type": "manual",
        "transcript_s3_key": transcript_s3_key,
        "expected_verdict": _verdict_list_to_singular(verdict_list),
        "expected_failure_type": case_spec.get("expected_artifact_verdict"),
        "expected_artifacts": [
            {
                "type": a.get("type"),
                "expected_artifact_verdict": case_spec.get("expected_artifact_verdict"),
            }
            for a in (fixture.get("artifacts") or [])
        ],
        "expected_safety_flags": case_spec["expected_safety_flags_strict"],
        "artifacts_s3_key": artifacts_s3_key,
        "metadata": {
            "agent_id": os.environ.get("LITHRIM_AGENT_ID", "").strip() or None,
            "paper": "paper-1-copilot",
            "source_pack_bench": case_spec["source_pack"],
            "pick_kind": case_spec["pick_kind"],
            "promotion_disposition": case_spec["promotion_disposition"],
            "promotion_rationale": case_spec["promotion_rationale"],
            "structural_catch_via": case_spec.get("structural_catch_via"),
            "source_commit_bench": bench_sha,
            "spec_path": str(SPEC_PATH.relative_to(REPO_ROOT)),
        },
        "paper_pick_label": case_spec["paper_pick_label"],
        "expected_safety_flags_strict": case_spec["expected_safety_flags_strict"],
        "expected_safety_flags_accepted_substitutes": case_spec[
            "expected_safety_flags_accepted_substitutes"
        ],
        "expected_compliance_verdict_list": verdict_list,
        "expected_structural_verdict": case_spec["expected_structural_verdict"],
        "created_at": now,
        "created_by": created_by,
    }


def main() -> int:
    organization_id = os.environ.get("LITHRIM_ORG_ID", "").strip()
    if not organization_id:
        sys.stderr.write("ERROR: LITHRIM_ORG_ID not set (e.g., 69b82f072c01d1cc481da187)\n")
        return 2
    mongo_uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
    db_name = os.environ.get("MONGODB_DB", "velto")
    s3_bucket = os.environ.get("S3_BUCKET_NAME", "lithrim")
    s3_endpoint = os.environ.get("S3_ENDPOINT_URL", "http://localhost:9000")
    aws_key = os.environ.get("AWS_ACCESS_KEY_ID", "minioadmin")
    aws_secret = os.environ.get("AWS_SECRET_ACCESS_KEY", "minioadmin")
    aws_region = os.environ.get("AWS_REGION", "us-east-1")
    created_by = os.environ.get("LITHRIM_CREATED_BY", "paper-1-copilot")

    if not SPEC_PATH.exists():
        sys.stderr.write(f"ERROR: spec not found at {SPEC_PATH}\n")
        return 2
    if not PICKLIST_PATH.exists():
        sys.stderr.write(f"ERROR: picklist not found at {PICKLIST_PATH}\n")
        return 2

    spec_bytes = SPEC_PATH.read_bytes()
    spec = json.loads(spec_bytes)
    spec_hash = hashlib.sha256(spec_bytes).hexdigest()
    bench_sha = _git_rev_parse()
    picklist = json.loads(PICKLIST_PATH.read_text())
    pick_by_label = {p["pick_label"]: p for p in picklist}

    case_ids = {c["case_id"] for c in spec["cases"]}
    fixtures = resolve_case_fixtures(case_ids)
    missing = case_ids - fixtures.keys()
    if missing:
        sys.stderr.write(
            f"ERROR: {len(missing)} cases unresolved from bench fixtures: {sorted(missing)}\n"
        )
        return 2

    client = MongoClient(mongo_uri)
    db = client[db_name]
    eval_pack_col = db["eval_pack"]
    eval_case_col = db["eval_case"]

    existing_pack = eval_pack_col.count_documents({"pack_id": PACK_ID})
    existing_cases = eval_case_col.count_documents({"pack_id": PACK_ID})
    if existing_pack > 0 or existing_cases > 0:
        sys.stderr.write(
            f"ERROR: pack '{PACK_ID}' already present in Mongo "
            f"(eval_pack={existing_pack}, eval_case={existing_cases}). "
            f"Refusing to overwrite paper-grade artifact. "
            f"Delete the existing docs manually and re-run if intentional.\n"
        )
        return 3

    s3 = boto3.client(
        "s3",
        endpoint_url=s3_endpoint,
        aws_access_key_id=aws_key,
        aws_secret_access_key=aws_secret,
        region_name=aws_region,
    )

    print(f"Authoring pack '{PACK_ID}' for organization_id={organization_id}")
    print(f"  bench commit: {bench_sha}")
    print(f"  spec sha256:  {spec_hash}")
    print(f"  cases:        {len(spec['cases'])}")
    print(f"  mongo:        {mongo_uri}/{db_name}")
    print(f"  s3 endpoint:  {s3_endpoint}  bucket={s3_bucket}")
    print()

    eval_case_ids: list[str] = []
    for case_spec in spec["cases"]:
        case_id = case_spec["case_id"]
        fixture = fixtures[case_id]
        picklist_row = pick_by_label.get(case_spec["paper_pick_label"], {})

        transcript = fixture.get("transcript") or picklist_row.get("transcript") or ""
        if not transcript:
            sys.stderr.write(
                f"ERROR: empty transcript for case {case_id}; bench fixture row "
                f"is missing the 'transcript' field. Halting.\n"
            )
            return 4

        artifacts = fixture.get("artifacts") or []
        if not artifacts:
            sys.stderr.write(
                f"ERROR: no artifacts on bench fixture for case {case_id}. Halting.\n"
            )
            return 4

        transcript_key = (
            f"organizations/{organization_id}/eval_cases/{PACK_ID}/{case_id}.txt"
        )
        artifacts_key = (
            f"organizations/{organization_id}/eval_cases/{PACK_ID}/{case_id}.artifacts.json"
        )
        s3.put_object(
            Bucket=s3_bucket,
            Key=transcript_key,
            Body=transcript.encode("utf-8"),
            ContentType="text/plain; charset=utf-8",
        )
        s3.put_object(
            Bucket=s3_bucket,
            Key=artifacts_key,
            Body=json.dumps(artifacts).encode("utf-8"),
            ContentType="application/json; charset=utf-8",
        )

        ec_doc = _build_eval_case_doc(
            organization_id=organization_id,
            pack_id=PACK_ID,
            case_spec=case_spec,
            fixture=fixture,
            transcript_s3_key=transcript_key,
            artifacts_s3_key=artifacts_key,
            bench_sha=bench_sha,
            created_by=created_by,
        )
        ec_doc["_id"] = ObjectId()
        eval_case_col.insert_one(ec_doc)
        ec_id = str(ec_doc["_id"])
        eval_case_ids.append(ec_id)
        print(
            f"  inserted eval_case {case_spec['paper_pick_label']:3s} "
            f"_id={ec_id}  case_id={case_id[-12:]:12s} "
            f"disposition={case_spec['promotion_disposition']}"
        )

    ep_doc = _build_eval_pack_doc(
        organization_id=organization_id,
        eval_case_ids=eval_case_ids,
        bench_sha=bench_sha,
        spec=spec,
        spec_hash=spec_hash,
    )
    ep_doc["_id"] = ObjectId()
    eval_pack_col.insert_one(ep_doc)
    ep_id = str(ep_doc["_id"])
    print()
    print(f"  inserted eval_pack  _id={ep_id}  pack_id={PACK_ID}  case_ids={len(eval_case_ids)}")
    print()
    print(
        f"inserted: 1 eval_pack + {len(eval_case_ids)} eval_case docs into "
        f"{db_name}.eval_pack / {db_name}.eval_case"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
