"""Deterministic raw-observation hashing and change classification."""

import hashlib
import json


def content_hash(payload: dict) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def classify_change(previous_hash: str | None, new_hash: str) -> str:
    if previous_hash is None:
        return "NEW"
    return "UNCHANGED" if previous_hash == new_hash else "CHANGED"
