"""Shared helpers for SOAP-body-projection injectors.

Every text-projection injector follows the same pattern: locate an
anchor in the SOAP body, mutate around it, return the new artifact with
the rest of the document untouched. Concentrating that boilerplate here
keeps the per-defect injector focused on the defect.
"""
from __future__ import annotations

import json
from typing import Any, Callable


def mutate_soap_body(
    artifact: dict[str, Any],
    mutator: Callable[[str], str],
) -> tuple[dict[str, Any], str, str]:
    """Apply `mutator` to the SOAP body inside the DocumentReference attachment.

    Returns (new_artifact, original_soap, mutated_soap). Raises ValueError
    if the mutator returned an unchanged body (a no-op injector is a bug,
    not a soft-pass).
    """
    new_artifact = json.loads(json.dumps(artifact))
    doc = json.loads(new_artifact["content"])
    attachment = doc["content"][0]["attachment"]
    original: str = attachment["data"]
    mutated = mutator(original)
    if mutated == original:
        raise ValueError("SOAP mutator was a no-op; injector did not modify the body")
    attachment["data"] = mutated
    new_artifact["content"] = json.dumps(doc)
    new_artifact["_soap_text"] = mutated
    return new_artifact, original, mutated
