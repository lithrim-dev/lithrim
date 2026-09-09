"""FINETUNE-1: fine-tune tooling that can be tested without a job, and refuses to spend unasked."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "ragtruth_finetune", REPO / "examples/ragtruth/arms/finetune_azure.py"
)
ft = importlib.util.module_from_spec(_spec)
sys.modules["ragtruth_finetune"] = ft
_spec.loader.exec_module(ft)


def test_estimate_and_cost_from_a_chat_file(tmp_path):
    f = tmp_path / "train.jsonl"
    f.write_text(
        "\n".join(
            json.dumps(
                {
                    "messages": [
                        {"role": "user", "content": "x" * 400},
                        {"role": "assistant", "content": "y" * 40},
                    ]
                }
            )
            for _ in range(10)
        )
        + "\n"
    )
    est = ft.estimate_tokens(f)
    assert est == {"rows": 10, "chars": 4400, "tokens_estimate": 1100}
    cost = ft.cost_estimate(1_000_000, "gpt-4.1-mini-2025-04-14", 3)
    assert (
        cost["priced"]
        and cost["training_usd_list"] == 15.0
        and cost["training_tokens_total"] == 3_000_000
    )
    assert ft.cost_estimate(10, "mystery", 1) == {"base": "mystery", "priced": False}


def test_job_body_and_bind_bodies():
    body = ft.job_body("file-1", "gpt-4.1-mini-2025-04-14", 3, "lithrim", None)
    assert body == {
        "model": "gpt-4.1-mini-2025-04-14",
        "training_file": "file-1",
        "hyperparameters": {"n_epochs": 3},
        "suffix": "lithrim",
    }
    assert ft.job_body("file-1", "b", 1, "s", "file-2")["validation_file"] == "file-2"
    probe, pin, roster = ft.bind_bodies("ft-dep", "trained_grader")
    assert probe == {
        "plane": "grading",
        "provider": "azure",
        "role": "trained_grader",
        "model": "ft-dep",
    }
    assert pin["model"] == "ft-dep" and roster["roster"] == ["trained_grader"]


def test_submit_and_bind_refuse_without_confirm():
    out = subprocess.run(
        [
            sys.executable,
            str(REPO / "examples/ragtruth/arms/finetune_azure.py"),
            "submit",
            "--training-file-id",
            "file-x",
            "--training-tokens",
            "360000",
        ],
        capture_output=True,
        text=True,
        cwd=REPO,
        env={
            "PATH": "/usr/bin",
            "AZURE_OPENAI_ENDPOINT": "https://x.example",
            "AZURE_OPENAI_API_KEY": "k",
        },
    )
    assert (
        out.returncode != 0
        and "REFUSING to submit" in out.stderr
        and "training_usd_list" in out.stderr
    )
    out = subprocess.run(
        [sys.executable, str(REPO / "examples/ragtruth/arms/finetune_azure.py"), "bind", "--deployment", "d"],
        capture_output=True,
        text=True,
        cwd=REPO,
        env={"PATH": "/usr/bin"},
    )
    assert out.returncode != 0 and "REFUSING" in out.stderr


def test_estimate_is_the_only_networkless_paid_free_path(tmp_path):
    f = tmp_path / "t.jsonl"
    f.write_text(
        json.dumps(
            {
                "messages": [
                    {"role": "user", "content": "abcd" * 100},
                    {"role": "assistant", "content": "{}"},
                ]
            }
        )
        + "\n"
    )
    out = subprocess.run(
        [
            sys.executable,
            str(REPO / "examples/ragtruth/arms/finetune_azure.py"),
            "estimate",
            "--training",
            str(f),
        ],
        capture_output=True,
        text=True,
        cwd=REPO,
        env={"PATH": "/usr/bin"},
    )
    assert out.returncode == 0 and '"rows": 1' in out.stdout and '"priced": true' in out.stdout


def test_live_jobs_flags_a_same_suffix_job_that_is_not_terminal():
    listing = {
        "data": [
            {"id": "a", "suffix": "x", "status": "running"},
            {"id": "b", "suffix": "x", "status": "cancelled"},
            {"id": "c", "suffix": "y", "status": "pending"},
        ]
    }
    assert [j["id"] for j in ft.live_jobs(listing, "x")] == ["a"]
    assert ft.live_jobs({"data": []}, "x") == []
