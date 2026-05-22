"""Response profiles.

A profile lets the caller indicate how much information they actually need
from a result. This is implemented two ways:

1.  Hint to the backend (passed through to MarkLogic / QLever where the
    backend understands it) so we don't pull unnecessary data.
2.  Client-side projection, so even when the backend doesn't honour the
    hint, the user still gets a slimmed down result.

The supported profiles are:

* ``full`` (default): the unmodified API response.
* ``results``: just the ``orderedItems`` list with ``id`` and ``type``.
* ``name``: only the ``id`` and human-readable label of each result.
* ``count``: just the total number of matching items.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable

PROFILE_FULL = "full"
PROFILE_RESULTS = "results"
PROFILE_NAME = "name"
PROFILE_COUNT = "count"

VALID_PROFILES = {PROFILE_FULL, PROFILE_RESULTS, PROFILE_NAME, PROFILE_COUNT}


def normalize(profile: str) -> str:
    """Validate a profile name (returns the canonical form)."""
    if profile not in VALID_PROFILES:
        raise ValueError(
            f"Unknown profile {profile!r}. Valid profiles: {sorted(VALID_PROFILES)}"
        )
    return profile


def _label_of(item: Dict[str, Any]) -> str:
    """Best-effort label extraction from a record dict."""
    label = item.get("_label") or item.get("label") or ""
    if isinstance(label, dict):
        for value in label.values():
            if isinstance(value, list) and value:
                return str(value[0])
            if isinstance(value, str):
                return value
    if isinstance(label, list) and label:
        return str(label[0])
    return str(label)


def project(payload: Dict[str, Any], profile: str) -> Dict[str, Any]:
    """Project a search response down to the requested profile."""
    profile = normalize(profile)

    if profile == PROFILE_FULL:
        return payload

    if profile == PROFILE_COUNT:
        total = 0
        try:
            total = int(payload["partOf"][0].get("totalItems", 0))
        except (KeyError, IndexError, TypeError, ValueError):
            total = len(payload.get("orderedItems", []) or [])
        return {"totalItems": total}

    items: Iterable[Dict[str, Any]] = payload.get("orderedItems", []) or []
    if profile == PROFILE_RESULTS:
        slim = [{"id": it.get("id"), "type": it.get("type")} for it in items]
    else:  # PROFILE_NAME
        slim = [
            {"id": it.get("id"), "label": _label_of(it)}
            for it in items
        ]

    return {
        "id": payload.get("id"),
        "type": payload.get("type"),
        "totalItems": _total_items(payload),
        "orderedItems": slim,
    }


def _total_items(payload: Dict[str, Any]) -> int:
    try:
        return int(payload["partOf"][0]["totalItems"])
    except (KeyError, IndexError, TypeError, ValueError):
        return len(payload.get("orderedItems", []) or [])


__all__ = [
    "PROFILE_COUNT",
    "PROFILE_FULL",
    "PROFILE_NAME",
    "PROFILE_RESULTS",
    "VALID_PROFILES",
    "normalize",
    "project",
]
