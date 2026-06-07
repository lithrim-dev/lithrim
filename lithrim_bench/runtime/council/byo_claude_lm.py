"""ClaudeCliLM — BYO-Claude (the local ``claude`` CLI) as a tool-less ``dspy.BaseLM``.

BYOC-1 (bench-salvage). Makes the customer's own Claude (subscription / desktop auth,
**no API key**) a first-class judge / generation LM for the DSPy council — the
provider-composition lab's third provider alongside the Azure GPT / Mistral / Llama
trio (``judges_dspy._ROLE_DEPLOYMENT``). Completes the airgapped/BYO trust thesis: today
the conversational shell runs BYO-Claude but the judges are Azure-locked; this closes it.

TOOL-LESS BY CONSTRUCTION — the A-SAFE floor (builds directly on the ASAFE-1 / S-BS-90
finding). ``claude -p`` is Claude *Code*: Bash/Read/Write are enabled by default and an
agent under ``bypassPermissions`` WILL run them (the S-BS-90 host-leak). A judge LM is a
**completion, not an agent**, so every invocation is built (:func:`build_toolless_argv`)
with the three-layer bound, each verified live 2026-06-07:

  * ``--tools ""``                  — L1: no built-in tool is available; the model cannot
                                      execute one (tool-baiting prompt → ``num_turns==1``,
                                      ``permission_denials==[]``).
  * ``--system-prompt <neutral>``   — L2: replaces the agentic Claude Code prompt AND
                                      excludes the dynamic env sections (cwd / username /
                                      git) the default prompt injects. Verified: bare
                                      ``--tools ""`` alone still leaked the host username
                                      into the completion text; adding ``--system-prompt``
                                      stops it.
  * ``--strict-mcp-config`` + ``--setting-sources ""`` + ``--no-session-persistence``
                                      — L3: no MCP servers, no inherited ``~/.claude``
                                      settings / allow-rules, no on-disk session.

and **never** ``--dangerously-skip-permissions`` / ``--permission-mode bypassPermissions``
(the S-BS-90 hole). ``--bare`` is deliberately NOT used: it forces ``ANTHROPIC_API_KEY`` /
apiKeyHelper auth and never reads OAuth/keychain, so it breaks BYO-Claude subscription auth
("Not logged in"). The prompt is passed on **stdin**, never argv, so a long judge prompt
can't hit ``ARG_MAX`` and can't inject a CLI flag.

NO LOGPROBS — the honest caveat. Anthropic models don't expose token logprobs, so the
returned ``ModelResponse`` carries none and ``compliance_council.extract_verdict_confidence``
returns ``None``. A BYO-Claude judge round-trips ``confidence=None`` exactly like the
Mistral path (``supports_logprobs=False``), **never** a synthesized or self-reported float
(the anti-pattern ``judges_dspy`` guards against). Azure stays the logprob/calibration
option; both are selectable per-judge.

Import-isolated: ``dspy`` / ``litellm`` import lazily inside :func:`build_claude_cli_lm`
(the subclass is defined there), mirroring ``judges_dspy._build_signature``. Importing this
module is cheap; the heavy import only fires when a BYO-Claude LM is actually built. The
``runner`` seam (the subprocess shell-out) is injectable so tests run ``$0`` / hermetic.

Cost honesty: each ``claude -p`` reports a ``total_cost_usd`` that is a
**subscription-equivalent estimate**, not an incremental charge — ``$0`` out-of-pocket on a
Claude subscription (consistent with ``apps/bff/agent/loop.py``'s ``COST_LABEL``).
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from typing import Any

# The model-string value that selects this provider (per-judge ``model`` field or the
# global ``LITHRIM_LLM_PROVIDER``). ``judges_dspy.build_judge_lm`` matches against these.
BYO_CLAUDE_MODEL_VALUES: frozenset[str] = frozenset({"byo-claude", "claude-cli", "claude"})

# The neutral completion system prompt — REPLACES the Claude Code agentic prompt (so the
# model behaves as a text-completion function, not a tool-using agent) and, by being a
# custom ``--system-prompt``, makes the CLI EXCLUDE the dynamic env / cwd / username
# sections the default prompt injects.
_COMPLETION_SYSTEM_PROMPT = (
    "You are a deterministic text-completion function inside an automated evaluation "
    "pipeline. You have no tools, no shell, no file access, and no network. Do not attempt "
    "to call, invoke, or describe any tool. Respond with ONLY the requested output."
)

# The flags that make ``claude -p`` a tool-less, isolated completion (the A-SAFE floor).
# The empty string after ``--tools`` is load-bearing: it disables ALL built-in tools.
_TOOLLESS_FLAGS: tuple[str, ...] = (
    "--tools",
    "",
    "--strict-mcp-config",
    "--setting-sources",
    "",
    "--no-session-persistence",
)

# Flags that would re-open the agent surface — asserted-ABSENT by the A-SAFE negative test.
FORBIDDEN_FLAGS: frozenset[str] = frozenset(
    {
        "--dangerously-skip-permissions",
        "--allow-dangerously-skip-permissions",
        "--bare",  # breaks BYO-Claude subscription auth (forces ANTHROPIC_API_KEY)
    }
)


def build_toolless_argv(
    *,
    system_prompt: str = _COMPLETION_SYSTEM_PROMPT,
    claude_model: str | None = None,
    output_format: str = "json",
) -> list[str]:
    """The tool-less ``claude -p`` argv (flags ONLY — the prompt is passed on stdin).

    This is the single construction point the A-SAFE negative test asserts against: it
    ALWAYS carries ``--tools ""`` + a non-default ``--system-prompt`` + the isolation
    flags, and NEVER a flag in :data:`FORBIDDEN_FLAGS`. Keeping the prompt off argv means
    no prompt content can masquerade as a flag.
    """
    argv = ["claude", "-p", *_TOOLLESS_FLAGS, "--system-prompt", system_prompt]
    if claude_model:
        argv += ["--model", claude_model]
    argv += ["--output-format", output_format]
    return argv


def _default_runner(argv: list[str], *, prompt: str, timeout: float) -> str:
    """Shell out to the local ``claude`` CLI (prompt on stdin) and return raw stdout (the
    ``--output-format json`` blob). Injectable so tests never spawn a real process."""
    proc = subprocess.run(  # noqa: S603 — argv is built internally, prompt is stdin not shell
        argv,
        input=prompt,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"claude CLI exited {proc.returncode}: {(proc.stderr or proc.stdout or '')[:300]}"
        )
    return proc.stdout


def _messages_to_prompt(prompt: str | None, messages: list[dict[str, Any]] | None) -> str:
    """Flatten DSPy's (role, content) message list into one stdin prompt string.

    DSPy's ChatAdapter passes the signature instructions as a ``system`` message and the
    formatted inputs as a ``user`` message; both must reach the model via the stdin prompt
    (our ``--system-prompt`` carries only the neutral tool-less constraint). Roles are
    labelled so the judge instructions survive."""
    if messages:
        parts: list[str] = []
        for m in messages:
            role = str(m.get("role", "user"))
            content = m.get("content", "")
            if isinstance(content, list):  # dspy may pass content blocks
                content = "\n".join(
                    (c.get("text", "") if isinstance(c, dict) else str(c)) for c in content
                )
            content = str(content).strip()
            if not content:
                continue
            parts.append(content if role == "user" else f"[{role.upper()}]\n{content}")
        return "\n\n".join(parts)
    return prompt or ""


def build_claude_cli_lm(
    *,
    model: str = "byo-claude",
    claude_model: str | None = None,
    system_prompt: str = _COMPLETION_SYSTEM_PROMPT,
    timeout: float = 120.0,
    runner: Callable[..., str] | None = None,
    **kwargs: Any,
):
    """Construct a tool-less ``ClaudeCliLM`` bound to the local ``claude`` CLI.

    ``dspy`` / ``litellm`` import lazily here (import-isolation). ``runner`` overrides the
    subprocess shell-out for ``$0`` hermetic tests (signature
    ``(argv, *, prompt, timeout) -> raw_json_str``). ``claude_model`` optionally pins a
    specific Claude (e.g. ``"opus"`` / ``"sonnet"``); default = the CLI's configured
    default. Extra ``kwargs`` pass to ``dspy.BaseLM.__init__`` (temperature / max_tokens).
    """
    import dspy
    from litellm.types.utils import Choices, Message, ModelResponse, Usage

    resolved_runner = runner or _default_runner
    base_kwargs = dict(kwargs)
    cache = base_kwargs.pop("cache", True)

    class ClaudeCliLM(dspy.BaseLM):
        """Tool-less BYO-Claude completion LM. ``forward`` shells the local ``claude`` CLI
        and returns a litellm ``ModelResponse`` WITHOUT logprobs (confidence → None)."""

        def __init__(self) -> None:
            super().__init__(model=model, model_type="chat", cache=cache, **base_kwargs)
            self.system_prompt = system_prompt
            self.claude_model = claude_model
            self.timeout = timeout
            self._runner = resolved_runner

        def forward(self, prompt=None, messages=None, **_kw):
            prompt_text = _messages_to_prompt(prompt, messages)
            argv = build_toolless_argv(
                system_prompt=self.system_prompt, claude_model=self.claude_model
            )
            raw = self._runner(argv, prompt=prompt_text, timeout=self.timeout)
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, TypeError) as exc:
                raise RuntimeError(
                    f"claude CLI returned non-JSON output: {str(raw)[:200]}"
                ) from exc
            if data.get("is_error"):
                raise RuntimeError(f"claude CLI error: {str(data.get('result'))[:300]}")
            content = data.get("result") or ""
            usage = data.get("usage") or {}
            in_tok = int(usage.get("input_tokens", 0) or 0)
            out_tok = int(usage.get("output_tokens", 0) or 0)
            # NO logprobs attached — Anthropic exposes none; extract_verdict_confidence → None.
            return ModelResponse(
                choices=[
                    Choices(
                        index=0,
                        finish_reason="stop",
                        message=Message(role="assistant", content=content),
                    )
                ],
                model=self.model,
                usage=Usage(
                    prompt_tokens=in_tok,
                    completion_tokens=out_tok,
                    total_tokens=in_tok + out_tok,
                ),
            )

    return ClaudeCliLM()
