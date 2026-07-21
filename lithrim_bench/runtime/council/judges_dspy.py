"""DSPy per-judge layer for the ported v2 council — the §6 hybrid.

WS-6c-DSPy (bench-salvage). Rebuilds the council's per-judge prompt-and-parse as
a DSPy module that emits the EXACT per-judge dict seam documented at
``runtime/council/__init__.py`` (``{model, decision, confidence, findings, errors}``)
and consumed by the ported ``ComplianceCouncil._apply_consensus``. DSPy lives
strictly ABOVE the seam; the consensus math (tier tables, owner-gating, PHI false
positive suppression, the v2 llama-veto, None-confidence tolerance) is the ported
IP, wrapped UNCHANGED below the seam. Optimizing a judge prompt can therefore
never weaken a Tier-1 never-event rule — the rule lives below this layer
(``RECOMPOSITION_PLAN_ws6.md`` §6 invariant).

Incremental (``RECOMPOSITION_PLAN_ws6.md`` §Ratification Q3): one judge is rebuilt
first — ``risk_judge``, which owns the Tier-1 ``WRONG_DOSAGE`` the by-construction
packs exercise most. The other roles stay pluggable behind the same signature,
ported-imperative (or fixtured) until rebuilt; the hybrid wraps DSPy and non-DSPy
judges identically, so a MIXED fan-out (some ``Judge`` modules, some pre-built
seam dicts) is valid and is what :func:`evaluate_dspy` accepts.

``dspy`` is imported lazily inside the builders (mirroring
``verification/jute_dspy.py``) so this module stays import-safe wherever the
``[council]`` extra is present but ``[verification]`` is not — the heavy import
only fires when a live ``Judge`` is built. The package ``__init__`` does not import
this module, so the default pydantic+pandas core never pulls ``dspy`` or the
judge layer.

Confidence is sourced from the response logprobs via the ported
``extract_verdict_confidence`` (the decision-token ``exp(logprob)``), NOT a model
self-report output field. A judge whose response carries no logprobs (Mistral, by
design) round-trips as ``None`` and is never coerced to a float. The S-BS-27
worktree prototype's ``confidence: float = dspy.OutputField(...)`` is exactly the
self-report anti-pattern this avoids.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from pydantic import BaseModel, Field

from .compliance_council import (
    KNOWN_TAXONOMY_CODES,
    TIER_1_NEVER_EVENTS,
    TIER_2_HIGH_RISK,
    TIER_3_MEDIUM,
    ComplianceCouncil,
    extract_verdict_confidence,
)
from .settings import settings

V2_ROLES = ("risk_judge", "policy_judge", "faithfulness_judge")
_DECISIONS = {"approve", "needs_review", "reject"}

# The prompt↔ontology bridge lives in the council-LIGHT ``judge_assignment`` module
# (no openai/dspy import) so the BFF can serve the $0 prompt preview without the
# [council] extra. Re-exported here so ``build_trio`` + ``judge_optimize`` + the
# tests keep one import surface.
from .judge_assignment import load_role_prompt, render_role_questions  # noqa: E402

# Role → the Azure deployment id, read from the salvaged ``settings`` (the same
# source ``llm_provider._resolve_model`` reads for purposes council/mistral_judge/
# meta_judge). DSPy binds its own litellm LM, so we reuse the CONFIG plane, not
# the openai client the factory returns.
_ROLE_DEPLOYMENT = {
    "risk_judge": "AZURE_OPENAI_DEPLOYMENT_COUNCIL",
    "policy_judge": "AZURE_OPENAI_DEPLOYMENT_MISTRAL_LARGE_3",
    "faithfulness_judge": "AZURE_OPENAI_DEPLOYMENT_LLAMA_4_MAVERICK",
}
# Per-reviewer default sampling count k (the axes are independent, not a voting council).
# Risk samples most (k=5 — the safety axis where instability must surface); Faithfulness k=3;
# Policy k=1 (deterministic compliance check). An authored ``JudgeConfig.k`` overrides; absent
# both, the global ``settings.COUNCIL_JUDGE_SAMPLES`` (default 1) applies. A module-level constant,
# OUTSIDE the frozen consensus-seam symbol set.
DEFAULT_JUDGE_SAMPLES = {
    "risk_judge": 5,
    "policy_judge": 1,
    "faithfulness_judge": 3,
}
# Role → the OpenAI-direct model setting key (BYOK single-provider, Cycle 1). When
# LITHRIM_LLM_PROVIDER=openai and OPENAI_API_KEY is set, ``build_judge_lm`` binds each role to
# ``settings.<this key>`` on the user's one key — preserving the multi-judge council + per-role
# model diversity, with logprobs ON so calibrated confidence survives. A module-level constant
# (not a top-level def/class), so it sits OUTSIDE the frozen consensus-seam symbol set.
_OPENAI_ROLE_MODEL = {
    "risk_judge": "OPENAI_MODEL_RISK",
    "policy_judge": "OPENAI_MODEL_POLICY",
    "faithfulness_judge": "OPENAI_MODEL_FAITHFULNESS",
}
# Role → the GENERIC per-role provider-override setting keys (PROVIDER-CENTER-A,
# S-BS-MR1a-CROSSPROVIDER). When ``settings.<provider key>`` is set, ``build_judge_lm`` LAYERS a
# per-role provider override ON TOP of the global path — so risk→OpenAI, policy→Gemini,
# faithfulness→Anthropic coexist (a TRUE cross-provider council). The registry bind writes these
# vars (LITHRIM_LLM_{PROVIDER,MODEL,API_KEY,API_BASE}_<ROLE>). A module-level constant (not a
# top-level def/class), so it sits OUTSIDE the frozen consensus-seam symbol set, like the maps above.
_ROLE_PROVIDER_KEYS = {
    "risk_judge": {
        "provider": "LITHRIM_LLM_PROVIDER_RISK", "model": "LITHRIM_LLM_MODEL_RISK",
        "api_key": "LITHRIM_LLM_API_KEY_RISK", "api_base": "LITHRIM_LLM_API_BASE_RISK",
        "api_version": "LITHRIM_LLM_API_VERSION_RISK",
    },
    "policy_judge": {
        "provider": "LITHRIM_LLM_PROVIDER_POLICY", "model": "LITHRIM_LLM_MODEL_POLICY",
        "api_key": "LITHRIM_LLM_API_KEY_POLICY", "api_base": "LITHRIM_LLM_API_BASE_POLICY",
        "api_version": "LITHRIM_LLM_API_VERSION_POLICY",
    },
    "faithfulness_judge": {
        "provider": "LITHRIM_LLM_PROVIDER_FAITHFULNESS", "model": "LITHRIM_LLM_MODEL_FAITHFULNESS",
        "api_key": "LITHRIM_LLM_API_KEY_FAITHFULNESS", "api_base": "LITHRIM_LLM_API_BASE_FAITHFULNESS",
        "api_version": "LITHRIM_LLM_API_VERSION_FAITHFULNESS",
    },
}
# REPRO-1 R2a: the per-role binding generalizes to ANY judge role (3→N — authored roles bind
# like pack roles). The v2 trio keeps its SHORT legacy suffixes via _ROLE_PROVIDER_KEYS above;
# any other role derives generic names from its sanitized uppercased id. Dynamic keys are NOT
# declared on the Settings model, so _role_setting falls back to os.environ — exactly where the
# BFF's bind/hydration writes them (and what a subprocess grade inherits).
def _role_provider_keys(role: str) -> dict[str, str]:
    keys = _ROLE_PROVIDER_KEYS.get(role)
    if keys is not None:
        return keys
    s = "".join(c if c.isalnum() else "_" for c in (role or "").upper())
    return {
        "provider": f"LITHRIM_LLM_PROVIDER_{s}", "model": f"LITHRIM_LLM_MODEL_{s}",
        "api_key": f"LITHRIM_LLM_API_KEY_{s}", "api_base": f"LITHRIM_LLM_API_BASE_{s}",
        "api_version": f"LITHRIM_LLM_API_VERSION_{s}",
    }


def _role_setting(key: str) -> str:
    """A per-role binding value: the settings holder first (the declared trio fields, refreshed
    in-place on bind), else os.environ (authored roles' dynamic keys)."""
    import os

    val = str(getattr(settings, key, "") or "")
    if not val:
        val = os.environ.get(key, "")
    return val.strip()


# The litellm provider/model PREFIX per provider id. ``openai_compatible`` rides the ``openai``
# prefix + a per-role ``api_base`` (vLLM / Together / a local OpenAI-shaped server). litellm routes
# ``openai/`` / ``azure/`` / ``anthropic/`` / ``gemini/`` / ``bedrock/`` natively.
_LITELLM_PREFIX = {
    "openai": "openai",
    "azure": "azure",
    "anthropic": "anthropic",
    "gemini": "gemini",
    "bedrock": "bedrock",
    "openai_compatible": "openai",
}
# Only openai + azure return token logprobs → the calibrated-confidence read. The rest are honest
# confidence-dark (logprobs OFF in the LM kwargs), exactly like the BYO-Claude path.
_LOGPROBS_PROVIDERS = frozenset({"openai", "azure"})


def _litellm_prefix(provider: str) -> str:
    """The litellm provider/model prefix for ``provider`` (``openai_compatible`` → ``openai``).
    An unknown provider falls back to its own lower-cased id (litellm decides)."""
    p = (provider or "").strip().lower()
    return _LITELLM_PREFIX.get(p, p)


def _provider_supports_logprobs(provider: str) -> bool:
    """True iff ``provider`` exposes token logprobs (openai/azure → calibrated confidence). Every
    other provider (anthropic/gemini/bedrock/openai_compatible/unknown) → False (confidence dark)."""
    return (provider or "").strip().lower() in _LOGPROBS_PROVIDERS


# DRYRUN-2026-07-03 (stranger journey, live-caught): logprobs support is MODEL-granular now —
# the reasoning families on an otherwise-logprobs provider REJECT the param outright
# ("'logprobs' is not supported with this model"), which errored the judge into a silent
# needs_review. Confidence-dark is the safe direction (we lose a number, never a verdict).
# LOGPROBS-MODEL-GRANULAR-1 (2026-07-19, live-proven on Azure AI Foundry): "gpt-5" was too broad —
# gpt-5.x CHAT models DO return logprobs (azure/gpt-5.4 verified; the model registry catalog already
# marks gpt-5-x logprobs=True), so excluding them cost gpt-5.4 its calibrated confidence
# (faithfulness_judge ran confidence-dark). The genuine rejecters are the o-series reasoning models
# AND the non-OpenAI Azure-MaaS families (Mistral/Llama), which 400 "Logprobs are not enabled for
# this model" on EVERY route. A specific gpt-5 reasoning id that rejects the param should be added
# by its exact id, never the whole family.
_NO_LOGPROBS_MODEL_PREFIXES = ("o1", "o3", "o4", "mistral", "llama", "mixtral")


def _model_supports_logprobs(provider: str, model: str) -> bool:
    if not _provider_supports_logprobs(provider):
        return False
    m = (model or "").strip().lower()
    return not any(m.startswith(p) for p in _NO_LOGPROBS_MODEL_PREFIXES)


# --------------------------------------------------------------------------- #
# structured findings (pydantic core dep — no dspy needed to define these)
# --------------------------------------------------------------------------- #
class EvidenceSpan(BaseModel):
    """One grounding span for a finding. ``quote`` is the verbatim text the
    judge anchors the violation in; a finding with no span is dropped (the
    ``_normalize_result`` discipline — evidence-less findings never enter
    consensus)."""

    quote: str = Field(default="", description="verbatim span grounding the finding")
    turn_ids: list[int] = Field(default_factory=list, description="source turn ids, if any")


class Finding(BaseModel):
    """One taxonomy finding with its evidence. ``taxonomy_code`` must be a known
    code; ``evidence_spans`` must be non-empty for the finding to count."""

    taxonomy_code: str = Field(description="an UPPER_SNAKE_CASE code from the valid taxonomy")
    evidence_spans: list[EvidenceSpan] = Field(
        default_factory=list, description=">=1 span grounding this finding"
    )


def default_taxonomy_context() -> str:
    """A compact, tier-labelled listing of the valid codes for the signature's
    ``taxonomy_context`` input, so the judge emits only in-taxonomy codes. The
    tier semantics mirror the consensus rules the seam feeds."""
    return (
        "VALID TAXONOMY CODES — emit ONLY these, one finding per code, each grounded "
        "in at least one evidence span:\n"
        f"  Tier-1 never-events (a single owning judge with evidence rejects): "
        f"{sorted(TIER_1_NEVER_EVENTS)}\n"
        f"  Tier-2 high-risk (2+ judges reject; 1 judge = needs_review): "
        f"{sorted(TIER_2_HIGH_RISK)}\n"
        f"  Tier-3 medium (flagged for awareness): {sorted(TIER_3_MEDIUM)}"
    )


# --------------------------------------------------------------------------- #
# small accessors (work over pydantic models, dicts, or plain namespaces — the
# injected offline predictor returns dicts; the live dspy.Predict returns models)
# --------------------------------------------------------------------------- #
def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _norm_decision(value: Any) -> str:
    d = str(value).strip().lower()
    return d if d in _DECISIONS else "needs_review"


def _span_to_dict(span: Any) -> dict[str, Any]:
    quote = _get(span, "quote", "") or ""
    turn_ids = _get(span, "turn_ids", []) or []
    return {"quote": str(quote), "turn_ids": list(turn_ids) if isinstance(turn_ids, list) else []}


def _validate_findings(raw_findings: Any) -> list[dict[str, Any]]:
    """Project judge-emitted findings onto the seam's ``findings`` shape.

    Mirrors ``compliance_council._normalize_result`` (:1505-1527): discard a
    finding whose ``taxonomy_code`` is unknown or whose evidence is empty, so a
    judge can never inject an ungrounded or off-taxonomy finding into consensus.
    A span counts only if it carries a non-empty quote or at least one turn id.
    """
    out: list[dict[str, Any]] = []
    for f in raw_findings or []:
        code = (_get(f, "taxonomy_code", "") or "").strip()
        if not code or code not in KNOWN_TAXONOMY_CODES:
            continue
        spans = [_span_to_dict(s) for s in (_get(f, "evidence_spans", []) or [])]
        spans = [s for s in spans if s["quote"].strip() or s["turn_ids"]]
        if not spans:
            continue
        out.append({"taxonomy_code": code, "evidence_spans": spans})
    return out


def _raw_response_for(pred: Any, predictor: Any) -> Any:
    """The raw chat-completion behind a prediction, for logprob extraction.

    Offline tests attach a synthesized response at ``pred._raw_response`` (the
    shape ``extract_verdict_confidence`` accepts as a dict); the live path reads
    the bound LM's last history entry. Either way the confidence comes from the
    response logprobs, never a model output field.
    """
    explicit = _get(pred, "_raw_response", None)
    if explicit is not None:
        return explicit
    lm = getattr(predictor, "lm", None)
    history = getattr(lm, "history", None) if lm is not None else None
    if history:
        last = history[-1]
        return last.get("response") if isinstance(last, dict) else getattr(last, "response", None)
    return None


def _build_signature():
    """The findings-first judge signature (built lazily — needs ``dspy``)."""
    import dspy

    class JudgeSignature(dspy.Signature):
        """Audit one produced artifact against its source conversation.

        You are one judge on an audit council. Apply
        the role guidance in ``role_key_questions`` to the transcript and artifact
        and raise ONLY violations you can ground in a specific span. Emit each
        violation as a finding {taxonomy_code, evidence_spans} using ONLY a code
        from ``taxonomy_context``; never raise a code outside your role's scope.
        Decisions: approve (no grounded violation), needs_review (ambiguous /
        borderline), reject (a clear grounded violation). findings is empty when
        you approve. Do NOT report a self-rated confidence — calibration is read
        from the model's logprobs, not your assertion.
        """

        transcript: str = dspy.InputField(desc="the source conversation (ground truth)")
        artifact: str = dspy.InputField(
            desc="the produced artifact under audit"
        )
        role_key_questions: str = dspy.InputField(desc="this judge's role prompt and key questions")
        taxonomy_context: str = dspy.InputField(desc="the valid taxonomy codes + tiers")

        decision: str = dspy.OutputField(desc="approve | needs_review | reject")
        findings: list[Finding] = dspy.OutputField(
            desc="grounded violations as {taxonomy_code, evidence_spans}; empty list when approving"
        )
        reason: str = dspy.OutputField(desc="one or two sentences justifying the decision")

    return JudgeSignature


def build_judge_lm(role: str, **overrides: Any):
    """Construct the per-``role`` judge LM — provider-aware (BYOC-1).

    Default: a deterministic Azure ``dspy.LM`` bound to ``role``'s deployment (the v2
    deployment-id-substitution route; temperature=0 + logprobs on for the calibrated-
    confidence path; the caller may override any litellm kwarg). BYOC-1: when the
    per-judge ``model``/``provider`` override names BYO-Claude
    (``byo-claude``/``claude-cli``/``claude``) OR the global
    ``settings.LITHRIM_LLM_PROVIDER`` selects ``claude-cli``, return the tool-less
    :class:`ClaudeCliLM` instead (the customer's own ``claude -p`` — no API key, no
    logprobs → confidence ``None``). ``model``/``provider`` are BYOC-1 selectors, not
    litellm kwargs, so they never reach the byte-unchanged Azure construction below.
    ``dspy`` imported lazily.
    """
    from lithrim_bench.harness.plugins import resolve_provider_id

    from .byo_claude_lm import BYO_CLAUDE_MODEL_VALUES

    selector = str(overrides.get("model") or overrides.get("provider") or "").strip().lower()
    global_provider = str(getattr(settings, "LITHRIM_LLM_PROVIDER", "") or "").strip().lower()
    # Plugin Phase-1 (D4): the BYOC-1 provider selection now routes through the unified plugin
    # registry. ``resolve_provider_id`` is byte-identical to the prior inline set-membership
    # (``selector in BYO_CLAUDE_MODEL_VALUES or global_provider in …``) — ``byo_values`` is
    # threaded in so ``plugins`` stays dspy-free. The per-role DEPLOYMENT binding below stays
    # CORE (``_ROLE_DEPLOYMENT`` — PACK-2c, infra ∉ a domain pack); only the SELECTION is folded.
    if resolve_provider_id(selector, global_provider, byo_values=BYO_CLAUDE_MODEL_VALUES) == "byo_claude":
        from .byo_claude_lm import build_claude_cli_lm

        for _selector_key in ("model", "provider", "logprobs"):
            overrides.pop(_selector_key, None)  # selectors / no-Anthropic-logprobs, not LM kwargs
        return build_claude_cli_lm(**overrides)
    # An Azure build carries no BYOC-1 selector kwarg; drop them so the frozen path below
    # is byte-identical for every existing caller (a no-op when none was passed).
    overrides.pop("model", None)
    overrides.pop("provider", None)

    # CACHE-TRAP-1 (2026-07-19, live-caught): a "Run live" re-grade replayed the DSPy LM disk
    # cache byte-for-byte (same model/prompt/seed/temp → same key; tokens=0), so re-running a
    # case never actually re-sampled. The BFF grade paths set LITHRIM_JUDGE_CACHE=0 for LIVE
    # grades; unset/default stays cache-on (offline tests + every non-live path byte-identical).
    import os

    lm_cache = os.environ.get("LITHRIM_JUDGE_CACHE", "1") != "0"

    import dspy

    # CACHE-TRAP-2 (2026-07-21, live-caught): the per-LM flag above is NOT sufficient. dspy keeps
    # its own PROCESS-GLOBAL disk + memory caches which serve hits whatever the LM says, so a
    # full 14-case live arm came back in ~2s per case at tokens=0 and only a container restart
    # cleared it. Disable every layer when the gate is off. Only when OFF: the default path must
    # never touch the global config, so $0/replay/offline stay byte-identical. The lever lives in
    # harness/judge_cache.py because this module is frozen at its top-level symbol set.
    if not lm_cache:
        from lithrim_bench.harness.judge_cache import set_global_judge_cache

        set_global_judge_cache(False)

    # PROVIDER-CENTER-A (S-BS-MR1a-CROSSPROVIDER): a PER-ROLE provider override LAYERED ON TOP of the
    # global path. When ``settings.LITHRIM_LLM_PROVIDER_<ROLE>`` is set, THIS role runs on its own
    # provider (risk→OpenAI, policy→Gemini, faithfulness→Anthropic — a true cross-provider council),
    # routed via litellm's provider/model string. When UNSET → fall through to the byte-identical
    # global branches below (the regression guard, tests/test_provider_center_crossprovider.py::
    # test_no_per_role_* + the byte-frozen byo-claude routing above). logprobs ride
    # ``_provider_supports_logprobs`` (openai/azure True, else off — honest confidence-dark).
    # R2a: resolves for ANY role (authored roles ride os.environ via _role_setting; the trio
    # reads the declared settings fields exactly as before).
    role_keys = _role_provider_keys(role)
    role_provider = _role_setting(role_keys["provider"]).lower()
    if role_provider:
        role_model = _role_setting(role_keys["model"])
        role_api_key = _role_setting(role_keys["api_key"])
        role_api_base = _role_setting(role_keys["api_base"])
        # F8-PROVIDER: ``provider: composo`` binds a reward-model judge — NOT a chat LM, so it
        # never reaches the dspy.LM construction below. ``judge_call`` branches on the returned
        # ``is_reward_lm`` marker (score→verdict lives in the unfrozen sampling layer).
        if role_provider == "composo":
            from .reward_lm import build_composo_reward_lm

            return build_composo_reward_lm(
                api_key=role_api_key,
                api_base=role_api_base or None,
                model=role_model or None,
            )
        per_role_kwargs: dict[str, Any] = {
            "temperature": 0,
            "max_tokens": 4096,
            "cache": lm_cache,
            # DRYRUN-2026-07-03 (stranger journey, live-caught): modern models REJECT params
            # they don't support — gpt-5.5 refuses any non-default temperature; anthropic
            # refuses the logprobs PARAM even as False — which errored the judge into a
            # silent needs_review. drop_params lets litellm drop the per-model-unsupported
            # ones instead; logprobs is sent ONLY where it is real (openai/azure), so the
            # confidence-dark providers stay honestly confidence-dark.
            "drop_params": True,
        }
        if _model_supports_logprobs(role_provider, role_model):
            per_role_kwargs["logprobs"] = True
        if role_api_key:
            per_role_kwargs["api_key"] = role_api_key
        if role_api_base:  # azure / openai_compatible (vLLM, Together, a local server)
            per_role_kwargs["api_base"] = role_api_base
        if role_provider == "azure":
            # CONNECT-AI-AZURE-1: a per-role azure judge needs an api_version (the GLOBAL azure
            # branch threads it; without it litellm hits the api-version / DeploymentNotFound wall).
            # Read the per-role LITHRIM_LLM_API_VERSION_<ROLE>; default to the council default.
            per_role_kwargs["api_version"] = (
                _role_setting(role_keys["api_version"]) or settings.AZURE_OPENAI_API_VERSION
            )
        per_role_kwargs.update(overrides)
        return dspy.LM(f"{_litellm_prefix(role_provider)}/{role_model}", **per_role_kwargs)

    # BYOK single-provider (Cycle 1): OpenAI-direct is the DEFAULT provider (LITHRIM_LLM_PROVIDER=
    # openai). Bind each role to its model on the user's ONE OPENAI_API_KEY (no Azure trio). The
    # 3-judge council is preserved and each role keeps its OWN configurable model (OPENAI_MODEL_
    # {RISK,POLICY,FAITHFULNESS}) — model diversity on a single provider — with logprobs ON so the
    # calibrated-confidence read survives (the axis BYO-Claude loses). The Azure trio is opt-in via
    # LITHRIM_LLM_PROVIDER=azure (the branch below); any non-openai/non-byo selector falls there too.
    if global_provider == "openai":
        if not settings.OPENAI_API_KEY:
            raise ValueError(
                f"OPENAI_API_KEY is unset; required to bind role={role!r} on the single-provider "
                f"OpenAI council (LITHRIM_LLM_PROVIDER=openai). Set OPENAI_API_KEY, or select the "
                f"Azure trio with LITHRIM_LLM_PROVIDER=azure."
            )
        model_attr = _OPENAI_ROLE_MODEL.get(role, "OPENAI_MODEL_RISK")
        model = getattr(settings, model_attr, "") or "gpt-4o"
        openai_kwargs: dict[str, Any] = {
            "api_key": settings.OPENAI_API_KEY,
            "temperature": 0,
            "max_tokens": 4096,
            "cache": lm_cache,
            # DRYRUN-2026-07-03: same model-granular guards as the per-role branch — the
            # reasoning families reject logprobs (and a forced temperature); drop_params keeps
            # a param mismatch from erroring the judge into a silent needs_review.
            "drop_params": True,
        }
        if _model_supports_logprobs("openai", model):
            openai_kwargs["logprobs"] = True
        openai_kwargs.update(overrides)
        return dspy.LM(f"openai/{model}", **openai_kwargs)

    dep_attr = _ROLE_DEPLOYMENT.get(role, "AZURE_OPENAI_DEPLOYMENT_COUNCIL")
    deployment = getattr(settings, dep_attr, None)
    if not deployment:
        raise ValueError(
            f"{dep_attr} is unset; required to bind a live LM for role={role!r} "
            f"(COMPLIANCE_COUNCIL_VERSION=v2). For the single-provider OpenAI council set "
            f"LITHRIM_LLM_PROVIDER=openai + OPENAI_API_KEY instead."
        )
    kwargs: dict[str, Any] = {
        "api_key": settings.AZURE_OPENAI_API_KEY,
        "api_base": settings.AZURE_OPENAI_ENDPOINT,
        "api_version": settings.AZURE_OPENAI_API_VERSION,
        "temperature": 0,
        # 1024 truncated the structured verdict (evidence_consensus_pillar_verdicts) on
        # evidence-heavy cases — the judge quotes clinical spans (e.g. a 20-item PMH), so
        # it needs headroom. Caps, never forces, so cost only rises on genuinely long output (S-BS-111).
        "max_tokens": 4096,
        "logprobs": True,
        "cache": lm_cache,
    }
    kwargs.update(overrides)
    return dspy.LM(f"azure/{deployment}", **kwargs)


class Judge:
    """A single DSPy-rebuilt judge that emits the §6 per-judge dict seam.

    ``forward`` returns ``{model, decision, confidence, findings, errors}`` — the
    EXACT shape ``_apply_consensus`` consumes. The whole judge call is wrapped so
    a model/parse/transport failure becomes a non-empty ``errors`` list (the judge
    is excluded from consensus) rather than aborting the fan-out.

    Construction is dependency-light: pass ``predictor`` (any callable returning
    an object/dict with ``decision``/``findings``) for offline tests, or pass
    ``lm`` (a ``dspy.LM``) to bind a live ``dspy.Predict``.
    """

    def __init__(
        self,
        role: str,
        *,
        predictor: Callable[..., Any] | None = None,
        lm: Any = None,
        role_prompt: str = "",
        taxonomy_context: str | None = None,
    ) -> None:
        self.role = role
        self.role_prompt = role_prompt
        self.taxonomy_context = taxonomy_context or default_taxonomy_context()
        if predictor is not None:
            self.predict = predictor
        else:
            import dspy

            self.predict = dspy.Predict(_build_signature())
            if lm is not None:
                self.predict.set_lm(lm)

    def forward(self, *, transcript: str, artifact: str) -> dict[str, Any]:
        errors: list[str] = []
        decision = "needs_review"
        findings: list[dict[str, Any]] = []
        confidence: float | None = None
        try:
            pred = self.predict(
                transcript=transcript,
                artifact=artifact,
                role_key_questions=self.role_prompt,
                taxonomy_context=self.taxonomy_context,
            )
            decision = _norm_decision(_get(pred, "decision"))
            findings = _validate_findings(_get(pred, "findings", []))
            confidence = extract_verdict_confidence(_raw_response_for(pred, self.predict))
        except Exception as exc:  # noqa: BLE001 — capture per-judge, never abort the fan-out
            errors.append(f"{type(exc).__name__}: {str(exc)[:300]}")
        return {
            "model": self.role,
            "decision": decision,
            "confidence": confidence,
            "findings": findings,
            "errors": errors,
        }

    # convenience: a Judge is callable like a dspy.Module
    __call__ = forward


def build_trio(
    *,
    predictors: dict[str, Callable[..., Any]] | None = None,
    taxonomy_context: str | None = None,
    ontology: Any = None,
    assignments: dict[str, Sequence[str]] | None = None,
    models: dict[str, str] | None = None,
    roles: Sequence[str] | None = None,
    judge_samples: int | None = None,
    samples: dict[str, int] | None = None,
    temperatures: dict[str, float] | None = None,
    criteria: dict[str, str] | None = None,
    demos: dict[str, Sequence[Any]] | None = None,
) -> list[Judge]:
    """Assemble the V2 trio (:data:`V2_ROLES`) as role-prompt-bound ``Judge``s.

    Each judge is the SAME generic ``Judge`` module bound to its role prompt via
    ``role_prompt=`` — role specialization rides the prompt, not a per-role
    signature (the module is already generic; this is a convenience, not a seam
    change).

    Prompt source (UAP-2 bridge): when ``ontology`` is passed, each judge's
    ``role_prompt`` is rendered from the ontology assignment via
    :func:`render_role_questions` (the seed ``.txt`` base + any authored refinement
    from ``assignments[role]``, a list of assigned flag codes). When ``ontology`` is
    omitted (the default / back-compat path) each judge binds its
    ``council_roles/<role>.txt`` text verbatim via :func:`load_role_prompt` — so
    ``build_trio()`` with no args is byte-identical to before (A5; the A4 parity
    guard proves the rendered default equals the ``.txt``).

    Offline/tests: pass ``predictors={role: callable}`` to inject a per-role
    predictor (no ``dspy``/network). Live: omit ``predictors`` and each judge
    binds its own deterministic ``dspy.LM`` via :func:`build_judge_lm` (the role's
    Azure deployment, temperature=0, logprobs on). The returned list feeds
    :func:`evaluate_dspy` directly.

    ``models`` (BYOC-1): an optional per-role provider selector (role → model string,
    e.g. ``{"risk_judge": "byo-claude"}``) threaded into :func:`build_judge_lm` so a
    MIXED-provider council (one role on the tool-less BYO-Claude LM, the rest on Azure)
    is assemblable. ``None``/empty (the default) is byte-identical to before — each
    judge binds ``build_judge_lm(role)`` with no override (A5 back-compat).

    ``judge_samples`` (sampling layer): k, the number of completions each LIVE judge
    requests per grade through the single :func:`sampling.judge_call` primitive (native
    ``n``). ``None`` (the default) reads ``settings.COUNCIL_JUDGE_SAMPLES`` (default 1 →
    one completion, byte-equivalent to the pre-sampling path). This is a sampling-layer
    knob, NOT reviewer config — it never touches the per-role bindings/ontology/prompts.
    The ``predictors=`` offline path ignores it (fakes bypass ``judge_call`` entirely).

    ``samples`` / ``temperatures`` / ``criteria`` (PER-REVIEWER config, the independent-axes
    model): role → k / temperature / one-sentence criterion. Each is resolved per role:
    k = ``samples[role]`` → :data:`DEFAULT_JUDGE_SAMPLES` (5/1/3) → ``judge_samples`` → settings;
    temperature flows into :func:`build_judge_lm` (note DSPy forces 0.7 when k>1, so per-role
    temperature mainly affects k=1 reviewers); the criterion is appended to the role prompt.
    All ``None``/empty (the default) is byte-identical to before. Parallel to ``models`` /
    ``assignments`` (the existing per-role dicts).

    ``roles`` (DOGFOOD-1 D2b / PHASE2-B): an optional ordered roster — a SMALLER subset (the
    judge-set-ladder rungs) OR a LARGER roster carrying an AUTHORED judge (PHASE2-B). ``None``
    (the default) builds the active pack's full ``production_judges`` roster, byte-identical to
    before when ``production_judges == V2_ROLES`` (the ``_core``/support default). NOTE: the
    frozen ``_apply_consensus`` requires ``len(valid) >= 2`` in full-council mode, so a 2- or
    3-role roster grades normally but a SINGLE-role roster returns ``insufficient_valid_models``
    (a degenerate ``needs_review``) — single-judge support is a consensus-policy decision, not a
    ``build_trio`` change.

    PHASE2-B relaxed the allowlist from the fixed :data:`V2_ROLES` to the active pack's
    ``pack_production_judges()`` UNION any explicitly-authored role (a key in ``assignments`` /
    ``models``) — so an authored judge spliced into the pack snapshot joins the trio→N-tet. A
    role that is NEITHER a production judge NOR an authored key is a truly-unknown identity and
    raises (the caller derives ``roles`` via :func:`harness.judges.derive_roster_order`).
    ``build_judge_lm`` already binds any role via ``.get(role, default)`` (PROBE Q5), so no
    deployment-map edit is needed. :data:`V2_ROLES` is kept as the back-compat constant.
    """
    from lithrim_bench.harness.pack import pack_production_judges  # lazy: keep import acyclic

    production = tuple(pack_production_judges())
    selected = tuple(roles) if roles else production
    # admissible = the active roster ∪ the explicitly-authored extras (assignments/models keys).
    admissible = set(production) | set(assignments or {}) | set(models or {})
    unknown = [r for r in selected if r not in admissible]
    if unknown:
        raise ValueError(
            f"roles {unknown!r} are neither production judges {production!r} nor "
            "authored (assignments/models keys)"
        )
    # SAMPLING LAYER (judge_call): the LIVE model call routes through the single
    # ``judge_call`` primitive (native ``n`` for k completions) instead of a raw
    # ``dspy.Predict``. k comes from the sampling-layer knob (the explicit
    # ``judge_samples`` arg, else ``settings.COUNCIL_JUDGE_SAMPLES``), NEVER the per-role
    # judge config — so reviewer configuration is untouched. ``Judge.forward`` is
    # byte-frozen; we wire the primitive in here (an authorized symbol) by injecting a
    # ``judge_call``-backed predictor whose returned ``JudgeResult`` duck-types the
    # ``{decision, findings, _raw_response}`` shape ``Judge.forward`` already consumes.
    from .sampling import JudgeResult, judge_call  # lazy: keep import acyclic (sampling↔dspy)

    # Global fallback k (back-compat); per-role k is resolved per judge below.
    global_k = judge_samples if judge_samples is not None else settings.COUNCIL_JUDGE_SAMPLES

    def _resolve_k(role: str) -> int:
        # per-role authored (samples[role]) → per-role default (3/1/5) → global → 1.
        if samples and samples.get(role) is not None:
            return int(samples[role])
        if role in DEFAULT_JUDGE_SAMPLES:
            return int(DEFAULT_JUDGE_SAMPLES[role])
        return int(global_k)

    def _capturing(inner, holder):
        """Wrap a predictor so a returned ``JudgeResult`` is stashed for telemetry.
        Transparent: a non-JudgeResult return (the offline fakes) passes through
        unchanged, so the existing ``predictors=`` behaviour is byte-equivalent."""

        def _wrapped(**kw):
            result = inner(**kw)
            if isinstance(result, JudgeResult):
                holder["last"] = result
            return result

        return _wrapped

    judges: list[Judge] = []
    for role in selected:
        if ontology is not None:
            assigned = assignments.get(role) if assignments else None
            role_prompt = render_role_questions(ontology, role, assigned_flags=assigned)
        else:
            role_prompt = load_role_prompt(role)
        # Per-reviewer criterion: the ONE injected criterion sentence, appended to the role
        # prompt. ``criteria`` is empty/None by default (byte-identical). policy_judge's
        # case-level criterion is layered ON TOP per-grade in authored_stage (a runtime
        # role_prompt override), so this global criterion is its fallback.
        role_criterion = (criteria or {}).get(role) or ""
        if role_criterion.strip():
            role_prompt = f"{role_prompt}\n\nEvaluation criterion: {role_criterion.strip()}"
        holder: dict[str, Any] = {}
        if predictors is not None:
            judge = Judge(
                role,
                predictor=_capturing(predictors[role], holder),
                role_prompt=role_prompt,
                taxonomy_context=taxonomy_context,
            )
            judge.llm_model = None  # VOTE-MODEL-1: offline predictor path binds no LM
        else:
            role_k = _resolve_k(role)
            lm_overrides: dict[str, Any] = {}
            role_model = (models or {}).get(role) or ""
            if role_model:
                lm_overrides["model"] = role_model
            role_temp = (temperatures or {}).get(role)
            if role_temp is not None:
                lm_overrides["temperature"] = float(role_temp)
            lm = build_judge_lm(role, **lm_overrides)
            # REWARD-SEMANTICS-1 (measured — the case09 six-call table): a reward LM's
            # evaluation_criteria must be SME TEXT, never the rendered lens/refinement machinery
            # (which dragged the score ~+0.2). Hand it the reviewer's one-sentence criterion when
            # authored, else the BASE role prompt (A4 parity: refinement-free). Chat-LM judges are
            # untouched — their role_prompt keeps carrying the full rendered lens as before.
            if getattr(lm, "is_reward_lm", False) and not getattr(lm, "criterion", ""):
                lm.criterion = (role_criterion or "").strip() or (
                    render_role_questions(ontology, role)
                    if ontology is not None
                    else load_role_prompt(role)
                )

            # The judge_call-backed predictor. ``dspy.Predict`` is built lazily INSIDE
            # ``judge_call`` (on first forward), never at build_trio time, so a
            # monkeypatched non-dspy fake LM (the vote-model attribution test) does not
            # trip Predict construction here. ``_k`` is the per-role sampling count.
            # DEMO-PIN-1: the role's compiled demos (from an optimize run) ride into judge_call so
            # the lazily-built dspy.Predict grades few-shot. None (default) → demo-less, byte-identical.
            role_demos = (demos or {}).get(role)

            def _sampling_predictor(
                _lm=lm, _tax=taxonomy_context, _k=role_k, _temp=role_temp, _demos=role_demos, **kw
            ):
                return judge_call(
                    kw.get("transcript", ""),
                    model=_lm,
                    k=_k,
                    temperature=_temp,  # None → judge_call uses DEFAULT_SAMPLE_TEMPERATURE for k>1
                    artifact=kw.get("artifact", ""),
                    role_key_questions=kw.get("role_key_questions", ""),
                    taxonomy_context=kw.get("taxonomy_context") or _tax,
                    demos=_demos,
                )

            live_predictor = _capturing(_sampling_predictor, holder)
            # Expose the bound LM on the predictor so it quacks like the ``dspy.Predict``
            # it replaced (``predictor.lm``): keeps ``_raw_response_for``'s fallback and
            # the per-role provider introspection (``judge.predict.lm``) working through
            # the closure, so no caller that reached the old ``Judge(lm=)`` binding breaks.
            live_predictor.lm = lm
            judge = Judge(
                role,
                predictor=live_predictor,
                role_prompt=role_prompt,
                taxonomy_context=taxonomy_context,
            )
            # VOTE-MODEL-1: stamp the resolved deployment (``dspy.LM`` / ``ClaudeCliLM`` both
            # expose ``.model``) onto the judge so the authored stage can attribute each vote to
            # the REAL model it graded on, not the role name. Set here (the carve-out provider
            # binder), never on the frozen ``Judge`` symbol.
            judge.llm_model = getattr(lm, "model", None)
        judge._sampling_holder = holder  # read by authored_stage for distribution telemetry
        judges.append(judge)
    return judges


# A fan-out element is either a live Judge (run now) or a pre-built seam dict
# (a ported-imperative / fixtured judge not yet rebuilt — the Q3 mixed fan-out).
JudgeOrSeam = Judge | dict[str, Any]


def evaluate_dspy(
    judges: list[JudgeOrSeam],
    *,
    transcript: str,
    artifact: str,
    council: ComplianceCouncil | None = None,
    gate_mode: bool = False,
) -> dict[str, Any]:
    """The §6 hybrid: fan out the judges, collect the per-judge seam dicts, and
    call the ported ``_apply_consensus`` UNCHANGED.

    ``judges`` is a mixed list: ``Judge`` modules are run now; plain dicts are
    taken as already-built seam dicts (the not-yet-rebuilt roles). The returned
    verdict dict carries zero LLM/Mongo dependency below the seam — the consensus
    math is the ported IP. This function adds NOTHING to that math; it only
    marshals the per-judge list into the existing consumer.
    """
    council = council or ComplianceCouncil()
    results: list[dict[str, Any]] = []
    for j in judges:
        results.append(
            j if isinstance(j, dict) else j.forward(transcript=transcript, artifact=artifact)
        )
    return council._apply_consensus(results, gate_mode=gate_mode)
