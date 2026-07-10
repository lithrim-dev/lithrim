"""Per-deployment health probe for the v2 council's Azure endpoint.

Fires ONE token at each configured deployment (council / Mistral / Llama) so you
can see exactly which one is unhealthy when a live grade fails with
"no healthy upstream" or a timeout. Reads the council's own loaded settings
(endpoint / key / api-version / deployment names) — the API key is never printed.

Run via the dev stack:   scripts/dev/devstack.sh probe
Or directly:             PYTHONPATH=<repo-root> python scripts/dev/probe_azure.py

Cost: a successful probe is ~1 completion token (≈ $0.0001); a 503/timeout is free.
"""

from __future__ import annotations

import httpx

from lithrim_bench.runtime.council.settings import settings as s


def main() -> None:
    endpoint = (s.AZURE_OPENAI_ENDPOINT or "").rstrip("/")
    ver = s.AZURE_OPENAI_API_VERSION
    key = s.AZURE_OPENAI_API_KEY or ""
    deployments = [
        ("risk_judge        ", "gpt-4.1 (standard)", s.AZURE_OPENAI_DEPLOYMENT_COUNCIL),
        ("policy_judge      ", "Mistral (MaaS)", s.AZURE_OPENAI_DEPLOYMENT_MISTRAL_LARGE_3),
        ("faithfulness_judge", "Llama (MaaS)", s.AZURE_OPENAI_DEPLOYMENT_LLAMA_4_MAVERICK),
    ]

    host = endpoint.split("//")[-1] or "(unset)"
    print(f"provider={s.LITHRIM_LLM_PROVIDER}  council={s.COMPLIANCE_COUNCIL_VERSION}")
    print(f"endpoint={host}  api-version={ver}  key_len={len(key)}")
    print("-" * 72)

    if s.LITHRIM_LLM_PROVIDER != "azure":
        print("LITHRIM_LLM_PROVIDER is not 'azure' — live grades use the OpenAI-direct path; "
              "this probe only checks Azure deployments.")
        return

    any_down = False
    for role, kind, dep in deployments:
        if not dep:
            print(f"{role} [{kind}] -> DEPLOYMENT NAME MISSING (None) — set it in .env"); any_down = True; continue
        url = f"{endpoint}/openai/deployments/{dep}/chat/completions?api-version={ver}"
        try:
            r = httpx.post(
                url,
                headers={"api-key": key, "content-type": "application/json"},
                json={"messages": [{"role": "user", "content": "ping"}], "max_tokens": 1},
                timeout=30,
            )
            body = " ".join(r.text.split())[:160]
            tag = "OK ✓" if r.status_code == 200 else f"FAIL ({r.status_code})"
            if r.status_code != 200:
                any_down = True
            print(f"{role} [{kind}] dep={dep!r}\n    -> HTTP {r.status_code} {tag} :: {body}\n")
        except Exception as exc:  # noqa: BLE001 — surface any transport error per deployment
            any_down = True
            print(f"{role} [{kind}] dep={dep!r}\n    -> {type(exc).__name__}: {str(exc)[:140]} (unhealthy / timed out)\n")

    print("-" * 72)
    print("one or more deployments unhealthy — fix/redeploy them in Azure, then retry live."
          if any_down else "all council deployments healthy — live grades should work.")


if __name__ == "__main__":
    main()
