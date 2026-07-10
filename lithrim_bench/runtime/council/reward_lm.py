"""RewardModelLM — a purpose-built eval reward model (Composo-shaped) as a judge provider.

F8-PROVIDER. The research's F8 finding: the strongest commodity judge tested is a reward model —
deterministic and graded — and the honest architecture keeps it IN the swappable judge slot with
the deterministic floor beneath it. This module is that slot's provider: ``provider: composo`` on
the per-role binding routes ``build_judge_lm`` here, and ``sampling.judge_call`` (the unfrozen
wiring layer) maps the returned score to a verdict deterministically — threshold at
:data:`DEFAULT_THRESHOLD` (0.5, the research's cut), RAW scores kept as the honest artifact.

NOT a text LM: the reward API answers ``(messages, criteria) -> score``, not a dspy signature
prompt, so this class deliberately does NOT subclass ``dspy.BaseLM`` — the ``is_reward_lm`` marker
makes ``judge_call`` branch before any ``dspy.Predict`` construction. Honesty invariants the
sampling layer enforces on top: findings stay EMPTY (a reward model types no defect codes),
confidence stays ``None`` (no logprobs), usage stays ``None`` (no token report), and a transport
failure DECLINES (``needs_review``) rather than guessing.

The criterion sent as ``evaluation_criteria`` is the reviewer's AUTHORED text: the explicit
``criterion`` param when set, else the composed role prompt ``judge_call`` passes in (which
carries the CRITERION-TEXT sentence). Secrets: the API key rides the per-role env binding
(``LITHRIM_LLM_API_KEY_<ROLE>``) / write-only ``.provider_env`` like every provider secret —
never a manifest, never a repr, never a response. ``transport`` is injectable so tests are
$0/offline; the default is a stdlib ``urllib`` POST (no new dependency).
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable
from typing import Any

COMPOSO_DEFAULT_API_BASE = "https://platform.composo.ai"
_REWARD_PATH = "/api/v1/evals/reward"
DEFAULT_THRESHOLD = 0.5
_TIMEOUT_S = 90.0

Transport = Callable[[str, dict[str, str], dict[str, Any]], dict[str, Any]]


def _http_transport(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        # the User-Agent is load-bearing: the platform's edge 403s urllib's default agent
        headers={
            **headers,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "lithrim-bench/0.1",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as r:  # noqa: S310 — https API base
        return json.load(r)


class RewardModelLM:
    """The reward-model judge provider (Composo wire shape).

    ``evaluate(user, assistant, criterion)`` POSTs the two-message conversation + the criterion
    and returns the raw ``{"score", "explanation"}`` — it RAISES on transport/shape failure so the
    caller (``judge_call``) can decline per-sample. Verdict mapping lives in the sampling layer,
    not here."""

    is_reward_lm = True
    supports_n = False  # one evaluation per call; k rides repeated calls in judge_call

    def __init__(
        self,
        *,
        api_key: str,
        api_base: str | None = None,
        model: str = "composo-reward",
        criterion: str = "",
        threshold: float = DEFAULT_THRESHOLD,
        task_instruction: str = "",
        transport: Transport | None = None,
    ) -> None:
        self._api_key = api_key
        self.api_base = (api_base or COMPOSO_DEFAULT_API_BASE).rstrip("/")
        self.model = model
        self.criterion = criterion
        self.threshold = float(threshold)
        # REWARD-SEMANTICS-1: the task line the user message is framed with (a reward model
        # scores "did the assistant serve the request" — the request must exist). Empty → the
        # sampling layer's generic default; SME-overridable so a domain pack/reviewer can name
        # the artifact kind its scribe was actually asked to produce.
        self.task_instruction = task_instruction
        self._transport = transport

    def __repr__(self) -> str:  # the key must never leak into a log/blob
        return f"RewardModelLM(model={self.model!r}, api_base={self.api_base!r}, threshold={self.threshold})"

    def evaluate(self, user: str, assistant: str, criterion: str) -> dict[str, Any]:
        payload = {
            "messages": [
                {"role": "user", "content": user},
                {"role": "assistant", "content": assistant},
            ],
            "evaluation_criteria": criterion,
        }
        transport = self._transport or _http_transport
        out = transport(f"{self.api_base}{_REWARD_PATH}", {"API-Key": self._api_key}, payload)
        score = out.get("score") if isinstance(out, dict) else None
        if not isinstance(score, (int, float)):
            raise ValueError(f"reward API returned no numeric score (keys: {sorted(out or {})})")
        return {"score": float(score), "explanation": str(out.get("explanation") or "")}


def build_composo_reward_lm(
    *,
    api_key: str,
    api_base: str | None = None,
    model: str | None = None,
    criterion: str = "",
    threshold: float = DEFAULT_THRESHOLD,
    task_instruction: str = "",
    transport: Transport | None = None,
) -> RewardModelLM:
    """The ``provider: composo`` construction point ``build_judge_lm`` dispatches to."""
    return RewardModelLM(
        api_key=api_key,
        api_base=api_base,
        model=model or "composo-reward",
        criterion=criterion,
        threshold=threshold,
        task_instruction=task_instruction,
        transport=transport,
    )
