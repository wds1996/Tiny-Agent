from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence

from .models import Evidence, ResearchMetrics


def normalize_evidence(items: Sequence[Evidence], *, limit: int) -> list[Evidence]:
    if limit <= 0:
        raise ValueError("limit must be positive")
    seen: set[str] = set()
    normalized: list[Evidence] = []
    for item in items:
        fingerprint = sha256(
            (item.kind + "\0" + (item.source_url or "") + "\0" + (item.locator or "") + "\0" + item.text).encode("utf-8")
        ).hexdigest()
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        normalized.append(
            Evidence(
                id=f"E{len(normalized) + 1}",
                kind=item.kind,
                title=item.title,
                text=item.text,
                source_url=item.source_url,
                locator=item.locator,
                score=item.score,
                metadata=item.metadata,
            )
        )
        if len(normalized) >= limit:
            break
    return normalized


def evidence_to_dict(item: Evidence) -> dict[str, Any]:
    return {
        "id": item.id,
        "kind": item.kind,
        "title": item.title,
        "text": item.text,
        "source_url": item.source_url,
        "locator": item.locator,
        "score": item.score,
        "metadata": dict(item.metadata),
    }


def evidence_from_dict(value: Mapping[str, Any]) -> Evidence:
    return Evidence(
        id=str(value["id"]),
        kind=value["kind"],  # type: ignore[arg-type]
        title=str(value["title"]),
        text=str(value["text"]),
        source_url=value.get("source_url"),
        locator=value.get("locator"),
        score=float(value.get("score", 0.0)),
        metadata=dict(value.get("metadata", {})),
    )


def metrics_from_dict(value: Mapping[str, Any]) -> ResearchMetrics:
    return ResearchMetrics(
        local_searches=int(value.get("local_searches", 0)),
        external_searches=int(value.get("external_searches", 0)),
        evidence_items=int(value.get("evidence_items", 0)),
        model_calls=int(value.get("model_calls", 0)),
        revisions=int(value.get("revisions", 0)),
        agent_calls=int(value.get("agent_calls", 0)),
    )


def bump(metrics: Mapping[str, Any], **updates: int) -> dict[str, int]:
    result = {
        "local_searches": int(metrics.get("local_searches", 0)),
        "external_searches": int(metrics.get("external_searches", 0)),
        "evidence_items": int(metrics.get("evidence_items", 0)),
        "model_calls": int(metrics.get("model_calls", 0)),
        "revisions": int(metrics.get("revisions", 0)),
        "agent_calls": int(metrics.get("agent_calls", 0)),
    }
    for key, value in updates.items():
        if key not in result:
            raise KeyError(key)
        result[key] += int(value)
    return result
