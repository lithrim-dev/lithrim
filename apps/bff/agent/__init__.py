"""The conversational-shell agent loop (UAP-5b / R11) — the Claude Agent SDK hosted
in the BFF, BYO-Claude, with the BFF ops wrapped as in-process SDK-MCP tools.

Import-isolated: this package is import-safe on the default deps (it pulls
claude_agent_sdk LAZILY, only when the loop actually runs), so the [agent] extra
does not leak into the offline core (A5, mirroring [council]/[bff]). The handler
logic + the parts-adapter are SDK-free and unit-testable without the SDK.
"""

from .adapter import agent_part, audit_part, flag_part, judge_part, verdict_part
from .loop import COST_LABEL, run_chat, sse_format
from .tools import (
    PAID_KEYS,
    RUN_EVAL_SCHEMA,
    ToolContext,
    build_sdk_tools,
)

__all__ = [
    "COST_LABEL",
    "PAID_KEYS",
    "RUN_EVAL_SCHEMA",
    "ToolContext",
    "agent_part",
    "audit_part",
    "build_sdk_tools",
    "flag_part",
    "judge_part",
    "run_chat",
    "sse_format",
    "verdict_part",
]
