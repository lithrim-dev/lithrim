"""Shared helpers for SOAP-body-projection injectors.

Every text-projection injector targets the first artifact in the
artifacts list, locates an anchor in its SOAP body, mutates around it,
and returns the new artifacts list with the rest untouched.
"""
from __future__ import annotations

import json
from typing import Any, Callable


def mutate_soap_body(
    artifacts: list[dict[str, Any]],
    mutator: Callable[[str], str],
) -> tuple[list[dict[str, Any]], str, str]:
    """Apply `mutator` to the SOAP body inside artifacts[0].

    Returns (new_artifacts, original_soap, mutated_soap). Raises
    ValueError if the mutator returned an unchanged body.
    """
    if not artifacts:
        raise ValueError("no artifacts to mutate")
    new_artifacts = json.loads(json.dumps(artifacts))
    doc = json.loads(new_artifacts[0]["content"])
    attachment = doc["content"][0]["attachment"]
    original: str = attachment["data"]
    mutated = mutator(original)
    if mutated == original:
        raise ValueError("SOAP mutator was a no-op; injector did not modify the body")
    attachment["data"] = mutated
    new_artifacts[0]["content"] = json.dumps(doc)
    new_artifacts[0]["_soap_text"] = mutated
    return new_artifacts, original, mutated
