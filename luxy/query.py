"""Graph-style query construction layer.

Every luxy query is a real luxql tree. This module is a thin convenience
wrapper that turns Pythonic ``filter(**kwargs)`` calls and chained
attribute access (``Objects().memberOf("Letters", depth=2)``) into
``LuxBoolean`` / ``LuxRelationship`` / ``LuxLeaf`` nodes that get attached
directly to the root :class:`LuxAPI` instance held by :class:`BaseLux`.

There is no parallel JSON / dict representation. The luxql tree *is* the
query. Whenever a JSON view is needed, the tree is rendered with
``to_json()``.

The user-facing surface:

* :func:`apply_filters` -- the main entry point. Takes a parent boolean
  and a ``**kwargs`` mapping and attaches one luxql node per kwarg.
* :class:`Chain` -- the result of a terminated :class:`FilterBuilder`
  expression. A Chain is a *deferred* sub-tree that knows how to
  materialise itself under any parent.
* :class:`FilterBuilder` -- the legacy ``Objects().some.path.builder``
  syntax, now producing :class:`Chain` instances instead of dicts.
"""

from __future__ import annotations

from typing import Any, Iterable, List, Optional, Tuple

from luxql import LuxAPI, LuxBoolean, LuxLeaf, LuxRelationship


COMPARATOR_ALIASES = {
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
    "eq": "==",
    "ne": "!=",
}

VALID_COMPARATORS = {">", ">=", "<", "<=", "==", "!="}
BOOLEAN_KEYS = ("AND", "OR", "NOT")
DEFAULT_TEXT_FIELD = "text"


class QueryBuildError(ValueError):
    """Raised when a filter expression can't be turned into a luxql tree."""


# ---------------------------------------------------------------------------
# Chain: a deferred luxql sub-tree
# ---------------------------------------------------------------------------


class Chain:
    """A buildable luxql sub-tree that hasn't been attached to a parent yet.

    Produced by :class:`FilterBuilder` and by some of the kwarg parsing
    paths in :func:`apply_filters`. A chain remembers a sequence of
    relationship fields and an optional terminal leaf, plus a couple of
    legacy modifiers (``depth=N`` for self-nested relationships).
    """

    def __init__(
        self,
        fields: List[str],
        *,
        value: Any = None,
        comparitor: Optional[str] = None,
        depth: Optional[int] = None,
    ):
        if not fields:
            raise QueryBuildError("Chain requires at least one field")
        self.fields: List[str] = list(fields)
        self.value = value
        self.comparitor = comparitor
        self.depth = depth

    # -- materialisation --------------------------------------------------

    def materialize(self, parent) -> Any:
        """Build the corresponding luxql nodes under ``parent`` and return
        the topmost newly created node.
        """
        if self.depth is not None:
            return self._materialize_depth(parent)

        relationships = self.fields[:-1]
        leaf_field = self.fields[-1]

        current = parent
        top = None
        for f in relationships:
            rel = LuxRelationship(f, parent=current)
            top = top or rel
            current = rel

        if self.value is None:
            # An unterminated chain: pretend the last segment is a relationship.
            # This mirrors the legacy FilterBuilder behaviour where `obj.parent.child`
            # without a value still produces a path.
            rel = LuxRelationship(leaf_field, parent=current)
            return top or rel

        leaf = LuxLeaf(
            leaf_field,
            parent=current,
            value=_normalise_leaf_value(self.value),
            comparitor=self.comparitor,
        )
        return top or leaf

    def _materialize_depth(self, parent) -> Any:
        if self.depth is None or self.depth < 1:
            raise QueryBuildError("Depth must be at least 1")

        path = self.fields[:-1]
        last_field = self.fields[-1]
        value = self.value

        current = parent
        top = None
        for f in path:
            rel = LuxRelationship(f, parent=current)
            top = top or rel
            current = rel

        for _ in range(self.depth):
            rel = LuxRelationship(last_field, parent=current)
            top = top or rel
            current = rel

        if isinstance(value, dict):
            _attach_dict(current, value)
        elif value is not None:
            LuxLeaf(
                DEFAULT_TEXT_FIELD,
                parent=current,
                value=_normalise_leaf_value(value),
            )

        return top

    # -- introspection ----------------------------------------------------

    def to_json(self) -> dict:
        """Materialise into a scope-less container and serialise to JSON.

        Useful for inspection and tests; equivalent to building the chain
        under a real parent and reading off the JSON.
        """
        container = LuxBoolean("AND")
        node = self.materialize(container)
        return node.to_json()

    def __repr__(self) -> str:  # pragma: no cover - trivial
        bits = ".".join(self.fields)
        if self.depth:
            return f"Chain({bits}, depth={self.depth}, value={self.value!r})"
        return f"Chain({bits}, value={self.value!r}, comp={self.comparitor!r})"


