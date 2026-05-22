"""Query complexity calculation.

Operates exclusively on a luxql tree -- there is no parallel dict path.
Each node kind contributes a different cost; the result is used both by
:mod:`luxy.rate_limiter` (to choose a rate-limit bucket) and by callers
wanting to back off from particularly large queries.
"""

from __future__ import annotations

from luxql import LuxAPI, LuxBoolean, LuxLeaf, LuxRelationship

from .rate_limiter import REQUEST_RELATIONSHIP, REQUEST_SIMPLE


COST_LEAF = 1
COST_BOOLEAN = 1
COST_RELATIONSHIP = 5  # relationships traverse the graph and are much more expensive


def score(node) -> int:
    """Return the complexity score of a luxql tree (or sub-tree).

    ``node`` may be a :class:`LuxAPI`, in which case the score of its
    single top-level child is returned. ``None`` (or an empty tree) gives
    a score of ``0``.
    """
    if node is None:
        return 0
    if isinstance(node, LuxAPI):
        if not node.children:
            return 0
        return score(node.children[0])

    if isinstance(node, LuxLeaf):
        return COST_LEAF

    children = list(getattr(node, "children", None) or [])

    if isinstance(node, LuxRelationship):
        total = COST_RELATIONSHIP
    elif isinstance(node, LuxBoolean):
        total = COST_BOOLEAN
    else:
        total = 0

    for child in children:
        total += score(child)
    return total


def category_for(complexity_score: int) -> str:
    """Map a complexity score to a rate-limit bucket."""
    if complexity_score >= COST_RELATIONSHIP:
        return REQUEST_RELATIONSHIP
    return REQUEST_SIMPLE


__all__ = [
    "COST_BOOLEAN",
    "COST_LEAF",
    "COST_RELATIONSHIP",
    "category_for",
    "score",
]
