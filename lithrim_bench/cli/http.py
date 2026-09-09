"""The CLI's BFF client: three verbs over urllib, no third-party dependency."""

from __future__ import annotations

import json
import urllib.request


def get(bff: str, path: str, timeout: float = 60) -> dict:
    with urllib.request.urlopen(bff + path, timeout=timeout) as r:
        return json.load(r)


def post(bff: str, path: str, body: dict, timeout: float = 36000) -> dict:
    req = urllib.request.Request(
        bff + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def put(bff: str, path: str, body: dict, timeout: float = 120) -> dict:
    req = urllib.request.Request(
        bff + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())