# ---------------------------------------------------------------------------
# FilterBuilder: chained attribute access
# ---------------------------------------------------------------------------


class FilterBuilder:
    """Fluent builder for chained relationship paths.

    ``FilterBuilder().produced.classification.name("painting")`` returns a
    :class:`Chain` describing a 3-segment path. The final element of the
    chain is taken to be the leaf field unless ``depth`` is given (in
    which case the last element is repeated ``depth`` times before the
    text leaf).
    """

    def __init__(self, path: Optional[Iterable[str]] = None):
        self._path: List[str] = list(path or [])

    def __getattr__(self, name: str) -> "FilterBuilder":
        if name.startswith("_"):
            raise AttributeError(name)
        return FilterBuilder(self._path + [name])

    def __call__(self, value=None, depth=None) -> Any:
        if value is None and depth is None:
            return self
        if not self._path:
            raise QueryBuildError("FilterBuilder has no path; use attribute access first")
        return Chain(self._path, value=value, depth=depth)

    def name(self, value) -> Chain:
        """Shortcut for ``...name(value)`` -- terminates the chain on a name leaf."""
        return Chain(self._path + ["name"], value=value)


# ---------------------------------------------------------------------------
# Kwargs -> luxql attachments
# ---------------------------------------------------------------------------


def apply_filters(parent_bool: LuxBoolean, kwargs: dict) -> None:
    """Attach one luxql node per ``filter(**kwargs)`` entry to ``parent_bool``.

    ``parent_bool`` is the root ``LuxBoolean("AND")`` held by
    :class:`luxy.api.BaseLux`. Every entry in ``kwargs`` becomes exactly
    one direct child of that AND.
    """
    for key, value in kwargs.items():
        _apply_one(parent_bool, key, value)


def _apply_one(parent, key: str, value: Any) -> None:
    # Logical operator?
    if key in BOOLEAN_KEYS:
        if not isinstance(value, (list, tuple)):
            raise QueryBuildError(f"{key} filter must be a list of conditions")
        bl = LuxBoolean(key, parent=parent)
        for cond in value:
            _attach_condition(bl, cond)
        return

    # Tuple-style comparator: filter(height=(1, ">="))
    if isinstance(value, tuple) and len(value) == 2 and not _looks_like_chain(key):
        val, comp = value
        if comp not in VALID_COMPARATORS:
            raise QueryBuildError(f"Invalid comparison operator: {comp}")
        LuxLeaf(
            key,
            parent=parent,
            value=_normalise_leaf_value(val),
            comparitor=comp,
        )
        return

    # ``__`` chain syntax: produced__classification__name="painting"
    chain_fields, comparitor = _split_chain(key)
    _attach_chain(parent, chain_fields, value, comparitor)


def _attach_chain(
    parent,
    fields: List[str],
    value: Any,
    comparitor: Optional[str],
) -> None:
    # Single field, dict value -> relationship to a sub-query
    if len(fields) == 1 and isinstance(value, dict):
        rel = LuxRelationship(fields[0], parent=parent)
        _attach_dict(rel, value)
        return

    # Single field, Chain value -> attach the chain under a relationship
    if len(fields) == 1 and isinstance(value, Chain):
        rel = LuxRelationship(fields[0], parent=parent)
        value.materialize(rel)
        return

    # Single field, BaseLux value -> attach its tree under a relationship
    from .api import BaseLux  # local import to avoid circular dep

    if len(fields) == 1 and isinstance(value, BaseLux):
        rel = LuxRelationship(fields[0], parent=parent)
        value._copy_filters_into(rel)
        return

    # Single field, scalar value -> leaf
    if len(fields) == 1:
        LuxLeaf(
            fields[0],
            parent=parent,
            value=_normalise_leaf_value(value),
            comparitor=comparitor,
        )
        return

    # Multi-segment chain
    relationships = fields[:-1]
    leaf_field = fields[-1]
    current = parent
    for rel_field in relationships:
        current = LuxRelationship(rel_field, parent=current)

    if isinstance(value, dict):
        rel = LuxRelationship(leaf_field, parent=current)
        _attach_dict(rel, value)
    elif isinstance(value, Chain):
        rel = LuxRelationship(leaf_field, parent=current)
        value.materialize(rel)
    else:
        LuxLeaf(
            leaf_field,
            parent=current,
            value=_normalise_leaf_value(value),
            comparitor=comparitor,
        )


def _attach_condition(parent_bool: LuxBoolean, condition: Any) -> None:
    """Attach a single member of an ``OR=[]`` / ``AND=[]`` / ``NOT=[]`` list."""
    from .api import BaseLux  # local import to avoid circular dep

    if isinstance(condition, BaseLux):
        condition._copy_filters_into(parent_bool)
        return
    if isinstance(condition, Chain):
        condition.materialize(parent_bool)
        return
    if isinstance(condition, dict):
        _attach_dict(parent_bool, condition)
        return
    if isinstance(condition, (LuxBoolean, LuxRelationship, LuxLeaf)):
        parent_bool.add(condition)
        return
    raise QueryBuildError(f"Unsupported condition in boolean: {condition!r}")


def _attach_dict(parent, payload: dict) -> None:
    """Attach a legacy nested-dict payload under ``parent``.

    This keeps the door open for users (and for the
    ``filter(gender={"name": "male"})`` shape from the README) but
    everything still ends up as luxql nodes.
    """
    cmpr = payload.get("_comp")
    weight = payload.get("_weight")
    options = payload.get("_options", []) or []
    complete = payload.get("_complete", False)

    for key, value in payload.items():
        if key.startswith("_"):
            continue
        if key in BOOLEAN_KEYS and isinstance(value, list):
            bl = LuxBoolean(key, parent=parent)
            for cond in value:
                _attach_condition(bl, cond)
            continue
        if isinstance(value, dict):
            rel = LuxRelationship(key, parent=parent)
            _attach_dict(rel, value)
            continue
        if isinstance(value, Chain):
            rel = LuxRelationship(key, parent=parent)
            value.materialize(rel)
            continue
        # Leaf
        LuxLeaf(
            key,
            parent=parent,
            value=_normalise_leaf_value(value),
            comparitor=cmpr,
            options=options,
            weight=weight or 0,
            complete=bool(complete),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _looks_like_chain(key: str) -> bool:
    return "__" in key


def _split_chain(key: str) -> Tuple[List[str], Optional[str]]:
    parts = [p for p in key.split("__") if p]
    if not parts:
        raise QueryBuildError(f"Empty filter key: {key!r}")
    if len(parts) > 1 and parts[-1] in COMPARATOR_ALIASES:
        return parts[:-1], COMPARATOR_ALIASES[parts[-1]]
    return parts, None


def _normalise_leaf_value(value: Any) -> Any:
    """Map Python natives to what luxql's :class:`LuxLeaf` accepts.

    luxql is happy with strings, bools, ints and floats; the only
    transformation we apply here is for booleans, which luxql then
    serialises as ``"1"`` / ``"0"``.
    """
    return value


def make_api(scope: str) -> LuxAPI:
    """Build an empty :class:`LuxAPI` rooted at ``scope``."""
    return LuxAPI(scope)


__all__ = [
    "BOOLEAN_KEYS",
    "COMPARATOR_ALIASES",
    "Chain",
    "DEFAULT_TEXT_FIELD",
    "FilterBuilder",
    "QueryBuildError",
    "VALID_COMPARATORS",
    "apply_filters",
    "make_api",
]
